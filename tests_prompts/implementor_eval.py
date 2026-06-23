"""Eval for the implementor prompt.

Everything that makes THIS prompt's test specific lives here: where its
resources are, how to set up the sandbox repo, how to render a test case, what
to observe afterwards, and what to assert. The generic loop lives in harness.py.

Add a test case  -> append a line to resources/prompts/implementor-prompts.jsonl
Add an assertion -> append a Check to CHECKS below
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from config import REPO_ROOT, RESOURCES
from harness import Check, EvalContext, EvalSpec, run, run_eval

# --- where this eval's resources live ----------------------------------
FIXTURE = RESOURCES / "fixture"
SKILLS = RESOURCES / "skills"
PROMPTS = RESOURCES / "prompts"

IMPLEMENTOR_PROMPT = REPO_ROOT / "src" / "ai_harness" / "resources" / "loop-agent" / "implementor.md"
CODING_STANDARDS = RESOURCES / "CODING_STANDARDS.md"
TDD_SKILL = SKILLS / "tdd" / "SKILL.md"
PROMPT_TEMPLATE = PROMPTS / "implementor-prompt.md"
PROMPTS_JSONL = PROMPTS / "implementor-prompts.jsonl"

CONFIG = json.loads((RESOURCES / "fixture-config.json").read_text(encoding="utf-8"))
BRANCH = CONFIG["branch"]
BASE_BRANCH = CONFIG["base_branch"]
ISSUE_TAG = "[#42] "  # matches the issue number in implementor-prompt.md


# --- what we observe after the implementor runs ------------------------
@dataclass
class Facts:
    branch: str
    head: str
    commit_count: int
    subject: str
    tests_passed: bool
    clean_working_tree: bool
    math_utils_source: str
    stdout: str
    pytest_stdout: str = ""
    pytest_stderr: str = ""


# --- the six phases of this eval ---------------------------------------
def prepare() -> None:
    """One-time host setup: make the tdd skill discoverable to the agent."""
    skill_path = Path.home() / ".agents" / "skills" / "tdd" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(TDD_SKILL, skill_path)


def setup(repo: Path) -> str:
    """Build the fixture repo, init git, return the base commit SHA."""
    repo.mkdir(parents=True)
    shutil.copy(CODING_STANDARDS, repo / "CODING_STANDARDS.md")
    shutil.copy(FIXTURE / "pyproject.toml", repo / "pyproject.toml")
    shutil.copy(FIXTURE / "math_utils.py", repo / "math_utils.py")
    tests = repo / "tests"
    tests.mkdir()
    shutil.copy(FIXTURE / "test_math_utils.py", tests / "test_math_utils.py")

    run("git", "init", "-b", "main", cwd=repo)
    run("git", "config", "user.email", CONFIG["git_user_email"], cwd=repo)
    run("git", "config", "user.name", CONFIG["git_user_name"], cwd=repo)
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", CONFIG["initial_commit_message"], cwd=repo)
    run("git", "checkout", "-b", BASE_BRANCH, cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def render(prompt_data: dict) -> str:
    return PROMPT_TEMPLATE.read_text(encoding="utf-8").format(
        branch=BRANCH,
        base_branch=BASE_BRANCH,
        title=prompt_data["title"],
        body=prompt_data["body"],
        explorer_report=prompt_data["explorer_report"],
    )


def gather(repo: Path, initial_sha: str, stdout: str) -> Facts:
    """Observe the repo after the implementor ran. No judgement here."""
    tests = run("uv", "run", "pytest", cwd=repo, check=False)
    return Facts(
        branch=run("git", "branch", "--show-current", cwd=repo).stdout.strip(),
        head=run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip(),
        commit_count=int(
            run("git", "rev-list", "--count", f"{initial_sha}..HEAD", cwd=repo).stdout.strip()
        ),
        subject=run("git", "log", "-1", "--pretty=%s", cwd=repo).stdout.strip(),
        tests_passed=tests.returncode == 0,
        clean_working_tree=not run("git", "status", "--porcelain", cwd=repo).stdout.strip(),
        math_utils_source=(repo / "math_utils.py").read_text(encoding="utf-8"),
        stdout=stdout,
        pytest_stdout=tests.stdout if tests.returncode != 0 else "",
        pytest_stderr=tests.stderr if tests.returncode != 0 else "",
    )


def tdd_skill_was_called(stdout: str) -> bool:
    """True if the agent read the tdd SKILL.md (parsed from the event stream)."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "tool_use":
            continue
        part = event.get("part", {})
        if part.get("tool") != "read":
            continue
        path = part.get("state", {}).get("input", {}).get("filePath", "")
        if "tdd/SKILL.md" in path:
            return True
    return False


# === ADD NEW ASSERTIONS HERE ===========================================
# Each Check is a pure predicate over the EvalContext (facts + test case).
# One entry = one assertion that automatically counts toward pass/fail.

CHECKS: list[Check] = [
    Check(
        "branch_correct",
        "commit landed on the orchestrator-provided branch",
        lambda c: c.facts.branch == BRANCH,
    ),
    Check(
        "single_commit",
        "exactly one commit was made",
        lambda c: c.facts.commit_count == 1,
    ),
    Check(
        "tests_passed",
        "uv run pytest is green",
        lambda c: c.facts.tests_passed,
    ),
    Check(
        "function_implemented",
        "the requested function is defined in math_utils.py",
        lambda c: f"def {c.prompt['function_name']}" in c.facts.math_utils_source,
    ),
    Check(
        "tdd_skill_called",
        "the agent read the tdd SKILL.md",
        lambda c: tdd_skill_was_called(c.facts.stdout),
    ),
    Check(
        "commit_subject_format",
        "commit subject starts with the issue tag and has a message",
        lambda c: c.facts.subject.startswith(ISSUE_TAG)
        and len(c.facts.subject) > len(ISSUE_TAG),
    ),
    Check(
        "clean_working_tree",
        "no uncommitted changes left behind",
        lambda c: c.facts.clean_working_tree,
    ),
]
# =======================================================================


def build_report(prompt_data: dict, facts: Facts, results: dict[str, bool]) -> dict:
    """Raw facts (for debugging) merged with the derived check results."""
    report: dict = {
        "branch": facts.branch,
        "head": facts.head,
        "commit_count": facts.commit_count,
        "subject": facts.subject,
        **results,
    }
    if not facts.tests_passed:
        report["pytest_stdout"] = facts.pytest_stdout
        report["pytest_stderr"] = facts.pytest_stderr
    return report


SPEC = EvalSpec(
    name="implementor",
    prompts_path=PROMPTS_JSONL,
    agent_prompt=IMPLEMENTOR_PROMPT,
    setup=setup,
    render=render,
    gather=gather,
    checks=CHECKS,
    build_report=build_report,
    prepare=prepare,
)


def main() -> int:
    return run_eval(SPEC)


if __name__ == "__main__":
    sys.exit(main())
