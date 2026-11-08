# FILE: tests/conftest.py
# ROLE: Shared pytest fixtures and fakes: fake_paths (isolated AppPaths), fake_clock, and marker auto-skips per OS.
# ARCH REF: D-35 (markers, fakes); FR-4
# OWNS: Shared fixtures
# DOES NOT OWN: Module-specific test cases
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/paths.py: AppPaths (isolated directories)
#   - called by tests/m5_shared/state_store/test_schema.py: fake_paths
#   - called by tests/m5_shared/state_store/test_store.py: fake_paths
#   - called by tests/m5_shared/state_store/test_recovery.py: fake_paths
#   - called by tests/m5_shared/state_store/test_backup.py: fake_paths
#   - called by tests/m5_shared/events/test_event_log.py: fake_paths
#   - called by tests/m5_shared/workspace/test_blobs.py: fake_paths
#   - called by tests/m5_shared/workspace/test_workspace.py: fake_paths
#   - called by tests/m5_shared/runtime/test_probes.py: fake_paths
#   - called by tests/m5_shared/runtime/test_backends.py: fake_paths
#   - called by tests/m5_shared/tools/test_policy.py: fake_paths
#   - called by tests/m5_shared/tools/test_executor.py: fake_paths
#   - called by tests/m5_shared/tools/test_builtin_tools.py: fake_paths
#   - called by tests/m5_shared/tools/test_skills.py: fake_paths
#   - called by tests/m5_shared/tools/test_mcp_client.py: fake_paths
#   - called by tests/m5_shared/tools/codeexec/test_runner.py: fake_paths
#   - called by tests/m5_shared/context/test_repo_index.py: fake_paths
#   - called by tests/platform/test_base.py: fake_paths
#   - called by tests/platform/test_linux.py: fake_paths
#   - called by tests/platform/test_windows.py: fake_paths
#   - called by tests/platform/test_fallback.py: fake_paths
#   - called by tests/platform/test_sandbox_bwrap.py: fake_paths
#   - called by tests/platform/test_sandbox_srt.py: fake_paths
#   - called by tests/platform/test_sandbox_jobobject.py: fake_paths
#   - called by tests/platform/test_select.py: fake_paths
#   - called by tests/config/test_paths.py: fake_paths
#   - called by tests/config/test_loader.py: fake_paths
#   - called by tests/config/test_secrets.py: fake_paths
#   - called by tests/doctor/test_checks.py: fake_paths
#   - called by tests/doctor/test_report.py: fake_paths
#   - called by tests/test_logging_setup.py: fake_paths
#   - called by tests/m2_request/test_document_ingestion.py: fake_paths
#   - called by tests/m2_request/test_repository_intake.py: fake_paths
#   - called by tests/m3_orchestration/test_run_control.py: fake_paths
#   - called by tests/m4_execution/worker/test_worker_graph.py: fake_paths
#   - called by tests/m4_execution/verification/test_gate.py: fake_paths
#   - called by tests/cli/commands/test_init.py: fake_paths
#   - called by tests/cli/commands/test_project.py: fake_paths
#   - called by tests/cli/commands/test_run.py: fake_paths
#   - called by tests/cli/commands/test_report.py: fake_paths
#   - called by tests/cli/commands/test_events.py: fake_paths
#   - called by tests/cli/test_project_input.py: fake_paths
#   - called by tests/web/test_server.py: fake_paths
#   - called by tests/scripts/test_check_headers.py: fake_paths
#   - called by tests/scripts/test_scan_forbidden.py: fake_paths
#   - called by tests/scripts/test_gen_notice.py: fake_paths
#   - called by tests/scripts/test_export_requirements.py: fake_paths
#   - called by tests/scripts/test_smoke.py: fake_paths
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use pathlib.Path for every path; obtain base directories only from src/asf/config/paths.py; never hardcode drive letters, home directories or system temp directories (use tempfile when a scratch location is needed).
#   6. Start processes only with argument lists (never shell=True, never os.system); route OS-specific behaviour (sandbox, process tree, file locks, signals, detach) through asf.platform.select.get_platform().
#   7. Behave identically on Windows and Linux (Debian-family and Arch); when a capability is missing, degrade through the safe fallback and report it, never crash.
#   8. Markers are declared in pyproject.toml [tool.pytest.ini_options]; skip windows_only on Linux and linux_only on Windows here.
#   9. needs_gpu, needs_sandbox and needs_network tests are skipped unless FACTORY_TEST_<MARKER>=1 is set.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) `uv run python scripts/check_headers.py` reports no problem for this file. (2) `uv run ruff check tests/conftest.py` and `uv run mypy tests/conftest.py` are clean.

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from asf.config.paths import AppPaths

OPT_IN_MARKERS = ("needs_gpu", "needs_sandbox", "needs_network")


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[AppPaths]:
    """AppPaths rooted in tmp_path; FACTORY_HOME points there too."""
    monkeypatch.setenv("FACTORY_HOME", str(tmp_path))
    paths = AppPaths(config_dir=tmp_path / "config", data_dir=tmp_path / "data", log_dir=tmp_path / "logs", cache_dir=tmp_path / "cache")
    for p in (paths.config_dir, paths.data_dir, paths.log_dir, paths.cache_dir):
        p.mkdir(parents=True, exist_ok=True)
    yield paths


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    on_windows = sys.platform == "win32"
    for item in items:
        if "windows_only" in item.keywords and not on_windows:
            item.add_marker(pytest.mark.skip(reason="windows_only"))
        if "linux_only" in item.keywords and not sys.platform.startswith("linux"):
            item.add_marker(pytest.mark.skip(reason="linux_only"))
        for marker in OPT_IN_MARKERS:
            if marker in item.keywords and os.environ.get(f"FACTORY_TEST_{marker.upper()}") != "1":
                item.add_marker(pytest.mark.skip(reason=f"{marker}: set FACTORY_TEST_{marker.upper()}=1"))
