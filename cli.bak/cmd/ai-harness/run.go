package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/diegoagd10/ai-harness-setup/cli/internal/commands"
	"github.com/diegoagd10/ai-harness-setup/cli/internal/install"
	"github.com/diegoagd10/ai-harness-setup/cli/internal/opencode"
	"github.com/diegoagd10/ai-harness-setup/cli/internal/sdd"
)

const usage = `usage: ai-harness <command> [flags] [change]

Commands:
  sdd-status   [change]   Report the SDD phase state for a change.
  sdd-continue [change]   Report the SDD dispatcher routing for a change.
	install      [--repo P] Wire selected harnesses into your home: always copy the
	                          generic .agents config, plus per-harness artifacts for the harnesses
	                          you pick (claude, copilot, opencode).
	uninstall              Remove every harness artifact we created (manifest-listed copies,
	                          generated commands, and the generated opencode.json).

Flags (sdd commands):
  --json                  Emit indented JSON instead of markdown.
  --instructions          Attach per-phase instructions to the status.
  --cwd <path>            Workspace directory to read openspec/ from.

Flags (install/uninstall):
  --repo <path>           Repo root holding skills/ and AGENTS.md (default: cwd).
  --harness <list>        Comma-separated harnesses to install: claude,copilot,opencode.
                          If omitted, install prompts interactively on a TTY, else picks all.
                          uninstall always cleans every harness regardless of this flag.
`

// Run is the unit-testable entrypoint: it parses args, dispatches to the
// requested subcommand, and renders to stdout. All error and usage text goes to
// stderr. It returns the process exit code so func main stays trivial.
//
// stdin and interactive are injected (not read from os.Stdin) so the install
// picker is testable: interactive says whether a human is present, stdin is what
// the picker reads. main wires os.Stdin and isInteractive(os.Stdin).
func Run(args []string, stdin io.Reader, interactive bool, stdout, stderr io.Writer) int {
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
		return runInstall(rest, stdin, interactive, stdout, stderr, false)
	case "uninstall":
		return runInstall(rest, stdin, interactive, stdout, stderr, true)
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

// runInstall drives the install/uninstall subcommands. Install resolves and
// validates the repo root (--repo or cwd); uninstall is manifest-only and does
// not require the source repo. Both paths build a $HOME-based Config, print the
// per-target Report, and exit non-zero on error.
func runInstall(args []string, stdin io.Reader, interactive bool, stdout, stderr io.Writer, remove bool) int {
	fs := flag.NewFlagSet("ai-harness", flag.ContinueOnError)
	fs.SetOutput(stderr)
	var repo, harness string
	fs.StringVar(&repo, "repo", "", "repo root holding skills/ and AGENTS.md (install only)")
	fs.StringVar(&harness, "harness", "", "comma-separated harnesses: claude,copilot,opencode")
	if err := fs.Parse(args); err != nil {
		return 2
	}

	repoDir := repo
	var err error
	if !remove {
		var cwd string
		cwd, err = os.Getwd()
		if err != nil {
			fmt.Fprintf(stderr, "ai-harness: %v\n", err)
			return 1
		}
		repoDir, err = install.ResolveRepoDir(repo, cwd)
		if err != nil {
			fmt.Fprintf(stderr, "ai-harness: %v\n", err)
			return 1
		}
	}

	// Uninstall always targets every harness; selection is install-only.
	selection := install.AllHarnesses
	if !remove {
		selection, err = resolveSelection(harness, stdin, interactive, stdout)
		if err != nil {
			fmt.Fprintf(stderr, "ai-harness: %v\n", err)
			return 1
		}
	}

	cfg := homeConfig(repoDir)
	cfg.Harnesses = selection
	var (
		report  install.Report
		entries []install.ManifestEntry
		opErr   error
	)
	if remove {
		report, opErr = install.Uninstall(cfg)
	} else {
		report, entries, opErr = install.Install(cfg)
	}
	for _, o := range report {
		fmt.Fprintln(stdout, formatOutcome(o))
	}

	if !remove {
		var manifestErr error
		if wantsHarness(selection, install.HarnessOpenCode) {
			var cmdEntries []install.ManifestEntry
			cmdEntries, manifestErr = syncOpencodeCommands(repoDir, opencodeDir(), stdout)
			entries = append(entries, cmdEntries...)
			if manifestErr == nil {
				var configEntries []install.ManifestEntry
				configEntries, manifestErr = syncOpencodeConfig(repoDir, opencodeDir(), stdout)
				entries = append(entries, configEntries...)
			}
		}
		if opErr != nil || manifestErr != nil {
			if len(entries) > 0 {
				if err := install.WriteManifest(cfg, entries); err != nil {
					fmt.Fprintf(stderr, "ai-harness: %v\n", err)
					return 1
				}
			}
			if opErr != nil {
				fmt.Fprintf(stderr, "ai-harness: %v\n", opErr)
				return 1
			}
			fmt.Fprintf(stderr, "ai-harness: %v\n", manifestErr)
			return 1
		}
		if err := install.WriteManifest(cfg, entries); err != nil {
			fmt.Fprintf(stderr, "ai-harness: %v\n", err)
			return 1
		}
	}
	if opErr != nil {
		fmt.Fprintf(stderr, "ai-harness: %v\n", opErr)
		return 1
	}
	return 0
}

// resolveSelection decides which harnesses to install: an explicit --harness
// flag wins; otherwise, when a human is present, the picker prompts on stdin;
// otherwise (CI / scripts) every harness is selected.
func resolveSelection(harness string, stdin io.Reader, interactive bool, stdout io.Writer) ([]install.Harness, error) {
	if strings.TrimSpace(harness) != "" {
		return parseHarnesses(harness)
	}
	if interactive {
		return promptHarnesses(stdin, stdout)
	}
	return install.AllHarnesses, nil
}

// wantsHarness reports whether h is in the selection.
func wantsHarness(selection []install.Harness, h install.Harness) bool {
	for _, s := range selection {
		if s == h {
			return true
		}
	}
	return false
}

// isInteractive reports whether f is a terminal (a character device), so the CLI
// only prompts when a human is actually present.
func isInteractive(f *os.File) bool {
	info, err := f.Stat()
	if err != nil {
		return false
	}
	return info.Mode()&os.ModeCharDevice != 0
}

// parseHarnesses turns a comma-separated list into a validated harness slice.
// Tokens are trimmed and lower-cased; an unknown token is an error naming it.
func parseHarnesses(list string) ([]install.Harness, error) {
	var selected []install.Harness
	for _, raw := range strings.Split(list, ",") {
		token := strings.ToLower(strings.TrimSpace(raw))
		if token == "" {
			continue
		}
		h, ok := harnessFromToken(token)
		if !ok {
			return nil, fmt.Errorf("unknown harness %q: choose from claude, copilot, opencode", token)
		}
		selected = append(selected, h)
	}
	if len(selected) == 0 {
		return install.AllHarnesses, nil
	}
	return selected, nil
}

// harnessFromToken maps a number (1/2/3, matching the prompt's listing) or a
// name to a Harness. The numbering follows install.AllHarnesses order.
func harnessFromToken(token string) (install.Harness, bool) {
	switch token {
	case "1", string(install.AllHarnesses[0]):
		return install.AllHarnesses[0], true
	case "2", string(install.AllHarnesses[1]):
		return install.AllHarnesses[1], true
	case "3", string(install.AllHarnesses[2]):
		return install.AllHarnesses[2], true
	}
	return "", false
}

// promptHarnesses prints the harness menu to out, reads one line from in, and
// returns the selection. It is pure over (in, out) so tests can feed a reader.
// Empty input or "all" selects every harness; numbers and names may be mixed
// and separated by spaces or commas.
func promptHarnesses(in io.Reader, out io.Writer) ([]install.Harness, error) {
	fmt.Fprintln(out, "Select harnesses to install (default: all):")
	fmt.Fprintln(out, "  1) opencode  - full config: skills, AGENTS.md, prompts/sdd, plugins, opencode.json")
	fmt.Fprintln(out, "  2) claude    - skills + CLAUDE.md")
	fmt.Fprintln(out, "  3) copilot   - skills + copilot-instructions.md")
	fmt.Fprint(out, "Enter numbers or names (comma/space separated), or blank for all: ")

	// A read that yields no data (EOF with an empty line, e.g. stdin closed or
	// redirected from /dev/null) means no choice was made: fall back to the
	// documented safe default of all harnesses.
	line, _ := bufio.NewReader(in).ReadString('\n')
	return parseSelectionLine(line)
}

// parseSelectionLine interprets a single prompt line into a harness selection.
// Blank or "all" => every harness; otherwise each comma/space token is resolved
// as a number or name.
func parseSelectionLine(line string) ([]install.Harness, error) {
	trimmed := strings.TrimSpace(line)
	if trimmed == "" || strings.EqualFold(trimmed, "all") {
		return install.AllHarnesses, nil
	}
	fields := strings.FieldsFunc(trimmed, func(r rune) bool {
		return r == ',' || r == ' '
	})
	var selected []install.Harness
	for _, field := range fields {
		h, ok := harnessFromToken(strings.ToLower(field))
		if !ok {
			return nil, fmt.Errorf("unknown harness %q: choose from claude, copilot, opencode", field)
		}
		selected = append(selected, h)
	}
	return selected, nil
}

// syncOpencodeConfig generates the OpenCode agent config (opencode.json) with
// the real $HOME substituted on install. This is the composition root: the only
// place $HOME is read; the opencode package itself stays host-injectable.
func syncOpencodeConfig(repoDir, opencodeDir string, stdout io.Writer) ([]install.ManifestEntry, error) {
	out, err := opencode.Generate(repoDir, opencodeDir, os.Getenv("HOME"))
	fmt.Fprintln(stdout, formatOpencodeOutcome(out))
	if err != nil {
		return nil, err
	}
	return []install.ManifestEntry{{Dest: out.Dest, Source: out.Src, Kind: "file"}}, nil
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
// canonical prompts/commands/ source. The command dir is <OpencodeDir>/commands
// — OpenCode's user-level custom-command location.
func syncOpencodeCommands(repoDir, opencodeDir string, stdout io.Writer) ([]install.ManifestEntry, error) {
	profile := commands.OpenCodeProfile(filepath.Join(opencodeDir, "commands"))
	report, err := commands.Generate(repoDir, profile)
	for _, o := range report {
		fmt.Fprintln(stdout, formatCommandOutcome(o))
	}
	entries := make([]install.ManifestEntry, 0, len(report))
	for _, o := range report {
		entries = append(entries, install.ManifestEntry{Dest: o.Dest, Source: o.Src, Kind: "file"})
	}
	return entries, err
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
// install.Config so the copy/ownership module is not burdened with a path it
// never manages.
func opencodeDir() string {
	return filepath.Join(os.Getenv("HOME"), ".config", "opencode")
}

// formatOutcome renders one Report entry as a single human-readable line.
func formatOutcome(o install.Outcome) string {
	switch o.Action {
	case install.ActionCopied, install.ActionOverwritten:
		return fmt.Sprintf("  %s %s <- %s", o.Action, o.Dest, o.Src)
	case install.ActionSourceMissing:
		return fmt.Sprintf("  source missing for %s: %s", o.Dest, o.Src)
	case install.ActionRemoved:
		if o.Target != "" {
			return fmt.Sprintf("  removed %s (from %s)", o.Dest, o.Target)
		}
		return fmt.Sprintf("  removed %s", o.Dest)
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
