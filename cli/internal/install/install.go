// Package install ports the repo's install.sh / uninstall.sh into a tested Go
// deep module. It symlinks the shared agent config (skills/, AGENTS.md, the
// OpenCode prompts/sdd dir, and the OpenCode plugins dir) into the user's
// home-dir locations, and removes only the symlinks that point back into this
// repo.
//
// The link set is conditional on the selected harnesses (see Config.Harnesses):
// the generic .agents links are always installed, while the claude, copilot, and
// opencode links are added only when their harness is selected. Each harness gets
// a different scope (claude: skills + CLAUDE.md; copilot: skills +
// copilot-instructions.md; opencode: the full skills + AGENTS.md + prompts/sdd +
// plugins set).
//
// The package is host-injectable on purpose: it never reads $HOME or the wall
// clock itself. The caller supplies every directory and a timestamp source via
// Config, so the whole behavior is exercisable against temp dirs with
// deterministic backup names.
package install

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Action is the outcome category for a single target. It is the vocabulary both
// the CLI (for printing) and the tests (for assertions) speak.
type Action string

const (
	ActionLinked          Action = "linked"
	ActionRelinked        Action = "relinked"
	ActionBackedUp        Action = "backed up"
	ActionSourceMissing   Action = "source missing"
	ActionRemoved         Action = "removed"
	ActionSkippedForeign  Action = "skipped (points elsewhere)"
	ActionSkippedRealFile Action = "skipped (real file)"
	ActionAbsent          Action = "absent"
)

// Outcome records what happened for one destination link.
type Outcome struct {
	Dest   string // the link path under a home dir
	Src    string // the repo path it should point at (install only)
	Action Action // what install/uninstall did
	Backup string // backup path, set only when Action == ActionBackedUp
	Target string // existing symlink target observed (uninstall reporting)
}

// Report is the per-target log of an Install or Uninstall run, in target order.
type Report []Outcome

// Harness names one AI CLI whose home-dir config this module can wire up.
type Harness string

const (
	HarnessClaude   Harness = "claude"
	HarnessCopilot  Harness = "copilot"
	HarnessOpenCode Harness = "opencode"
)

// AllHarnesses is the full, stable-ordered set of selectable harnesses. The CLI
// uses it to validate --harness values and as the default selection.
var AllHarnesses = []Harness{HarnessOpenCode, HarnessClaude, HarnessCopilot}

// Config carries every host-specific input so the logic stays pure and testable.
// ClaudeDir/AgentsDir/CopilotDir/OpencodeDir default-filling is the CLI layer's
// job, not this module's.
type Config struct {
	RepoDir     string
	ClaudeDir   string
	AgentsDir   string
	CopilotDir  string
	OpencodeDir string
	// Harnesses selects which harnesses to configure. An EMPTY slice means ALL
	// harnesses (back-compat / safe default); the generic .agents links are
	// always installed regardless of this selection.
	Harnesses []Harness
	// Timestamp produces the suffix for "<dest>.bak.<ts>" backups. Inject a
	// fixed value in tests; the CLI injects a real clock via DefaultTimestamp.
	Timestamp func() string
}

// wants reports whether harness h is selected. An empty Harnesses slice selects
// every harness, so wants returns true for all of them in that case.
func (c Config) wants(h Harness) bool {
	if len(c.Harnesses) == 0 {
		return true
	}
	for _, selected := range c.Harnesses {
		if selected == h {
			return true
		}
	}
	return false
}

// link is one source->dest mapping.
type link struct {
	src  string
	dest string
}

// mappings builds the repo->home links for the selected harnesses, in a stable
// order: the always-on generic .agents links first, then claude, copilot, and
// opencode, each added only when wants() selects it. Every harness has a
// different scope:
//   - .agents (always): skills/ + AGENTS.md.
//   - claude: skills/ + CLAUDE.md.
//   - copilot: skills/ + copilot-instructions.md.
//   - opencode: skills/ + AGENTS.md (its global persona) + the prompts/sdd dir
//     its agents reference + the agent-clis/opencode/plugins dir (OpenCode
//     auto-loads plugins it finds under ~/.config/opencode/plugins).
//
// Every link rides the same idempotent backup/relink/uninstall logic.
func (c Config) mappings() []link {
	skills := filepath.Join(c.RepoDir, "skills")
	agents := filepath.Join(c.RepoDir, "AGENTS.md")

	links := []link{
		{skills, filepath.Join(c.AgentsDir, "skills")},
		{agents, filepath.Join(c.AgentsDir, "AGENTS.md")},
	}
	if c.wants(HarnessClaude) {
		links = append(links,
			link{skills, filepath.Join(c.ClaudeDir, "skills")},
			link{agents, filepath.Join(c.ClaudeDir, "CLAUDE.md")},
		)
	}
	if c.wants(HarnessCopilot) {
		links = append(links,
			link{skills, filepath.Join(c.CopilotDir, "skills")},
			link{agents, filepath.Join(c.CopilotDir, "copilot-instructions.md")},
		)
	}
	if c.wants(HarnessOpenCode) {
		links = append(links,
			link{skills, filepath.Join(c.OpencodeDir, "skills")},
			link{agents, filepath.Join(c.OpencodeDir, "AGENTS.md")},
			link{filepath.Join(c.RepoDir, "prompts", "sdd"), filepath.Join(c.OpencodeDir, "prompts", "sdd")},
			link{filepath.Join(c.RepoDir, "agent-clis", "opencode", "plugins"), filepath.Join(c.OpencodeDir, "plugins")},
		)
	}
	return links
}

// DefaultTimestamp is the production timestamp source: a local-time stamp in the
// same YYYYMMDDHHMMSS format install.sh used (date +%Y%m%d%H%M%S).
func DefaultTimestamp() string {
	return time.Now().Format("20060102150405")
}

// Install symlinks every mapping into the home dirs idempotently and returns a
// per-target Report. If any required source is missing it still attempts the
// other links, but returns a non-nil error so the CLI can exit non-zero — this
// matches install.sh, whose link() returns 1 on a missing source.
func Install(cfg Config) (Report, error) {
	mappings := cfg.mappings()
	report := make(Report, 0, len(mappings))
	var firstErr error
	for _, m := range mappings {
		outcome, err := installOne(cfg, m)
		report = append(report, outcome)
		if err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return report, firstErr
}

// installOne realizes a single link with the idempotent backup/relink rules.
func installOne(cfg Config, m link) (Outcome, error) {
	out := Outcome{Dest: m.dest, Src: m.src}

	if _, err := os.Lstat(m.src); err != nil {
		out.Action = ActionSourceMissing
		return out, fmt.Errorf("source missing, skipping: %s", m.src)
	}

	if err := os.MkdirAll(filepath.Dir(m.dest), 0o755); err != nil {
		return out, fmt.Errorf("create parent dir for %s: %w", m.dest, err)
	}

	info, err := os.Lstat(m.dest)
	switch {
	case err == nil && info.Mode()&os.ModeSymlink != 0:
		// Existing symlink -> force relink.
		if err := relink(m.src, m.dest); err != nil {
			return out, err
		}
		out.Action = ActionRelinked
		return out, nil

	case err == nil:
		// Real file/dir in the way -> back it up, then link.
		backup := m.dest + ".bak." + cfg.Timestamp()
		if err := os.Rename(m.dest, backup); err != nil {
			return out, fmt.Errorf("back up %s: %w", m.dest, err)
		}
		if err := os.Symlink(m.src, m.dest); err != nil {
			return out, fmt.Errorf("link %s: %w", m.dest, err)
		}
		out.Action = ActionBackedUp
		out.Backup = backup
		return out, nil

	case errors.Is(err, os.ErrNotExist):
		// Nothing there -> link.
		if err := os.Symlink(m.src, m.dest); err != nil {
			return out, fmt.Errorf("link %s: %w", m.dest, err)
		}
		out.Action = ActionLinked
		return out, nil

	default:
		return out, fmt.Errorf("inspect %s: %w", m.dest, err)
	}
}

// relink atomically repoints an existing symlink (ln -sfn): remove then create.
func relink(src, dest string) error {
	if err := os.Remove(dest); err != nil {
		return fmt.Errorf("remove old link %s: %w", dest, err)
	}
	if err := os.Symlink(src, dest); err != nil {
		return fmt.Errorf("relink %s: %w", dest, err)
	}
	return nil
}

// Uninstall removes only the symlinks whose target lives under RepoDir, leaving
// real files, foreign symlinks, and *.bak.* backups untouched. It never returns
// an error for an expected per-target outcome.
func Uninstall(cfg Config) (Report, error) {
	mappings := cfg.mappings()
	report := make(Report, 0, len(mappings))
	var firstErr error
	for _, m := range mappings {
		outcome, err := uninstallOne(cfg, m.dest)
		report = append(report, outcome)
		if err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return report, firstErr
}

// uninstallOne classifies one destination and removes it only if it is a symlink
// pointing back into the repo.
func uninstallOne(cfg Config, dest string) (Outcome, error) {
	out := Outcome{Dest: dest}

	info, err := os.Lstat(dest)
	switch {
	case errors.Is(err, os.ErrNotExist):
		out.Action = ActionAbsent
		return out, nil

	case err != nil:
		return out, fmt.Errorf("inspect %s: %w", dest, err)

	case info.Mode()&os.ModeSymlink == 0:
		out.Action = ActionSkippedRealFile
		return out, nil
	}

	target, err := os.Readlink(dest)
	if err != nil {
		return out, fmt.Errorf("readlink %s: %w", dest, err)
	}
	out.Target = target

	if pointsInto(target, cfg.RepoDir) {
		if err := os.Remove(dest); err != nil {
			return out, fmt.Errorf("remove %s: %w", dest, err)
		}
		out.Action = ActionRemoved
		return out, nil
	}

	out.Action = ActionSkippedForeign
	return out, nil
}

// pointsInto reports whether target is the repo dir or sits under "<repo>/".
func pointsInto(target, repo string) bool {
	prefix := strings.TrimRight(repo, string(os.PathSeparator)) + string(os.PathSeparator)
	return strings.HasPrefix(target, prefix)
}

// ResolveRepoDir picks the repo root (explicit repo flag, else cwd) and verifies
// it actually holds the shared config (skills/ and AGENTS.md). The shell derived
// the root from the script's own location; an installed binary cannot, so the
// Go equivalent is cwd-or-flag plus a content check.
func ResolveRepoDir(repo, cwd string) (string, error) {
	root := repo
	if root == "" {
		root = cwd
	}

	missing := make([]string, 0, 2)
	for _, marker := range []string{"skills", "AGENTS.md"} {
		if _, err := os.Stat(filepath.Join(root, marker)); err != nil {
			missing = append(missing, marker)
		}
	}
	if len(missing) > 0 {
		return "", fmt.Errorf("%s is not an ai-harness repo: missing %s", root, strings.Join(missing, ", "))
	}
	return root, nil
}
