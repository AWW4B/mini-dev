# FILE: src/asf/contracts/requests.py
# ROLE: Defines SubmitRequest (IF-01), StructuredRequest (IF-02) and RepoProfile.
# ARCH REF: p02 Project Input; p03 Request Processing; IF-01; IF-02; D-29
# OWNS: Request shapes and task types
# DOES NOT OWN: Parsing and understanding (src/asf/m2_request/*)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/contracts/ids.py: ProjectId (typed ids)
#   - called by src/asf/m2_request/intake_router.py: SubmitRequest, StructuredRequest
#   - called by src/asf/m2_request/repository_intake.py: RepoProfile
#   - called by src/asf/m2_request/request_understanding.py: StructuredRequest, RepoProfile, TaskType
#   - called by src/asf/m3_orchestration/run_graph.py: StructuredRequest
#   - called by src/asf/m3_orchestration/acceptance.py: StructuredRequest
#   - called by src/asf/m3_orchestration/planning/modes.py: StructuredRequest, TaskType
#   - called by src/asf/cli/project_input.py: SubmitRequest, TaskType
#   - called by tests/contracts/test_requests.py: TaskType, SubmitRequest, Requirement, RepoProfile, StructuredRequest
#   - called by tests/m3_orchestration/test_acceptance.py: StructuredRequest
#   - called by src/asf/m3_orchestration/planning/planner_graph.py: StructuredRequest
#   - called by tests/m3_orchestration/planning/test_modes.py: StructuredRequest
#   - called by tests/m3_orchestration/planning/test_planner_graph.py: StructuredRequest
#   - called by tests/m3_orchestration/test_run_graph.py: StructuredRequest
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. This file is declarations only: Pydantic models, enums and type aliases. Add field validators only where the docstring of a field states a constraint.
#   6. Every model must round-trip through model_dump_json() / model_validate_json() unchanged; the JSON Schema exported from these models is the published contract (D-39: no hand-written JSON).
#   7. Changing a field name or type is a contract change: stop and report instead.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys; business logic; I/O; imports from asf.m1-m5 packages, asf.cli, asf.web or asf.platform
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/contracts/test_requests.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/contracts/requests.py` and `uv run mypy src/asf/contracts/requests.py` are clean.

from enum import StrEnum

from pydantic import BaseModel, Field

from asf.contracts.ids import ProjectId


class TaskType(StrEnum):
    NEW_BUILD = "new_build"
    DEBUG = "debug"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST_GENERATION = "test_generation"
    CODE_DOCS = "code_docs"
    UNSUPPORTED = "unsupported"


class SubmitRequest(BaseModel):
    """IF-01."""
    project_id: ProjectId
    text: str
    attachment_refs: list[str] = Field(default_factory=list, description="blob refs (sha-256)")
    repo_ref: str | None = Field(default=None, description="local path as text or git URL")
    mode_hint: TaskType | None = None


class Requirement(BaseModel):
    req_id: str = Field(description="REQ anchor from the source document")
    text: str
    source_ref: str


class RepoProfile(BaseModel):
    languages: list[str]
    build_commands: list[list[str]] = Field(description="argument lists, never shell strings")
    test_commands: list[list[str]]
    baseline_passed: list[str] = Field(default_factory=list)
    baseline_failed: list[str] = Field(default_factory=list)
    index_ref: str | None = None
    supported: bool = True


class StructuredRequest(BaseModel):
    """IF-02."""
    request_id: str
    project_id: ProjectId
    task_type: TaskType
    requirements: list[Requirement]
    constraints: list[str] = Field(default_factory=list)
    nfrs: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    repo_profile: RepoProfile | None = None
