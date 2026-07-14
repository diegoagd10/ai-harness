# Design — add-verifiable-receipts

## Context

Root final validation currently authorizes archive through mutable prose and structural checks. The new invariant is stronger: archive is authorized only by the conjunction of the validator's narrowly parsed semantic approval, a native record that every declared gate passed against one exact repository candidate, an exact-byte binding to root `validation.md`, and a successful current-state recheck immediately before the first archive move.

This is a change-wide design because candidate capture, command execution, validation, routing, and archive ordering cross both legacy and sliced flows. The design adds one deep public module and composes it into the existing `ChangeLifecycle`; it does not create parallel legacy/sliced receipt implementations. Existing task, approval, freshness, collision, specs-promotion, and rollback rules remain authoritative and execute before the new terminal authorization check.

### Invariants

- A receipt records facts; it does not decide the validator's verdict or discover gates.
- Gate declarations are the only executable input. Exit status, evidence digests, candidate IDs, pass/fail values, validation facts, and receipt IDs are always derived natively.
- Gate execution uses an argv vector with `shell=False`, closed stdin, a confined working directory, and a bounded timeout. It is not a sandbox.
- A gate run is archive-eligible only when its before/after candidate IDs are equal and every gate has a successful launch, normal exit zero, complete bounded evidence, and no timeout or overflow.
- Semantic approval and native gate approval are separate persisted fields. Neither can substitute for the other.
- Runs, evidence, and receipts are immutable content-addressed objects. `current` is the only replaceable pointer.
- Unsupported versions, unknown fields, non-canonical objects, duplicate JSON keys, malformed validation, missing evidence, symlinks in evidence storage, and any digest mismatch fail closed.
- Archive verifies the receipt after every existing preflight check and immediately before `_archive_move`. Verification performs no writes and never reruns gates.
- v1 provides single-process ordering, not protection from a concurrent writer after final verification.

### Canonical encoding and typed hashes

All persisted JSON is composed only of objects, arrays, UTF-8 strings, booleans, nulls, and bounded integers. Canonical bytes are:

```text
json.dumps(value,
           ensure_ascii=False,
           sort_keys=True,
           separators=(",", ":"),
           allow_nan=False).encode("utf-8")
```

There is no BOM, trailing newline, insignificant whitespace, float, timestamp, or duration in a content-addressed object. Readers reject duplicate keys and then require the original bytes to equal canonical re-encoding. Exact key sets are schema-defined; unknown or missing keys are errors.

All hashes use SHA-256 over a domain-separated, length-delimited frame:

```text
frame(label, payload) = u32be(len(utf8(label))) || utf8(label)
                      || u64be(len(payload))    || payload
typed_hash(label, payload) = "sha256:" || hex(SHA256(frame(label, payload)))
```

Labels include the object and policy version, for example `ai-harness/candidate/v1`, `ai-harness/gate-run/v1`, `ai-harness/receipt/v1`, `ai-harness/evidence/v1`, and `ai-harness/validation/v1`. IDs are always lowercase `sha256:<64 hex>`. This prevents cross-type substitution and concatenation-boundary ambiguity.

## Deep modules

### `FinalValidationReceipts`

- **Seam:** `src/ai_harness/modules/harness/receipts.py`; this class is the only public receipt-policy seam. CLI adapters and `ChangeLifecycle` compose it. Internal codec, Git, process, parser, redaction, and storage classes are not exported and are not bypassed by module-level convenience functions.
- **Interface:**

  ```python
  @dataclass(frozen=True, slots=True)
  class GateDeclaration:
      gate_id: str
      argv: tuple[str, ...]
      cwd: str
      timeout_seconds: int

  @dataclass(frozen=True, slots=True)
  class GateRunRequest:
      schema_name: Literal["ai-harness.gate-declaration"]
      schema_version: Literal[1]
      gates: tuple[GateDeclaration, ...]

  @dataclass(frozen=True, slots=True)
  class GateOutcomeSummary:
      gate_id: str
      launch: Literal["ok", "not-found", "permission-denied", "os-error"]
      termination: Literal["exited", "launch-error", "timeout", "output-overflow"]
      return_code: int | None
      passed: bool

  @dataclass(frozen=True, slots=True)
  class GateRunResult:
      run_id: str
      candidate_before: str
      candidate_after: str
      all_gates_passed: bool
      gates: tuple[GateOutcomeSummary, ...]

  @dataclass(frozen=True, slots=True)
  class SealResult:
      receipt_id: str
      gate_run: str
      semantic_approval: bool
      native_all_gates_passed: bool
      archive_eligible: bool

  @dataclass(frozen=True, slots=True)
  class ArchiveAuthorization:
      receipt_id: str
      run_id: str
      candidate_id: str
      validation_id: str

  class ReceiptError(RuntimeError):
      code: str
      message: str
      context: Mapping[str, str]

  class FinalValidationReceipts:
      def __init__(self, repository_root: Path) -> None: ...
      def run_gates(self, change: str, request: GateRunRequest) -> GateRunResult: ...
      def seal(self, change: str) -> SealResult: ...
      def verify_for_archive(self, change: str) -> ArchiveAuthorization: ...
  ```

  `run_gates` validates the complete declaration before launching anything, captures the candidate, attempts each gate exactly once in declaration order, captures the candidate again, publishes one immutable run bundle, and returns facts without retained output text. Gate failure is a successful fact-recording operation and therefore returns a result with `all_gates_passed=false`; declaration, capture, or persistence failure raises `ReceiptError` and publishes no run.

  `seal` accepts only a Change name. It reads the gate-run reference from root `validation.md`, validates that run and its evidence, re-captures the candidate, binds the complete validation bytes, derives semantic/native booleans, publishes an immutable receipt, and atomically points `current` to it. A well-formed semantic denial or failed run may be sealed for diagnosis; malformed, contradictory, stale, or tampered inputs are not sealed.

  `verify_for_archive` strictly reads the current receipt and all transitive objects, re-parses validation semantics, re-hashes validation bytes, and captures the candidate last. Every read is a stable regular-file read (`lstat`/read/`fstat`/final `lstat`), and the canonical `current` bytes and validation bytes are read again after candidate capture; either changing during the observed verification fails closed. It returns only an authorization identity when every invariant is true; otherwise it raises. It never repairs data, selects an older receipt, rewrites `current`, or invokes a process.

- **Hides:** Git-aware candidate enumeration, recursive submodule handling, race detection, strict JSON schemas, typed hashing, no-shell process lifecycle, streaming binary redaction, bounded evidence, content-addressed bundle publication, semantic-envelope parsing, transitive integrity checks, and safe diagnostics.
- **Depth note:** deleting this module would force every CLI, validator prompt, router, and archive path to reproduce security-sensitive policy and ordering. Its three operations expose a much smaller interface than the complexity they contain.

#### Gate declaration policy

The CLI request has this exact shape:

```json
{
  "schema_name": "ai-harness.gate-declaration",
  "schema_version": 1,
  "gates": [
    {
      "gate_id": "unit-tests",
      "argv": ["uv", "run", "pytest", "tests"],
      "cwd": ".",
      "timeout_seconds": 900
    }
  ]
}
```

- One through 64 gates are allowed; declaration order is significant and duplicate IDs are rejected.
- `gate_id` matches `[a-z0-9][a-z0-9._-]{0,63}`.
- `argv` contains 1 through 256 non-empty, NUL-free UTF-8 strings, each at most 4096 encoded bytes and at most 64 KiB in total. It is passed directly to `subprocess.Popen`; it is never joined or shell-interpreted.
- `cwd` is a POSIX repository-relative path. `.` is valid; absolute paths, empty components, `..`, NUL, backslash separators, missing/non-directory targets, and resolutions outside the repository are rejected. An internal symlink may be used only when its fully resolved target remains inside the repository.
- `timeout_seconds` is an integer from 1 through 3600. Boolean values are not integers for schema purposes.
- No caller-controlled environment override exists in v1. The child receives one snapshot of the runner's inherited environment under policy `inherit-all-redact-secrets-v1`.
- Before any launch, every argv element is encoded and checked for any exact non-empty secret value classified by that environment policy. A match anywhere in an argument rejects the whole request without persisting the argument.

Each command receives closed stdin and piped stdout/stderr. A fresh process group/session permits timeout or overflow handling to terminate, wait briefly, then kill the group. Later declarations are still attempted after an ordinary non-zero exit, launch error, timeout, or overflow so the run records one outcome per declared gate. An infrastructure failure that prevents trustworthy capture or persistence aborts the operation.

#### Environment and redaction policy

`inherit-all-redact-secrets-v1` snapshots `os.environ` once and passes that exact mapping to every gate. Secret-classified variables are:

- names matching, case-insensitively, a token delimited by start/end or `_` from `TOKEN`, `SECRET`, `PASSWORD`, `PASSWD`, `PRIVATE_KEY`, `API_KEY`, `ACCESS_KEY`, or `AUTH`; and
- the policy's explicit names: `GITHUB_TOKEN`, `GH_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AWS_SECRET_ACCESS_KEY`, and `GOOGLE_APPLICATION_CREDENTIALS`.

The policy is versioned because changing classification changes evidence bytes. Empty values are ignored. Unique secret values are encoded using the process environment encoding, ordered longest-first then bytewise, and replaced in stdout/stderr with the literal bytes `<redacted:secret>`. Ordering makes overlap deterministic; equal values are deduplicated. Redaction is streaming and preserves enough suffix bytes to detect a value spanning read chunks.

Each stream has both a 1 MiB raw-observed limit and a 1 MiB redacted-retained limit. Exceeding either limit terminates the gate, records `termination="output-overflow"`, persists only the bounded redacted prefix with `complete=false`, and makes the gate non-passing. Raw bytes exist only in bounded in-memory chunks and are never written or hashed. Persisted stream metadata records retained byte count, typed evidence digest, completeness, redaction policy ID, and aggregate replacement count; it records neither secret values nor raw-output digests. Routine results and errors never print evidence contents.

This policy reduces accidental retention but is not a secret detector or hermetic execution boundary. Gate declarations must be trusted, and gates must not intentionally print secrets.

#### Candidate identity policy

Candidate policy `git-worktree-v1` is repository-wide and Change-specific only through its two exclusions. Capture requires the supplied root to be the Git top level. A Change name must be one non-empty path component, and the active Change directory must be a real directory beneath `.ai-harness/changes/`, not a symlink.

The manifest binds:

1. `HEAD` as either `{state: "commit", oid: <40-or-64 lowercase hex>}` or `{state: "unborn"}`. Detached and attached HEADs with the same commit identify the same candidate; branch names are not release content.
2. Every Git index entry from NUL-delimited plumbing output: encoded path, Git mode, object ID, and stage. Conflict stages are represented rather than collapsed.
3. One tracked-worktree record per indexed path: regular-file content digest and executable mode, symlink target bytes, recursive submodule candidate ID, or explicit deletion/missing state.
4. Every non-ignored untracked path reported by Git: regular-file digest and executable mode, or symlink target bytes. Non-ignored special files are unsupported and fail capture.

The exact manifest shape is:

```json
{
  "schema_name": "ai-harness.candidate",
  "schema_version": 1,
  "policy": "git-worktree-v1",
  "head": {"state": "commit", "oid": "<git-object-id>"},
  "exclusions": {
    "exact": [".ai-harness/changes/<change>/validation.md"],
    "prefix": [".ai-harness/changes/<change>/.receipts/"]
  },
  "index": [
    {"path": "src/a.py", "mode": "100644", "oid": "<git-object-id>", "stage": 0}
  ],
  "worktree": [
    {"path": "src/a.py", "kind": "regular", "mode": "100644", "content": "sha256:<hex>"}
  ],
  "untracked": [
    {"path": "notes.txt", "kind": "regular", "mode": "100644", "content": "sha256:<hex>"}
  ]
}
```

Variant records have exact keys: a deletion has `kind="missing"`; a symlink has `kind="symlink"`, mode `120000`, and a typed digest of the link-target bytes; a submodule has `kind="submodule"`, mode `160000`, its checked-out HEAD state, and a recursively captured nested candidate ID. Nested capture uses the same policy but no target-Change exclusions. Nested submodules are supported with cycle and repository-boundary detection.

Paths come from Git's NUL-delimited byte output, must decode as strict UTF-8, are represented with `/`, are not Unicode-normalized, and are sorted by their UTF-8 encoded repository-relative path. Index records additionally sort by stage. Two distinct byte paths that cannot be represented unambiguously fail closed. `.git/` administrative data, Git-ignored paths, the target root `validation.md`, and the target `.receipts/` prefix are excluded. No other source, configuration, task, approval, slice validation, sibling Change, or non-ignored untracked path is excluded.

Regular files are opened without following symlinks where the platform permits. Type, device/inode, size, nanosecond mtime, and mode are compared before/after the read and against a final `lstat`; symlinks are read as links and must resolve lexically within their repository root. Escaping links, unreadable paths, sockets/devices/FIFOs, Git errors, and observable mutations fail capture. The complete manifest is captured twice consecutively and both canonical byte sequences must agree; capture never retries to hide a changing tree.

`candidate_id = typed_hash("ai-harness/candidate/v1", canonical_manifest)`. The stored manifest permits stale diagnostics to name only the first differing category and path (`head`, `index`, `worktree`, or `untracked`) without exposing file bytes.

Ignored files and inherited environment can influence a command while remaining outside candidate identity. Accordingly, a receipt proves bounded local execution facts, not reproducible or hermetic execution.

#### Gate-run schema

The immutable `run.json` has this exact top-level shape:

```json
{
  "schema_name": "ai-harness.gate-run",
  "schema_version": 1,
  "candidate_policy": "git-worktree-v1",
  "candidate_before": {"id": "sha256:<hex>", "manifest": {}},
  "candidate_after": {"id": "sha256:<hex>", "manifest": {}},
  "gates": [],
  "all_gates_passed": true
}
```

Each ordered gate record has exact fields:

```json
{
  "gate_id": "unit-tests",
  "argv": ["uv", "run", "pytest", "tests"],
  "cwd": ".",
  "environment_policy": "inherit-all-redact-secrets-v1",
  "timeout_seconds": 900,
  "launch": "ok",
  "termination": "exited",
  "return_code": 0,
  "stdout": {
    "path": "evidence/0000.stdout",
    "bytes": 123,
    "digest": "sha256:<hex>",
    "complete": true,
    "redaction_policy": "exact-secret-values-v1",
    "replacement_count": 0
  },
  "stderr": {
    "path": "evidence/0000.stderr",
    "bytes": 0,
    "digest": "sha256:<hex>",
    "complete": true,
    "redaction_policy": "exact-secret-values-v1",
    "replacement_count": 0
  },
  "passed": true
}
```

`launch` is `ok`, `not-found`, `permission-denied`, or `os-error`. `termination` is `exited`, `launch-error`, `timeout`, or `output-overflow`. `return_code` is a signed integer only for `exited`, otherwise null. Evidence files exist even for empty streams. `passed` and top-level `all_gates_passed` are redundant derived facts and must exactly recompute; the latter also requires equal candidate IDs. The run ID is the typed hash of canonical `run.json`; the ID is not embedded and therefore has no self-reference.

### Existing `ChangeLifecycle` archive transaction

- **Seam:** the existing `ChangeLifecycle.archive(change) -> None` in `modules/harness/change.py`; callers continue to use `change-archive`, not a second receipt-aware archive command.
- **Interface:** unchanged. Internally, `ChangeLifecycle` composes `FinalValidationReceipts(root)`. Archive executes `existing structural preflight -> fail if any error -> verify_for_archive -> _archive_move`, with no command, callback, file write, status derivation, or logging operation between verification and the first move.
- **Hides:** mode-aware legacy/sliced eligibility, task and approval recomputation, root-validation freshness, destination collision checks, specs promotion, second-stage Change move, and rollback. Receipt errors are translated into the existing `ChangeStoreError.errors: list[str]` CLI shape.
- **Depth note:** this remains the sole transaction owner. Moving receipt checks into a new archive class would split the all-or-nothing ordering and create a bypass.

#### Routing and compatibility contract

- Existing legacy and sliced structural derivation remains unchanged until the terminal archive decision.
- When an otherwise terminal route lacks a current archive-eligible receipt, `change-continue` reports `validate` for legacy or `final-validate` for sliced, with an actionable blocked reason such as missing receipt, stale candidate, stale validation, semantic denial, or failed native gates. It must not route to archive merely because `validation.md` exists.
- Routing may call the same strict verifier and convert its safe error to guidance; it does not implement a weaker parser. Direct `change-archive` always repeats every structural and receipt check from disk and never trusts prior status JSON.
- A slice validation and continuation approval remain independent. Only root final validation participates in run/seal/archive authorization.
- Legacy mode is not a waiver. After rollout, every active legacy and sliced Change must produce a new run, root validation, and receipt. Already archived Changes are not read or migrated.
- Existing mtime safeguards remain in place, especially sliced root validation newer than the latest continuation approval. Exact validation hashing and candidate identity are additive safeguards, not replacements.

## Internal collaborators

These classes live in `receipts.py`, are private implementation details, and are exercised transitively through `FinalValidationReceipts`; tests do not mock them.

### `_CanonicalCodec`

Owns duplicate-key JSON loading, exact schema/key/type checks, canonical encoding, typed framing, and ID validation. It prevents each object reader from inventing a subtly different canonicalization rule.

### `_CandidateIdentityBuilder`

Composes a private no-shell `_GitInspector` and filesystem reader. It owns the complete `git-worktree-v1` policy, exclusions, record ordering, recursive submodule capture, observable-race checks, and safe manifest differencing. It invokes Git with argv arrays and NUL-delimited plumbing output; it never parses localized human status output.

### `_GateExecutor`

Owns sequential process launch, closed stdin, process-group timeout/kill behavior, concurrent stdout/stderr draining, and conversion of launch/termination outcomes into records. It composes `_BoundedRedactor`; it does not persist objects or decide semantic approval.

### `_BoundedRedactor`

Owns deterministic byte-pattern replacement across stream chunk boundaries, raw/retained limits, replacement counts, and evidence digests. Raw chunks cannot escape this class.

### `_ValidationEnvelopeParser`

Reads complete validation bytes, hashes them, and extracts exactly one unfenced, unquoted `## Verdict` section. Within that section, only blank lines and exactly one each of these fields are allowed:

```text
verdict: pass | pass-with-warnings | fail
critical: 0 | [1-9][0-9]*
gate-run: sha256:<64 lowercase hex>
```

The section ends at the next unfenced heading of level one or two or at EOF. A BOM, invalid UTF-8, duplicate/missing section or field, unknown nonblank line, leading-zero/negative critical value, `pass*` with positive critical, or `fail` with zero critical is contradictory and rejected. Semantic approval is exactly `(verdict in {pass, pass-with-warnings}) and critical == 0`.

### `_ReceiptObjectStore`

Owns path confinement, strict regular-file checks, complete-bundle validation, immutable publication, collision verification, `current` replacement, fsync ordering, and orphan handling. It never chooses eligibility.

### Data ownership and file layout

All receipt-owned data is beneath the active Change and therefore moves with that Change:

```text
.ai-harness/changes/<change>/.receipts/
├── runs/
│   └── sha256/
│       └── <run-hex>/
│           ├── run.json
│           └── evidence/
│               ├── 0000.stdout
│               ├── 0000.stderr
│               └── ...
├── receipts/
│   └── sha256/
│       └── <receipt-hex>/
│           └── receipt.json
├── current
└── tmp/                         # never readable as evidence or current
```

Ownership does not blur across seams: the validator owns writing root `validation.md`; Git and the working tree own candidate inputs; `FinalValidationReceipts` exclusively owns `.receipts/`; and `ChangeLifecycle` exclusively owns specs promotion and archive movement. The receipt module reads but never edits candidate or validation inputs, while archive code reads but never manufactures receipt facts.

Run and receipt directory names use the hex portion of their typed IDs. Every path stored inside an object is a fixed relative POSIX path and is resolved beneath its owning bundle; absolute/traversing paths and symlink components are invalid. A run directory may contain only `run.json` and the exact declared evidence files. A receipt directory may contain only `receipt.json`. Evidence must be a regular, non-symlink file whose bytes and length match metadata.

For a run, the store creates a random directory under `.receipts/tmp/` on the same filesystem, writes and fsyncs every evidence file, writes canonical `run.json`, fsyncs directories, then renames the complete directory to `runs/sha256/<hex>`. A receipt uses the same bundle protocol. Existing destinations are never overwritten; reuse is allowed only after a complete byte-for-byte and transitive integrity verification. A differing object at a claimed ID is corruption.

`current` is canonical JSON, not a symlink:

```json
{"receipt_id":"sha256:<hex>","schema_name":"ai-harness.receipt-pointer","schema_version":1}
```

Seal writes a sibling temporary file, fsyncs it, atomically replaces `current`, and fsyncs `.receipts/`. A crash before object rename leaves only ignored temp data; a crash after object publication but before pointer replacement leaves an immutable orphan; neither is current or archive-eligible. v1 retains all complete historical objects and provides no pruning operation.

#### Receipt schema and sealing derivation

`receipt.json` is:

```json
{
  "schema_name": "ai-harness.final-validation-receipt",
  "schema_version": 1,
  "candidate_policy": "git-worktree-v1",
  "candidate_id": "sha256:<hex>",
  "gate_run": "sha256:<hex>",
  "validation": {
    "path": "validation.md",
    "digest": "sha256:<hex>"
  },
  "semantic": {
    "verdict": "pass",
    "critical": 0,
    "gate_run": "sha256:<hex>",
    "approved": true
  },
  "native": {
    "all_gates_passed": true,
    "candidate_stable": true
  },
  "archive_eligible": true
}
```

Seal requires the semantic `gate-run` to equal the loaded run ID and the current candidate to equal `candidate_after.id`. It binds `candidate_id` to that after-candidate. `candidate_stable`, native approval, semantic approval, and `archive_eligible` are recomputed, never caller-provided; all redundant values are verified on every read. `archive_eligible` is exactly semantic approval AND native all-gates-pass AND candidate stability. The receipt ID is the typed hash of canonical `receipt.json` and is not embedded.

### CLI adapters

`commands/change.py` remains a thin JSON boundary and `main.py` only registers names:

```text
ai-harness change-gates-run -c <change> -i '<GateRunRequest JSON>'
ai-harness change-receipt-seal <change>
ai-harness change-archive <change>       # unchanged public archive seam
```

- `change-gates-run` parses edge JSON into immutable domain values, calls `FinalValidationReceipts.run_gates`, and emits `GateRunResult` JSON. It never accepts fact fields.
- `change-receipt-seal` accepts only the Change argument, calls `seal`, and emits `SealResult` JSON.
- A recorded failed gate or semantic denial is not a command crash: run/seal exits zero with `all_gates_passed` or `archive_eligible` false. Invalid input, capture/storage/integrity failure, or stale binding exits non-zero.
- Adapters do not hash, redact, parse validation, inspect Git, select gates, or decide eligibility.
- `change-archive` retains success text `done` and failure JSON `{ "errors": [<string>, ...] }` for compatibility.

### Error model and security boundary

`ReceiptError` carries a stable code plus a safe message and optional gate/category/path context. Codes are grouped as:

```text
declaration.invalid
change.invalid
candidate.capture-failed | candidate.mutated | candidate.stale
gate.infrastructure-failed
validation.missing | validation.malformed | validation.contradictory | validation.stale
run.missing | run.invalid | run.gates-failed
evidence.missing | evidence.invalid
receipt.missing | receipt.invalid | receipt.not-eligible
storage.failed
policy.unsupported | schema.unsupported
```

Messages may name a gate ID, policy, schema, and repository-relative path. They never include argv after a secret-match failure, environment values, raw output, retained output, or file contents. Archive translates one error into the existing string list without discarding its actionable code.

Trust boundaries are explicit:

- Gate declarations come from the trusted validator/orchestrator contract. No-shell execution prevents interpolation but does not prevent a declared executable from deleting files, reading secrets, using the network, or spawning descendants with the runner's OS permissions.
- Candidate and evidence integrity detects change/tampering but is not an identity signature. A hostile user with write access can replace code and issue a fresh receipt.
- Content addressing and immediate recheck establish single-process current-state ordering only. They do not close a mutation race after verification or provide multi-writer locking.
- Validation remains validator-authored judgment. Product code validates only the narrow verdict envelope and its consistency.

### Rollout and rollback

Rollout is fail-closed in one release boundary: register both producer commands, update validator/archiver instructions, add routing guidance, and enable archive enforcement together. There is no timestamp cutoff, compatibility flag, manually authored receipt, legacy exception, or fallback to an older receipt. Existing active Changes stay readable and routable but must refresh final validation through run/write/seal before archive. Archived Changes are untouched.

Rollback removes prompt guidance, CLI registrations, routing guidance, and archive enforcement together. Existing `.receipts/` directories remain inert data and move with a later archive under the restored behavior. A partial rollback that leaves enforcement without producers, or producers while archive ignores receipts, is forbidden.

### Test seams

The public test surface is `FinalValidationReceipts` plus the existing `ChangeLifecycle`/CLI seams:

- Canonical/schema tests create objects through public operations, then assert byte identity, IDs, strict duplicate/unknown-key rejection, and transitive tamper detection.
- Candidate tests use temporary real Git repositories and cover unborn/commit HEAD, staged/unstaged/deleted/mode changes, symlinks, recursive submodules, conflicts, non-ignored untracked files, ignored files, exclusions, unsupported paths/special files, and observable capture mutation.
- Process tests use controlled `sys.executable -c ...` argv, never a shell, for pass, non-zero, missing executable, timeout, binary stdout/stderr, chunk-boundary redaction, overlapping secrets, empty streams, exact limits, overflow, and candidate mutation.
- Storage tests exercise the public operation and inspect disk; failure injection is limited to stdlib filesystem primitives at atomic-write boundaries. Private collaborators are not mocked.
- Seal tests write exact validation bytes and cover semantic combinations, duplicate/malformed fields, wrong run references, changed validation, failed runs, stale candidates, existing-object reuse, and interrupted/orphan publication.
- Archive tests construct receipts through `run_gates` and `seal`, then prove both legacy and fully completed sliced success. Every structural, missing receipt, malformed pointer/object, failed gate, semantic denial, validation edit, evidence tamper, and candidate change failure occurs before specs promotion or Change movement.
- Ordering tests spy only on the public verifier and `_archive_move` boundary to prove structural preflight precedes verification and no operation intervenes before the first move. Existing destination-collision and rollback tests remain unchanged except receipt setup.
- Renderer tests pin the validator's run/write/seal sequence, exact `gate-run` field, judgment/fact separation, and the archiver's single native archive call with verbatim error surfacing.

## Seam map

### Class interaction

```text
Typer adapter
    |
    | GateRunRequest / Change name
    v
+---------------------------+
| FinalValidationReceipts   |  public deep seam
| run_gates / seal / verify |
+-------------+-------------+
              | composes; private, never bypassed
       +------+-------+----------+-------------+----------------+
       v              v          v             v                v
 _Candidate      _GateExecutor  _Validation  _ReceiptObject  _Canonical
 IdentityBuilder      |          EnvelopeParser Store          Codec
       |               v
   _GitInspector  _BoundedRedactor
```

### Validation-to-receipt interaction

```text
validator/orchestrator     CLI adapter       FinalValidationReceipts       disk
        |                      |                       |                     |
        | declare ordered gates                       |                     |
        |--------------------->| run_gates            |                     |
        |                      |---------------------->| capture candidate A |
        |                      |                       | run argv sequential |
        |                      |                       | capture candidate B |
        |                      |                       | publish run bundle  |
        |                      |<----------------------| run ID + facts      |
        |<---------------------|                       |                     |
        | write root validation.md with gate-run      |                     |
        |--------------------------------------------------------------->   |
        |                      | seal(change)          |                     |
        |--------------------->|---------------------->| parse validation    |
        |                      |                       | verify run/evidence |
        |                      |                       | recapture candidate |
        |                      |                       | publish receipt     |
        |                      |                       | replace current     |
        |<---------------------|<----------------------| receipt facts       |
```

### Archive interaction and ordering

```text
change-archive
     |
     v
ChangeLifecycle.archive
     |
     +--> existing legacy/sliced structural preflight
     |      tasks + approvals + validation freshness + collisions
     |      failure ------------------------------------> NO MOVE
     |
     +--> FinalValidationReceipts.verify_for_archive
     |      current -> receipt -> run -> evidence -> validation
     |      -> semantic facts -> candidate capture -> current re-read
     |      failure ------------------------------------> NO MOVE
     |
     +--> _archive_move                         (no intervening operation)
            specs promotion -> Change move
                    \-> existing rollback on second-stage failure
```

## Rejected alternatives

### Public `CandidateIdentity`, `GateRunner`, and `ReceiptStore` services

This exposes policy plumbing as three shallow seams and lets callers combine a candidate from one capture with facts from another. The selected protocol keeps those collaborators internal and makes invalid ordering unrepresentable at the public boundary.

### One `validate-and-archive` command

Combining gate execution, semantic judgment, sealing, and movement would either ask native code to invent the verdict or ask the validator to supply native facts. The two-step run/seal protocol deliberately leaves room for the validator to write judgment after observing facts, while archive remains a separate immediate verifier/transaction.

### Shell command strings

Shell strings make quoting and interpolation part of the evidence contract and permit accidental command injection. Argv arrays are less expressive but deterministic, auditable, and sufficient for declared gates; pipelines must be represented by an explicitly trusted executable/script already in the candidate.

### Commit SHA or `git diff` text as candidate identity

A commit alone omits staged, unstaged, deleted, untracked, symlink, and submodule state. Human diff text is localization/configuration sensitive and can omit binary content. The canonical head/index/worktree/untracked manifest is deeper because it hides those Git and filesystem distinctions behind one candidate ID.

### Hash every filesystem path, including ignored files and receipts

Including receipt output creates self-reference and makes publication stale itself. Including `.git` and ignored caches/secrets is both unstable and unsafe. The selected explicit exclusions avoid self-reference while intentionally documenting that ignored inputs prevent hermetic claims.

### Persist raw output and redact later

This leaves secrets on disk during normal execution or crashes and makes redaction non-atomic. Streaming redaction before persistence ensures only bounded redacted evidence crosses the storage boundary.

### Store only output digests

A digest can detect later change but provides no retained evidence for audit. Conversely, unbounded inline output makes receipt JSON large and secret-prone. Bounded binary evidence files inside the immutable run bundle provide auditability while keeping the run schema small.

### Mutable `latest.json` receipt or archive-time resealing

Overwriting evidence destroys history; resealing at archive converts verification into mutation and can bless changed state. Immutable objects plus one atomic `current` pointer preserve history, while archive remains read-only.

### Timestamp freshness or legacy grandfathering

Mtimes do not bind bytes and a legacy waiver defeats the invariant precisely for active work most likely to have old artifacts. Existing mtime rules stay as structural defense-in-depth, but every active Change must satisfy exact hashes and current candidate identity.

### Prompt-only receipt fields

A hand-authored digest or `all gates passed` line is forgeable and cannot prove execution or bounded evidence. The CLI accepts declarations only and derives all facts; prompts coordinate the protocol but do not enforce it.
