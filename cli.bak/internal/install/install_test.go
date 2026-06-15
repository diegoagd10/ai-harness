package install

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeRepo builds a minimal valid repo with real files for every copied tree.
func fakeRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	mustMkdirAll(t, filepath.Join(repo, "skills", "example"))
	mustMkdirAll(t, filepath.Join(repo, "prompts", "sdd"))
	mustMkdirAll(t, filepath.Join(repo, "agent-clis", "opencode", "plugins"))
	mustWriteFile(t, filepath.Join(repo, "AGENTS.md"), []byte("# Agents\n"))
	mustWriteFile(t, filepath.Join(repo, "skills", "example", "SKILL.md"), []byte("# Example skill\n"))
	mustWriteFile(t, filepath.Join(repo, "prompts", "sdd", "sdd-orchestrator.md"), []byte("# Orchestrator\n"))
	mustWriteFile(t, filepath.Join(repo, "agent-clis", "opencode", "plugins", "model-variants.ts"), []byte("export {};\n"))
	return repo
}

func mustMkdirAll(t *testing.T, path string) {
	t.Helper()
	if err := os.MkdirAll(path, 0o755); err != nil {
		t.Fatalf("mkdir %s: %v", path, err)
	}
}

func mustWriteFile(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func cfgFor(repo, home string) Config {
	return Config{
		RepoDir:     repo,
		ClaudeDir:   filepath.Join(home, ".claude"),
		AgentsDir:   filepath.Join(home, ".agents"),
		CopilotDir:  filepath.Join(home, ".copilot"),
		OpencodeDir: filepath.Join(home, ".config", "opencode"),
	}
}

func findOutcome(t *testing.T, r Report, dest string) Outcome {
	t.Helper()
	for _, o := range r {
		if o.Dest == dest {
			return o
		}
	}
	t.Fatalf("no outcome for dest %q in report %+v", dest, r)
	return Outcome{}
}

func testManifestPath(home string) string {
	return filepath.Join(home, ".config", "ai-harness", "install-manifest.json")
}

func readTestManifest(t *testing.T, path string) Manifest {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read manifest %s: %v", path, err)
	}
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		t.Fatalf("decode manifest %s: %v", path, err)
	}
	return manifest
}

func assertCopiedFile(t *testing.T, dest, want string) {
	t.Helper()
	info, err := os.Lstat(dest)
	if err != nil {
		t.Fatalf("lstat %s: %v", dest, err)
	}
	if info.Mode()&os.ModeSymlink != 0 {
		t.Fatalf("expected %s to be a copied file, not a symlink", dest)
	}
	got, err := os.ReadFile(dest)
	if err != nil {
		t.Fatalf("read %s: %v", dest, err)
	}
	if string(got) != want {
		t.Fatalf("%s content = %q, want %q", dest, got, want)
	}
}

func TestInstallCopiesAllTargetsAndWritesManifest(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	report, entries, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install returned error: %v", err)
	}
	if err := WriteManifest(cfg, entries); err != nil {
		t.Fatalf("WriteManifest returned error: %v", err)
	}
	if len(report) != 10 {
		t.Fatalf("expected 10 outcomes, got %d: %+v", len(report), report)
	}
	if len(entries) != 10 {
		t.Fatalf("expected 10 manifest entries, got %d: %+v", len(entries), entries)
	}

	sources := map[string]string{
		filepath.Join(repo, "skills", "example", "SKILL.md"):                          "# Example skill\n",
		filepath.Join(repo, "AGENTS.md"):                                              "# Agents\n",
		filepath.Join(repo, "prompts", "sdd", "sdd-orchestrator.md"):                  "# Orchestrator\n",
		filepath.Join(repo, "agent-clis", "opencode", "plugins", "model-variants.ts"): "export {};\n",
	}

	fileChecks := []struct {
		dest string
		src  string
	}{
		{filepath.Join(home, ".agents", "skills", "example", "SKILL.md"), filepath.Join(repo, "skills", "example", "SKILL.md")},
		{filepath.Join(home, ".agents", "AGENTS.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".claude", "skills", "example", "SKILL.md"), filepath.Join(repo, "skills", "example", "SKILL.md")},
		{filepath.Join(home, ".claude", "CLAUDE.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".copilot", "skills", "example", "SKILL.md"), filepath.Join(repo, "skills", "example", "SKILL.md")},
		{filepath.Join(home, ".copilot", "copilot-instructions.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".config", "opencode", "skills", "example", "SKILL.md"), filepath.Join(repo, "skills", "example", "SKILL.md")},
		{filepath.Join(home, ".config", "opencode", "AGENTS.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".config", "opencode", "prompts", "sdd", "sdd-orchestrator.md"), filepath.Join(repo, "prompts", "sdd", "sdd-orchestrator.md")},
		{filepath.Join(home, ".config", "opencode", "plugins", "model-variants.ts"), filepath.Join(repo, "agent-clis", "opencode", "plugins", "model-variants.ts")},
	}
	for _, c := range fileChecks {
		assertCopiedFile(t, c.dest, sources[c.src])
	}
	for _, dest := range []string{
		filepath.Join(home, ".agents", "skills"),
		filepath.Join(home, ".agents", "AGENTS.md"),
		filepath.Join(home, ".claude", "skills"),
		filepath.Join(home, ".claude", "CLAUDE.md"),
		filepath.Join(home, ".copilot", "skills"),
		filepath.Join(home, ".copilot", "copilot-instructions.md"),
		filepath.Join(home, ".config", "opencode", "skills"),
		filepath.Join(home, ".config", "opencode", "AGENTS.md"),
		filepath.Join(home, ".config", "opencode", "prompts", "sdd"),
		filepath.Join(home, ".config", "opencode", "plugins"),
	} {
		o := findOutcome(t, report, dest)
		if o.Action != ActionCopied {
			t.Fatalf("dest %s: expected action %q, got %q", dest, ActionCopied, o.Action)
		}
	}

	manifest := readTestManifest(t, testManifestPath(home))
	if manifest.Version != 1 {
		t.Fatalf("manifest version = %d, want 1", manifest.Version)
	}
	if len(manifest.Installed) != 10 {
		t.Fatalf("manifest installed = %d, want 10: %+v", len(manifest.Installed), manifest.Installed)
	}
	if manifest.Installed[0].Kind != "file" {
		t.Fatalf("manifest entry kind = %q, want file", manifest.Installed[0].Kind)
	}
}

func TestInstallOverwritesExistingDestinationWithoutBackup(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	dest := filepath.Join(home, ".claude", "CLAUDE.md")
	mustMkdirAll(t, filepath.Dir(dest))
	mustWriteFile(t, dest, []byte("old\n"))

	report, _, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install returned error: %v", err)
	}
	o := findOutcome(t, report, dest)
	if o.Action != ActionOverwritten {
		t.Fatalf("expected action %q, got %q", ActionOverwritten, o.Action)
	}
	assertCopiedFile(t, dest, "# Agents\n")
	if matches, _ := filepath.Glob(dest + ".bak.*"); len(matches) != 0 {
		t.Fatalf("unexpected backup files: %v", matches)
	}
}

func TestInstallMissingSourceIsError(t *testing.T) {
	repo := t.TempDir()
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	report, entries, err := Install(cfg)
	if err == nil {
		t.Fatalf("expected error when sources are missing")
	}
	if len(report) == 0 || len(entries) != 0 {
		t.Fatalf("expected no owned entries on missing source, got report=%+v entries=%+v", report, entries)
	}
	if _, err := os.Stat(filepath.Join(home, ".claude", "skills")); !os.IsNotExist(err) {
		t.Fatalf("expected no destination to be created, stat err = %v", err)
	}
}

func TestInstallDirectoryFailureRollsBackPartialCopies(t *testing.T) {
	src := t.TempDir()
	dest := filepath.Join(t.TempDir(), "skills")
	mustWriteFile(t, filepath.Join(src, "a-copied-before-failure.txt"), []byte("partial\n"))
	if err := os.Symlink(filepath.Join(src, "missing-target"), filepath.Join(src, "broken-link")); err != nil {
		t.Fatalf("create broken symlink: %v", err)
	}

	_, entries, err := installOne(link{src: src, dest: dest})
	if err == nil {
		t.Fatalf("expected installOne to fail on broken symlink")
	}
	if len(entries) != 0 {
		t.Fatalf("failed mapping must not return manifest entries, got %+v", entries)
	}
	if _, statErr := os.Stat(filepath.Join(dest, "a-copied-before-failure.txt")); !os.IsNotExist(statErr) {
		t.Fatalf("partial copied file must be rolled back, stat err = %v", statErr)
	}
}

func TestInstallDirectoryPreservesUnmanifestedUserFiles(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	custom := filepath.Join(cfg.OpencodeDir, "skills", "custom", "SKILL.md")
	mustMkdirAll(t, filepath.Dir(custom))
	mustWriteFile(t, custom, []byte("# Custom\n"))

	_, entries, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install returned error: %v", err)
	}
	if got, readErr := os.ReadFile(custom); readErr != nil || string(got) != "# Custom\n" {
		t.Fatalf("custom file must survive install, got %q err=%v", got, readErr)
	}
	for _, entry := range entries {
		if entry.Dest == custom {
			t.Fatalf("custom file must not become manifest-owned: %+v", entries)
		}
	}

	_, entries, err = Install(cfg)
	if err != nil {
		t.Fatalf("reinstall returned error: %v", err)
	}
	if got, readErr := os.ReadFile(custom); readErr != nil || string(got) != "# Custom\n" {
		t.Fatalf("custom file must survive reinstall, got %q err=%v", got, readErr)
	}
	for _, entry := range entries {
		if entry.Dest == custom {
			t.Fatalf("custom file must not become manifest-owned after reinstall: %+v", entries)
		}
	}
}

func TestUninstallRemovesManifestListedFilesAndKeepsUnlistedFiles(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	if _, entries, err := Install(cfg); err != nil {
		t.Fatalf("install: %v", err)
	} else if err := WriteManifest(cfg, entries); err != nil {
		t.Fatalf("write manifest: %v", err)
	}

	installed := filepath.Join(home, ".config", "opencode", "AGENTS.md")
	if err := os.WriteFile(installed, []byte("edited\n"), 0o644); err != nil {
		t.Fatalf("edit installed file: %v", err)
	}
	unlisted := filepath.Join(home, ".config", "opencode", "custom.txt")
	mustWriteFile(t, unlisted, []byte("keep me\n"))

	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall: %v", err)
	}
	o := findOutcome(t, report, installed)
	if o.Action != ActionRemoved {
		t.Fatalf("expected removed action for edited file, got %q", o.Action)
	}
	if _, err := os.Stat(installed); !os.IsNotExist(err) {
		t.Fatalf("installed file should be removed, stat err = %v", err)
	}
	if got, err := os.ReadFile(unlisted); err != nil {
		t.Fatalf("unlisted file should remain, read err = %v", err)
	} else if string(got) != "keep me\n" {
		t.Fatalf("unlisted file content changed: %q", got)
	}
	if _, err := os.Stat(testManifestPath(home)); !os.IsNotExist(err) {
		t.Fatalf("manifest should be removed, stat err = %v", err)
	}
}

func TestUninstallNoopWithoutManifest(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	if err := os.MkdirAll(filepath.Join(home, ".config", "opencode"), 0o755); err != nil {
		t.Fatalf("mkdir custom dir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(home, ".config", "opencode", "custom.txt"), []byte("keep\n"), 0o644); err != nil {
		t.Fatalf("seed custom file: %v", err)
	}
	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall without manifest: %v", err)
	}
	if report != nil && len(report) != 0 {
		t.Fatalf("expected no report entries without manifest, got %+v", report)
	}
	if _, err := os.Stat(filepath.Join(home, ".config", "opencode", "custom.txt")); err != nil {
		t.Fatalf("custom file should remain: %v", err)
	}
}

func TestWriteManifestMergesExistingOwnedArtifacts(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	_, allEntries, err := Install(cfg)
	if err != nil {
		t.Fatalf("install all: %v", err)
	}
	if err := WriteManifest(cfg, allEntries); err != nil {
		t.Fatalf("write initial manifest: %v", err)
	}

	narrowCfg := cfg
	narrowCfg.Harnesses = []Harness{HarnessClaude}
	_, narrowEntries, err := Install(narrowCfg)
	if err != nil {
		t.Fatalf("install narrower selection: %v", err)
	}
	if err := WriteManifest(narrowCfg, narrowEntries); err != nil {
		t.Fatalf("write narrower manifest: %v", err)
	}

	manifest := readTestManifest(t, testManifestPath(home))
	opencodePlugin := filepath.Join(home, ".config", "opencode", "plugins", "model-variants.ts")
	found := false
	for _, entry := range manifest.Installed {
		if entry.Dest == opencodePlugin {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("narrow reinstall must preserve previously owned opencode artifact %s in manifest: %+v", opencodePlugin, manifest.Installed)
	}
}

func TestUninstallRejectsManifestEntryOutsideManagedRoots(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	outside := filepath.Join(home, "outside.txt")
	mustWriteFile(t, outside, []byte("keep\n"))

	if err := WriteManifest(cfg, []ManifestEntry{{Dest: outside, Kind: "file"}}); err != nil {
		t.Fatalf("write unsafe manifest: %v", err)
	}
	_, err := Uninstall(cfg)
	if err == nil {
		t.Fatalf("expected unsafe manifest entry to be rejected")
	}
	if got, readErr := os.ReadFile(outside); readErr != nil || string(got) != "keep\n" {
		t.Fatalf("outside file must remain untouched, got %q err=%v", got, readErr)
	}
}

func TestUninstallRejectsUnsafeManifestAtomically(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	safe := filepath.Join(cfg.OpencodeDir, "AGENTS.md")
	unsafe := filepath.Join(home, "outside.txt")
	mustMkdirAll(t, filepath.Dir(safe))
	mustWriteFile(t, safe, []byte("keep safe\n"))
	mustWriteFile(t, unsafe, []byte("keep outside\n"))

	if err := WriteManifest(cfg, []ManifestEntry{
		{Dest: safe, Kind: "file"},
		{Dest: unsafe, Kind: "file"},
	}); err != nil {
		t.Fatalf("write mixed manifest: %v", err)
	}

	_, err := Uninstall(cfg)
	if err == nil {
		t.Fatalf("expected unsafe manifest entry to be rejected")
	}
	if got, readErr := os.ReadFile(safe); readErr != nil || string(got) != "keep safe\n" {
		t.Fatalf("safe file must not be removed before later unsafe entry is rejected, got %q err=%v", got, readErr)
	}
	if got, readErr := os.ReadFile(unsafe); readErr != nil || string(got) != "keep outside\n" {
		t.Fatalf("outside file must remain untouched, got %q err=%v", got, readErr)
	}
}

func TestUninstallRejectsKindFilePointingAtDirectory(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	dir := filepath.Join(cfg.OpencodeDir, "skills")
	child := filepath.Join(dir, "custom.txt")
	mustMkdirAll(t, dir)
	mustWriteFile(t, child, []byte("keep\n"))

	if err := WriteManifest(cfg, []ManifestEntry{{Dest: dir, Kind: "file"}}); err != nil {
		t.Fatalf("write directory-as-file manifest: %v", err)
	}
	_, err := Uninstall(cfg)
	if err == nil {
		t.Fatalf("expected kind:file directory target to be rejected")
	}
	if got, readErr := os.ReadFile(child); readErr != nil || string(got) != "keep\n" {
		t.Fatalf("directory contents must remain untouched, got %q err=%v", got, readErr)
	}
}

func TestUninstallRejectsManifestEntryWithPathTraversalOutsideManagedRoots(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	outside := filepath.Join(home, "escaped.txt")
	mustWriteFile(t, outside, []byte("keep\n"))
	unsafeDest := filepath.Join(cfg.OpencodeDir, "..", "..", "escaped.txt")

	if err := WriteManifest(cfg, []ManifestEntry{{Dest: unsafeDest, Kind: "file"}}); err != nil {
		t.Fatalf("write traversal manifest: %v", err)
	}
	_, err := Uninstall(cfg)
	if err == nil {
		t.Fatalf("expected traversal manifest entry to be rejected")
	}
	if got, readErr := os.ReadFile(outside); readErr != nil || string(got) != "keep\n" {
		t.Fatalf("escaped file must remain untouched, got %q err=%v", got, readErr)
	}
}

func TestUninstallRejectsDirectoryKindManifestEntry(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	dir := filepath.Join(cfg.OpencodeDir, "skills")
	mustMkdirAll(t, dir)
	mustWriteFile(t, filepath.Join(dir, "custom.txt"), []byte("keep\n"))

	if err := WriteManifest(cfg, []ManifestEntry{{Dest: dir, Kind: "directory"}}); err != nil {
		t.Fatalf("write directory manifest: %v", err)
	}
	_, err := Uninstall(cfg)
	if err == nil {
		t.Fatalf("expected directory manifest entry to be rejected")
	}
	if _, statErr := os.Stat(filepath.Join(dir, "custom.txt")); statErr != nil {
		t.Fatalf("directory contents must remain untouched: %v", statErr)
	}
}

// destsOf returns the set of destination paths a Config's mappings would copy.
func destsOf(c Config) map[string]bool {
	set := make(map[string]bool)
	for _, m := range c.mappings() {
		set[m.dest] = true
	}
	return set
}

func TestMappingsEmptyHarnessesIncludesAllTargets(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	dests := destsOf(cfg)
	want := []string{
		filepath.Join(home, ".agents", "skills"),
		filepath.Join(home, ".agents", "AGENTS.md"),
		filepath.Join(home, ".claude", "skills"),
		filepath.Join(home, ".claude", "CLAUDE.md"),
		filepath.Join(home, ".copilot", "skills"),
		filepath.Join(home, ".copilot", "copilot-instructions.md"),
		filepath.Join(home, ".config", "opencode", "skills"),
		filepath.Join(home, ".config", "opencode", "AGENTS.md"),
		filepath.Join(home, ".config", "opencode", "prompts", "sdd"),
		filepath.Join(home, ".config", "opencode", "plugins"),
	}
	if len(dests) != len(want) {
		t.Fatalf("empty Harnesses: got %d targets, want %d: %v", len(dests), len(want), dests)
	}
	for _, d := range want {
		if !dests[d] {
			t.Fatalf("empty Harnesses: missing target %q in %v", d, dests)
		}
	}
}

func TestMappingsHarnessSelection(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)
	cfg.Harnesses = []Harness{HarnessClaude}

	dests := destsOf(cfg)
	if !dests[filepath.Join(home, ".claude", "CLAUDE.md")] || !dests[filepath.Join(home, ".agents", "skills")] {
		t.Fatalf("claude selection should include agents and claude targets: %v", dests)
	}
	if dests[filepath.Join(home, ".config", "opencode", "plugins")] {
		t.Fatalf("claude selection should not include opencode targets: %v", dests)
	}
}

func TestWantsEmptyMeansAll(t *testing.T) {
	cfg := Config{}
	for _, h := range AllHarnesses {
		if !cfg.wants(h) {
			t.Fatalf("empty Harnesses: wants(%q) = false, want true", h)
		}
	}
}

func TestWantsRespectsSelection(t *testing.T) {
	cfg := Config{Harnesses: []Harness{HarnessClaude}}
	if !cfg.wants(HarnessClaude) {
		t.Fatalf("wants(claude) = false, want true")
	}
	if cfg.wants(HarnessOpenCode) {
		t.Fatalf("wants(opencode) = true, want false")
	}
	if cfg.wants(HarnessCopilot) {
		t.Fatalf("wants(copilot) = true, want false")
	}
}

func TestResolveRepoDirValidatesContents(t *testing.T) {
	repo := fakeRepo(t)
	got, err := ResolveRepoDir(repo, "/some/cwd")
	if err != nil {
		t.Fatalf("valid repo rejected: %v", err)
	}
	if got != repo {
		t.Fatalf("ResolveRepoDir = %q, want %q", got, repo)
	}
}

func TestResolveRepoDirFallsBackToCwd(t *testing.T) {
	repo := fakeRepo(t)
	got, err := ResolveRepoDir("", repo)
	if err != nil {
		t.Fatalf("cwd fallback rejected: %v", err)
	}
	if got != repo {
		t.Fatalf("ResolveRepoDir = %q, want %q", got, repo)
	}
}

func TestResolveRepoDirRejectsInvalidRepo(t *testing.T) {
	bare := t.TempDir()
	_, err := ResolveRepoDir(bare, "/cwd")
	if err == nil {
		t.Fatalf("expected error for repo missing skills/ and AGENTS.md")
	}
	if !strings.Contains(err.Error(), "skills") && !strings.Contains(err.Error(), "AGENTS.md") {
		t.Fatalf("error should mention the missing markers, got %v", err)
	}
}
