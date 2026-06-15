package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/diegoagd10/ai-harness-setup/cli/internal/install"
)

// runResult captures everything an end-to-end Run invocation produces.
type runResult struct {
	code   int
	stdout string
	stderr string
}

func invoke(args ...string) runResult {
	var out, errBuf bytes.Buffer
	// Default test invocations are non-interactive with empty stdin, matching a
	// CI/script run. Tests that drive the picker call Run directly with a reader
	// and interactive=true.
	code := Run(args, strings.NewReader(""), false, &out, &errBuf)
	return runResult{code: code, stdout: out.String(), stderr: errBuf.String()}
}

// TestRunInstallInteractivePromptSelectsHarness drives the picker through Run:
// with no --harness and interactive=true, the injected stdin ("2" = claude)
// selects claude only — proving the prompt path without relying on a real TTY.
func TestRunInstallInteractivePromptSelectsHarness(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	var out, errBuf bytes.Buffer
	code := Run([]string{"install", "--repo", repo}, strings.NewReader("2\n"), true, &out, &errBuf)
	if code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", code, errBuf.String())
	}
	if info, err := os.Lstat(filepath.Join(home, ".claude", "skills", "example", "SKILL.md")); err != nil || info.Mode()&os.ModeSymlink != 0 {
		t.Fatalf("claude skills should be copied when '2' is chosen: %v", err)
	}
	if _, err := os.Stat(filepath.Join(home, ".config", "opencode", "opencode.json")); !os.IsNotExist(err) {
		t.Fatalf("opencode.json must be absent when only claude is chosen (err=%v)", err)
	}
}

func TestRunNoArgsPrintsUsageAndFails(t *testing.T) {
	res := invoke()
	if res.code == 0 {
		t.Fatalf("expected non-zero exit, got %d", res.code)
	}
	if !strings.Contains(res.stderr, "usage") && !strings.Contains(res.stderr, "Usage") {
		t.Fatalf("expected usage on stderr, got %q", res.stderr)
	}
	if res.stdout != "" {
		t.Fatalf("expected empty stdout on usage error, got %q", res.stdout)
	}
}

func TestRunUnknownSubcommandFails(t *testing.T) {
	res := invoke("bogus-cmd")
	if res.code == 0 {
		t.Fatalf("expected non-zero exit for unknown subcommand")
	}
	if !strings.Contains(res.stderr, "bogus-cmd") {
		t.Fatalf("expected stderr to name the unknown subcommand, got %q", res.stderr)
	}
}

func TestRunUnknownFlagFails(t *testing.T) {
	res := invoke("sdd-status", "--nope")
	if res.code == 0 {
		t.Fatalf("expected non-zero exit for unknown flag")
	}
	if res.stderr == "" {
		t.Fatalf("expected an error message on stderr")
	}
}

func TestRunTooManyPositionalsFails(t *testing.T) {
	res := invoke("sdd-status", "alpha", "beta")
	if res.code == 0 {
		t.Fatalf("expected non-zero exit for two positionals")
	}
	if !strings.Contains(res.stderr, "beta") {
		t.Fatalf("expected stderr to name the extra positional, got %q", res.stderr)
	}
}

// writeOpenSpecTree builds a minimal openspec change tree under a temp dir and
// returns the workspace root. The change has a proposal so it is a real,
// resolvable change rather than an empty workspace.
func writeOpenSpecChange(t *testing.T, change string) string {
	t.Helper()
	root := t.TempDir()
	changeDir := filepath.Join(root, "openspec", "changes", change)
	if err := os.MkdirAll(changeDir, 0o755); err != nil {
		t.Fatalf("mkdir change: %v", err)
	}
	if err := os.WriteFile(filepath.Join(changeDir, "proposal.md"), []byte("# Proposal\n\nWhy.\n"), 0o644); err != nil {
		t.Fatalf("write proposal: %v", err)
	}
	return root
}

func TestRunSDDStatusMarkdown(t *testing.T) {
	root := writeOpenSpecChange(t, "add-widget")
	res := invoke("sdd-status", "--cwd", root)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	if !strings.Contains(res.stdout, "## SDD Status: add-widget") {
		t.Fatalf("expected markdown header for change, got %q", res.stdout)
	}
}

func TestRunSDDStatusJSON(t *testing.T) {
	root := writeOpenSpecChange(t, "add-widget")
	res := invoke("sdd-status", "--cwd", root, "--json")
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(res.stdout), &payload); err != nil {
		t.Fatalf("stdout is not valid JSON: %v\n%s", err, res.stdout)
	}
	if payload["changeName"] != "add-widget" {
		t.Fatalf("expected changeName add-widget, got %v", payload["changeName"])
	}
	// sdd-status without --instructions must NOT include phaseInstructions.
	if _, ok := payload["phaseInstructions"]; ok {
		t.Fatalf("sdd-status should omit phaseInstructions, got %v", payload["phaseInstructions"])
	}
	// Indented output is requested via MarshalIndent (2 spaces).
	if !strings.Contains(res.stdout, "\n  \"schemaName\"") {
		t.Fatalf("expected 2-space indented JSON, got %q", res.stdout)
	}
}

func TestRunSDDStatusWithInstructionsFlagIncludesInstructions(t *testing.T) {
	root := writeOpenSpecChange(t, "add-widget")
	res := invoke("sdd-status", "--cwd", root, "--json", "--instructions")
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(res.stdout), &payload); err != nil {
		t.Fatalf("stdout is not valid JSON: %v", err)
	}
	if _, ok := payload["phaseInstructions"]; !ok {
		t.Fatalf("--instructions should include phaseInstructions, got %v", payload)
	}
}

func TestRunSDDContinueMarkdown(t *testing.T) {
	root := writeOpenSpecChange(t, "add-widget")
	res := invoke("sdd-continue", "--cwd", root)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	if !strings.Contains(res.stdout, "## Native SDD Dispatcher: add-widget") {
		t.Fatalf("expected dispatcher header, got %q", res.stdout)
	}
}

func TestRunSDDContinueJSONAlwaysIncludesInstructions(t *testing.T) {
	root := writeOpenSpecChange(t, "add-widget")
	// No --instructions flag; sdd-continue must still include them.
	res := invoke("sdd-continue", "--cwd", root, "--json")
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(res.stdout), &payload); err != nil {
		t.Fatalf("stdout is not valid JSON: %v", err)
	}
	if _, ok := payload["phaseInstructions"]; !ok {
		t.Fatalf("sdd-continue must always include phaseInstructions, got %v", payload)
	}
}

func TestRunSDDStatusEmptyWorkspaceRecommendsSddNew(t *testing.T) {
	root := t.TempDir() // existing dir, no openspec tree
	res := invoke("sdd-status", "--cwd", root, "--json")
	if res.code != 0 {
		t.Fatalf("expected exit 0 for empty workspace, got %d (stderr=%q)", res.code, res.stderr)
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(res.stdout), &payload); err != nil {
		t.Fatalf("stdout is not valid JSON: %v", err)
	}
	if payload["nextRecommended"] != "sdd-new" {
		t.Fatalf("expected nextRecommended sdd-new, got %v", payload["nextRecommended"])
	}
}

// writeFakeRepo builds a minimal valid harness repo with real files for the
// copied skills, OpenCode assets, and generated command inputs.
func writeFakeRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	if err := os.MkdirAll(filepath.Join(repo, "skills"), 0o755); err != nil {
		t.Fatalf("mkdir skills: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(repo, "skills", "example"), 0o755); err != nil {
		t.Fatalf("mkdir skills/example: %v", err)
	}
	if err := os.WriteFile(filepath.Join(repo, "AGENTS.md"), []byte("# Agents\n"), 0o644); err != nil {
		t.Fatalf("write AGENTS.md: %v", err)
	}
	if err := os.WriteFile(filepath.Join(repo, "skills", "example", "SKILL.md"), []byte("# Example skill\n"), 0o644); err != nil {
		t.Fatalf("write skills/example/SKILL.md: %v", err)
	}
	cmdDir := filepath.Join(repo, "prompts", "commands")
	if err := os.MkdirAll(cmdDir, 0o755); err != nil {
		t.Fatalf("mkdir prompts/commands: %v", err)
	}
	canonical := "---\ndescription: Continue the next SDD phase\nsubtask: false\nread-only: false\n---\n\n" +
		"You are the `{{ORCHESTRATOR_AGENT}}`.\n\nRun `ai-harness sdd-continue`.\n\nChange: {{ARGS}}\n"
	if err := os.WriteFile(filepath.Join(cmdDir, "sdd-continue.md"), []byte(canonical), 0o644); err != nil {
		t.Fatalf("write canonical command: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(repo, "prompts", "sdd"), 0o755); err != nil {
		t.Fatalf("mkdir prompts/sdd: %v", err)
	}
	if err := os.WriteFile(filepath.Join(repo, "prompts", "sdd", "sdd-orchestrator.md"), []byte("# Orchestrator\n"), 0o644); err != nil {
		t.Fatalf("write prompts/sdd/sdd-orchestrator.md: %v", err)
	}
	// agent-clis/opencode/opencode.json is the source ai-harness substitutes
	// {{HOME}} into and writes as a regular file.
	ocDir := filepath.Join(repo, "agent-clis", "opencode")
	if err := os.MkdirAll(ocDir, 0o755); err != nil {
		t.Fatalf("mkdir agent-clis/opencode: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(ocDir, "plugins"), 0o755); err != nil {
		t.Fatalf("mkdir agent-clis/opencode/plugins: %v", err)
	}
	if err := os.WriteFile(filepath.Join(ocDir, "plugins", "model-variants.ts"), []byte("export {};\n"), 0o644); err != nil {
		t.Fatalf("write agent-clis/opencode/plugins/model-variants.ts: %v", err)
	}
	// agent-clis/opencode/plugins is copied into the OpenCode config dir on
	// install (OpenCode auto-loads plugins it finds there).
	ocSource := `{"agent":{"sdd-orchestrator":{"prompt":"{file:{{HOME}}/.config/opencode/prompts/sdd/sdd-orchestrator.md}"}}}`
	if err := os.WriteFile(filepath.Join(ocDir, "opencode.json"), []byte(ocSource), 0o644); err != nil {
		t.Fatalf("write opencode.json source: %v", err)
	}
	return repo
}

func TestRunInstallCopiesHarnessIntoHomeAndWritesManifest(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	for _, dest := range []string{
		filepath.Join(home, ".claude", "skills", "example", "SKILL.md"),
		filepath.Join(home, ".config", "opencode", "plugins", "model-variants.ts"),
	} {
		info, err := os.Lstat(dest)
		if err != nil {
			t.Fatalf("expected copied file at %s: %v", dest, err)
		}
		if info.Mode()&os.ModeSymlink != 0 {
			t.Fatalf("%s should be copied, not symlinked", dest)
		}
		if !strings.Contains(res.stdout, filepath.Dir(filepath.Dir(dest))) && !strings.Contains(res.stdout, filepath.Dir(dest)) {
			t.Fatalf("expected stdout to mention %s, got %q", dest, res.stdout)
		}
	}
	manifest := filepath.Join(home, ".config", "ai-harness", "install-manifest.json")
	if _, err := os.Stat(manifest); err != nil {
		t.Fatalf("expected manifest at %s: %v", manifest, err)
	}
}

func TestRunUninstallUsesManifestWithoutRepoDependency(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	owned := filepath.Join(home, ".config", "opencode", "AGENTS.md")
	if err := os.MkdirAll(filepath.Dir(owned), 0o755); err != nil {
		t.Fatalf("mkdir owned parent: %v", err)
	}
	if err := os.WriteFile(owned, []byte("installed\n"), 0o644); err != nil {
		t.Fatalf("write owned file: %v", err)
	}
	manifestDir := filepath.Join(home, ".config", "ai-harness")
	if err := os.MkdirAll(manifestDir, 0o755); err != nil {
		t.Fatalf("mkdir manifest dir: %v", err)
	}
	manifest := install.Manifest{Version: 1, Installed: []install.ManifestEntry{{Dest: owned, Kind: "file"}}}
	payload, err := json.Marshal(manifest)
	if err != nil {
		t.Fatalf("marshal manifest: %v", err)
	}
	if err := os.WriteFile(filepath.Join(manifestDir, "install-manifest.json"), payload, 0o644); err != nil {
		t.Fatalf("write manifest: %v", err)
	}

	nonRepo := t.TempDir()
	oldCwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	if err := os.Chdir(nonRepo); err != nil {
		t.Fatalf("chdir non-repo: %v", err)
	}
	t.Cleanup(func() {
		if err := os.Chdir(oldCwd); err != nil {
			t.Fatalf("restore cwd: %v", err)
		}
	})

	res := invoke("uninstall")
	if res.code != 0 {
		t.Fatalf("expected uninstall from non-repo cwd to succeed, got %d stderr=%q", res.code, res.stderr)
	}
	if _, err := os.Stat(owned); !os.IsNotExist(err) {
		t.Fatalf("owned file should be removed, stat err=%v", err)
	}
}

func TestRunInstallGeneratesOpenCodeCommandFiles(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	dest := filepath.Join(home, ".config", "opencode", "commands", "sdd-continue.md")
	content, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("expected generated command at %s: %v", dest, err)
	}
	text := string(content)
	if !strings.Contains(text, "agent: sdd-orchestrator") {
		t.Fatalf("generated command missing opencode frontmatter:\n%s", text)
	}
	if strings.Contains(text, "{{ORCHESTRATOR_AGENT}}") || strings.Contains(text, "{{ARGS}}") {
		t.Fatalf("generated command still has placeholders:\n%s", text)
	}
	if !strings.Contains(text, "You are the `sdd-orchestrator`.") {
		t.Fatalf("orchestrator not substituted:\n%s", text)
	}
	if !strings.Contains(res.stdout, dest) {
		t.Fatalf("expected stdout to mention generated %s, got %q", dest, res.stdout)
	}
}

func TestRunUninstallRemovesOpenCodeCommandFiles(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	if res := invoke("install", "--repo", repo); res.code != 0 {
		t.Fatalf("install precondition failed: %q", res.stderr)
	}
	dest := filepath.Join(home, ".config", "opencode", "commands", "sdd-continue.md")
	if _, err := os.Stat(dest); err != nil {
		t.Fatalf("install should have created %s: %v", dest, err)
	}

	res := invoke("uninstall", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	if _, err := os.Lstat(dest); !os.IsNotExist(err) {
		t.Fatalf("expected generated command %s removed, lstat err = %v", dest, err)
	}
	if _, err := os.Stat(filepath.Join(home, ".config", "ai-harness", "install-manifest.json")); !os.IsNotExist(err) {
		t.Fatalf("manifest should be removed after uninstall, err = %v", err)
	}
}

func TestRunInstallGeneratesOpenCodeJSONWithHomeSubstituted(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	dest := filepath.Join(home, ".config", "opencode", "opencode.json")
	content, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("expected generated opencode.json at %s: %v", dest, err)
	}
	text := string(content)
	if strings.Contains(text, "{{HOME}}") {
		t.Fatalf("opencode.json still has {{HOME}}:\n%s", text)
	}
	want := filepath.Join(home, ".config", "opencode", "prompts", "sdd", "sdd-orchestrator.md")
	if !strings.Contains(text, want) {
		t.Fatalf("opencode.json missing substituted home path %q:\n%s", want, text)
	}
	if !strings.Contains(res.stdout, dest) {
		t.Fatalf("expected stdout to mention generated %s, got %q", dest, res.stdout)
	}
}

func TestRunInstallPersistsManifestForGeneratedArtifactsBeforeLateFailure(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)
	if err := os.Remove(filepath.Join(repo, "agent-clis", "opencode", "opencode.json")); err != nil {
		t.Fatalf("remove opencode source to force late failure: %v", err)
	}

	res := invoke("install", "--harness", "opencode", "--repo", repo)
	if res.code == 0 {
		t.Fatalf("expected install to fail after copying/generating artifacts")
	}
	commandDest := filepath.Join(home, ".config", "opencode", "commands", "sdd-continue.md")
	if _, err := os.Stat(commandDest); err != nil {
		t.Fatalf("late-failure setup should have generated command before failing: %v", err)
	}
	manifestPath := filepath.Join(home, ".config", "ai-harness", "install-manifest.json")
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatalf("manifest must be written for artifacts created before late failure: %v", err)
	}
	var manifest install.Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		t.Fatalf("decode manifest: %v", err)
	}
	wantOwned := map[string]bool{
		filepath.Join(home, ".config", "opencode", "plugins", "model-variants.ts"): true,
		commandDest: true,
	}
	for _, entry := range manifest.Installed {
		delete(wantOwned, entry.Dest)
		if entry.Dest == filepath.Join(home, ".config", "opencode", "opencode.json") {
			t.Fatalf("failed opencode.json generation must not be recorded as owned: %+v", manifest.Installed)
		}
	}
	if len(wantOwned) != 0 {
		t.Fatalf("manifest missing created artifacts: %v in %+v", wantOwned, manifest.Installed)
	}
}

func TestRunUninstallRemovesOpenCodeJSON(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	if res := invoke("install", "--repo", repo); res.code != 0 {
		t.Fatalf("install precondition failed: %q", res.stderr)
	}
	dest := filepath.Join(home, ".config", "opencode", "opencode.json")
	if _, err := os.Stat(dest); err != nil {
		t.Fatalf("install should have created %s: %v", dest, err)
	}

	res := invoke("uninstall", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	if _, err := os.Lstat(dest); !os.IsNotExist(err) {
		t.Fatalf("expected opencode.json %s removed, lstat err = %v", dest, err)
	}
}

func TestRunInstallHarnessClaudeSkipsOpenCodeExtras(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--harness", "claude", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	// claude + agents files exist as copies.
	for _, copied := range []string{
		filepath.Join(home, ".claude", "CLAUDE.md"),
		filepath.Join(home, ".agents", "skills", "example", "SKILL.md"),
	} {
		info, err := os.Lstat(copied)
		if err != nil {
			t.Fatalf("expected copied file %s: %v", copied, err)
		}
		if info.Mode()&os.ModeSymlink != 0 {
			t.Fatalf("expected copied file, not symlink: %s", copied)
		}
	}

	// No opencode.json, no command files, no opencode copies.
	if _, err := os.Stat(filepath.Join(home, ".config", "opencode", "opencode.json")); !os.IsNotExist(err) {
		t.Fatalf("claude-only must not generate opencode.json, err = %v", err)
	}
	if _, err := os.Stat(filepath.Join(home, ".config", "opencode", "commands", "sdd-continue.md")); !os.IsNotExist(err) {
		t.Fatalf("claude-only must not generate command files, err = %v", err)
	}
	if _, err := os.Lstat(filepath.Join(home, ".config", "opencode", "plugins")); !os.IsNotExist(err) {
		t.Fatalf("claude-only must not create opencode plugins copy, err = %v", err)
	}
}

func TestRunInstallHarnessOpenCodeGeneratesExtras(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--harness", "opencode", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	if info, err := os.Lstat(filepath.Join(home, ".config", "opencode", "opencode.json")); err != nil || info.Mode()&os.ModeSymlink != 0 {
		t.Fatalf("opencode selection should generate opencode.json: %v", err)
	}
	if info, err := os.Lstat(filepath.Join(home, ".config", "opencode", "commands", "sdd-continue.md")); err != nil || info.Mode()&os.ModeSymlink != 0 {
		t.Fatalf("opencode selection should generate command files: %v", err)
	}
	if info, err := os.Lstat(filepath.Join(home, ".config", "opencode", "plugins", "model-variants.ts")); err != nil || info.Mode()&os.ModeSymlink != 0 {
		t.Fatalf("opencode selection should copy plugins: %v", err)
	}
	// claude must not be configured.
	if _, err := os.Lstat(filepath.Join(home, ".claude", "CLAUDE.md")); !os.IsNotExist(err) {
		t.Fatalf("opencode-only must not copy claude CLAUDE.md, err = %v", err)
	}
}

func TestRunInstallUnknownHarnessFails(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--harness", "bogus", "--repo", repo)
	if res.code == 0 {
		t.Fatalf("expected non-zero exit for unknown harness")
	}
	if !strings.Contains(res.stderr, "bogus") {
		t.Fatalf("expected stderr to name the unknown harness, got %q", res.stderr)
	}
}

func TestRunUninstallCleansAllHarnessesIgnoringFlag(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	// Install everything (no --harness => all in non-TTY).
	if res := invoke("install", "--repo", repo); res.code != 0 {
		t.Fatalf("install precondition failed: %q", res.stderr)
	}

	// Uninstall with a narrow --harness flag must still clean every link.
	res := invoke("uninstall", "--harness", "claude", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	for _, dest := range []string{
		filepath.Join(home, ".claude", "skills"),
		filepath.Join(home, ".copilot", "copilot-instructions.md"),
		filepath.Join(home, ".config", "opencode", "plugins"),
	} {
		if _, err := os.Lstat(dest); !os.IsNotExist(err) {
			t.Fatalf("uninstall should remove %s regardless of flag, lstat err = %v", dest, err)
		}
	}
}

// TestOpenCodeAgentsHaveDefaultModels guards the per-agent default model
// assignments in the canonical opencode.json (orchestrator + the 10 SDD phases).
// They are written verbatim into ~/.config/opencode/opencode.json at install.
func TestOpenCodeAgentsHaveDefaultModels(t *testing.T) {
	repoRoot := filepath.Clean(filepath.Join("..", "..", ".."))
	raw := readAssetText(t, filepath.Join(repoRoot, "agent-clis", "opencode", "opencode.json"))
	var cfg struct {
		Agent map[string]struct {
			Model string `json:"model"`
		} `json:"agent"`
	}
	if err := json.Unmarshal([]byte(raw), &cfg); err != nil {
		t.Fatalf("opencode.json is not valid JSON: %v", err)
	}
	want := map[string]string{
		"sdd-orchestrator": "openai/gpt-5.5",
		"sdd-init":         "minimax/MiniMax-M2.7",
		"sdd-explore":      "openai/gpt-5.5",
		"sdd-propose":      "openai/gpt-5.5",
		"sdd-spec":         "openai/gpt-5.5",
		"sdd-design":       "openai/gpt-5.5",
		"sdd-tasks":        "openai/gpt-5.5",
		"sdd-apply":        "openai/gpt-5.4-mini",
		"sdd-verify":       "openai/gpt-5.5",
		"sdd-archive":      "minimax/MiniMax-M2.7",
		"sdd-onboard":      "openai/gpt-5.5",
	}
	for agent, model := range want {
		if got := cfg.Agent[agent].Model; got != model {
			t.Errorf("agent %q model = %q, want %q", agent, got, model)
		}
	}
}

func TestPromptHarnessesEmptyMeansAll(t *testing.T) {
	in := strings.NewReader("\n")
	var out bytes.Buffer
	got, err := promptHarnesses(in, &out)
	if err != nil {
		t.Fatalf("promptHarnesses error: %v", err)
	}
	if len(got) != len(install.AllHarnesses) {
		t.Fatalf("empty input: got %v, want all %v", got, install.AllHarnesses)
	}
}

func TestPromptHarnessesNumberSelectsOpencode(t *testing.T) {
	in := strings.NewReader("1\n")
	var out bytes.Buffer
	got, err := promptHarnesses(in, &out)
	if err != nil {
		t.Fatalf("promptHarnesses error: %v", err)
	}
	if len(got) != 1 || got[0] != install.HarnessOpenCode {
		t.Fatalf(`input "1": got %v, want [opencode]`, got)
	}
}

func TestPromptHarnessesNamesSelectThose(t *testing.T) {
	in := strings.NewReader("claude,copilot\n")
	var out bytes.Buffer
	got, err := promptHarnesses(in, &out)
	if err != nil {
		t.Fatalf("promptHarnesses error: %v", err)
	}
	want := map[install.Harness]bool{install.HarnessClaude: true, install.HarnessCopilot: true}
	if len(got) != 2 {
		t.Fatalf(`input "claude,copilot": got %v, want 2`, got)
	}
	for _, h := range got {
		if !want[h] {
			t.Fatalf("unexpected harness %q in %v", h, got)
		}
	}
}

func TestPromptHarnessesRejectsBadInput(t *testing.T) {
	in := strings.NewReader("bogus\n")
	var out bytes.Buffer
	_, err := promptHarnesses(in, &out)
	if err == nil {
		t.Fatalf(`input "bogus": expected an error`)
	}
}

func TestRunInstallInvalidRepoFails(t *testing.T) {
	bare := t.TempDir() // no skills/, no AGENTS.md
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--repo", bare)
	if res.code == 0 {
		t.Fatalf("expected non-zero exit for invalid repo")
	}
	if res.stderr == "" {
		t.Fatalf("expected an error message on stderr")
	}
}

func TestRunUninstallRemovesHarnessLinks(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	if res := invoke("install", "--repo", repo); res.code != 0 {
		t.Fatalf("install precondition failed: %q", res.stderr)
	}
	res := invoke("uninstall", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	dest := filepath.Join(home, ".claude", "skills")
	if _, err := os.Lstat(dest); !os.IsNotExist(err) {
		t.Fatalf("expected %s removed, lstat err = %v", dest, err)
	}
	if !strings.Contains(res.stdout, "removed") {
		t.Fatalf("expected stdout to report a removal, got %q", res.stdout)
	}
}

func TestRunPositionalChangeNameIsPassedThrough(t *testing.T) {
	root := writeOpenSpecChange(t, "add-widget")
	// Ask for a change that does not exist -> blocked status, sdd-new, but the
	// requested name is echoed in changeName.
	res := invoke("sdd-status", "--cwd", root, "--json", "missing-change")
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(res.stdout), &payload); err != nil {
		t.Fatalf("stdout is not valid JSON: %v", err)
	}
	if payload["changeName"] != "missing-change" {
		t.Fatalf("expected changeName missing-change, got %v", payload["changeName"])
	}
}

func TestOpenCodeSDDAssetsPreferAIHarnessNativeDispatcher(t *testing.T) {
	repoRoot := filepath.Clean(filepath.Join("..", "..", ".."))
	assets := []struct {
		path     string
		required []string
	}{
		{filepath.Join(repoRoot, "prompts", "commands", "sdd-status.md"), []string{"ai-harness sdd-status"}},
		{filepath.Join(repoRoot, "prompts", "commands", "sdd-continue.md"), []string{"ai-harness sdd-continue"}},
		{filepath.Join(repoRoot, "prompts", "sdd", "sdd-orchestrator.md"), []string{"ai-harness sdd-status", "ai-harness sdd-continue"}},
	}

	for _, asset := range assets {
		content, err := os.ReadFile(asset.path)
		if err != nil {
			t.Fatalf("read %s: %v", asset.path, err)
		}

		text := string(content)
		for _, required := range asset.required {
			if !strings.Contains(text, required) {
				t.Fatalf("%s should document %q", asset.path, required)
			}
		}
		if strings.Contains(text, "gentle-ai sdd-status") || strings.Contains(text, "gentle-ai sdd-continue") {
			t.Fatalf("%s still documents the old gentle-ai dispatcher", asset.path)
		}
	}
}

func TestOpenCodeControlledBlocksStaySynchronized(t *testing.T) {
	repoRoot := filepath.Clean(filepath.Join("..", "..", ".."))
	opencodeRoot := filepath.Join(repoRoot, "agent-clis", "opencode")

	modelAssignments := readAssetText(t, filepath.Join(opencodeRoot, "blocks", "sdd-model-assignments.md"))
	orchestrator := readAssetText(t, filepath.Join(repoRoot, "prompts", "sdd", "sdd-orchestrator.md"))
	if !strings.Contains(orchestrator, strings.TrimSpace(modelAssignments)) {
		t.Fatalf("sdd-orchestrator.md must include blocks/sdd-model-assignments.md")
	}

	// AGENTS.md is the global persona OpenCode loads (copied into
	// ~/.config/opencode at install time); the orchestrator carries generated
	// blocks. Neither may fence controlled sections with HTML sentinels.
	agents := readAssetText(t, filepath.Join(repoRoot, "AGENTS.md"))
	for _, text := range []struct {
		name    string
		content string
	}{
		{"AGENTS.md", agents},
		{"sdd-orchestrator.md", orchestrator},
	} {
		if strings.Contains(text.content, "<!-- ai-harness:") || strings.Contains(text.content, "<!-- /ai-harness:") ||
			strings.Contains(text.content, "<!-- gentle-ai:") || strings.Contains(text.content, "<!-- /gentle-ai:") {
			t.Fatalf("%s should not use HTML sentinels for controlled blocks", text.name)
		}
	}
}

func TestOpenCodeSddOrchestratorDefaultsToHybridWithoutArtifactChoice(t *testing.T) {
	repoRoot := filepath.Clean(filepath.Join("..", "..", ".."))
	orchestrator := readAssetText(t, filepath.Join(repoRoot, "prompts", "sdd", "sdd-orchestrator.md"))

	if strings.Contains(orchestrator, "B. Artifacts") {
		t.Fatalf("sdd-orchestrator.md still presents an artifact-store choice block")
	}
	if strings.Contains(orchestrator, "B1") {
		t.Fatalf("sdd-orchestrator.md still mentions artifact-store choice codes")
	}
	if strings.Contains(orchestrator, "B1 Hybrid") {
		t.Fatalf("sdd-orchestrator.md still maps hybrid as a preflight choice code")
	}
	if strings.Contains(orchestrator, "engram -> default when available") {
		t.Fatalf("sdd-orchestrator.md still documents engram as the default artifact store")
	}
	if !strings.Contains(orchestrator, "`hybrid` -> default SDD persistence; repo files plus Engram copy") {
		t.Fatalf("sdd-orchestrator.md must document hybrid as the default SDD persistence mode")
	}
}

func readAssetText(t *testing.T, path string) string {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(content)
}
