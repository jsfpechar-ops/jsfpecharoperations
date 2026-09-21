# Guidance for AI agents

Before changing UbyHost’s user interface, read **[docs/DESIGN.md](docs/DESIGN.md)**.

**Dark mode:** Do not add or restore dark mode, system-theme switching, or
`prefers-color-scheme` dark styling unless the product owner explicitly requests
it in the current task. UbyHost is light-mode only by policy.

Application code lives under **`App/`**. Run tests from `App/` with:

```bash
.venv/bin/python -m pytest tests -q
```

Do not add `PYTHONPATH=App` here. From `App/` that resolves to `App/App`, which
on a case-insensitive filesystem (macOS) is the same directory as `App/app` —
so `app/operator.py` shadows the standard library `operator` module and pytest
fails during collection.
