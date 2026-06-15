package sdd

import (
	"os"
	"regexp"
	"strings"
)

// The verify-report heuristic decides whether a verify-report.md "clearly
// passes". A report is clearly passing when it has at least one pass-signal
// line AND zero blocker lines. The patterns below mirror the reference
// implementation exactly — this heuristic is the trickiest contract in the
// package and small wording differences change the outcome.
//
// See the test cases in verifyreport_test.go for the specific wording patterns
// that are known to matter. Patterns that differ from these regexes — even
// subtly — have produced wrong outcomes in practice.
var (
	// reportField parses an optionally-bulleted, optionally-bold "Label: value"
	// line, capturing the label and the value.
	reportField = regexp.MustCompile(`^\s*(?:[-*]\s+)?(?:\*\*)?([A-Za-z][A-Za-z\s-]*?)(?:\*\*)?\s*:\s*(.*)$`)

	// passValue matches a value that, on its own, signals a pass.
	passValue = regexp.MustCompile(`(?i)^(?:PASS|PASSED|PASS\s+WITH\s+WARNINGS|SUCCESS|SUCCESSFUL)$`)

	// failValue matches a value that, on its own, signals a failure.
	failValue = regexp.MustCompile(`(?i)^(?:FAIL|FAILED|FAILING|FAILURE|BLOCKED|UNTESTED)$`)

	// glyphFailStatus matches a red-cross glyph followed by a fail keyword.
	glyphFailStatus = regexp.MustCompile(`(?i)❌\s*(?:FAIL|FAILED|FAILING|FAILURE|BLOCKED|UNTESTED)\b`)

	// passNegation matches "not passed"-style phrases or "pass: no" style denials.
	passNegation = regexp.MustCompile(`(?i)\bnot\s+(?:pass|passed|passing|successful|complete|completed)\b|\b(?:pass|passed|success|successful|complete|completed)\s*:\s*no\b`)

	// pendingWord matches outstanding-work markers.
	pendingWord = regexp.MustCompile(`(?i)\b(?:TODO|PENDING)\b`)

	// benignValue matches values that, for an otherwise-blocking field, are safe.
	benignValue = regexp.MustCompile(`(?i)^(?:none|no|n/a|not\s+applicable|0\s+(?:failed|blockers?|critical|issues?))\.?$`)

	// failedCountPatterns capture a numeric failed count in either order.
	failedCountPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\bfailed\s*:\s*(\d+)\b`),
		regexp.MustCompile(`(?i)\b(\d+)\s+failed\b`),
	}
)

// reportIsClearlyPassing reads the verify report and reports whether it clearly
// passes. An empty path or blank report is not passing. Any blocker line wins.
func reportIsClearlyPassing(path string) (bool, error) {
	if path == "" {
		return false, nil
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return false, err
	}
	if strings.TrimSpace(string(content)) == "" {
		return false, nil
	}

	hasPassSignal := false
	for _, raw := range strings.Split(string(content), "\n") {
		line := strings.TrimSpace(raw)
		if lineHasBlocker(line) {
			return false, nil
		}
		if lineHasPassSignal(line) {
			hasPassSignal = true
		}
	}
	return hasPassSignal, nil
}

// lineHasBlocker reports whether a single line signals that the report does not
// clearly pass.
func lineHasBlocker(line string) bool {
	if line == "" {
		return false
	}
	if passNegation.MatchString(line) || pendingWord.MatchString(line) {
		return true
	}
	if glyphFailStatus.MatchString(line) {
		return true
	}
	for _, pattern := range failedCountPatterns {
		if match := pattern.FindStringSubmatch(line); len(match) == 2 && match[1] != "0" {
			return true
		}
	}
	if label, value, ok := parseReportField(line); ok && fieldIsBlocking(label, value) {
		return true
	}
	return failValue.MatchString(stripMarkdownSignal(line))
}

// fieldIsBlocking decides whether a "Label: value" field is a blocker. Blocker
// fields (critical, blocker, ...) block unless their value is benign; verdict
// fields (status, result, ...) block when their value reads as a failure.
func fieldIsBlocking(label, value string) bool {
	trimmed := strings.TrimSpace(value)
	switch normalizeFieldName(label) {
	case "critical", "blocker", "blockers", "verificationblocker", "verificationblockers", "failure", "fail", "failed":
		return !valueIsBenign(trimmed)
	case "verdict", "status", "result", "verification", "finalverdict", "build", "tests":
		return failValue.MatchString(stripMarkdownSignal(trimmed))
	default:
		return false
	}
}

// lineHasPassSignal reports whether a single line affirmatively signals a pass.
func lineHasPassSignal(line string) bool {
	if line == "" {
		return false
	}
	if _, value, ok := parseReportField(line); ok && passValue.MatchString(stripMarkdownSignal(value)) {
		return true
	}
	stripped := stripMarkdownSignal(line)
	return passValue.MatchString(stripped) ||
		equalsAnyFold(stripped, "all checks passed", "all checks passed.", "ready for archive", "ready for archive.")
}

// parseReportField extracts the label and value of a "Label: value" line.
func parseReportField(line string) (label, value string, ok bool) {
	match := reportField.FindStringSubmatch(line)
	if len(match) != 3 {
		return "", "", false
	}
	return match[1], match[2], true
}

// valueIsBenign reports whether a blocker field's value is safe (empty, zero,
// none, "no blockers", etc.).
func valueIsBenign(value string) bool {
	value = strings.TrimSpace(stripMarkdownSignal(value))
	if value == "" || value == "0" {
		return true
	}
	return benignValue.MatchString(value) || strings.EqualFold(value, "no blockers")
}

// stripMarkdownSignal removes surrounding markdown emphasis and a leading status
// emoji so the underlying keyword can be matched.
func stripMarkdownSignal(value string) string {
	value = strings.TrimSpace(value)
	value = strings.Trim(value, "*`_")
	value = strings.TrimSpace(value)
	for _, prefix := range []string{"✅", "❌", "⚠️", "⚠"} {
		if strings.HasPrefix(value, prefix) {
			value = strings.TrimSpace(strings.TrimPrefix(value, prefix))
		}
	}
	return strings.TrimSpace(value)
}

// normalizeFieldName lowercases a label and keeps only its letters so that
// "Verification Blocker" and "verificationblocker" compare equal.
func normalizeFieldName(value string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(value) {
		if r >= 'a' && r <= 'z' {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func equalsAnyFold(value string, candidates ...string) bool {
	for _, candidate := range candidates {
		if strings.EqualFold(value, candidate) {
			return true
		}
	}
	return false
}
