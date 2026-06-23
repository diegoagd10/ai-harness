"""Self-check for the implementor assertion registry.
Run: python test_implementor_eval.py

Shows how a check sees the world: build Facts, wrap in EvalContext, evaluate().
"""

from harness import EvalContext, evaluate
from implementor_eval import BRANCH, CHECKS, Facts

TDD_READ_EVENT = (
    '{"type":"tool_use","part":{"tool":"read",'
    '"state":{"input":{"filePath":"/home/x/.agents/skills/tdd/SKILL.md"}}}}'
)


def passing_facts() -> Facts:
    return Facts(
        branch=BRANCH,
        head="abc123",
        commit_count=1,
        subject="[#42] add fizzbuzz",
        tests_passed=True,
        clean_working_tree=True,
        math_utils_source="def fizzbuzz(n: int) -> list[str]: ...",
        stdout=TDD_READ_EVENT,
    )


def ctx(facts: Facts) -> EvalContext:
    return EvalContext(facts=facts, prompt={"function_name": "fizzbuzz"})


def results_for(facts: Facts) -> dict:
    return evaluate(ctx(facts), CHECKS)


def test_all_checks_pass_on_good_run():
    assert all(results_for(passing_facts()).values())


def test_each_check_can_fail():
    cases = {
        "branch_correct": lambda f: setattr(f, "branch", "wrong"),
        "single_commit": lambda f: setattr(f, "commit_count", 2),
        "tests_passed": lambda f: setattr(f, "tests_passed", False),
        "function_implemented": lambda f: setattr(f, "math_utils_source", "# nothing"),
        "tdd_skill_called": lambda f: setattr(f, "stdout", ""),
        "commit_subject_format": lambda f: setattr(f, "subject", "no tag"),
        "clean_working_tree": lambda f: setattr(f, "clean_working_tree", False),
    }
    for check_name, break_it in cases.items():
        f = passing_facts()
        break_it(f)
        assert results_for(f)[check_name] is False, check_name


if __name__ == "__main__":
    test_all_checks_pass_on_good_run()
    test_each_check_can_fail()
    print("ok")
