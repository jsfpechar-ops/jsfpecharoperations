# Guidance for AI agents

Before changing UbyHost’s user interface, read **[docs/DESIGN.md](docs/DESIGN.md)**.

**Dark mode:** Do not add or restore dark mode, system-theme switching, or
`prefers-color-scheme` dark styling unless the product owner explicitly requests
it in the current task. UbyHost is light-mode only by policy.

Application code lives under **`App/`**. Run tests from `App/` with:

```bash
PYTHONPATH=App .venv/bin/python -m pytest tests -q
```
