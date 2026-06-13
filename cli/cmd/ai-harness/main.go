// Command ai-harness is the entry point for the SDD dispatcher binary.
//
// This file does one thing: hand the process arguments to Run and exit with its
// code. All command behavior (flag parsing, subcommand dispatch, rendering)
// lives in run.go; all SDD logic lives in the internal/sdd package.
package main

import "os"

func main() {
	os.Exit(Run(os.Args[1:], os.Stdin, isInteractive(os.Stdin), os.Stdout, os.Stderr))
}
