package sdd

import (
	"os"
	"regexp"
	"strings"
)

// taskCheckbox matches a markdown task line: a bullet (-, *) or ordered marker
// (1. / 1)) followed by a [ ], [x], or [X] checkbox. The captured group is the
// checkbox character; lines that do not match are ignored.
var taskCheckbox = regexp.MustCompile(`^\s*(?:[-*]|\d+[.)])\s+\[([ xX])\]`)

// countTaskProgress parses tasks.md and tallies its checkbox tasks. An empty
// path (no tasks.md) yields a zero TaskProgress. AllComplete requires at least
// one task and zero pending.
func countTaskProgress(tasksPath string) (TaskProgress, error) {
	if tasksPath == "" {
		return TaskProgress{}, nil
	}
	content, err := os.ReadFile(tasksPath)
	if err != nil {
		return TaskProgress{}, err
	}

	var progress TaskProgress
	for _, line := range strings.Split(string(content), "\n") {
		match := taskCheckbox.FindStringSubmatch(line)
		if match == nil {
			continue
		}
		progress.Total++
		if isCheckedMark(match[1]) {
			progress.Completed++
		} else {
			progress.Pending++
		}
	}
	progress.AllComplete = progress.Total > 0 && progress.Pending == 0
	return progress, nil
}

func isCheckedMark(mark string) bool {
	return mark == "x" || mark == "X"
}
