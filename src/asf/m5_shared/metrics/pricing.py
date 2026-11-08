# FILE: src/asf/m5_shared/metrics/pricing.py
# ROLE: Computes call cost from the user-editable pricing table, flagging estimates.
# ARCH REF: M5; p10; D-27
# OWNS: Cost calculation
# DOES NOT OWN: Fetching prices (never fetched from the internet)
# CONNECTS TO (external boundaries only):
#   - imports from src/asf/config/loader.py: load_layered (reads pricing.toml)
#   - called by src/asf/m5_shared/gateway/usage_callback.py: price_for
#   - called by tests/m5_shared/metrics/test_pricing.py: price_for
#   - emits/consumes: none
# INSTRUCTIONS (strict, imperative):
#   1. Implement only this file. If this file's contract with another file must change, stop and report; do not edit the other file.
#   2. Keep every public name and signature declared below exactly as written; they are the contract other files rely on.
#   3. Use only the standard library, the pinned dependencies in pyproject.toml, and the files listed under CONNECTS TO. Ask before adding a dependency.
#   4. Open text files with encoding="utf-8" explicitly.
# FORBIDDEN: shell=True; os.system; hardcoded absolute paths; container runtimes; importing project modules not listed under CONNECTS TO; printing secrets or API keys
# ERRORS: Raise a subclass of asf.contracts.errors.AsfError with an actionable message; never swallow exceptions silently.
# DONE WHEN: (1) tests/m5_shared/metrics/test_pricing.py passes on Windows and Linux. (2) `uv run python scripts/check_headers.py` reports no problem for this file. (3) `uv run ruff check src/asf/m5_shared/metrics/pricing.py` and `uv run mypy src/asf/m5_shared/metrics/pricing.py` are clean.

from asf.config.loader import load_layered


def price_for(provider: str, model: str, tokens_in: int, tokens_out: int) -> tuple[float, bool]:
    """Return (cost, estimated). Missing entries cost 0.0 with estimated=True."""
    try:
        pricing = load_layered("pricing.toml")
    except Exception:
        return (0.0, True)

    provider_dict = pricing.get(provider)
    if not isinstance(provider_dict, dict):
        return (0.0, True)

    model_dict = provider_dict.get(model)
    if not isinstance(model_dict, dict):
        return (0.0, True)

    in_rate = model_dict.get("input_per_mtok", model_dict.get("input_per_mtoken", model_dict.get("input")))
    out_rate = model_dict.get("output_per_mtok", model_dict.get("output_per_mtoken", model_dict.get("output")))

    if in_rate is None or out_rate is None:
        return (0.0, True)

    try:
        cost = (tokens_in / 1_000_000.0) * float(in_rate) + (tokens_out / 1_000_000.0) * float(out_rate)
        return (cost, False)
    except (ValueError, TypeError):
        return (0.0, True)
