"""Tests for tests-prompts/docker-test.sh host harness.

These tests inspect the script's source for the contracts the
docker-host-harness spec defines:
  - Auth preflight (fail-fast, names path)
  - Image tag + override
  - Three mounts (repo ro, auth ro, logs rw)
  - --network host flag
  - Exit code propagation (no || true masking)
  - [FAIL] headline surfacing
  - Style mirror with e2e/docker-test.sh (SCRIPT_DIR, PROJECT_ROOT,
    IMAGE_TAG, ENV_FLAGS, run_with_timeout)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


_HARNESS = Path(__file__).resolve().parent.parent / "tests-prompts" / "docker-test.sh"
_E2E_HARNESS = Path(__file__).resolve().parent.parent / "e2e" / "docker-test.sh"


@pytest.fixture(scope="module")
def harness_text() -> str:
    return _HARNESS.read_text()


@pytest.fixture(scope="module")
def syntax_ok() -> bool:
    result = subprocess.run(
        ["bash", "-n", str(_HARNESS)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


class TestStyleMirror:
    def test_syntax_valid(self, syntax_ok: bool) -> None:
        assert syntax_ok

    def test_defines_script_dir(self, harness_text: str) -> None:
        assert "SCRIPT_DIR=" in harness_text

    def test_defines_project_root(self, harness_text: str) -> None:
        assert "PROJECT_ROOT=" in harness_text

    def test_defines_image_tag_with_default(self, harness_text: str) -> None:
        # Must define IMAGE_TAG and use a default that matches the spec.
        assert "IMAGE_TAG=" in harness_text
        assert "ai-harness-prompt-tests:local" in harness_text

    def test_defines_env_flags(self, harness_text: str) -> None:
        assert "ENV_FLAGS" in harness_text

    def test_defines_run_with_timeout(self, harness_text: str) -> None:
        assert "run_with_timeout" in harness_text

    def test_emits_build_prefix(self, harness_text: str) -> None:
        assert "[BUILD]" in harness_text

    def test_emits_run_prefix(self, harness_text: str) -> None:
        assert "[RUN]" in harness_text

    def test_emits_fail_prefix(self, harness_text: str) -> None:
        assert "[FAIL]" in harness_text


class TestAuthPreflight:
    def test_namesexact_path(self, harness_text: str) -> None:
        # The preflight MUST reference the exact default path from the spec.
        assert "/home/diegoagd10/.local/share/opencode/auth.json" in harness_text

    def test_preflight_uses_test_f(self, harness_text: str) -> None:
        assert re.search(r"\[\s*!\s*-f\s+\"?\$HOST_AUTH_FILE\"?", harness_text), (
            'preflight must check [ ! -f "$HOST_AUTH_FILE" ]'
        )

    def test_preflight_exits_nonzero_before_docker(self, harness_text: str) -> None:
        # The preflight block must include `exit 1` and must NOT proceed
        # past it into docker build. We assert the exit precedes any docker build.
        preflight_idx = harness_text.find('! -f "$HOST_AUTH_FILE"')
        exit_idx = harness_text.find("exit 1", preflight_idx)
        docker_build_idx = harness_text.find("docker build")
        assert preflight_idx != -1, "preflight guard missing"
        assert exit_idx != -1 and exit_idx < docker_build_idx, "exit 1 must appear between preflight and docker build"

    def test_preflight_message_names_path(self, harness_text: str) -> None:
        # The [FAIL] message must include the auth file path so the
        # human sees what to fix.
        m = re.search(r"\[FAIL\][^\n]*HOST_AUTH_FILE", harness_text)
        assert m is not None, "preflight [FAIL] line must reference HOST_AUTH_FILE"


class TestImageBuild:
    def test_default_tag(self, harness_text: str) -> None:
        m = re.search(r'IMAGE_TAG="\$\{IMAGE_TAG:-(ai-harness-prompt-tests:local)\}"', harness_text)
        assert m is not None, "default tag mismatch"

    def test_override_via_image_tag_env(self, harness_text: str) -> None:
        # The shell idiom IMAGE_TAG:-<default> IS the override mechanism.
        assert re.search(r'IMAGE_TAG="\$\{IMAGE_TAG:-', harness_text)

    def test_uses_tests_prompts_dockerfile(self, harness_text: str) -> None:
        assert "tests-prompts/Dockerfile" in harness_text


class TestMountComposition:
    def test_repo_mount_ro(self, harness_text: str) -> None:
        # The repo mount must be :ro so container writes die with the container.
        assert re.search(r"PROJECT_ROOT:/source-ro:ro", harness_text), "repo must mount to /source-ro with :ro"

    def test_auth_mount_ro(self, harness_text: str) -> None:
        assert re.search(
            r"HOST_AUTH_FILE:/root/\.local/share/opencode/auth\.json:ro",
            harness_text,
        ), "auth must mount read-only to /root/.local/share/opencode/auth.json"

    def test_logs_mount_writable(self, harness_text: str) -> None:
        # The logs mount must NOT be :ro — that's where failure traces go.
        assert re.search(r"SCRIPT_DIR/logs:/logs(?!:ro)", harness_text), "logs must mount writable (no :ro suffix)"

    def test_all_three_mounts_present(self, harness_text: str) -> None:
        assert harness_text.count("-v ") >= 3, "expected at least three -v flags"


class TestNetworkHost:
    def test_network_host_flag(self, harness_text: str) -> None:
        assert "--network host" in harness_text


class TestAggregateExitCode:
    def test_no_or_true_around_docker_run(self, harness_text: str) -> None:
        # The docker run invocation must not be wrapped in `|| true`.
        for line in harness_text.splitlines():
            stripped = line.strip()
            if "docker run" in stripped:
                assert "|| true" not in stripped, f"docker run line masked with || true: {stripped!r}"

    def test_failure_branch_propagates_exit(self, harness_text: str) -> None:
        # The else branch must exit with the captured rc.
        assert re.search(r'rc=\$?[\s\S]{0,200}exit\s+"\$rc"', harness_text), (
            "failure branch must propagate container exit code"
        )

    def test_no_set_e_in_script(self, harness_text: str) -> None:
        # `set -e` would mask the failure path; we rely on explicit returns.
        for line in harness_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert stripped != "set -e", "harness must not `set -e` (would mask failure path)"


class TestFailHeadline:
    def test_fail_prefix_appears_at_least_once(self, harness_text: str) -> None:
        # The script MUST print a [FAIL] line on the failure path —
        # either via the preflight or the run-result branch.
        assert "[FAIL]" in harness_text

    def test_container_fail_lines_flow_through(self, harness_text: str) -> None:
        # The docker run invocation must redirect stderr to stdout
        # (or merge into 2>&1) so the container's [FAIL] lines are
        # visible to the host harness consumer.
        assert "2>&1" in harness_text
