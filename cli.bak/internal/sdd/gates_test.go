package sdd

import (
	"path/filepath"
	"strings"
	"testing"
)

func TestResolveArtifactStatesAndTaskProgress(t *testing.T) {
	root := t.TempDir()
	changeRoot := seedReadyChange(t, root, "add-auth", strings.Join([]string{
		"# Tasks",
		"",
		"- [x] 1.1 Build foundation",
		"- [X] 1.2 Add API",
		"- [ ] 1.3 Wire routes",
		"plain [ ] note is ignored",
		"",
	}, "\n"))
	write(t, filepath.Join(changeRoot, "apply-progress.md"), "# Apply\n")

	status, err := Resolve(root, "", "add-auth", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}

	assertArtifact(t, status, "proposal", ArtifactDone)
	assertArtifact(t, status, "specs", ArtifactDone)
	assertArtifact(t, status, "design", ArtifactDone)
	assertArtifact(t, status, "tasks", ArtifactDone)
	assertArtifact(t, status, "applyProgress", ArtifactDone)
	assertArtifact(t, status, "verifyReport", ArtifactMissing)

	want := TaskProgress{Total: 3, Completed: 2, Pending: 1, AllComplete: false}
	if status.TaskProgress != want {
		t.Fatalf("TaskProgress = %#v, want %#v", status.TaskProgress, want)
	}
	if status.Dependencies.Verify != DependencyReady {
		t.Fatalf("Verify dependency = %q, want %q (apply-progress present)", status.Dependencies.Verify, DependencyReady)
	}
}

func TestResolveArtifactPartialAndMissingStates(t *testing.T) {
	root := t.TempDir()
	changeRoot := filepath.Join(root, "openspec", "changes", "thin")
	// proposal exists but is blank -> partial.
	write(t, filepath.Join(changeRoot, "proposal.md"), "   \n")
	// design missing entirely.
	write(t, filepath.Join(changeRoot, "tasks.md"), "- [ ] 1.1 Work\n")
	// specs dir exists with a non-spec file but no spec.md -> partial.
	write(t, filepath.Join(changeRoot, "specs", "auth", "notes.md"), "notes\n")

	status, err := Resolve(root, "", "thin", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}

	assertArtifact(t, status, "proposal", ArtifactPartial)
	assertArtifact(t, status, "design", ArtifactMissing)
	assertArtifact(t, status, "specs", ArtifactPartial)
	assertArtifact(t, status, "tasks", ArtifactDone)
	if status.ApplyState != ApplyBlocked {
		t.Fatalf("ApplyState = %q, want %q", status.ApplyState, ApplyBlocked)
	}
}

func TestResolveBlankSpecFileIsPartial(t *testing.T) {
	root := t.TempDir()
	changeRoot := seedReadyChange(t, root, "thin", "- [ ] 1.1 Work\n")
	// overwrite the seeded spec with a blank one.
	write(t, filepath.Join(changeRoot, "specs", "auth", "spec.md"), "  \n")

	status, err := Resolve(root, "", "thin", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	assertArtifact(t, status, "specs", ArtifactPartial)
}

func TestResolveTasksDoneButNoCheckboxesBlocks(t *testing.T) {
	root := t.TempDir()
	seedReadyChange(t, root, "thin", "# Tasks\n\nProse only, no checkboxes.\n")

	status, err := Resolve(root, "", "thin", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if status.TaskProgress.Total != 0 {
		t.Fatalf("Total = %d, want 0", status.TaskProgress.Total)
	}
	if !strings.Contains(strings.Join(status.BlockedReasons, "\n"), "tasks.md has no markdown task checkboxes.") {
		t.Fatalf("BlockedReasons = %v, want checkbox note", status.BlockedReasons)
	}
	if status.ApplyState != ApplyBlocked {
		t.Fatalf("ApplyState = %q, want blocked", status.ApplyState)
	}
}

func TestResolveApplyVerifyArchiveGates(t *testing.T) {
	tests := []struct {
		name              string
		seed              func(t *testing.T, root string)
		wantApply         ApplyState
		wantApplyD        DependencyState
		wantVerify        DependencyState
		wantArchive       DependencyState
		wantNext          string
		wantBlocked       string
		wantBlockedAbsent string
	}{
		{
			name: "apply blocked when core artifacts are missing",
			seed: func(t *testing.T, root string) {
				write(t, filepath.Join(root, "openspec", "changes", "thin", "tasks.md"), "- [ ] 1.1 Work\n")
			},
			wantApply:   ApplyBlocked,
			wantApplyD:  DependencyBlocked,
			wantVerify:  DependencyBlocked,
			wantArchive: DependencyBlocked,
			wantNext:    "resolve-blockers",
			wantBlocked: "proposal.md is missing or partial.",
		},
		{
			name: "apply ready when core done and tasks pending",
			seed: func(t *testing.T, root string) {
				seedReadyChange(t, root, "thin", "- [ ] 1.1 Work\n")
			},
			wantApply:   ApplyReady,
			wantApplyD:  DependencyReady,
			wantVerify:  DependencyBlocked,
			wantArchive: DependencyBlocked,
			wantNext:    "apply",
		},
		{
			name: "apply all done makes verify ready",
			seed: func(t *testing.T, root string) {
				seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
		},
		{
			name: "apply progress makes verify ready before tasks complete",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Done\n- [ ] 1.2 Remaining\n")
				write(t, filepath.Join(changeRoot, "apply-progress.md"), "# Apply\n")
			},
			wantApply:   ApplyReady,
			wantApplyD:  DependencyReady,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "apply",
		},
		{
			name: "apply ready ignores stale bad verify report blockers while tasks pending",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Done\n- [ ] 1.2 Remaining\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nVerdict: PASS\nfailed: 1\n")
			},
			wantApply:         ApplyReady,
			wantApplyD:        DependencyReady,
			wantVerify:        DependencyBlocked,
			wantArchive:       DependencyBlocked,
			wantNext:          "apply",
			wantBlockedAbsent: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive ready when verify report exists and tasks complete",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nPASS\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyAllDone,
			wantArchive: DependencyReady,
			wantNext:    "archive",
		},
		{
			name: "archive ready for canonical passing verify report",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), strings.Join([]string{
					"## Verification Report",
					"### Build & Tests Execution",
					"**Tests**: ✅ 12 passed / ❌ 0 failed / ⚠️ 0 skipped",
					"failed: 0",
					"### Issues Found",
					"**CRITICAL**: None",
					"No blockers",
					"### Verdict",
					"Verdict: PASS",
					"",
				}, "\n"))
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyAllDone,
			wantArchive: DependencyReady,
			wantNext:    "archive",
		},
		{
			name: "archive ready for canonical pass with warnings verdict",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), strings.Join([]string{
					"## Verification Report",
					"**Tests**: ✅ 12 passed / ❌ 0 failed / ⚠️ 1 skipped",
					"**CRITICAL**: None",
					"**WARNING**: flaky integration was skipped",
					"### Verdict",
					"PASS WITH WARNINGS",
					"",
				}, "\n"))
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyAllDone,
			wantArchive: DependencyReady,
			wantNext:    "archive",
		},
		{
			name: "archive blocked when verify report has critical findings",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\ncritical: archive blocker\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when verify report has nonzero failed count",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nVerdict: PASS\nfailed: 1\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when canonical matrix has untested result despite pass verdict",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), strings.Join([]string{
					"## Verification Report",
					"### Spec Compliance Matrix",
					"| Requirement | Scenario | Test | Result |",
					"|-------------|----------|------|--------|",
					"| REQ-01 | Covers auth | (none found) | ❌ UNTESTED |",
					"### Verdict",
					"Verdict: PASS",
					"",
				}, "\n"))
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when canonical matrix has failing result despite pass verdict",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), strings.Join([]string{
					"## Verification Report",
					"### Spec Compliance Matrix",
					"| Requirement | Scenario | Test | Result |",
					"|-------------|----------|------|--------|",
					"| REQ-01 | Covers auth | `auth_test.go > TestAuth` | ❌ FAILING |",
					"### Verdict",
					"Verdict: PASS",
					"",
				}, "\n"))
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when verify report has blockers present",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nVerdict: PASS\nBlockers: missing evidence\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when verify report has todo pending and blockers",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nPASS\nTODO: finish audit\nPENDING: test run\nVerification blocker: missing evidence\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when verify report says status not passed",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nStatus: not passed\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when verify report says pass no",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nPASS: no\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive blocked when verify report has success and failure",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nStatus: SUCCESS\nFailure: build broke\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyReady,
			wantArchive: DependencyBlocked,
			wantNext:    "verify",
			wantBlocked: "verify-report.md is not clearly passing.",
		},
		{
			name: "archive ready when verify report has status pass",
			seed: func(t *testing.T, root string) {
				changeRoot := seedReadyChange(t, root, "thin", "- [x] 1.1 Work\n")
				write(t, filepath.Join(changeRoot, "verify-report.md"), "# Verify\nStatus: PASS\n")
			},
			wantApply:   ApplyAllDone,
			wantApplyD:  DependencyAllDone,
			wantVerify:  DependencyAllDone,
			wantArchive: DependencyReady,
			wantNext:    "archive",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			root := t.TempDir()
			tt.seed(t, root)

			status, err := Resolve(root, "", "thin", false)
			if err != nil {
				t.Fatalf("Resolve() error = %v", err)
			}

			if status.ApplyState != tt.wantApply {
				t.Fatalf("ApplyState = %q, want %q", status.ApplyState, tt.wantApply)
			}
			if status.Dependencies.Apply != tt.wantApplyD {
				t.Fatalf("Dependencies.Apply = %q, want %q", status.Dependencies.Apply, tt.wantApplyD)
			}
			if status.Dependencies.Verify != tt.wantVerify {
				t.Fatalf("Dependencies.Verify = %q, want %q", status.Dependencies.Verify, tt.wantVerify)
			}
			if status.Dependencies.Archive != tt.wantArchive {
				t.Fatalf("Dependencies.Archive = %q, want %q", status.Dependencies.Archive, tt.wantArchive)
			}
			if status.NextRecommended != tt.wantNext {
				t.Fatalf("NextRecommended = %q, want %q", status.NextRecommended, tt.wantNext)
			}
			if tt.wantBlocked != "" && !strings.Contains(strings.Join(status.BlockedReasons, "\n"), tt.wantBlocked) {
				t.Fatalf("BlockedReasons = %v, want containing %q", status.BlockedReasons, tt.wantBlocked)
			}
			if tt.wantBlockedAbsent != "" && strings.Contains(strings.Join(status.BlockedReasons, "\n"), tt.wantBlockedAbsent) {
				t.Fatalf("BlockedReasons = %v, want NOT containing %q", status.BlockedReasons, tt.wantBlockedAbsent)
			}
		})
	}
}

func TestResolveNextRecommendedUsesStableTokenNotProse(t *testing.T) {
	root := t.TempDir()
	write(t, filepath.Join(root, "openspec", "changes", "thin", "tasks.md"), "- [ ] 1.1 Work\n")

	status, err := Resolve(root, "", "thin", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}

	blockedProse := "proposal.md is missing or partial."
	if status.NextRecommended != "resolve-blockers" {
		t.Fatalf("NextRecommended = %q, want resolve-blockers", status.NextRecommended)
	}
	if strings.Contains(status.NextRecommended, blockedProse) {
		t.Fatalf("NextRecommended = %q must not contain blocked prose", status.NextRecommended)
	}
	if !strings.Contains(strings.Join(status.BlockedReasons, "\n"), blockedProse) {
		t.Fatalf("BlockedReasons = %v, want containing %q", status.BlockedReasons, blockedProse)
	}
}
