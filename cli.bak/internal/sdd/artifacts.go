package sdd

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const specFileName = "spec.md"

// discoverArtifactPaths finds the on-disk paths for every artifact kind under a
// change root. Single-file artifacts yield a one-element slice when present;
// specs are discovered by a recursive walk for files named exactly spec.md.
func discoverArtifactPaths(changeRoot string) (ArtifactPaths, error) {
	paths := emptyArtifactPaths()
	paths.Proposal = existingFile(filepath.Join(changeRoot, "proposal.md"))
	paths.Design = existingFile(filepath.Join(changeRoot, "design.md"))
	paths.Tasks = existingFile(filepath.Join(changeRoot, "tasks.md"))
	paths.ApplyProgress = existingFile(filepath.Join(changeRoot, "apply-progress.md"))
	paths.VerifyReport = existingFile(filepath.Join(changeRoot, "verify-report.md"))

	specs, err := findSpecFiles(filepath.Join(changeRoot, "specs"))
	if err != nil {
		return ArtifactPaths{}, err
	}
	paths.Specs = specs
	return paths, nil
}

// classifyArtifacts maps each discovered artifact to its completeness state.
func classifyArtifacts(changeRoot string, paths ArtifactPaths) map[string]ArtifactState {
	return map[string]ArtifactState{
		"proposal":      fileArtifactState(paths.Proposal),
		"specs":         specsArtifactState(paths.Specs, filepath.Join(changeRoot, "specs")),
		"design":        fileArtifactState(paths.Design),
		"tasks":         fileArtifactState(paths.Tasks),
		"applyProgress": fileArtifactState(paths.ApplyProgress),
		"verifyReport":  fileArtifactState(paths.VerifyReport),
	}
}

// existingFile returns a single-element slice with path when the file exists,
// otherwise an empty slice.
func existingFile(path string) []string {
	if _, err := os.Stat(path); err == nil {
		return []string{path}
	}
	return []string{}
}

// findSpecFiles recursively collects every file named exactly spec.md under
// specsRoot, sorted. A missing specs directory yields an empty list.
func findSpecFiles(specsRoot string) ([]string, error) {
	var files []string
	err := filepath.WalkDir(specsRoot, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if !entry.IsDir() && entry.Name() == specFileName {
			files = append(files, path)
		}
		return nil
	})
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}
	sort.Strings(files)
	return files, nil
}

// fileArtifactState classifies a single-file artifact: missing when absent,
// partial when present but blank, done when it has non-whitespace content.
func fileArtifactState(paths []string) ArtifactState {
	if len(paths) == 0 {
		return ArtifactMissing
	}
	if hasContent(paths[0]) {
		return ArtifactDone
	}
	return ArtifactPartial
}

// specsArtifactState classifies the specs artifact: missing when no specs dir,
// partial when the dir is non-empty but lacks usable spec.md files, done when
// every discovered spec.md has content.
func specsArtifactState(paths []string, specsRoot string) ArtifactState {
	if len(paths) == 0 {
		if entries, err := os.ReadDir(specsRoot); err == nil && len(entries) > 0 {
			return ArtifactPartial
		}
		return ArtifactMissing
	}
	for _, path := range paths {
		if !hasContent(path) {
			return ArtifactPartial
		}
	}
	return ArtifactDone
}

// hasContent reports whether the file exists and contains non-whitespace text.
func hasContent(path string) bool {
	content, err := os.ReadFile(path)
	return err == nil && strings.TrimSpace(string(content)) != ""
}
