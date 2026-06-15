package sdd

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestResolveChangeSelection(t *testing.T) {
	tests := []struct {
		name          string
		seed          func(t *testing.T, root string)
		changeName    string
		wantChange    *string
		wantNext      string
		wantBlockedRx string
	}{
		{
			name:          "no active change blocks with sdd-new",
			seed:          func(t *testing.T, root string) { mkdir(t, filepath.Join(root, "openspec", "changes")) },
			wantNext:      "sdd-new",
			wantBlockedRx: "No active OpenSpec changes",
		},
		{
			name: "ambiguous active changes block with select-change",
			seed: func(t *testing.T, root string) {
				mkdir(t, filepath.Join(root, "openspec", "changes", "first"))
				mkdir(t, filepath.Join(root, "openspec", "changes", "second"))
			},
			wantNext:      "select-change",
			wantBlockedRx: "ambiguous: first, second",
		},
		{
			name: "explicit missing change blocks with sdd-new",
			seed: func(t *testing.T, root string) {
				mkdir(t, filepath.Join(root, "openspec", "changes", "real"))
			},
			changeName:    "missing",
			wantChange:    strPtr("missing"),
			wantNext:      "sdd-new",
			wantBlockedRx: "not found: missing",
		},
		{
			name: "single active change is inferred and ready to apply",
			seed: func(t *testing.T, root string) {
				seedReadyChange(t, root, "add-auth", "- [ ] 1.1 Wire routes\n")
			},
			wantChange: strPtr("add-auth"),
			wantNext:   "apply",
		},
		{
			name: "archive directory is excluded from active changes",
			seed: func(t *testing.T, root string) {
				mkdir(t, filepath.Join(root, "openspec", "changes", "archive", "2026-01-01-old"))
				seedReadyChange(t, root, "only", "- [ ] 1.1 Work\n")
			},
			wantChange: strPtr("only"),
			wantNext:   "apply",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			tt.seed(t, root)

			status, err := Resolve(root, "", tt.changeName, false)
			if err != nil {
				t.Fatalf("Resolve() error = %v", err)
			}

			if !equalStringPtr(status.ChangeName, tt.wantChange) {
				t.Fatalf("ChangeName = %v, want %v", ptrValue(status.ChangeName), ptrValue(tt.wantChange))
			}
			if status.NextRecommended != tt.wantNext {
				t.Fatalf("NextRecommended = %q, want %q", status.NextRecommended, tt.wantNext)
			}
			if tt.wantBlockedRx != "" && !strings.Contains(strings.Join(status.BlockedReasons, "\n"), tt.wantBlockedRx) {
				t.Fatalf("BlockedReasons = %v, want containing %q", status.BlockedReasons, tt.wantBlockedRx)
			}
		})
	}
}

func TestResolveWorkspaceRootOverridesCWD(t *testing.T) {
	cwd := t.TempDir()
	workspace := t.TempDir()
	seedReadyChange(t, workspace, "add-auth", "- [ ] 1.1 Work\n")

	status, err := Resolve(cwd, workspace, "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if status.ChangeName == nil || *status.ChangeName != "add-auth" {
		t.Fatalf("ChangeName = %v, want add-auth (workspaceRoot should win over cwd)", ptrValue(status.ChangeName))
	}
}

func TestResolveRejectsNonexistentRoot(t *testing.T) {
	root := filepath.Join(t.TempDir(), "missing")
	if _, err := Resolve(root, "", "", false); err == nil {
		t.Fatal("Resolve() expected error for nonexistent root")
	}
}

func TestResolveExistingRootWithoutOpenSpecBlocks(t *testing.T) {
	root := t.TempDir()

	status, err := Resolve(root, "", "", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if status.NextRecommended != "sdd-new" {
		t.Fatalf("NextRecommended = %q, want sdd-new", status.NextRecommended)
	}
	if !strings.Contains(strings.Join(status.BlockedReasons, "\n"), "No active OpenSpec changes") {
		t.Fatalf("BlockedReasons = %v, want no active change block", status.BlockedReasons)
	}
}

// --- helpers ---

func seedReadyChange(t *testing.T, root string, name string, tasks string) string {
	t.Helper()
	changeRoot := filepath.Join(root, "openspec", "changes", name)
	write(t, filepath.Join(changeRoot, "proposal.md"), "# Proposal\n")
	write(t, filepath.Join(changeRoot, "specs", "auth", "spec.md"), "# Auth Spec\n")
	write(t, filepath.Join(changeRoot, "design.md"), "# Design\n")
	write(t, filepath.Join(changeRoot, "tasks.md"), tasks)
	return changeRoot
}

func write(t *testing.T, path string, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("MkdirAll() error = %v", err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("WriteFile() error = %v", err)
	}
}

func mkdir(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(path, 0o755); err != nil {
		t.Fatalf("MkdirAll() error = %v", err)
	}
}

func assertArtifact(t *testing.T, status Status, key string, want ArtifactState) {
	t.Helper()
	if status.Artifacts[key] != want {
		t.Fatalf("Artifacts[%q] = %q, want %q", key, status.Artifacts[key], want)
	}
}

func decodeJSON(t *testing.T, status Status) map[string]json.RawMessage {
	t.Helper()
	payload, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("Marshal() error = %v", err)
	}
	var decoded map[string]json.RawMessage
	if err := json.Unmarshal(payload, &decoded); err != nil {
		t.Fatalf("Unmarshal() error = %v", err)
	}
	return decoded
}

func strPtr(value string) *string { return &value }

func equalStringPtr(left *string, right *string) bool {
	if left == nil || right == nil {
		return left == right
	}
	return *left == *right
}

func ptrValue(value *string) string {
	if value == nil {
		return "<nil>"
	}
	return *value
}
