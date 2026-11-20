# FILE: src/asf/m5_shared/gateway/dummy.py
# ROLE: A deterministic stand-in chat model (provider "dummy") that answers every purpose the factory asks for, so the whole flow can run without a real model.
# ARCH REF: M5; p11; D-07; D-35 (fakes)
# OWNS: DummyChatModel and its scripted answers per purpose
# DOES NOT OWN: Choosing a route (gateway.py); building real chat models (providers.py)
# CONNECTS TO (external boundaries only):
#   - called by src/asf/m5_shared/gateway/providers.py: DummyChatModel
#   - called by tests/m5_shared/gateway/test_dummy.py: DummyChatModel, answer_for
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
#   5. Deterministic: the same prompt gives the same answer; no clock, no randomness, no network.
#   6. Answers are shaped like a real model's: structured output validates against the requested schema, worker steps are one JSON object.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/gateway/test_dummy.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/gateway/dummy.py` and `uv run mypy src/asf/m5_shared/gateway/dummy.py` are clean.

import json
import re
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from pydantic import BaseModel

_SIGNATURE = re.compile(r"`?([A-Za-z_]\w*)\(([^()`]*)\)\s*(?:->\s*([^`\n.]+?))?`?(?=[\s.,;:]|$)")
_PATH = re.compile(r"[\w./-]+\.py")

_CORE_PY = '''"""Word counting."""

import re


def top_words(text: str, n: int = 3) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for word in re.split(r"[^a-z']+", text.lower()):
        if word:
            counts[word] = counts.get(word, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]
'''

_CLI_PY = '''"""Command line for wordfreq."""

import argparse
import sys

from wordfreq.core import top_words


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wordfreq")
    parser.add_argument("path")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        with open(args.path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as err:
        print(f"wordfreq: cannot read {args.path}: {err}", file=sys.stderr)
        return 2
    for word, count in top_words(text, args.top):
        print(f"{word} {count}")
    return 0
'''

_TEST_CORE = '''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordfreq.core import top_words  # noqa: E402


def test_ranking_is_by_count_then_word():
    assert top_words("b a b c c c", 3) == [("c", 3), ("b", 2), ("a", 1)]


def test_ties_are_broken_alphabetically():
    assert top_words("pear apple fig", 2) == [("apple", 1), ("fig", 1)]


def test_punctuation_splits_words_but_apostrophes_stay():
    assert top_words("Don't stop, don't!", 1) == [("don't", 2)]


def test_empty_text_has_no_words():
    assert top_words("", 3) == []
'''

_TEST_CLI = '''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordfreq.cli import main  # noqa: E402


def test_prints_one_pair_per_line(tmp_path, capsys):
    path = tmp_path / "t.txt"
    path.write_text("a b b", encoding="utf-8")
    assert main([str(path), "--top", "2"]) == 0
    assert capsys.readouterr().out.splitlines() == ["b 2", "a 1"]


def test_a_missing_file_is_an_error_on_stderr(tmp_path, capsys):
    assert main([str(tmp_path / "nope.txt")]) == 2
    assert "cannot read" in capsys.readouterr().err
'''

_SOLUTIONS = {
    "src/wordfreq/core.py": _CORE_PY,
    "src/wordfreq/cli.py": _CLI_PY,
    "src/wordfreq/__init__.py": '"""wordfreq."""\n',
    "tests/test_core.py": _TEST_CORE,
    "tests/test_cli.py": _TEST_CLI,
}


def _stub_for(path: str, goal: str) -> str:
    if path.endswith(".py"):
        return f'"""{goal.strip()[:100]}"""\n\n\ndef run() -> bool:\n    return True\n'
    return f"# {goal.strip()[:100]}\n"


def _generic_test(target: str, under_test: list[str]) -> str:
    checks = "\n".join(f"    assert Path({p!r}).is_file()" for p in under_test) or "    assert True"
    return f"from pathlib import Path\n\n\ndef test_the_files_exist():\n{checks}\n"


def _requirements(prompt: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).strip()) for m in re.finditer(r"^- (REQ-\d+): (.*)$", prompt, re.M)]


def _plan(prompt: str) -> dict[str, Any]:
    """Modules from the files the requirements name: one per source file, its signatures as interfaces, a tests module over them."""
    reqs = _requirements(prompt)
    spans: list[tuple[str, list[tuple[str, str]]]] = []
    for rid, text in reqs:
        found = [p for p in _PATH.findall(text) if p.startswith("src/")]
        if found:
            spans.append((found[0], []))
        if spans:
            spans[-1][1].append((rid, text))
    modules: list[dict[str, Any]] = []
    covered: set[str] = set()
    for path, rows in spans:
        stem = path.rsplit("/", 1)[-1].removesuffix(".py")
        interfaces = []
        for _, text in rows:
            for match in _SIGNATURE.finditer(text):
                if match.group(1) not in {"print", "main"} or match.group(3):
                    interfaces.append({"name": match.group(1), "signature": f"{match.group(1)}({match.group(2)})", "returns": (match.group(3) or "None").strip()})
        ids = [rid for rid, _ in rows]
        covered.update(ids)
        modules.append({"name": stem, "goal": f"Implement {path}: " + " ".join(t for _, t in rows)[:240], "files": [path], "interfaces": interfaces[:6],
                        "deps": ["core"] if stem != "core" and any(m["name"] == "core" for m in modules) else [], "acceptance": [t for _, t in rows][:6], "covers": ids})
    rest = [rid for rid, _ in reqs if rid not in covered]
    if not modules:
        modules.append({"name": "app", "goal": "Implement the request.", "files": ["src/app.py"], "interfaces": [], "deps": [], "acceptance": [t for _, t in reqs][:6], "covers": rest})
    elif rest:
        modules[-1]["covers"] = [*modules[-1]["covers"], *rest]
    if any("test" in t.lower() for _, t in reqs):
        names = [m["name"] for m in modules]
        modules.append({"name": "tests", "goal": "Write the tests that prove the other modules work.", "files": [f"tests/test_{n}.py" for n in names], "interfaces": [],
                        "deps": names, "acceptance": ["pytest passes"], "covers": []})
    return {"modules": modules, "shared_types": [], "assumptions": ["dummy planner: modules follow the files the requirements name"], "open_decisions": []}


def _worker_step(prompt: str) -> dict[str, Any]:
    allowed = [p.strip() for p in re.search(r"ALLOWED FILES: (.*)", prompt).group(1).split(",") if p.strip()] if re.search(r"ALLOWED FILES: (.*)", prompt) else []  # type: ignore[union-attr]
    goal = (re.search(r"TASK: (.*)", prompt).group(1) if re.search(r"TASK: (.*)", prompt) else "task")  # type: ignore[union-attr]
    written = set(re.findall(r'write_file\(\{"rel_path": "([^"]+)"', prompt))
    for path in allowed:
        if path not in written:
            return {"action": "tool", "tool": "write_file", "args": {"rel_path": path, "content": _SOLUTIONS.get(path) or _stub_for(path, goal)}}
    refs = [r.strip() for r in (re.search(r"ACCEPTANCE TESTS: (.*)", prompt).group(1).split(",") if re.search(r"ACCEPTANCE TESTS: (.*)", prompt) else []) if r.strip()]  # type: ignore[union-attr]
    if refs and not re.search(r"Turn \d+: run_tests\(", prompt):
        return {"action": "tool", "tool": "run_tests", "args": {"selectors": refs}}
    return {"action": "done", "message": f"dummy worker wrote {', '.join(sorted(written)) or 'nothing'} and ran {', '.join(refs) or 'no tests'}"}


def answer_for(purpose: str, prompt: str, schema_name: str | None = None) -> str:
    """The scripted reply for one request, as the text a real model would return (JSON for structured output)."""
    if purpose == "plan":
        return json.dumps(_plan(prompt))
    if purpose == "plan_critique":
        return "NO_ISSUES"
    if purpose == "rubric":
        return json.dumps({"ambiguity": 0.1, "coupling": 0.1, "notes": "dummy rubric"})
    if purpose == "split_proposal":
        return json.dumps({"children": [], "new_contract_ids": [], "rationale": "dummy: no split"})
    if purpose.startswith("acceptance_tests"):
        keys = re.search(r"Use exactly these keys for the test files: (.*)", prompt)
        under = [p.strip() for p in (re.search(r"FILES UNDER TEST[^:]*: (.*)", prompt).group(1).split(",") if re.search(r"FILES UNDER TEST[^:]*: (.*)", prompt) else []) if p.strip()]  # type: ignore[union-attr]
        targets = [k.strip() for k in (keys.group(1).split(",") if keys else [])] or ["tests/test_suite_meta.py"]
        files = []
        for target in targets:
            safe = target if "<" not in target else "tests/test_suite_meta.py"
            files.append({"path": safe, "content": _SOLUTIONS.get(safe) or _generic_test(safe, under)})
        return json.dumps({"files": files})
    if purpose == "code_step":
        return json.dumps(_worker_step(prompt))
    if purpose == "normalisation":
        return prompt.split("\n\n", 1)[1] if "\n\n" in prompt else prompt
    if purpose == "classify_failure":
        return "LOCAL_BUG"
    if purpose == "review_change":
        return "[]"
    if purpose == "compaction":
        return "Earlier turns: files were written and tests were run."
    if purpose == "memory_navigation":
        return "[]"
    return "pong"


def _text_of(messages: Sequence[BaseMessage] | Any) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        return "\n".join(str(getattr(m, "content", m)) for m in messages)
    return str(getattr(messages, "content", messages))


class DummyChatModel(BaseChatModel):
    """Answers from ``answer_for`` by the purpose of the request; reports token use as characters / 4 so budgets and metrics are exercised."""

    purpose: str = "pong"
    role: str = ""
    model_name: str = "dummy"

    @property
    def _llm_type(self) -> str:
        return "dummy"

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        prompt = _text_of(messages)
        text = answer_for(self.purpose, prompt)
        usage = {"prompt_tokens": max(1, len(prompt) // 4), "completion_tokens": max(1, len(text) // 4)}
        message = AIMessage(content=text, response_metadata={"token_usage": usage, "model_name": self.model_name})
        return ChatResult(generations=[ChatGeneration(message=message)], llm_output={"token_usage": usage, "model_name": self.model_name})

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable[Any, Any]:
        def run(messages: Any, config: RunnableConfig | None = None) -> Any:
            reply = self.invoke(messages, config=config)
            data = json.loads(str(reply.content))
            return schema.model_validate(data) if isinstance(schema, type) and issubclass(schema, BaseModel) else data

        return RunnableLambda(run)
