// Package install owns ai-harness filesystem installation and uninstall logic.
// It copies the shared agent assets into the user's home locations, records the
// owned files in a central manifest, and removes only manifest-listed paths on
// uninstall.
package install

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// Action is the outcome category for a single target. It is the vocabulary both
// the CLI (for printing) and the tests (for assertions) speak.
type Action string

const (
	ActionCopied        Action = "copied"
	ActionOverwritten   Action = "overwritten"
	ActionSourceMissing Action = "source missing"
	ActionRemoved       Action = "removed"
	ActionAbsent        Action = "absent"
)

// Outcome records what happened for one destination artifact.
type Outcome struct {
	Dest   string // the destination path under a home dir
	Src    string // the repo path it was copied from (install only)
	Action Action // what install/uninstall did
	Target string // optional extra context for CLI output
}

// Report is the per-target log of an Install or Uninstall run, in target order.
type Report []Outcome

// ManifestEntry describes one owned installed file.
type ManifestEntry struct {
	Dest   string `json:"dest"`
	Source string `json:"source,omitempty"`
	Kind   string `json:"kind"`
}

// Manifest is the central registry of owned installed files.
type Manifest struct {
	Version   int             `json:"version"`
	Installed []ManifestEntry `json:"installed"`
}

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
	// harnesses (back-compat / safe default); the generic .agents artifacts are
	// always installed regardless of this selection.
	Harnesses []Harness
	// Timestamp remains for compatibility with older callers and tests.
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

// mappings builds the repo->home artifact copy set for the selected harnesses,
// in a stable order: the always-on generic .agents artifacts first, then
// claude, copilot, and opencode, each added only when wants() selects it.
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

// DefaultTimestamp is preserved for compatibility with older callers.
func DefaultTimestamp() string {
	return time.Now().Format("20060102150405")
}

// Install copies every mapping into the home dirs idempotently and returns a
// per-target Report plus the manifest entries needed for uninstall.
func Install(cfg Config) (Report, []ManifestEntry, error) {
	mappings := cfg.mappings()
	report := make(Report, 0, len(mappings))
	entries := make([]ManifestEntry, 0)
	var firstErr error
	for _, m := range mappings {
		outcome, owned, err := installOne(m)
		report = append(report, outcome)
		entries = append(entries, owned...)
		if err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return report, entries, firstErr
}

// installOne realizes a single copy target.
func installOne(m link) (Outcome, []ManifestEntry, error) {
	out := Outcome{Dest: m.dest, Src: m.src}
	entries := make([]ManifestEntry, 0)

	srcInfo, err := os.Stat(m.src)
	if err != nil {
		out.Action = ActionSourceMissing
		return out, nil, fmt.Errorf("source missing, skipping: %s", m.src)
	}

	if err := os.MkdirAll(filepath.Dir(m.dest), 0o755); err != nil {
		return out, nil, fmt.Errorf("create parent dir for %s: %w", m.dest, err)
	}

	existed := true
	if _, err := os.Lstat(m.dest); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			existed = false
		} else {
			return out, nil, fmt.Errorf("inspect %s: %w", m.dest, err)
		}
	}
	if srcInfo.IsDir() {
		if err := copyDir(m.src, m.dest); err != nil {
			return out, nil, err
		}
		entries, err = manifestEntriesForTree(m.src, m.dest)
		if err != nil {
			return out, nil, err
		}
	} else {
		if err := os.RemoveAll(m.dest); err != nil {
			return out, nil, fmt.Errorf("replace %s: %w", m.dest, err)
		}
		if err := copyFile(m.src, m.dest, srcInfo.Mode().Perm()); err != nil {
			return out, nil, err
		}
		entries = append(entries, ManifestEntry{Dest: m.dest, Source: m.src, Kind: "file"})
	}

	if existed {
		out.Action = ActionOverwritten
	} else {
		out.Action = ActionCopied
	}
	return out, entries, nil
}

// copyDir copies a directory tree recursively, preserving file contents and
// permissions where practical.
func copyDir(src, dest string) error {
	srcInfo, err := os.Stat(src)
	if err != nil {
		return fmt.Errorf("stat %s: %w", src, err)
	}
	createdDirs := make([]string, 0)
	if err := ensureDir(dest, srcInfo.Mode().Perm(), &createdDirs); err != nil {
		return fmt.Errorf("create dir %s: %w", dest, err)
	}
	changes := make([]fileChange, 0)
	rollback := func(copyErr error) error {
		rollbackCopiedFiles(changes)
		removeCreatedDirs(createdDirs)
		return copyErr
	}
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return rollback(walkErr)
		}
		if path == src {
			return nil
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return rollback(err)
		}
		target := filepath.Join(dest, rel)
		if d.IsDir() {
			if err := ensureDir(target, 0o755, &createdDirs); err != nil {
				return rollback(err)
			}
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return rollback(err)
		}
		change, err := captureFileChange(target)
		if err != nil {
			return rollback(err)
		}
		changes = append(changes, change)
		if err := copyFile(path, target, info.Mode().Perm()); err != nil {
			return rollback(err)
		}
		return nil
	})
}

type fileChange struct {
	path    string
	existed bool
	data    []byte
	perm    fs.FileMode
}

func ensureDir(path string, perm fs.FileMode, createdDirs *[]string) error {
	if _, err := os.Lstat(path); err != nil {
		if !errors.Is(err, os.ErrNotExist) {
			return err
		}
		if err := os.MkdirAll(path, perm); err != nil {
			return err
		}
		*createdDirs = append(*createdDirs, path)
		return nil
	}
	return os.MkdirAll(path, perm)
}

func captureFileChange(path string) (fileChange, error) {
	change := fileChange{path: path}
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return change, nil
	}
	if err != nil {
		return change, err
	}
	if !info.Mode().IsRegular() {
		return change, fmt.Errorf("replace %s: target is not a regular file", path)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return change, err
	}
	change.existed = true
	change.data = data
	change.perm = info.Mode().Perm()
	return change, nil
}

func rollbackCopiedFiles(changes []fileChange) {
	for i := len(changes) - 1; i >= 0; i-- {
		change := changes[i]
		if change.existed {
			_ = os.WriteFile(change.path, change.data, change.perm)
			continue
		}
		_ = os.Remove(change.path)
	}
}

func removeCreatedDirs(dirs []string) {
	for i := len(dirs) - 1; i >= 0; i-- {
		_ = os.Remove(dirs[i])
	}
}

// copyFile copies one regular file to dest.
func copyFile(src, dest string, perm fs.FileMode) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return fmt.Errorf("read %s: %w", src, err)
	}
	if perm == 0 {
		perm = 0o644
	}
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return fmt.Errorf("create parent dir for %s: %w", dest, err)
	}
	if err := os.WriteFile(dest, data, perm); err != nil {
		return fmt.Errorf("write %s: %w", dest, err)
	}
	return nil
}

// manifestEntriesForTree expands a copied directory tree to file-level manifest
// entries so uninstall can remove only owned files and keep unlisted user files.
func manifestEntriesForTree(srcRoot, destRoot string) ([]ManifestEntry, error) {
	entries := make([]ManifestEntry, 0)
	err := filepath.WalkDir(srcRoot, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(srcRoot, path)
		if err != nil {
			return err
		}
		entries = append(entries, ManifestEntry{
			Dest:   filepath.Join(destRoot, rel),
			Source: filepath.Join(srcRoot, rel),
			Kind:   "file",
		})
		return nil
	})
	return entries, err
}

// WriteManifest records the supplied owned file list without dropping existing
// ownership. Narrow reinstalls should refresh the artifacts they touched while
// preserving older manifest entries that still define what uninstall owns.
func WriteManifest(cfg Config, entries []ManifestEntry) error {
	path := manifestPath(cfg)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return fmt.Errorf("create manifest dir %s: %w", filepath.Dir(path), err)
	}
	merged := entries
	if existing, ok, err := readManifest(cfg); err != nil {
		return err
	} else if ok {
		merged = append(existing.Installed, entries...)
	}
	manifest := Manifest{Version: 1, Installed: dedupeAndSort(merged)}
	payload, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return fmt.Errorf("encode manifest %s: %w", path, err)
	}
	if err := os.WriteFile(path, payload, 0o644); err != nil {
		return fmt.Errorf("write manifest %s: %w", path, err)
	}
	return nil
}

// ResolveRepoDir picks the repo root (explicit repo flag, else cwd) and verifies
// it actually holds the shared config (skills/ and AGENTS.md).
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

// Uninstall removes the files listed in the central manifest and prunes empty
// owned directories when safe. If no manifest exists, uninstall is a no-op.
func Uninstall(cfg Config) (Report, error) {
	manifest, ok, err := readManifest(cfg)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, nil
	}
	if err := validateManifest(cfg, manifest); err != nil {
		return nil, err
	}

	report := make(Report, 0, len(manifest.Installed))
	var firstErr error
	for _, entry := range manifest.Installed {
		outcome, err := uninstallEntry(cfg, entry)
		report = append(report, outcome)
		if err != nil && firstErr == nil {
			firstErr = err
		}
	}
	if firstErr == nil {
		if err := os.Remove(manifestPath(cfg)); err != nil && !errors.Is(err, os.ErrNotExist) {
			firstErr = fmt.Errorf("remove manifest: %w", err)
		}
	}
	return report, firstErr
}

func uninstallEntry(cfg Config, entry ManifestEntry) (Outcome, error) {
	out := Outcome{Dest: entry.Dest, Src: entry.Source, Target: entry.Source}
	safeDest, err := validateManifestEntry(cfg, entry)
	if err != nil {
		return out, err
	}
	out.Dest = safeDest
	if _, err := os.Lstat(safeDest); errors.Is(err, os.ErrNotExist) {
		out.Action = ActionAbsent
		return out, nil
	} else if err != nil {
		return out, fmt.Errorf("inspect %s: %w", safeDest, err)
	}
	if err := os.Remove(safeDest); err != nil {
		return out, fmt.Errorf("remove %s: %w", safeDest, err)
	}
	out.Action = ActionRemoved
	cleanupEmptyParents(safeDest, ownedRoots(cfg))
	return out, nil
}

func validateManifest(cfg Config, manifest Manifest) error {
	for _, entry := range manifest.Installed {
		if _, err := validateManifestEntry(cfg, entry); err != nil {
			return err
		}
	}
	return nil
}

func validateManifestEntry(cfg Config, entry ManifestEntry) (string, error) {
	if entry.Kind != "file" {
		return "", fmt.Errorf("unsafe manifest entry %s: unsupported kind %q", entry.Dest, entry.Kind)
	}
	if !filepath.IsAbs(entry.Dest) {
		return "", fmt.Errorf("unsafe manifest entry %s: destination must be absolute", entry.Dest)
	}
	dest := filepath.Clean(entry.Dest)
	for _, root := range ownedRoots(cfg) {
		if pathWithinRoot(dest, root) {
			info, err := os.Lstat(dest)
			if errors.Is(err, os.ErrNotExist) {
				return dest, nil
			}
			if err != nil {
				return "", fmt.Errorf("inspect %s: %w", dest, err)
			}
			if !info.Mode().IsRegular() {
				return "", fmt.Errorf("unsafe manifest entry %s: kind file target is not a regular file", entry.Dest)
			}
			return dest, nil
		}
	}
	return "", fmt.Errorf("unsafe manifest entry %s: destination is outside ai-harness managed roots", entry.Dest)
}

func pathWithinRoot(path, root string) bool {
	cleanRoot := filepath.Clean(root)
	rel, err := filepath.Rel(cleanRoot, path)
	if err != nil || rel == "." {
		return false
	}
	return rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator))
}

func ownedRoots(cfg Config) []string {
	return []string{
		filepath.Clean(cfg.ClaudeDir),
		filepath.Clean(cfg.AgentsDir),
		filepath.Clean(cfg.CopilotDir),
		filepath.Clean(cfg.OpencodeDir),
		filepath.Clean(filepath.Dir(manifestPath(cfg))),
	}
}

func cleanupEmptyParents(path string, roots []string) {
	dir := filepath.Clean(filepath.Dir(path))
	for {
		if dir == "." || dir == string(os.PathSeparator) {
			return
		}
		if stopAt(dir, roots) {
			return
		}
		empty, err := dirEmpty(dir)
		if err != nil || !empty {
			return
		}
		if err := os.Remove(dir); err != nil {
			return
		}
		dir = filepath.Dir(dir)
	}
}

func stopAt(dir string, roots []string) bool {
	for _, root := range roots {
		if dir == root {
			return true
		}
	}
	return false
}

func dirEmpty(dir string) (bool, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return true, nil
		}
		return false, err
	}
	return len(entries) == 0, nil
}

func manifestPath(cfg Config) string {
	return filepath.Join(filepath.Dir(cfg.OpencodeDir), "ai-harness", "install-manifest.json")
}

func readManifest(cfg Config) (Manifest, bool, error) {
	path := manifestPath(cfg)
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return Manifest{}, false, nil
		}
		return Manifest{}, false, fmt.Errorf("read manifest %s: %w", path, err)
	}
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return Manifest{}, false, fmt.Errorf("decode manifest %s: %w", path, err)
	}
	return manifest, true, nil
}

func dedupeAndSort(entries []ManifestEntry) []ManifestEntry {
	if len(entries) == 0 {
		return nil
	}
	seen := make(map[string]ManifestEntry, len(entries))
	for _, entry := range entries {
		seen[entry.Dest] = entry
	}
	unique := make([]ManifestEntry, 0, len(seen))
	for _, entry := range seen {
		unique = append(unique, entry)
	}
	sort.Slice(unique, func(i, j int) bool {
		if unique[i].Dest == unique[j].Dest {
			return unique[i].Source < unique[j].Source
		}
		return unique[i].Dest < unique[j].Dest
	})
	return unique
}
