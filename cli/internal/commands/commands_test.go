package commands

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeCanonical builds a repoDir holding prompts/commands/<name>.md fixtures
// and returns the repo root.
func writeCanonical(t *testing.T, files map[string]string) string {
	t.Helper()
	repo := t.TempDir()
	dir := filepath.Join(repo, "prompts", "commands")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("mkdir commands: %v", err)
	}
	for name, body := range files {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(body), 0o644); err != nil {
			t.Fatalf("write %s: %v", name, err)
		}
	}
	return repo
}

const sampleStatus = `---
description: Show structured SDD status for an active change
subtask: false
read-only: true
---

You are the ` + "`{{ORCHESTRATOR_AGENT}}`" + `. This command is read-only.

- Working directory: use the returned path as the authoritative workspace.{{CWD_NOTE}}
- Change name: {{ARGS}}

Read the contract: {{SKILLS_DIR}}/_shared/sdd-status-contract.md
`

const sampleInit = `---
description: Initialize SDD context
subtask: true
read-only: false
---

You are the ` + "`{{ORCHESTRATOR_AGENT}}`" + `.

- Working directory: authoritative workspace.{{CWD_NOTE}}
`

func TestGenerateSubstitutesPlaceholdersInBody(t *testing.T) {
	repo := writeCanonical(t, map[string]string{"sdd-status.md": sampleStatus})
	out := t.TempDir()

	report, err := Generate(repo, OpenCodeProfile(out))
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if len(report) != 1 {
		t.Fatalf("expected 1 report entry, got %d", len(report))
	}

	got := readFile(t, filepath.Join(out, "sdd-status.md"))

	if strings.Contains(got, "{{ORCHESTRATOR_AGENT}}") || strings.Contains(got, "{{ARGS}}") ||
		strings.Contains(got, "{{CWD_NOTE}}") || strings.Contains(got, "{{SKILLS_DIR}}") {
		t.Fatalf("rendered output still contains a placeholder:\n%s", got)
	}
	if !strings.Contains(got, "You are the `gentle-orchestrator`.") {
		t.Fatalf("ORCHESTRATOR_AGENT not substituted:\n%s", got)
	}
	if !strings.Contains(got, "Change name: $ARGUMENTS") {
		t.Fatalf("ARGS not substituted to $ARGUMENTS:\n%s", got)
	}
	if !strings.Contains(got, "~/.config/opencode/skills/_shared/sdd-status-contract.md") {
		t.Fatalf("SKILLS_DIR not substituted:\n%s", got)
	}
	if !strings.Contains(got, "In OpenCode Desktop") {
		t.Fatalf("CWD_NOTE not substituted:\n%s", got)
	}
}

func TestGenerateEmitsOpenCodeFrontmatter(t *testing.T) {
	repo := writeCanonical(t, map[string]string{
		"sdd-status.md": sampleStatus,
		"sdd-init.md":   sampleInit,
	})
	out := t.TempDir()

	if _, err := Generate(repo, OpenCodeProfile(out)); err != nil {
		t.Fatalf("Generate: %v", err)
	}

	// sdd-status: read-only neutral, NOT a subtask -> opencode frontmatter has
	// description + agent, no subtask, no read-only.
	status := readFile(t, filepath.Join(out, "sdd-status.md"))
	if !strings.Contains(status, "description: Show structured SDD status for an active change") {
		t.Fatalf("description not carried over:\n%s", status)
	}
	if !strings.Contains(status, "agent: gentle-orchestrator") {
		t.Fatalf("agent not emitted:\n%s", status)
	}
	statusFM := frontmatterOf(t, status)
	if strings.Contains(statusFM, "subtask:") {
		t.Fatalf("non-subtask command must not emit subtask in frontmatter:\n%s", statusFM)
	}
	if strings.Contains(statusFM, "read-only") {
		t.Fatalf("opencode frontmatter must not emit read-only:\n%s", statusFM)
	}

	// sdd-init: subtask true -> must emit `subtask: true`.
	initOut := readFile(t, filepath.Join(out, "sdd-init.md"))
	if !strings.Contains(initOut, "subtask: true") {
		t.Fatalf("subtask command must emit subtask: true:\n%s", initOut)
	}
	if !strings.Contains(initOut, "description: Initialize SDD context") {
		t.Fatalf("init description not carried over:\n%s", initOut)
	}
}

func TestGenerateEmptyCwdNoteRendersCleanly(t *testing.T) {
	repo := writeCanonical(t, map[string]string{"sdd-init.md": sampleInit})
	out := t.TempDir()

	p := OpenCodeProfile(out)
	p.CwdNote = "" // simulate a platform with no cwd caveat
	if _, err := Generate(repo, p); err != nil {
		t.Fatalf("Generate: %v", err)
	}

	got := readFile(t, filepath.Join(out, "sdd-init.md"))
	if strings.Contains(got, "{{CWD_NOTE}}") {
		t.Fatalf("placeholder survived:\n%s", got)
	}
	// No dangling trailing space after "workspace." when the note is empty.
	if !strings.Contains(got, "authoritative workspace.\n") {
		t.Fatalf("empty CwdNote should leave a clean line ending:\n%q", got)
	}
	if strings.Contains(got, "workspace. \n") {
		t.Fatalf("empty CwdNote left a dangling space:\n%q", got)
	}
}

func TestGenerateReportListsEachFile(t *testing.T) {
	repo := writeCanonical(t, map[string]string{
		"sdd-status.md": sampleStatus,
		"sdd-init.md":   sampleInit,
	})
	out := t.TempDir()

	report, err := Generate(repo, OpenCodeProfile(out))
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	if len(report) != 2 {
		t.Fatalf("expected 2 report entries, got %d: %+v", len(report), report)
	}
	dests := map[string]bool{}
	for _, o := range report {
		dests[o.Dest] = true
		if o.Action != ActionGenerated {
			t.Fatalf("expected ActionGenerated, got %q for %s", o.Action, o.Dest)
		}
	}
	if !dests[filepath.Join(out, "sdd-status.md")] || !dests[filepath.Join(out, "sdd-init.md")] {
		t.Fatalf("report missing expected dests: %+v", dests)
	}
}

func TestRemoveDeletesGeneratedCommandFiles(t *testing.T) {
	repo := writeCanonical(t, map[string]string{
		"sdd-status.md": sampleStatus,
		"sdd-init.md":   sampleInit,
	})
	out := t.TempDir()

	if _, err := Generate(repo, OpenCodeProfile(out)); err != nil {
		t.Fatalf("Generate: %v", err)
	}

	report, err := Remove(repo, OpenCodeProfile(out))
	if err != nil {
		t.Fatalf("Remove: %v", err)
	}
	if len(report) != 2 {
		t.Fatalf("expected 2 removal entries, got %d", len(report))
	}
	for _, o := range report {
		if o.Action != ActionRemoved {
			t.Fatalf("expected ActionRemoved, got %q for %s", o.Action, o.Dest)
		}
		if _, statErr := os.Stat(o.Dest); !os.IsNotExist(statErr) {
			t.Fatalf("expected %s removed, stat err = %v", o.Dest, statErr)
		}
	}
}

func TestRemoveReportsAbsentForMissingFiles(t *testing.T) {
	// Canonical source lists two commands, but none were ever generated.
	repo := writeCanonical(t, map[string]string{
		"sdd-status.md": sampleStatus,
		"sdd-init.md":   sampleInit,
	})
	out := t.TempDir() // empty command dir

	report, err := Remove(repo, OpenCodeProfile(out))
	if err != nil {
		t.Fatalf("Remove must not error on absent files: %v", err)
	}
	if len(report) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(report))
	}
	for _, o := range report {
		if o.Action != ActionAbsent {
			t.Fatalf("expected ActionAbsent for never-generated file, got %q", o.Action)
		}
	}
}

func TestGenerateMissingSourceDirErrors(t *testing.T) {
	repo := t.TempDir() // no prompts/commands/
	out := t.TempDir()

	_, err := Generate(repo, OpenCodeProfile(out))
	if err == nil {
		t.Fatalf("expected an error when prompts/commands/ is absent")
	}
}

// frontmatterOf returns just the leading "---"-fenced block of a rendered file,
// so frontmatter-only assertions are not fooled by body text.
func frontmatterOf(t *testing.T, content string) string {
	t.Helper()
	const fence = "---\n"
	if !strings.HasPrefix(content, fence) {
		t.Fatalf("rendered file has no leading frontmatter fence:\n%s", content)
	}
	rest := content[len(fence):]
	end := strings.Index(rest, "\n---\n")
	if end < 0 {
		t.Fatalf("rendered file has no closing frontmatter fence:\n%s", content)
	}
	return rest[:end]
}

func readFile(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(b)
}
