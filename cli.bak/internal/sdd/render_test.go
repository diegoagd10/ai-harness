package sdd

import (
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"
)

func TestResolveBlockedStatusSerializesPathFieldsAsEmptyArrays(t *testing.T) {
	root := t.TempDir()
	mkdir(t, filepath.Join(root, "openspec", "changes"))

	status, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	decoded := decodeJSON(t, status)

	for _, section := range []string{"artifactPaths", "contextFiles"} {
		var paths map[string]json.RawMessage
		if err := json.Unmarshal(decoded[section], &paths); err != nil {
			t.Fatalf("Unmarshal(%s) error = %v", section, err)
		}
		for _, field := range []string{"proposal", "specs", "design", "tasks", "applyProgress", "verifyReport"} {
			if got := string(paths[field]); got != "[]" {
				t.Fatalf("%s.%s JSON = %s, want []", section, field, got)
			}
		}
	}
}

func TestResolveSerializesBlockedReasonsAndRelationshipsAsEmptyArrays(t *testing.T) {
	root := t.TempDir()
	seedReadyChange(t, root, "add-auth", "- [ ] 1.1 Work\n")

	status, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	decoded := decodeJSON(t, status)

	if got := string(decoded["blockedReasons"]); got != "[]" {
		t.Fatalf("blockedReasons JSON = %s, want []", got)
	}

	var rel map[string]json.RawMessage
	if err := json.Unmarshal(decoded["relationships"], &rel); err != nil {
		t.Fatalf("Unmarshal(relationships) error = %v", err)
	}
	for _, field := range []string{"dependsOn", "supersedes", "amends", "conflictsWith", "sameDomainActiveChanges"} {
		if got := string(rel[field]); got != "[]" {
			t.Fatalf("relationships.%s JSON = %s, want []", field, got)
		}
	}
}

func TestResolveSchemaAndActionContext(t *testing.T) {
	root := t.TempDir()
	seedReadyChange(t, root, "add-auth", "- [ ] 1.1 Work\n")

	status, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}

	if status.SchemaName != "ai-harness.sdd-status" || status.SchemaVersion != 1 {
		t.Fatalf("schema = %s@%d, want ai-harness.sdd-status@1", status.SchemaName, status.SchemaVersion)
	}
	if status.ArtifactStore != "openspec" {
		t.Fatalf("ArtifactStore = %q, want openspec", status.ArtifactStore)
	}
	if status.ActionContext.Mode != "repo-local" {
		t.Fatalf("ActionContext.Mode = %q, want repo-local", status.ActionContext.Mode)
	}
	wantRoot, _ := filepath.Abs(root)
	if status.ActionContext.WorkspaceRoot != wantRoot {
		t.Fatalf("WorkspaceRoot = %q, want %q", status.ActionContext.WorkspaceRoot, wantRoot)
	}
	if len(status.ActionContext.AllowedEditRoots) != 1 || status.ActionContext.AllowedEditRoots[0] != wantRoot {
		t.Fatalf("AllowedEditRoots = %v, want [%q]", status.ActionContext.AllowedEditRoots, wantRoot)
	}
}

func TestResolveAttachesInstructionsOnlyWhenRequested(t *testing.T) {
	root := t.TempDir()
	seedReadyChange(t, root, "add-auth", "- [x] 1.1 Work\n")

	without, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if without.PhaseInstructions != nil {
		t.Fatal("PhaseInstructions should be nil when not requested")
	}

	with, err := Resolve(root, "", "", true)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if with.PhaseInstructions == nil {
		t.Fatal("PhaseInstructions should be set when requested")
	}
	if !strings.Contains(strings.Join(with.PhaseInstructions.Archive, "\n"), "verify-report.md exists") {
		t.Fatalf("Archive instructions = %v", with.PhaseInstructions.Archive)
	}
}

func TestRenderMarkdownIncludesFencedJSON(t *testing.T) {
	root := t.TempDir()
	seedReadyChange(t, root, "add-auth", "- [ ] 1.1 Work\n")

	status, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	markdown := RenderMarkdown(status)

	for _, want := range []string{
		"## SDD Status: add-auth",
		"next: apply",
		"- tasks: 0/1 complete",
		"```json",
		`"schemaName": "ai-harness.sdd-status"`,
		"```",
	} {
		if !strings.Contains(markdown, want) {
			t.Fatalf("RenderMarkdown() missing %q:\n%s", want, markdown)
		}
	}
}

func TestRenderDispatcherMarkdownIncludesRoutingContext(t *testing.T) {
	root := t.TempDir()
	seedReadyChange(t, root, "add-auth", "- [ ] 1.1 Work\n")

	status, err := Resolve(root, "", "", true)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	markdown := RenderDispatcherMarkdown(status)

	for _, want := range []string{
		"## Native SDD Dispatcher: add-auth",
		"next_recommended: apply",
		"### Dependency States",
		"### Next Phase Instructions: apply",
		"Read proposal, specs, design, and tasks before editing.",
		"```json",
		`"schemaName": "ai-harness.sdd-status"`,
		"```",
	} {
		if !strings.Contains(markdown, want) {
			t.Fatalf("RenderDispatcherMarkdown() missing %q:\n%s", want, markdown)
		}
	}
}

func TestRenderDispatcherMarkdownIncludesBlockedReasons(t *testing.T) {
	root := t.TempDir()
	write(t, filepath.Join(root, "openspec", "changes", "thin", "tasks.md"), "- [ ] 1.1 Work\n")

	status, err := Resolve(root, "", "thin", true)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	markdown := RenderDispatcherMarkdown(status)

	for _, want := range []string{
		"next_recommended: resolve-blockers",
		"### Blocked Reasons",
		"proposal.md is missing or partial.",
		`"nextRecommended": "resolve-blockers"`,
	} {
		if !strings.Contains(markdown, want) {
			t.Fatalf("RenderDispatcherMarkdown() missing %q:\n%s", want, markdown)
		}
	}
	// resolve-blockers is not a concrete phase: no phase-instructions section.
	if strings.Contains(markdown, "### Next Phase Instructions") {
		t.Fatalf("dispatcher markdown should omit phase instructions for resolve-blockers:\n%s", markdown)
	}
}

func TestRenderMarkdownUnresolvedChangeName(t *testing.T) {
	root := t.TempDir()
	mkdir(t, filepath.Join(root, "openspec", "changes"))

	status, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	markdown := RenderMarkdown(status)
	if !strings.Contains(markdown, "## SDD Status: unresolved") {
		t.Fatalf("RenderMarkdown() missing unresolved header:\n%s", markdown)
	}
}
