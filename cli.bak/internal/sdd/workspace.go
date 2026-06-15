package sdd

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// resolveRoot picks the workspace root (workspaceRoot when set, else cwd, else
// the process working directory) and verifies it is an existing directory.
func resolveRoot(cwd, workspaceRoot string) (string, error) {
	candidate := workspaceRoot
	if strings.TrimSpace(candidate) == "" {
		candidate = cwd
	}

	root, err := absOrWorkingDir(candidate)
	if err != nil {
		return "", err
	}

	info, err := os.Stat(root)
	if err != nil {
		return "", err
	}
	if !info.IsDir() {
		return "", fmt.Errorf("workspace root is not a directory: %s", root)
	}
	return root, nil
}

// absOrWorkingDir resolves path to an absolute path, falling back to the
// process working directory when path is blank.
func absOrWorkingDir(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		return os.Getwd()
	}
	return filepath.Abs(path)
}

// listActiveChanges returns the sorted names of active changes: every direct
// subdirectory of openspec/changes/ except the reserved archive/ directory.
// A missing changes directory yields an empty list, not an error.
func listActiveChanges(root string) ([]string, error) {
	entries, err := os.ReadDir(filepath.Join(root, "openspec", "changes"))
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}

	changes := make([]string, 0, len(entries))
	for _, entry := range entries {
		if entry.IsDir() && entry.Name() != archiveDirName {
			changes = append(changes, entry.Name())
		}
	}
	sort.Strings(changes)
	return changes, nil
}

// contains reports whether needle is in values.
func contains(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}

// firstPath returns paths[0] or "" if empty.
func firstPath(paths []string) string {
	if len(paths) == 0 {
		return ""
	}
	return paths[0]
}
