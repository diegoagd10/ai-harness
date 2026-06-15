package sdd

import "path/filepath"

// emptyArtifactPaths returns an ArtifactPaths whose every field is a non-nil
// empty slice, guaranteeing the JSON serializes each as [] rather than null.
func emptyArtifactPaths() ArtifactPaths {
	return ArtifactPaths{
		Proposal:      []string{},
		Specs:         []string{},
		Design:        []string{},
		Tasks:         []string{},
		ApplyProgress: []string{},
		VerifyReport:  []string{},
	}
}

// newBlockedStatus builds a Status for a change that could not be resolved into
// a full state machine (no active change, ambiguous selection, or missing
// named change). Everything is at its blocked baseline.
func newBlockedStatus(root string, changeName *string, next string, reasons []string, includeInstructions bool) Status {
	status := newBaseStatus(root, changeName, nil, next, reasons)
	if includeInstructions {
		instructions := buildPhaseInstructions(status)
		status.PhaseInstructions = &instructions
	}
	return status
}

// newBaseStatus constructs a Status with every collection at its empty baseline
// and every phase blocked. resolveChange overwrites the computed fields on top.
func newBaseStatus(root string, changeName, changeRoot *string, next string, reasons []string) Status {
	if reasons == nil {
		reasons = []string{}
	}
	emptyPaths := emptyArtifactPaths()
	return Status{
		SchemaName:    SchemaName,
		SchemaVersion: SchemaVersion,
		ChangeName:    changeName,
		ArtifactStore: artifactStoreOpenSpec,
		PlanningHome: PlanningHome{
			Mode: actionModeRepoLocal,
			Path: filepath.Join(root, "openspec"),
		},
		ChangeRoot:    changeRoot,
		ArtifactPaths: emptyPaths,
		ContextFiles:  emptyPaths,
		Artifacts: map[string]ArtifactState{
			"proposal":      ArtifactMissing,
			"specs":         ArtifactMissing,
			"design":        ArtifactMissing,
			"tasks":         ArtifactMissing,
			"applyProgress": ArtifactMissing,
			"verifyReport":  ArtifactMissing,
		},
		TaskProgress: TaskProgress{},
		Dependencies: Dependencies{
			Proposal: DependencyBlocked,
			Specs:    DependencyBlocked,
			Design:   DependencyBlocked,
			Tasks:    DependencyBlocked,
			Apply:    DependencyBlocked,
			Verify:   DependencyBlocked,
			Archive:  DependencyBlocked,
		},
		ApplyState: ApplyBlocked,
		ActionContext: ActionContext{
			Mode:             actionModeRepoLocal,
			WorkspaceRoot:    root,
			AllowedEditRoots: []string{root},
		},
		Relationships: Relationships{
			DependsOn:               []string{},
			Supersedes:              []string{},
			Amends:                  []string{},
			ConflictsWith:           []string{},
			SameDomainActiveChanges: []string{},
		},
		NextRecommended: next,
		BlockedReasons:  reasons,
	}
}
