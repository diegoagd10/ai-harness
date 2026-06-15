// Package commands generates per-platform SDD slash-command entrypoints from a
// single canonical source. The canonical files live at <repo>/prompts/commands/
// and carry platform-NEUTRAL frontmatter plus four placeholders in their body:
// {{ORCHESTRATOR_AGENT}}, {{SKILLS_DIR}}, {{CWD_NOTE}}, and {{ARGS}}. A Profile
// supplies the per-platform values; Generate substitutes them, translates the
// neutral frontmatter into the platform's dialect, and writes one command file
// per source.
//
// This is the canonical-entrypoint layer. It is distinct from the phase
// EXECUTOR prompts at <repo>/prompts/sdd/ — those are agent prompts, not user
// slash commands, and this package never touches them.
//
// Like the install package, this module is host-injectable: it never reads
// $HOME. The caller supplies CommandDir (the platform's command directory), so
// the whole behavior is exercisable against temp dirs.
package commands

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Action is the outcome category for a single generated file. Today there is
// only one — emitting the file — but keeping the vocabulary parallel to the
// install package lets the CLI print both Reports the same way.
type Action string

const (
	ActionGenerated Action = "generated"
	ActionRemoved   Action = "removed"
	ActionAbsent    Action = "absent"
)

// Outcome records what happened for one generated command file.
type Outcome struct {
	Dest   string // the written command file under CommandDir
	Src    string // the canonical source it was generated from
	Action Action
}

// Report is the per-file log of a Generate run, in source-name order.
type Report []Outcome

// Profile carries every per-platform value Generate needs. It is host-injectable
// on purpose: CommandDir is supplied by the CLI layer (which knows $HOME), not
// derived here, so generation stays testable against temp dirs.
//
// Name identifies the platform for diagnostics. OrchestratorAgent, SkillsDir,
// CwdNote, and ArgsToken are the four body substitutions. CwdNote carries its
// own leading space when non-empty, so the canonical body can write
// "workspace.{{CWD_NOTE}}" and the empty case renders with no dangling space.
type Profile struct {
	Name              string
	OrchestratorAgent string
	SkillsDir         string
	CwdNote           string
	ArgsToken         string
	CommandDir        string
}

// The Electron cwd caveat shipped by the OpenCode profile. It begins with a
// space so it appends cleanly after "workspace." in the canonical body.
const opencodeCwdNote = " In OpenCode Desktop (Electron) the parse-time interpolation resolves to the app data directory, not the project."

// OpenCodeProfile returns the substitution values for the OpenCode platform.
// CommandDir is injected by the caller (e.g. ~/.config/opencode/commands).
func OpenCodeProfile(commandDir string) Profile {
	return Profile{
		Name:              "opencode",
		OrchestratorAgent: "sdd-orchestrator",
		SkillsDir:         "~/.config/opencode/skills",
		CwdNote:           opencodeCwdNote,
		ArgsToken:         "$ARGUMENTS",
		CommandDir:        commandDir,
	}
}

// commandsSubdir is where the canonical entrypoints live under the repo root.
var commandsSubdir = filepath.Join("prompts", "commands")

// Generate reads every *.md under <repoDir>/prompts/commands/, substitutes the
// profile's placeholders into each body, translates the neutral frontmatter into
// the OpenCode dialect, and writes <CommandDir>/<name>.md. It returns a per-file
// Report in source-name order. A missing or unreadable source directory is an
// error; a malformed individual file is also an error (callers should know the
// canonical source is broken rather than silently shipping a partial install).
func Generate(repoDir string, p Profile) (Report, error) {
	srcDir := filepath.Join(repoDir, commandsSubdir)
	names, err := canonicalNames(srcDir)
	if err != nil {
		return nil, err
	}

	if err := os.MkdirAll(p.CommandDir, 0o755); err != nil {
		return nil, fmt.Errorf("create command dir %s: %w", p.CommandDir, err)
	}

	report := make(Report, 0, len(names))
	for _, name := range names {
		outcome, err := generateOne(srcDir, name, p)
		if err != nil {
			return report, err
		}
		report = append(report, outcome)
	}
	return report, nil
}

// Remove deletes the command files Generate would have produced from the
// canonical source, leaving anything we did not generate untouched. It mirrors
// the install package's uninstall philosophy: only remove what we own, skip
// absent files, and never error on an expected outcome.
func Remove(repoDir string, p Profile) (Report, error) {
	srcDir := filepath.Join(repoDir, commandsSubdir)
	names, err := canonicalNames(srcDir)
	if err != nil {
		return nil, err
	}

	report := make(Report, 0, len(names))
	for _, name := range names {
		dest := filepath.Join(p.CommandDir, name)
		out := Outcome{Dest: dest, Src: filepath.Join(srcDir, name)}

		switch err := os.Remove(dest); {
		case err == nil:
			out.Action = ActionRemoved
		case os.IsNotExist(err):
			out.Action = ActionAbsent
		default:
			return report, fmt.Errorf("remove %s: %w", dest, err)
		}
		report = append(report, out)
	}
	return report, nil
}

// canonicalNames lists the *.md entrypoint filenames under the canonical source
// dir, in directory order. A missing or unreadable dir is an error so callers
// learn the source is broken rather than silently doing nothing.
func canonicalNames(srcDir string) ([]string, error) {
	entries, err := os.ReadDir(srcDir)
	if err != nil {
		return nil, fmt.Errorf("read canonical commands dir %s: %w", srcDir, err)
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".md") {
			continue
		}
		names = append(names, entry.Name())
	}
	return names, nil
}

// generateOne renders a single canonical file into the profile's CommandDir.
func generateOne(srcDir, name string, p Profile) (Outcome, error) {
	src := filepath.Join(srcDir, name)
	dest := filepath.Join(p.CommandDir, name)
	out := Outcome{Dest: dest, Src: src}

	raw, err := os.ReadFile(src)
	if err != nil {
		return out, fmt.Errorf("read %s: %w", src, err)
	}

	meta, body, err := splitFrontmatter(string(raw))
	if err != nil {
		return out, fmt.Errorf("parse %s: %w", src, err)
	}

	rendered := renderFrontmatter(meta, p) + substitute(body, p)
	if err := os.WriteFile(dest, []byte(rendered), 0o644); err != nil {
		return out, fmt.Errorf("write %s: %w", dest, err)
	}
	out.Action = ActionGenerated
	return out, nil
}

// substitute replaces the four canonical placeholders with the profile's values.
// Plain string replacement is deliberate (no template engine): the placeholder
// set is fixed and tiny.
func substitute(body string, p Profile) string {
	r := strings.NewReplacer(
		"{{ORCHESTRATOR_AGENT}}", p.OrchestratorAgent,
		"{{SKILLS_DIR}}", p.SkillsDir,
		"{{CWD_NOTE}}", p.CwdNote,
		"{{ARGS}}", p.ArgsToken,
	)
	return r.Replace(body)
}

// neutralMeta is the platform-neutral frontmatter every canonical file carries.
type neutralMeta struct {
	description string
	subtask     bool
	// readOnly is neutral metadata kept for future platforms; the OpenCode
	// dialect does not emit it.
	readOnly bool
}

// splitFrontmatter separates the leading "---"-fenced YAML-ish block from the
// body. The canonical files use a flat key: value form, so a full YAML parser
// would be overkill; this reads exactly the keys the dialect needs.
func splitFrontmatter(text string) (neutralMeta, string, error) {
	const fence = "---"
	if !strings.HasPrefix(text, fence+"\n") {
		return neutralMeta{}, "", fmt.Errorf("missing leading frontmatter fence")
	}
	rest := text[len(fence)+1:]
	end := strings.Index(rest, "\n"+fence+"\n")
	if end < 0 {
		return neutralMeta{}, "", fmt.Errorf("missing closing frontmatter fence")
	}
	header := rest[:end]
	body := rest[end+len("\n"+fence+"\n"):]

	var meta neutralMeta
	for _, line := range strings.Split(header, "\n") {
		key, value, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.TrimSpace(value)
		switch key {
		case "description":
			meta.description = value
		case "subtask":
			meta.subtask = value == "true"
		case "read-only":
			meta.readOnly = value == "true"
		}
	}
	if meta.description == "" {
		return neutralMeta{}, "", fmt.Errorf("frontmatter missing description")
	}
	return meta, body, nil
}

// renderFrontmatter emits the OpenCode frontmatter block for one command:
// description and agent always, subtask only when true. The agent is the
// profile's orchestrator. OpenCode has no read-only field, so the neutral
// readOnly flag is intentionally dropped here.
func renderFrontmatter(meta neutralMeta, p Profile) string {
	var b strings.Builder
	b.WriteString("---\n")
	b.WriteString("description: " + meta.description + "\n")
	b.WriteString("agent: " + p.OrchestratorAgent + "\n")
	if meta.subtask {
		b.WriteString("subtask: true\n")
	}
	b.WriteString("---\n")
	return b.String()
}
