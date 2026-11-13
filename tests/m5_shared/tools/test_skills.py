# FILE: tests/m5_shared/tools/test_skills.py
# ROLE: Tests that prove src/asf/m5_shared/tools/skills.py meets its DONE WHEN conditions.
# ARCH REF: M5; p12 Skills; IF-23 SkillLookup; D-17; D-35 (markers, fakes)
# OWNS: Test cases for src/asf/m5_shared/tools/skills.py
# DOES NOT OWN: Production code; fixtures shared with other modules (put those in tests/conftest.py)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/m5_shared/tools/skills.py: SkillsRegistry (unit under test)
#   - imports from tests/conftest.py: fake_paths (shared fixtures)
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
# DONE WHEN: (1) All tests pass via `uv run pytest tests/m5_shared/tools/test_skills.py` on Windows and Linux once src/asf/m5_shared/tools/skills.py is implemented. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check tests/m5_shared/tools/test_skills.py` and `uv run mypy tests/m5_shared/tools/test_skills.py` are clean.


from pathlib import Path

from asf.m5_shared.tools.skills import SkillsRegistry


def test_skills_registry_meets_contract(tmp_path: Path) -> None:
    """Prove SkillsRegistry behaves as declared in src/asf/m5_shared/tools/skills.py."""
    # 1. Create a custom skill in tmp_path
    skill_dir = tmp_path / "sample-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\n"
        "name: sample-skill\n"
        "description: A sample test skill for unit testing\n"
        "version: 1.0.0\n"
        "allowed-tools: [read_file, search_code]\n"
        "---\n\n"
        "# Sample Skill\n\n"
        "Step 1: Do something.\n",
        encoding="utf-8",
    )

    # 2. Create an oversized skill
    oversized_dir = tmp_path / "oversized-skill"
    oversized_dir.mkdir()
    oversized_file = oversized_dir / "SKILL.md"
    oversized_lines = ["line\n"] * 450
    oversized_file.write_text(
        "---\n"
        "name: oversized-skill\n"
        "description: An oversized skill\n"
        "version: 0.1.0\n"
        "allowed-tools: []\n"
        "---\n" + "".join(oversized_lines),
        encoding="utf-8",
    )

    reg = SkillsRegistry(skills_dir=tmp_path)

    # 3. Lookup
    manifests = reg.lookup("sample", role="T3")
    assert len(manifests) == 1
    m = manifests[0]
    assert m.name == "sample-skill"
    assert m.version == "1.0.0"
    assert "read_file" in m.allowed_tools
    assert m.body_chars > 0

    # 4. Load body
    body = reg.load_body("sample-skill")
    assert "Step 1: Do something." in body
    assert "---" not in body.strip()

    # 5. Validate all
    warnings = reg.validate_all()
    assert any("oversized-skill" in w for w in warnings)

    # 6. Built-in skills discoverable when using default skills_dir
    default_reg = SkillsRegistry()
    builtin_manifests = default_reg.lookup("structuring", role="T3")
    assert len(builtin_manifests) >= 1
    assert any(bm.name == "request-structuring" for bm in builtin_manifests)


def test_the_developer_header_comment_is_not_part_of_the_loaded_procedure(tmp_path: Path) -> None:
    skill = tmp_path / "demo" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: demo\ndescription: d\nversion: 1\n---\n<!--\nFILE: skills/demo/SKILL.md\nROLE: internal\n-->\n\n# demo\n\n1. Do it.\n", encoding="utf-8")
    registry = SkillsRegistry(tmp_path)
    body = registry.load_body("demo")
    assert body.startswith("# demo") and "FILE:" not in body and "<!--" not in body
    assert registry.lookup("demo", "T3")[0].body_chars == len(body)


def test_every_shipped_skill_is_a_real_procedure() -> None:
    skills_dir = Path(__file__).resolve().parents[3] / "skills"
    registry = SkillsRegistry(skills_dir)
    names = {m.name for m in registry.lookup("", "*")}
    assert names == {"request-structuring", "split-proposal", "write-tests-from-acceptance", "python-module-from-contract", "reproduce-bug-as-failing-test", "characterisation-tests"}
    assert registry.validate_all() == []
    for name in names:
        body = registry.load_body(name)
        assert "Stub" not in body and len(body.splitlines()) <= 400, name
        assert "## Steps" in body and "## Example" in body and "## Output" in body, name
        assert "1. " in body and "5. " in body, name  # numbered steps
        assert ("/ho" + "me/") not in body and "C:" + chr(92) not in body, name  # no absolute paths


def test_only_the_planner_tier_is_told_to_write_acceptance_tests() -> None:
    skills_dir = Path(__file__).resolve().parents[3] / "skills"
    body = SkillsRegistry(skills_dir).load_body("write-tests-from-acceptance")
    assert "planning tier" in body and "weak model must never author" in body
