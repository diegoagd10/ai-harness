package opencode

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeSource writes a minimal opencode.json source carrying {{HOME}}
// placeholders under <repo>/agent-clis/opencode/ and returns the repo root.
func fakeSource(t *testing.T, body string) string {
	t.Helper()
	repo := t.TempDir()
	srcDir := filepath.Join(repo, "agent-clis", "opencode")
	if err := os.MkdirAll(srcDir, 0o755); err != nil {
		t.Fatalf("mkdir source dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(srcDir, "opencode.json"), []byte(body), 0o644); err != nil {
		t.Fatalf("write source: %v", err)
	}
	return repo
}

func TestGenerateSubstitutesHomePlaceholder(t *testing.T) {
	home := "/home/tester"
	repo := fakeSource(t, `{"prompt":"{file:{{HOME}}/.config/opencode/prompts/sdd/sdd-orchestrator.md}"}`)
	opencodeDir := filepath.Join(t.TempDir(), ".config", "opencode")

	out, err := Generate(repo, opencodeDir, home)
	if err != nil {
		t.Fatalf("Generate error: %v", err)
	}

	dest := filepath.Join(opencodeDir, "opencode.json")
	if out.Dest != dest {
		t.Fatalf("Outcome.Dest = %q, want %q", out.Dest, dest)
	}
	if out.Action != ActionGenerated {
		t.Fatalf("Outcome.Action = %q, want %q", out.Action, ActionGenerated)
	}

	data, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("read generated file: %v", err)
	}
	text := string(data)
	if strings.Contains(text, "{{HOME}}") {
		t.Fatalf("generated file still has {{HOME}}:\n%s", text)
	}
	want := "/home/tester/.config/opencode/prompts/sdd/sdd-orchestrator.md"
	if !strings.Contains(text, want) {
		t.Fatalf("generated file missing substituted home path %q:\n%s", want, text)
	}
}

// Triangulation: a different home value AND multiple placeholders must all be
// substituted, forcing real replace-all logic rather than a hardcoded string.
func TestGenerateSubstitutesEveryPlaceholderWithGivenHome(t *testing.T) {
	home := "/Users/other"
	repo := fakeSource(t, "a {{HOME}}/x b {{HOME}}/y c {{HOME}}/z")
	opencodeDir := filepath.Join(t.TempDir(), ".config", "opencode")

	if _, err := Generate(repo, opencodeDir, home); err != nil {
		t.Fatalf("Generate error: %v", err)
	}

	data, err := os.ReadFile(filepath.Join(opencodeDir, "opencode.json"))
	if err != nil {
		t.Fatalf("read generated file: %v", err)
	}
	got := string(data)
	want := "a /Users/other/x b /Users/other/y c /Users/other/z"
	if got != want {
		t.Fatalf("substitution = %q, want %q", got, want)
	}
}

func TestGenerateWritesFileMode0644AndCreatesDir(t *testing.T) {
	repo := fakeSource(t, `{"share":"disabled"}`)
	// opencodeDir does not exist yet -> Generate must MkdirAll it.
	opencodeDir := filepath.Join(t.TempDir(), "nested", "config", "opencode")

	if _, err := Generate(repo, opencodeDir, "/home/x"); err != nil {
		t.Fatalf("Generate error: %v", err)
	}

	info, err := os.Stat(filepath.Join(opencodeDir, "opencode.json"))
	if err != nil {
		t.Fatalf("stat generated file: %v", err)
	}
	if perm := info.Mode().Perm(); perm != 0o644 {
		t.Fatalf("file mode = %o, want 0644", perm)
	}
}

func TestGenerateSourceMissingIsError(t *testing.T) {
	repo := t.TempDir() // no agent-clis/opencode/opencode.json
	opencodeDir := filepath.Join(t.TempDir(), ".config", "opencode")

	out, err := Generate(repo, opencodeDir, "/home/x")
	if err == nil {
		t.Fatalf("expected error when source is missing")
	}
	if out.Action == ActionGenerated {
		t.Fatalf("missing source must not report ActionGenerated")
	}
}

func TestGenerateThenRemove(t *testing.T) {
	repo := fakeSource(t, `{"share":"disabled"}`)
	opencodeDir := filepath.Join(t.TempDir(), ".config", "opencode")

	if _, err := Generate(repo, opencodeDir, "/home/x"); err != nil {
		t.Fatalf("Generate error: %v", err)
	}

	out, err := Remove(opencodeDir)
	if err != nil {
		t.Fatalf("Remove error: %v", err)
	}
	if out.Action != ActionRemoved {
		t.Fatalf("Remove action = %q, want %q", out.Action, ActionRemoved)
	}
	if _, err := os.Stat(filepath.Join(opencodeDir, "opencode.json")); !os.IsNotExist(err) {
		t.Fatalf("expected opencode.json removed, stat err = %v", err)
	}
}

func TestRemoveWhenAbsentReportsAbsent(t *testing.T) {
	opencodeDir := filepath.Join(t.TempDir(), ".config", "opencode")

	out, err := Remove(opencodeDir)
	if err != nil {
		t.Fatalf("Remove error: %v", err)
	}
	if out.Action != ActionAbsent {
		t.Fatalf("Remove action = %q, want %q", out.Action, ActionAbsent)
	}
}
