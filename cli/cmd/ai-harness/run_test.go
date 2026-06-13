package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// runResult captures everything an end-to-end Run invocation produces.
type runResult struct {
	code   int
	stdout string
	stderr string
}

func invoke(args ...string) runResult {
	var out, errBuf bytes.Buffer
	code := Run(args, &out, &errBuf)
	return runResult{code: code, stdout: out.String(), stderr: errBuf.String()}
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

// writeFakeRepo builds a minimal valid harness repo (skills/ + AGENTS.md) plus a
// canonical prompts/commands/ entrypoint so install can generate command files.
func writeFakeRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	if err := os.MkdirAll(filepath.Join(repo, "skills"), 0o755); err != nil {
		t.Fatalf("mkdir skills: %v", err)
	}
	if err := os.WriteFile(filepath.Join(repo, "AGENTS.md"), []byte("# Agents\n"), 0o644); err != nil {
		t.Fatalf("write AGENTS.md: %v", err)
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
	return repo
}

func TestRunInstallLinksHarnessIntoHome(t *testing.T) {
	repo := writeFakeRepo(t)
	home := t.TempDir()
	t.Setenv("HOME", home)

	res := invoke("install", "--repo", repo)
	if res.code != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%q)", res.code, res.stderr)
	}

	dest := filepath.Join(home, ".claude", "skills")
	target, err := os.Readlink(dest)
	if err != nil {
		t.Fatalf("expected symlink at %s: %v", dest, err)
	}
	if target != filepath.Join(repo, "skills") {
		t.Fatalf("symlink target = %q, want %q", target, filepath.Join(repo, "skills"))
	}
	if !strings.Contains(res.stdout, dest) {
		t.Fatalf("expected stdout to mention %s, got %q", dest, res.stdout)
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
	if !strings.Contains(text, "agent: gentle-orchestrator") {
		t.Fatalf("generated command missing opencode frontmatter:\n%s", text)
	}
	if strings.Contains(text, "{{ORCHESTRATOR_AGENT}}") || strings.Contains(text, "{{ARGS}}") {
		t.Fatalf("generated command still has placeholders:\n%s", text)
	}
	if !strings.Contains(text, "You are the `gentle-orchestrator`.") {
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
		{filepath.Join(repoRoot, "agent-clis", "opencode", "sdd-orchestrator.md"), []string{"ai-harness sdd-status", "ai-harness sdd-continue"}},
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

	persona := readAssetText(t, filepath.Join(opencodeRoot, "blocks", "persona.md"))
	agents := readAssetText(t, filepath.Join(opencodeRoot, "AGENTS.md"))
	if strings.TrimSpace(agents) != strings.TrimSpace(persona) {
		t.Fatalf("AGENTS.md must match blocks/persona.md")
	}

	modelAssignments := readAssetText(t, filepath.Join(opencodeRoot, "blocks", "sdd-model-assignments.md"))
	orchestrator := readAssetText(t, filepath.Join(opencodeRoot, "sdd-orchestrator.md"))
	if !strings.Contains(orchestrator, strings.TrimSpace(modelAssignments)) {
		t.Fatalf("sdd-orchestrator.md must include blocks/sdd-model-assignments.md")
	}

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

func readAssetText(t *testing.T, path string) string {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(content)
}
