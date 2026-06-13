package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/diegoagd10/ai-harness-setup/cli/internal/commands"
	"github.com/diegoagd10/ai-harness-setup/cli/internal/install"
	"github.com/diegoagd10/ai-harness-setup/cli/internal/opencode"
	"github.com/diegoagd10/ai-harness-setup/cli/internal/sdd"
)

const usage = `usage: ai-harness <command> [flags] [change]

Commands:
  sdd-status   [change]   Report the SDD phase state for a change.
  sdd-continue [change]   Report the SDD dispatcher routing for a change.
  install      [--repo P] Wire the harness into your home: symlink skills + AGENTS.md,
                          and fully configure OpenCode (opencode.json + prompts + skills + persona).
  uninstall    [--repo P] Remove only the harness artifacts we created (symlinks into the
                          repo and the generated opencode.json).

Flags (sdd commands):
  --json                  Emit indented JSON instead of markdown.
  --instructions          Attach per-phase instructions to the status.
  --cwd <path>            Workspace directory to read openspec/ from.

Flags (install/uninstall):
  --repo <path>           Repo root holding skills/ and AGENTS.md (default: cwd).
`

// Run is the unit-testable entrypoint: it parses args, dispatches to the
// requested subcommand, and renders to stdout. All error and usage text goes to
// stderr. It returns the process exit code so func main stays trivial.
func Run(args []string, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprint(stderr, usage)
		return 2
	}

	command, rest := args[0], args[1:]
	switch command {
	case "sdd-status":
		return runStatus(rest, stdout, stderr, false)
	case "sdd-continue":
		return runStatus(rest, stdout, stderr, true)
	case "install":
		return runInstall(rest, stdout, stderr, false)
	case "uninstall":
		return runInstall(rest, stdout, stderr, true)
	default:
		fmt.Fprintf(stderr, "unknown command %q\n\n%s", command, usage)
		return 2
	}
}

// runStatus drives one subcommand. alwaysInstructions is true for sdd-continue,
// which always attaches instructions; sdd-status only attaches them when the
// --instructions flag is given.
func runStatus(args []string, stdout, stderr io.Writer, alwaysInstructions bool) int {
	opts, code, ok := parseStatusArgs(args, stderr)
	if !ok {
		return code
	}

	includeInstructions := alwaysInstructions || opts.instructions
	status, err := sdd.Resolve(opts.cwd, "", opts.change, includeInstructions)
	if err != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", err)
		return 1
	}

	if opts.json {
		return writeJSON(status, stdout, stderr)
	}

	render := sdd.RenderMarkdown
	if alwaysInstructions {
		render = sdd.RenderDispatcherMarkdown
	}
	fmt.Fprintln(stdout, render(status))
	return 0
}

// statusOptions are the parsed flags and positional for a subcommand.
type statusOptions struct {
	json         bool
	instructions bool
	cwd          string
	change       string
}

// parseStatusArgs parses the shared flag set and enforces "at most one
// positional". On any error it has already written the message to stderr and
// returns ok=false with the exit code to use.
func parseStatusArgs(args []string, stderr io.Writer) (statusOptions, int, bool) {
	var opts statusOptions
	fs := flag.NewFlagSet("ai-harness", flag.ContinueOnError)
	fs.SetOutput(stderr)
	fs.BoolVar(&opts.json, "json", false, "emit indented JSON")
	fs.BoolVar(&opts.instructions, "instructions", false, "attach per-phase instructions")
	fs.StringVar(&opts.cwd, "cwd", "", "workspace directory")

	if err := fs.Parse(args); err != nil {
		return statusOptions{}, 2, false
	}

	positionals := fs.Args()
	if len(positionals) > 1 {
		fmt.Fprintf(stderr, "unexpected argument %q: at most one change name is allowed\n", positionals[1])
		return statusOptions{}, 2, false
	}
	if len(positionals) == 1 {
		opts.change = positionals[0]
	}
	return opts, 0, true
}

// runInstall drives the install/uninstall subcommands. It resolves the repo
// root (--repo or cwd), validates it, builds a $HOME-based Config, runs the
// requested operation, prints the per-target Report, and exits non-zero on
// error. remove selects Uninstall over Install.
func runInstall(args []string, stdout, stderr io.Writer, remove bool) int {
	fs := flag.NewFlagSet("ai-harness", flag.ContinueOnError)
	fs.SetOutput(stderr)
	var repo string
	fs.StringVar(&repo, "repo", "", "repo root holding skills/ and AGENTS.md")
	if err := fs.Parse(args); err != nil {
		return 2
	}

	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", err)
		return 1
	}
	repoDir, err := install.ResolveRepoDir(repo, cwd)
	if err != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", err)
		return 1
	}

	cfg := homeConfig(repoDir)
	op := install.Install
	if remove {
		op = install.Uninstall
	}
	report, opErr := op(cfg)
	for _, o := range report {
		fmt.Fprintln(stdout, formatOutcome(o))
	}
	if opErr != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", opErr)
		return 1
	}

	if cmdErr := syncOpencodeCommands(repoDir, opencodeDir(), remove, stdout); cmdErr != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", cmdErr)
		return 1
	}

	if jsonErr := syncOpencodeConfig(repoDir, opencodeDir(), remove, stdout); jsonErr != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", jsonErr)
		return 1
	}
	return 0
}

// syncOpencodeConfig generates the OpenCode agent config (opencode.json) with
// the real $HOME substituted on install, and removes that generated file on
// uninstall. This is the composition root: the only place $HOME is read; the
// opencode package itself stays host-injectable.
func syncOpencodeConfig(repoDir, opencodeDir string, remove bool, stdout io.Writer) error {
	if remove {
		out, err := opencode.Remove(opencodeDir)
		fmt.Fprintln(stdout, formatOpencodeOutcome(out))
		return err
	}
	out, err := opencode.Generate(repoDir, opencodeDir, os.Getenv("HOME"))
	fmt.Fprintln(stdout, formatOpencodeOutcome(out))
	return err
}

// formatOpencodeOutcome renders the opencode.json generate/remove result as a
// single line, mirroring formatCommandOutcome.
func formatOpencodeOutcome(o opencode.Outcome) string {
	switch o.Action {
	case opencode.ActionGenerated:
		return fmt.Sprintf("  generated %s (from %s)", o.Dest, o.Src)
	case opencode.ActionRemoved:
		return fmt.Sprintf("  removed %s", o.Dest)
	case opencode.ActionAbsent:
		return fmt.Sprintf("  absent %s", o.Dest)
	default:
		return fmt.Sprintf("  %s %s", o.Action, o.Dest)
	}
}

// syncOpencodeCommands generates the OpenCode slash-command files from the
// canonical prompts/commands/ source on install, and removes those same
// generated artifacts on uninstall. The command dir is <OpencodeDir>/commands —
// OpenCode's user-level custom-command location.
func syncOpencodeCommands(repoDir, opencodeDir string, remove bool, stdout io.Writer) error {
	profile := commands.OpenCodeProfile(filepath.Join(opencodeDir, "commands"))
	if remove {
		report, err := commands.Remove(repoDir, profile)
		for _, o := range report {
			fmt.Fprintln(stdout, formatCommandOutcome(o))
		}
		return err
	}
	report, err := commands.Generate(repoDir, profile)
	for _, o := range report {
		fmt.Fprintln(stdout, formatCommandOutcome(o))
	}
	return err
}

// formatCommandOutcome renders one generated/removed command file as a line.
func formatCommandOutcome(o commands.Outcome) string {
	switch o.Action {
	case commands.ActionGenerated:
		return fmt.Sprintf("  generated %s (from %s)", o.Dest, o.Src)
	case commands.ActionRemoved:
		return fmt.Sprintf("  removed %s", o.Dest)
	case commands.ActionAbsent:
		return fmt.Sprintf("  absent %s", o.Dest)
	default:
		return fmt.Sprintf("  %s %s", o.Action, o.Dest)
	}
}

// homeConfig returns a Config with all paths rooted under $HOME. The deep
// module accepts absolute paths so it stays testable against temp dirs.
func homeConfig(repoDir string) install.Config {
	home := os.Getenv("HOME")
	return install.Config{
		RepoDir:     repoDir,
		ClaudeDir:   filepath.Join(home, ".claude"),
		AgentsDir:   filepath.Join(home, ".agents"),
		CopilotDir:  filepath.Join(home, ".copilot"),
		OpencodeDir: opencodeDir(),
		Timestamp:   install.DefaultTimestamp,
	}
}

// opencodeDir returns the OpenCode config root under $HOME. Generated
// slash-commands live in its commands/ subdir. Kept separate from
// install.Config so the symlink module is not burdened with a path it never
// links.
func opencodeDir() string {
	return filepath.Join(os.Getenv("HOME"), ".config", "opencode")
}

// formatOutcome renders one Report entry as a single human-readable line.
func formatOutcome(o install.Outcome) string {
	switch o.Action {
	case install.ActionLinked, install.ActionRelinked:
		return fmt.Sprintf("  %s %s -> %s", o.Action, o.Dest, o.Src)
	case install.ActionBackedUp:
		return fmt.Sprintf("  backed up %s -> %s; linked -> %s", o.Dest, o.Backup, o.Src)
	case install.ActionSourceMissing:
		return fmt.Sprintf("  source missing for %s: %s", o.Dest, o.Src)
	case install.ActionRemoved:
		return fmt.Sprintf("  removed %s (was -> %s)", o.Dest, o.Target)
	case install.ActionSkippedForeign:
		return fmt.Sprintf("  skipped %s (points elsewhere: %s)", o.Dest, o.Target)
	case install.ActionSkippedRealFile:
		return fmt.Sprintf("  skipped %s (real file)", o.Dest)
	case install.ActionAbsent:
		return fmt.Sprintf("  absent %s", o.Dest)
	default:
		return fmt.Sprintf("  %s %s", o.Action, o.Dest)
	}
}

// writeJSON emits status as 2-space indented JSON to stdout.
func writeJSON(status sdd.Status, stdout, stderr io.Writer) int {
	payload, err := json.MarshalIndent(status, "", "  ")
	if err != nil {
		fmt.Fprintf(stderr, "ai-harness: marshal status: %v\n", err)
		return 1
	}
	fmt.Fprintln(stdout, string(payload))
	return 0
}
