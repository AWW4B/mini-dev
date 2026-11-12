# FILE: tests/contracts/test_interfaces.py
# ROLE: Tests that prove src/asf/contracts/interfaces.py meets its DONE WHEN conditions.
# ARCH REF: p15 interface catalog; IF-01; IF-02; IF-03; IF-04; IF-05; IF-06; IF-07; IF-07a; IF-08; IF-09; IF-10; IF-10b; IF-10c; IF-11; IF-12; IF-13; IF-14; IF-15; IF-16; IF-17; IF-18; IF-19; IF-20; IF-21; IF-23; IF-24; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/contracts/interfaces.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/interfaces.py: InterfaceInfo, INTERFACES (unit under test)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Use the tmp_path fixture or the fake_paths fixture for every filesystem location.
#   6. Use the fakes from tests/conftest.py instead of real GPUs, networks, sandboxes or model providers unless the test is marked needs_gpu, needs_network or needs_sandbox.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; real API keys; network access in unmarked tests; sleeping for timing (use the fake clock)
# ERRORS: Failures surface as pytest assertion failures.
# DONE WHEN: (1) All tests pass via `uv run pytest tests/contracts/test_interfaces.py` on Windows and Linux once src/asf/contracts/interfaces.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/contracts/test_interfaces.py` and `uv run mypy tests/contracts/test_interfaces.py` are clean.



import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from asf.contracts.interfaces import INTERFACES, InterfaceInfo

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "src" / "asf" / "contracts"

EXPECTED_IDS = {
    "IF-01", "IF-02", "IF-03", "IF-04", "IF-05", "IF-06", "IF-07", "IF-07a", "IF-08", "IF-09", "IF-10", "IF-10b", "IF-10c",
    "IF-11", "IF-12", "IF-13", "IF-14", "IF-15", "IF-16", "IF-17", "IF-18", "IF-19", "IF-20", "IF-21", "IF-23", "IF-24",
}


def test_registry_holds_exactly_the_documented_interfaces() -> None:
    assert set(INTERFACES) == EXPECTED_IDS


def test_registry_keys_match_each_entry_id() -> None:
    for key, info in INTERFACES.items():
        assert key == info.if_id


def test_every_entry_is_fully_populated() -> None:
    for info in INTERFACES.values():
        assert info.name and info.producer and info.consumer and info.payload_model and info.kind


def test_interface_info_requires_all_fields() -> None:
    with pytest.raises(ValidationError):
        InterfaceInfo.model_validate({"if_id": "IF-99", "name": "x"})


def test_every_payload_model_path_points_at_a_class_defined_in_the_contracts_package() -> None:
    for info in INTERFACES.values():
        module_path, _, class_name = info.payload_model.rpartition(".")
        assert module_path.startswith("asf.contracts."), info.if_id
        source = CONTRACTS_DIR / (module_path.split(".")[-1] + ".py")
        assert source.is_file(), f"{info.if_id}: {source} missing"
        text = source.read_text(encoding="utf-8")
        assert re.search(rf"^class {class_name}\b", text, re.MULTILINE), f"{info.if_id}: class {class_name} not found in {source.name}"
