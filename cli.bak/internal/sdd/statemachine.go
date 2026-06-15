package sdd

// stateMachine is the computed phase state for a concrete change.
type stateMachine struct {
	applyState   ApplyState
	dependencies Dependencies
	next         string
	reasons      []string
}

// computeStateMachine derives the apply state, per-phase dependencies, the next
// recommended action, and the blocked reasons from the artifact states, task
// progress, and whether the verify report is clearly passing.
func computeStateMachine(artifacts map[string]ArtifactState, tasks TaskProgress, verifyPassing bool) stateMachine {
	coreReady := isCoreReady(artifacts, tasks)
	applyState := resolveApplyState(coreReady, tasks)

	reasons := coreBlockedReasons(artifacts, tasks)
	if artifacts["verifyReport"] == ArtifactDone && !verifyPassing && applyState != ApplyReady {
		reasons = append(reasons, "verify-report.md is not clearly passing.")
	}

	dependencies := resolveDependencies(artifacts, tasks, applyState, coreReady, verifyPassing)
	next := resolveNextRecommended(dependencies, applyState)

	return stateMachine{
		applyState:   applyState,
		dependencies: dependencies,
		next:         next,
		reasons:      reasons,
	}
}

// isCoreReady reports whether the four core artifacts are done and tasks.md has
// at least one checkbox — the precondition for the apply phase.
func isCoreReady(artifacts map[string]ArtifactState, tasks TaskProgress) bool {
	return artifacts["proposal"] == ArtifactDone &&
		artifacts["specs"] == ArtifactDone &&
		artifacts["design"] == ArtifactDone &&
		artifacts["tasks"] == ArtifactDone &&
		tasks.Total > 0
}

// resolveApplyState classifies the apply phase: blocked until the core is
// ready, all_done when every task is checked, otherwise ready.
func resolveApplyState(coreReady bool, tasks TaskProgress) ApplyState {
	if !coreReady {
		return ApplyBlocked
	}
	if tasks.AllComplete {
		return ApplyAllDone
	}
	return ApplyReady
}

// resolveDependencies maps every phase to its readiness. The four core
// artifacts map done->all_done else blocked. Apply mirrors applyState. Verify
// and archive follow the cross-phase gating rules.
func resolveDependencies(artifacts map[string]ArtifactState, tasks TaskProgress, applyState ApplyState, coreReady, verifyPassing bool) Dependencies {
	deps := Dependencies{
		Proposal: artifactDependency(artifacts["proposal"]),
		Specs:    artifactDependency(artifacts["specs"]),
		Design:   artifactDependency(artifacts["design"]),
		Tasks:    artifactDependency(artifacts["tasks"]),
		Apply:    applyDependency(applyState),
		Verify:   DependencyBlocked,
		Archive:  DependencyBlocked,
	}

	applyProgressDone := artifacts["applyProgress"] == ArtifactDone
	verifyReportDone := artifacts["verifyReport"] == ArtifactDone

	if verifyReportDone && coreReady && tasks.AllComplete && verifyPassing {
		deps.Verify = DependencyAllDone
	} else if coreReady && (applyState == ApplyAllDone || applyProgressDone) {
		deps.Verify = DependencyReady
	}

	if deps.Verify == DependencyAllDone && tasks.AllComplete {
		deps.Archive = DependencyReady
	}
	return deps
}

// artifactDependency maps a core artifact state to its phase dependency.
func artifactDependency(state ArtifactState) DependencyState {
	if state == ArtifactDone {
		return DependencyAllDone
	}
	return DependencyBlocked
}

// applyDependency mirrors the internal apply state onto its phase dependency.
func applyDependency(applyState ApplyState) DependencyState {
	switch applyState {
	case ApplyReady:
		return DependencyReady
	case ApplyAllDone:
		return DependencyAllDone
	default:
		return DependencyBlocked
	}
}

// resolveNextRecommended chooses the single next action: apply when ready, else
// verify when ready, else archive when verify is done and apply is done, else
// resolve-blockers.
func resolveNextRecommended(deps Dependencies, applyState ApplyState) string {
	switch {
	case deps.Apply == DependencyReady:
		return phaseApply
	case deps.Verify == DependencyReady:
		return phaseVerify
	case deps.Verify == DependencyAllDone && applyState == ApplyAllDone:
		return phaseArchive
	default:
		return nextResolveBlockers
	}
}

// coreBlockedReasons lists the human reasons the core is not ready: one per
// missing-or-partial core artifact, plus a note when tasks.md is present but
// has no checkboxes.
func coreBlockedReasons(artifacts map[string]ArtifactState, tasks TaskProgress) []string {
	var reasons []string
	if artifacts["proposal"] != ArtifactDone {
		reasons = append(reasons, "proposal.md is missing or partial.")
	}
	if artifacts["specs"] != ArtifactDone {
		reasons = append(reasons, "specs/**/spec.md is missing or partial.")
	}
	if artifacts["design"] != ArtifactDone {
		reasons = append(reasons, "design.md is missing or partial.")
	}
	if artifacts["tasks"] != ArtifactDone {
		reasons = append(reasons, "tasks.md is missing or partial.")
	}
	if artifacts["tasks"] == ArtifactDone && tasks.Total == 0 {
		reasons = append(reasons, "tasks.md has no markdown task checkboxes.")
	}
	return reasons
}
