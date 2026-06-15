package sdd

import (
	"os"
	"path/filepath"
	"testing"
)

func writeReport(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "verify-report.md")
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("WriteFile() error = %v", err)
	}
	return path
}

func TestReportIsClearlyPassing(t *testing.T) {
	tests := []struct {
		name    string
		content string
		want    bool
	}{
		{name: "empty path", content: "", want: false},
		{name: "blank report", content: "   \n\t\n", want: false},
		{name: "bare PASS line", content: "PASS\n", want: true},
		{name: "status field pass", content: "# Verify\nStatus: PASS\n", want: true},
		{name: "all checks passed phrase", content: "# Verify\nAll checks passed.\n", want: true},
		{name: "ready for archive phrase", content: "Ready for archive\n", want: true},
		{name: "pass with warnings verdict", content: "Verdict: PASS WITH WARNINGS\n", want: true},
		{name: "no pass signal at all", content: "# Verify\nSome prose only.\n", want: false},
		{name: "pass but failed count nonzero", content: "PASS\nfailed: 2\n", want: false},
		{name: "pass but zero failed is benign", content: "PASS\nfailed: 0\n", want: true},
		{name: "N failed reversed order", content: "PASS\n3 failed\n", want: false},
		{name: "critical none is benign", content: "PASS\n**CRITICAL**: None\n", want: true},
		{name: "critical with content blocks", content: "PASS\ncritical: data loss\n", want: false},
		{name: "blockers no blockers benign", content: "PASS\nBlockers: no blockers\n", want: true},
		{name: "verdict fail blocks", content: "Verdict: FAIL\n", want: false},
		{name: "glyph fail status blocks", content: "PASS\n❌ FAILING\n", want: false},
		{name: "pass colon no blocks", content: "PASS: no\n", want: false},
		{name: "not complete blocks", content: "PASS\nWork is not complete\n", want: false},
		{name: "todo blocks", content: "PASS\nTODO: run e2e\n", want: false},
		{name: "pending blocks", content: "PASS\nPENDING review\n", want: false},
		{name: "bullet field pass", content: "- **Verdict**: PASS\n", want: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := ""
			if tt.content != "" {
				path = writeReport(t, tt.content)
			}
			got, err := reportIsClearlyPassing(path)
			if err != nil {
				t.Fatalf("reportIsClearlyPassing() error = %v", err)
			}
			if got != tt.want {
				t.Fatalf("reportIsClearlyPassing(%q) = %v, want %v", tt.content, got, tt.want)
			}
		})
	}
}
