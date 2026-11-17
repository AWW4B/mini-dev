# FILE: src/asf/cli/commands/memory_cmd.py
# ROLE: The `factory memory` commands: this machine's limits and layer budgets, memory search (flat or beta tree) and stats.
# ARCH REF: M1; M5; p12 Context & Memory Service; docs/architecture/MEMORY_ARCHITECTURE.md
# OWNS: The memory command group
# DOES NOT OWN: Memory logic (src/asf/m5_shared/memory)
# CONNECTS TO (external boundaries only):
#   - called by tests/cli/commands/test_memory_cmd.py: memory_plan, memory_search, memory_stats
#   - called by src/asf/cli/app.py: register
#   - imports from src/asf/cli/context.py: EXIT_OK, EXIT_USER, guard, project_root, renderer_for (CLI plumbing)
#   - imports from src/asf/m5_shared/memory/budgets.py: LAYERS, budgets_for (budget table)
#   - imports from src/asf/m5_shared/memory/device_budget.py: load_memory_config, plan_device, probe_device (limits)
#   - imports from src/asf/m5_shared/memory/store.py: open_memory_store, row_caps (memory database)
#   - imports from src/asf/m5_shared/memory/tree_rag.py: TreeRetriever (beta search)
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/cli/commands/test_memory_cmd.py pass on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/cli/commands/memory_cmd.py` and `uv run mypy src/asf/cli/commands/memory_cmd.py` are clean.

import json

import typer

from asf.cli.context import EXIT_OK, EXIT_USER, guard, project_root, renderer_for
from asf.m5_shared.memory.budgets import LAYERS, budgets_for
from asf.m5_shared.memory.device_budget import load_memory_config, plan_device, probe_device
from asf.m5_shared.memory.store import open_memory_store, row_caps
from asf.m5_shared.memory.tree_rag import TreeRetriever

_ROLES = ("T1", "T2", "T3", "reviewer")


def memory_plan(output: str = "rich") -> int:
    """This machine's limits: device shares, sized local models and the per-layer token budget of each role."""
    renderer = renderer_for(output)
    config = load_memory_config(project_root())
    snap = probe_device()
    plan = plan_device(snap, config)
    gpu = f"{snap.gpu_name} {snap.vram_total_mb} MB" if snap.vram_total_mb else "none"
    renderer.table(
        "Device and mini-dev's share of it",
        ["resource", "device", "mini-dev may use"],
        [
            ["RAM", f"{snap.ram_total_mb} MB ({snap.ram_free_mb} MB free)", f"{plan.ram_cap_mb} MB (process {plan.process_ram_mb}, models {plan.models_ram_mb})"],
            ["VRAM", gpu, f"{plan.vram_cap_mb} MB"],
            ["CPU threads", f"{snap.cpu_logical} ({snap.cpu_physical} cores)", f"{plan.cpu_threads} (workers {plan.worker_threads})"],
            ["Disk", f"{snap.disk_free_mb} MB free", f"{plan.disk_cap_mb} MB"],
        ],
    )
    renderer.table(
        "Local models that fit",
        ["role", "model", "placement", "context", "VRAM MB", "RAM MB", "on GPU"],
        [[m.role, m.name, m.placement, m.context_tokens, m.gpu_mb, m.ram_mb, f"{m.gpu_fraction:.0%}"] for m in plan.models.values()],
    )
    rows = []
    for role in _ROLES:
        b = budgets_for(role, plan.window_tokens(role), config)
        rows.append([role, b.window_tokens, *[b.get(layer) for layer in LAYERS]])
    renderer.table("Context budget per call (tokens, from memory.toml percentages)", ["role", "window", *LAYERS], rows)
    for warning in plan.warnings:
        renderer.message(warning, "warning")
    return EXIT_OK


def memory_search(query: str, layer: list[str], tree: bool = False, output: str = "rich") -> int:
    """Search the project's memory; --tree uses the beta tree retriever and prints its navigation trace."""
    renderer = renderer_for(output)
    layers = layer or ["episodic", "semantic", "procedural"]
    unknown = [x for x in layers if x not in ("episodic", "semantic", "procedural", "session")]
    if unknown:
        renderer.message(f"Unknown layer(s): {', '.join(unknown)}. Use episodic, semantic, procedural or session.", "error")
        return EXIT_USER
    root = project_root()
    config = load_memory_config(root)
    store = open_memory_store(root / ".factory" / "memory.db", retention=dict(config.get("retention", {})))
    if tree:
        beta = dict(config.get("beta", {}))
        got = TreeRetriever(store, beam=int(beta.get("tree_beam", 3)), max_depth=int(beta.get("tree_max_depth", 4))).retrieve(query, layers, 4000)
        records = got.records
        for step in got.trace:
            renderer.message(f"{step.node_id} -> {', '.join(step.opened) or '(nothing relevant)'} [{step.navigator}]", "info")
    else:
        records = store.search(query, layers)
    renderer.table(f"Memory matching '{query}'", ["id", "layer", "topic", "title", "score"], [[r.id, r.layer, r.topic, r.title, f"{r.score:.3f}"] for r in records])
    return EXIT_OK


def memory_stats(output: str = "rich") -> int:
    renderer = renderer_for(output)
    root = project_root()
    config = load_memory_config(root)
    store = open_memory_store(root / ".factory" / "memory.db")
    caps = row_caps(plan_device(probe_device(), config).disk_cap_mb, dict(config.get("retention", {})))
    counts = store.stats()
    renderer.table("Stored memory", ["layer", "records", "row share"], [[k, v, caps[k]] for k, v in counts.items()])
    renderer.message(f"beta tree retrieval: {json.dumps(bool(config.get('beta', {}).get('tree_rag', False)))}", "info")
    return EXIT_OK


def register(app: typer.Typer) -> None:
    """Attach the `memory` command group to the root Typer app."""
    group = typer.Typer(help="Memory: device limits, layer budgets, search (with the beta tree retriever) and stats.")
    app.add_typer(group, name="memory")

    @group.command("plan", help="Show this machine's limits, the local models that fit, and per-layer context budgets.")
    def plan_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: memory_plan(output)))

    @group.command("search", help="Search episodic, semantic and procedural memory.")
    def search_cmd(
        query: str = typer.Argument(...),
        layer: list[str] = typer.Option([], "--layer", "-l", help="episodic | semantic | procedural | session (repeatable)"),
        tree: bool = typer.Option(False, "--tree", help="Use the beta tree retriever and show its navigation."),
        output: str = typer.Option("rich", "--output", "-o"),
    ) -> None:
        raise typer.Exit(code=guard(lambda: memory_search(query, layer, tree, output)))

    @group.command("stats", help="Records per memory layer and each layer's row share.")
    def stats_cmd(output: str = typer.Option("rich", "--output", "-o")) -> None:
        raise typer.Exit(code=guard(lambda: memory_stats(output)))
