package install

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeRepo builds a minimal valid repo (skills/ dir, AGENTS.md, and the
// prompts/sdd dir the OpenCode links point at) under a temp dir and returns its
// path.
func fakeRepo(t *testing.T) string {
	t.Helper()
	repo := t.TempDir()
	if err := os.MkdirAll(filepath.Join(repo, "skills"), 0o755); err != nil {
		t.Fatalf("mkdir skills: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(repo, "prompts", "sdd"), 0o755); err != nil {
		t.Fatalf("mkdir prompts/sdd: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(repo, "agent-clis", "opencode", "plugins"), 0o755); err != nil {
		t.Fatalf("mkdir agent-clis/opencode/plugins: %v", err)
	}
	if err := os.WriteFile(filepath.Join(repo, "AGENTS.md"), []byte("# Agents\n"), 0o644); err != nil {
		t.Fatalf("write AGENTS.md: %v", err)
	}
	return repo
}

// fixedTimestamp returns a deterministic timestamp source for backup names.
func fixedTimestamp() func() string {
	return func() string { return "20240101000000" }
}

// cfgFor builds a Config rooted at repo with all home subdirs under home,
// including the OpenCode config dir whose skills/AGENTS.md/prompts links the
// install flow now owns.
func cfgFor(repo, home string) Config {
	return Config{
		RepoDir:     repo,
		ClaudeDir:   filepath.Join(home, ".claude"),
		AgentsDir:   filepath.Join(home, ".agents"),
		CopilotDir:  filepath.Join(home, ".copilot"),
		OpencodeDir: filepath.Join(home, ".config", "opencode"),
		Timestamp:   fixedTimestamp(),
	}
}

// findOutcome returns the outcome whose Dest matches, or fails the test.
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

func TestInstallLinksAllTargets(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	report, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install returned error: %v", err)
	}

	cases := []struct {
		dest string
		src  string
	}{
		{filepath.Join(home, ".claude", "skills"), filepath.Join(repo, "skills")},
		{filepath.Join(home, ".claude", "CLAUDE.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".agents", "skills"), filepath.Join(repo, "skills")},
		{filepath.Join(home, ".agents", "AGENTS.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".copilot", "copilot-instructions.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".config", "opencode", "skills"), filepath.Join(repo, "skills")},
		{filepath.Join(home, ".config", "opencode", "AGENTS.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".config", "opencode", "prompts", "sdd"), filepath.Join(repo, "prompts", "sdd")},
		{filepath.Join(home, ".config", "opencode", "plugins"), filepath.Join(repo, "agent-clis", "opencode", "plugins")},
	}

	if len(report) != len(cases) {
		t.Fatalf("expected %d outcomes, got %d: %+v", len(cases), len(report), report)
	}

	for _, c := range cases {
		got, err := os.Readlink(c.dest)
		if err != nil {
			t.Fatalf("expected symlink at %s: %v", c.dest, err)
		}
		if got != c.src {
			t.Fatalf("symlink %s points to %q, want %q", c.dest, got, c.src)
		}
		o := findOutcome(t, report, c.dest)
		if o.Action != ActionLinked {
			t.Fatalf("dest %s: expected action %q, got %q", c.dest, ActionLinked, o.Action)
		}
	}
}

func TestInstallRelinksExistingSymlink(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	dest := filepath.Join(home, ".claude", "skills")
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	// Pre-existing symlink pointing at a stale target.
	stale := filepath.Join(home, "stale-target")
	if err := os.Symlink(stale, dest); err != nil {
		t.Fatalf("pre-symlink: %v", err)
	}

	report, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install error: %v", err)
	}

	got, err := os.Readlink(dest)
	if err != nil {
		t.Fatalf("readlink: %v", err)
	}
	want := filepath.Join(repo, "skills")
	if got != want {
		t.Fatalf("relink target = %q, want %q", got, want)
	}
	o := findOutcome(t, report, dest)
	if o.Action != ActionRelinked {
		t.Fatalf("expected action %q, got %q", ActionRelinked, o.Action)
	}
}

func TestInstallBacksUpRealFileBeforeLinking(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	dest := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	original := []byte("my own claude instructions\n")
	if err := os.WriteFile(dest, original, 0o644); err != nil {
		t.Fatalf("write real file: %v", err)
	}

	report, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install error: %v", err)
	}

	// dest is now a symlink to repo/AGENTS.md
	got, err := os.Readlink(dest)
	if err != nil {
		t.Fatalf("expected symlink at dest after backup: %v", err)
	}
	wantSrc := filepath.Join(repo, "AGENTS.md")
	if got != wantSrc {
		t.Fatalf("symlink target = %q, want %q", got, wantSrc)
	}

	// The backup file exists at the deterministic name and holds the original bytes.
	backup := dest + ".bak.20240101000000"
	data, err := os.ReadFile(backup)
	if err != nil {
		t.Fatalf("expected backup at %s: %v", backup, err)
	}
	if string(data) != string(original) {
		t.Fatalf("backup content = %q, want %q", data, original)
	}

	o := findOutcome(t, report, dest)
	if o.Action != ActionBackedUp {
		t.Fatalf("expected action %q, got %q", ActionBackedUp, o.Action)
	}
	if o.Backup != backup {
		t.Fatalf("outcome backup = %q, want %q", o.Backup, backup)
	}
}

func TestInstallMissingSourceIsError(t *testing.T) {
	repo := t.TempDir() // no skills/, no AGENTS.md
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	report, err := Install(cfg)
	if err == nil {
		t.Fatalf("expected error when sources are missing")
	}
	// Outcomes for the missing sources should be reported as failed.
	dest := filepath.Join(home, ".claude", "skills")
	o := findOutcome(t, report, dest)
	if o.Action != ActionSourceMissing {
		t.Fatalf("expected action %q, got %q", ActionSourceMissing, o.Action)
	}
}

func TestInstallIsIdempotent(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	if _, err := Install(cfg); err != nil {
		t.Fatalf("first install: %v", err)
	}
	report, err := Install(cfg)
	if err != nil {
		t.Fatalf("second install: %v", err)
	}
	// Second run sees symlinks -> all relinked, no backups created.
	for _, o := range report {
		if o.Action != ActionRelinked {
			t.Fatalf("second install dest %s: expected %q, got %q", o.Dest, ActionRelinked, o.Action)
		}
	}
	// No stray .bak files were created.
	entries, _ := filepath.Glob(filepath.Join(home, ".claude", "*.bak.*"))
	if len(entries) != 0 {
		t.Fatalf("idempotent run created backups: %v", entries)
	}
}

func TestUninstallRemovesOnlyRepoPointingLinks(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	if _, err := Install(cfg); err != nil {
		t.Fatalf("install: %v", err)
	}

	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall error: %v", err)
	}

	dest := filepath.Join(home, ".claude", "skills")
	if _, err := os.Lstat(dest); !os.IsNotExist(err) {
		t.Fatalf("expected %s removed, lstat err = %v", dest, err)
	}
	o := findOutcome(t, report, dest)
	if o.Action != ActionRemoved {
		t.Fatalf("expected action %q, got %q", ActionRemoved, o.Action)
	}
}

func TestInstallLinksOpencodePromptsSkillsAndPersona(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	report, err := Install(cfg)
	if err != nil {
		t.Fatalf("Install error: %v", err)
	}

	cases := []struct {
		dest string
		src  string
	}{
		{filepath.Join(home, ".config", "opencode", "skills"), filepath.Join(repo, "skills")},
		{filepath.Join(home, ".config", "opencode", "AGENTS.md"), filepath.Join(repo, "AGENTS.md")},
		{filepath.Join(home, ".config", "opencode", "prompts", "sdd"), filepath.Join(repo, "prompts", "sdd")},
		{filepath.Join(home, ".config", "opencode", "plugins"), filepath.Join(repo, "agent-clis", "opencode", "plugins")},
	}
	for _, c := range cases {
		got, err := os.Readlink(c.dest)
		if err != nil {
			t.Fatalf("expected symlink at %s: %v", c.dest, err)
		}
		if got != c.src {
			t.Fatalf("symlink %s points to %q, want %q", c.dest, got, c.src)
		}
		o := findOutcome(t, report, c.dest)
		if o.Action != ActionLinked {
			t.Fatalf("dest %s: expected action %q, got %q", c.dest, ActionLinked, o.Action)
		}
	}
}

func TestUninstallRemovesOpencodeRepoPointingLinks(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	if _, err := Install(cfg); err != nil {
		t.Fatalf("install: %v", err)
	}

	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall error: %v", err)
	}

	for _, dest := range []string{
		filepath.Join(home, ".config", "opencode", "skills"),
		filepath.Join(home, ".config", "opencode", "AGENTS.md"),
		filepath.Join(home, ".config", "opencode", "prompts", "sdd"),
		filepath.Join(home, ".config", "opencode", "plugins"),
	} {
		if _, err := os.Lstat(dest); !os.IsNotExist(err) {
			t.Fatalf("expected %s removed, lstat err = %v", dest, err)
		}
		o := findOutcome(t, report, dest)
		if o.Action != ActionRemoved {
			t.Fatalf("dest %s: expected action %q, got %q", dest, ActionRemoved, o.Action)
		}
	}
}

func TestUninstallSkipsForeignSymlink(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	dest := filepath.Join(home, ".claude", "skills")
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	// Symlink points OUTSIDE the repo.
	foreign := filepath.Join(home, "somewhere-else")
	if err := os.Symlink(foreign, dest); err != nil {
		t.Fatalf("symlink: %v", err)
	}

	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall error: %v", err)
	}

	// Still present (not removed).
	got, err := os.Readlink(dest)
	if err != nil {
		t.Fatalf("foreign link should remain: %v", err)
	}
	if got != foreign {
		t.Fatalf("foreign link mutated: %q", got)
	}
	o := findOutcome(t, report, dest)
	if o.Action != ActionSkippedForeign {
		t.Fatalf("expected action %q, got %q", ActionSkippedForeign, o.Action)
	}
}

func TestUninstallSkipsRealFile(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	dest := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(dest, []byte("real\n"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall error: %v", err)
	}

	if _, err := os.Stat(dest); err != nil {
		t.Fatalf("real file should remain: %v", err)
	}
	o := findOutcome(t, report, dest)
	if o.Action != ActionSkippedRealFile {
		t.Fatalf("expected action %q, got %q", ActionSkippedRealFile, o.Action)
	}
}

func TestUninstallReportsAbsent(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	report, err := Uninstall(cfg)
	if err != nil {
		t.Fatalf("uninstall error: %v", err)
	}
	dest := filepath.Join(home, ".copilot", "copilot-instructions.md")
	o := findOutcome(t, report, dest)
	if o.Action != ActionAbsent {
		t.Fatalf("expected action %q, got %q", ActionAbsent, o.Action)
	}
}

func TestUninstallNeverTouchesBackups(t *testing.T) {
	repo := fakeRepo(t)
	home := t.TempDir()
	cfg := cfgFor(repo, home)

	// Create a real file so install backs it up, then re-install relinks.
	dest := filepath.Join(home, ".claude", "CLAUDE.md")
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(dest, []byte("orig\n"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if _, err := Install(cfg); err != nil {
		t.Fatalf("install: %v", err)
	}
	backup := dest + ".bak.20240101000000"

	if _, err := Uninstall(cfg); err != nil {
		t.Fatalf("uninstall: %v", err)
	}
	if _, err := os.Stat(backup); err != nil {
		t.Fatalf("backup must survive uninstall: %v", err)
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
	bare := t.TempDir() // no skills/, no AGENTS.md

	_, err := ResolveRepoDir(bare, "/cwd")
	if err == nil {
		t.Fatalf("expected error for repo missing skills/ and AGENTS.md")
	}
	if !strings.Contains(err.Error(), "skills") && !strings.Contains(err.Error(), "AGENTS.md") {
		t.Fatalf("error should mention the missing markers, got %v", err)
	}
}
