#!/usr/bin/env bash
# Idempotent dependency setup for the UbyHost app.
# Runs after the repository is checked out. Safe to run repeatedly.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/App"

# Cursor's default image ships python3.12 but not the venv/ensurepip package.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt -r requirements-dev.txt

# The guest pages have a browser test (tests/test_guest_browser_e2e.py) that
# must run, not skip, before a guest change is done. Best effort: a sandbox
# without network still gets the rest of the setup.
.venv/bin/python -m pip install --quiet playwright==1.63.0 \
  && (.venv/bin/python -m playwright install --with-deps chromium \
      || .venv/bin/python -m playwright install chromium) \
  || echo "Playwright/Chromium not installed: the guest browser test will skip"

echo "UbyHost dependencies installed into App/.venv"
