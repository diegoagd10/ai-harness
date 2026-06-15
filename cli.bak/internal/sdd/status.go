// Package sdd is a deterministic Spec-Driven Development dispatcher. It reads
// the OpenSpec change artifacts on disk for a single change and computes the
// phase state machine (which SDD phase is ready, blocked, or done).
//
// The package is a deep module: callers depend only on Resolve plus the two
// Render functions. Everything about how artifacts are discovered, how task
// progress is counted, and how the gnarly verify-report heuristic works is
// hidden behind that small surface.
package sdd

import (
	"fmt"
	"path/filepath"
	"strings"
)

// SchemaName and SchemaVersion identify the Status JSON contract.
const (
	SchemaName    = "ai-harness.sdd-status"
	SchemaVersion = 1
)

// archiveDirName is the reserved subdirectory under openspec/changes/ that
// holds archived changes; it is never treated as an active change.
const archiveDirName = "archive"

// ArtifactState is the on-disk completeness of a single artifact.
type ArtifactState string

const (
	ArtifactMissing ArtifactState = "missing"
	ArtifactPartial ArtifactState = "partial"
	ArtifactDone    ArtifactState = "done"
)

// DependencyState is the readiness of a phase in the SDD state machine.
type DependencyState string

const (
	DependencyBlocked DependencyState = "blocked"
	DependencyReady   DependencyState = "ready"
	DependencyAllDone DependencyState = "all_done"
)

// ApplyState is the internal apply-phase classification surfaced on Status.
type ApplyState string

const (
	ApplyBlocked ApplyState = "blocked"
	ApplyReady   ApplyState = "ready"
	ApplyAllDone ApplyState = "all_done"
)

const (
	artifactStoreOpenSpec = "openspec"
	actionModeRepoLocal   = "repo-local"
)

// Next-recommended sentinels that are not concrete phases.
const (
	nextResolveBlockers = "resolve-blockers"
	nextSDDNew          = "sdd-new"
	nextSelectChange    = "select-change"
	phaseApply          = "apply"
	phaseVerify         = "verify"
	phaseArchive        = "archive"
)

// ArtifactPaths holds the discovered absolute paths for each artifact kind.
// Each field is always a (possibly empty) slice so the JSON never emits null.
type ArtifactPaths struct {
	Proposal      []string `json:"proposal"`
	Specs         []string `json:"specs"`
	Design        []string `json:"design"`
	Tasks         []string `json:"tasks"`
	ApplyProgress []string `json:"applyProgress"`
	VerifyReport  []string `json:"verifyReport"`
}

// PlanningHome describes where the planning artifacts live.
type PlanningHome struct {
	Mode string `json:"mode"`
	Path string `json:"path"`
}

// TaskProgress summarizes the checkbox tasks parsed from tasks.md.
type TaskProgress struct {
	Total       int  `json:"total"`
	Completed   int  `json:"completed"`
	Pending     int  `json:"pending"`
	AllComplete bool `json:"allComplete"`
}

// Dependencies is the readiness of every phase in the state machine.
type Dependencies struct {
	Proposal DependencyState `json:"proposal"`
	Specs    DependencyState `json:"specs"`
	Design   DependencyState `json:"design"`
	Tasks    DependencyState `json:"tasks"`
	Apply    DependencyState `json:"apply"`
	Verify   DependencyState `json:"verify"`
	Archive  DependencyState `json:"archive"`
}

// ActionContext records where edits are permitted for this run.
type ActionContext struct {
	Mode             string   `json:"mode"`
	WorkspaceRoot    string   `json:"workspaceRoot"`
	AllowedEditRoots []string `json:"allowedEditRoots"`
}

// Relationships is reserved for cross-change links; every field is always empty.
type Relationships struct {
	DependsOn               []string `json:"dependsOn"`
	Supersedes              []string `json:"supersedes"`
	Amends                  []string `json:"amends"`
	ConflictsWith           []string `json:"conflictsWith"`
	SameDomainActiveChanges []string `json:"sameDomainActiveChanges"`
}

// PhaseInstructions are the human-readable next-step hints per phase.
type PhaseInstructions struct {
	Apply   []string `json:"apply"`
	Verify  []string `json:"verify"`
	Archive []string `json:"archive"`
}

// Status is the full resolved SDD state for one change, serialized to JSON.
type Status struct {
	SchemaName        string                   `json:"schemaName"`
	SchemaVersion     int                      `json:"schemaVersion"`
	ChangeName        *string                  `json:"changeName"`
	ArtifactStore     string                   `json:"artifactStore"`
	PlanningHome      PlanningHome             `json:"planningHome"`
	ChangeRoot        *string                  `json:"changeRoot"`
	ArtifactPaths     ArtifactPaths            `json:"artifactPaths"`
	ContextFiles      ArtifactPaths            `json:"contextFiles"`
	Artifacts         map[string]ArtifactState `json:"artifacts"`
	TaskProgress      TaskProgress             `json:"taskProgress"`
	Dependencies      Dependencies             `json:"dependencies"`
	ApplyState        ApplyState               `json:"applyState"`
	ActionContext     ActionContext            `json:"actionContext"`
	Relationships     Relationships            `json:"relationships"`
	PhaseInstructions *PhaseInstructions       `json:"phaseInstructions,omitempty"`
	NextRecommended   string                   `json:"nextRecommended"`
	BlockedReasons    []string                 `json:"blockedReasons"`
}

// Resolve reads {root}/openspec/changes and computes the SDD status for one
// change. root is workspaceRoot when non-empty, otherwise cwd. changeName may
// be empty to let Resolve infer the single active change (or block when zero or
// many exist). When includeInstructions is true, per-phase instructions are
// attached. A non-nil error means root could not be resolved or read; a blocked
// change is reported as a valid Status, not an error.
func Resolve(cwd, workspaceRoot, changeName string, includeInstructions bool) (Status, error) {
	root, err := resolveRoot(cwd, workspaceRoot)
	if err != nil {
		return Status{}, err
	}

	active, err := listActiveChanges(root)
	if err != nil {
		return Status{}, err
	}

	selected, blocked := selectChange(active, strings.TrimSpace(changeName))
	if blocked != nil {
		return newBlockedStatus(root, blocked.changeName, blocked.next, blocked.reasons, includeInstructions), nil
	}

	changeRoot := filepath.Join(root, "openspec", "changes", selected)
	return resolveChange(root, selected, changeRoot, includeInstructions)
}

// changeBlock is the outcome of change selection when no concrete change can be
// resolved into a full status.
type changeBlock struct {
	changeName *string
	next       string
	reasons    []string
}

// selectChange applies the change-selection rules: zero active -> sdd-new,
// many active with no name -> select-change, a name not among the active set ->
// sdd-new. It returns the resolved change name when exactly one is selected.
func selectChange(active []string, requested string) (string, *changeBlock) {
	if requested == "" {
		switch len(active) {
		case 0:
			return "", &changeBlock{
				next:    nextSDDNew,
				reasons: []string{"No active OpenSpec changes found under openspec/changes."},
			}
		case 1:
			return active[0], nil
		default:
			return "", &changeBlock{
				next:    nextSelectChange,
				reasons: []string{fmt.Sprintf("Change selection is ambiguous: %s.", strings.Join(active, ", "))},
			}
		}
	}
	if !contains(active, requested) {
		name := requested
		return "", &changeBlock{
			changeName: &name,
			next:       nextSDDNew,
			reasons:    []string{fmt.Sprintf("Active OpenSpec change not found: %s.", requested)},
		}
	}
	return requested, nil
}

// resolveChange computes the full state machine for a concrete, existing change.
func resolveChange(root, changeName, changeRoot string, includeInstructions bool) (Status, error) {
	paths, err := discoverArtifactPaths(changeRoot)
	if err != nil {
		return Status{}, err
	}

	artifacts := classifyArtifacts(changeRoot, paths)

	taskProgress, err := countTaskProgress(firstPath(paths.Tasks))
	if err != nil {
		return Status{}, err
	}

	verifyPassing, err := reportIsClearlyPassing(firstPath(paths.VerifyReport))
	if err != nil {
		return Status{}, err
	}

	machine := computeStateMachine(artifacts, taskProgress, verifyPassing)

	status := newBaseStatus(root, &changeName, &changeRoot, machine.next, machine.reasons)
	status.ArtifactPaths = paths
	status.ContextFiles = paths
	status.Artifacts = artifacts
	status.TaskProgress = taskProgress
	status.Dependencies = machine.dependencies
	status.ApplyState = machine.applyState
	if includeInstructions {
		instructions := buildPhaseInstructions(status)
		status.PhaseInstructions = &instructions
	}
	return status, nil
}
