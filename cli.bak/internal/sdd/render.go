package sdd

import (
	"encoding/json"
	"fmt"
	"strings"
)

const unresolvedChange = "unresolved"

// RenderMarkdown renders a human-readable status summary for sdd-status,
// ending with the full Status JSON in a fenced block.
func RenderMarkdown(s Status) string {
	lines := []string{
		fmt.Sprintf("## SDD Status: %s", changeNameOf(s)),
		"",
		fmt.Sprintf("schema: %s@%d", s.SchemaName, s.SchemaVersion),
		fmt.Sprintf("store: %s", s.ArtifactStore),
		fmt.Sprintf("planning_home: %s", s.PlanningHome.Path),
		fmt.Sprintf("next: %s", s.NextRecommended),
		"",
		"### Summary",
		fmt.Sprintf("- apply: %s", s.Dependencies.Apply),
		fmt.Sprintf("- verify: %s", s.Dependencies.Verify),
		fmt.Sprintf("- archive: %s", s.Dependencies.Archive),
		fmt.Sprintf("- tasks: %d/%d complete", s.TaskProgress.Completed, s.TaskProgress.Total),
	}
	lines = appendBlockedReasons(lines, s.BlockedReasons)
	return strings.Join(appendJSONBlock(lines, s), "\n")
}

// RenderDispatcherMarkdown renders the routing-oriented markdown for
// sdd-continue: the next action, every dependency state, blocked reasons, and
// the next phase's instructions, ending with the full Status JSON.
func RenderDispatcherMarkdown(s Status) string {
	lines := []string{
		fmt.Sprintf("## Native SDD Dispatcher: %s", changeNameOf(s)),
		"",
		"Native status is authoritative. Route by next_recommended and dependency state, not by prompt inference.",
		"",
		fmt.Sprintf("next_recommended: %s", s.NextRecommended),
		"",
		"### Dependency States",
		fmt.Sprintf("- proposal: %s", s.Dependencies.Proposal),
		fmt.Sprintf("- specs: %s", s.Dependencies.Specs),
		fmt.Sprintf("- design: %s", s.Dependencies.Design),
		fmt.Sprintf("- tasks: %s", s.Dependencies.Tasks),
		fmt.Sprintf("- apply: %s", s.Dependencies.Apply),
		fmt.Sprintf("- verify: %s", s.Dependencies.Verify),
		fmt.Sprintf("- archive: %s", s.Dependencies.Archive),
		fmt.Sprintf("- task_progress: %d/%d complete", s.TaskProgress.Completed, s.TaskProgress.Total),
	}
	lines = appendBlockedReasons(lines, s.BlockedReasons)

	if phase, ok := recommendedPhase(s.NextRecommended); ok {
		lines = append(lines, "", fmt.Sprintf("### Next Phase Instructions: %s", phase))
		for _, instruction := range instructionsForPhase(s, phase) {
			lines = append(lines, fmt.Sprintf("- %s", instruction))
		}
	}

	return strings.Join(appendJSONBlock(lines, s), "\n")
}

func changeNameOf(s Status) string {
	if s.ChangeName != nil {
		return *s.ChangeName
	}
	return unresolvedChange
}

func appendBlockedReasons(lines, reasons []string) []string {
	if len(reasons) == 0 {
		return lines
	}
	lines = append(lines, "", "### Blocked Reasons")
	for _, reason := range reasons {
		lines = append(lines, fmt.Sprintf("- %s", reason))
	}
	return lines
}

func appendJSONBlock(lines []string, s Status) []string {
	payload, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		payload = []byte("{}")
	}
	return append(lines, "", "### JSON", "```json", string(payload), "```")
}

// recommendedPhase reports whether next is a concrete phase (apply/verify/
// archive) that has renderable instructions.
func recommendedPhase(next string) (string, bool) {
	switch next {
	case phaseApply, phaseVerify, phaseArchive:
		return next, true
	default:
		return "", false
	}
}

// instructionsForPhase returns the instruction lines for a phase, building them
// on demand when the status did not carry them.
func instructionsForPhase(s Status, phase string) []string {
	instructions := s.PhaseInstructions
	if instructions == nil {
		built := buildPhaseInstructions(s)
		instructions = &built
	}
	switch phase {
	case phaseApply:
		return instructions.Apply
	case phaseVerify:
		return instructions.Verify
	case phaseArchive:
		return instructions.Archive
	default:
		return nil
	}
}

// buildPhaseInstructions composes the per-phase guidance from the resolved
// status (change name and the phase dependency states).
func buildPhaseInstructions(s Status) PhaseInstructions {
	change := unresolvedChange
	if s.ChangeName != nil {
		change = *s.ChangeName
	}
	return PhaseInstructions{
		Apply: []string{
			fmt.Sprintf("Change: %s", change),
			fmt.Sprintf("State: %s", s.Dependencies.Apply),
			"Read proposal, specs, design, and tasks before editing.",
			"Implement only unchecked tasks and update tasks.md checkboxes as work completes.",
		},
		Verify: []string{
			fmt.Sprintf("Change: %s", change),
			fmt.Sprintf("State: %s", s.Dependencies.Verify),
			"Verify implementation against proposal, specs, design, and task completion.",
			"Incomplete tasks remain archive blockers even when apply-progress.md exists.",
		},
		Archive: []string{
			fmt.Sprintf("Change: %s", change),
			fmt.Sprintf("State: %s", s.Dependencies.Archive),
			"Archive only when verify-report.md exists and every task checkbox is complete.",
		},
	}
}
