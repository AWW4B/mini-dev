# Rules for coding agents

1. Work on ONE target file. Read only its header and the files listed under its CONNECTS TO.
2. Implement only that file. If its contract with another file must change, stop and report; do not edit the other file.
3. Make the smallest diff that satisfies the header. Keep every declared name and signature.
4. Reuse existing functions from the files listed under CONNECTS TO; do not duplicate them.
5. Ask before adding or upgrading a dependency (pins live in pyproject.toml and uv.lock).
6. Use pathlib, argument-list subprocess calls and asf.platform.select.get_platform(); it must run on Windows and Linux.
7. Before finishing, run the header's DONE WHEN checks and:
   - uv run python scripts/check_headers.py
   - uv run python scripts/scan_forbidden.py
   - uv run ruff check <file> and uv run mypy <file>
8. Never commit secrets, model files or run data.
