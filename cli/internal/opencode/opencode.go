// Package opencode generates the OpenCode agent config (opencode.json) from the
// repo's canonical source. The source embeds {{HOME}} placeholders in its
// prompt-file references (e.g. {file:{{HOME}}/.config/opencode/prompts/sdd/...});
// OpenCode does not expand them itself, so ai-harness substitutes the real home
// dir at install time and writes a regular file the agent can read.
//
// Unlike the skills/prompts/persona artifacts (which are symlinked through the
// install package), opencode.json must be a generated regular file because its
// contents depend on the host's home path.
//
// Like the install and commands packages, this module is host-injectable: it
// never reads $HOME. The caller supplies opencodeDir and the home value, so the
// whole behavior is exercisable against temp dirs.
package opencode

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Action is the outcome category for the opencode.json artifact. The vocabulary
// parallels the commands package so the CLI prints both Reports the same way.
type Action string

const (
	ActionGenerated Action = "generated"
	ActionRemoved   Action = "removed"
	ActionAbsent    Action = "absent"
)

// Outcome records what happened to opencode.json for one Generate/Remove call.
type Outcome struct {
	Dest   string // the written opencode.json under opencodeDir
	Src    string // the canonical source it was generated from (Generate only)
	Action Action
}

// Report is the log of an opencode.json operation. A single artifact today, but
// kept as a slice for symmetry with install/commands so the CLI can print
// uniformly if more generated files appear later.
type Report []Outcome

// homePlaceholder is the literal token the canonical opencode.json carries
// wherever a host-absolute path is needed; Generate replaces every occurrence
// with the caller's home value.
const homePlaceholder = "{{HOME}}"

// sourceSubpath locates the canonical opencode.json under the repo root.
var sourceSubpath = filepath.Join("agent-clis", "opencode", "opencode.json")

// Generate reads the canonical opencode.json, substitutes every {{HOME}} with
// home, and writes the result to <opencodeDir>/opencode.json (0644), creating
// opencodeDir if needed. An unreadable source is an error so the caller learns
// the canonical source is broken rather than shipping a partial install.
func Generate(repoDir, opencodeDir, home string) (Outcome, error) {
	src := filepath.Join(repoDir, sourceSubpath)
	dest := filepath.Join(opencodeDir, "opencode.json")
	out := Outcome{Dest: dest, Src: src}

	raw, err := os.ReadFile(src)
	if err != nil {
		return out, fmt.Errorf("read opencode source %s: %w", src, err)
	}

	rendered := strings.ReplaceAll(string(raw), homePlaceholder, home)

	if err := os.MkdirAll(opencodeDir, 0o755); err != nil {
		return out, fmt.Errorf("create opencode dir %s: %w", opencodeDir, err)
	}
	if err := os.WriteFile(dest, []byte(rendered), 0o644); err != nil {
		return out, fmt.Errorf("write %s: %w", dest, err)
	}

	out.Action = ActionGenerated
	return out, nil
}

// Remove deletes the generated opencode.json, leaving anything else untouched.
// It mirrors the commands package's philosophy: a missing file is the expected
// absent outcome, not an error; only an unexpected removal failure errors.
func Remove(opencodeDir string) (Outcome, error) {
	dest := filepath.Join(opencodeDir, "opencode.json")
	out := Outcome{Dest: dest}

	switch err := os.Remove(dest); {
	case err == nil:
		out.Action = ActionRemoved
	case os.IsNotExist(err):
		out.Action = ActionAbsent
	default:
		return out, fmt.Errorf("remove %s: %w", dest, err)
	}
	return out, nil
}
