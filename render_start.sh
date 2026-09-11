#!/usr/bin/env bash
# Wrapper for hosts that start from the repository root instead of App/.
exec "$(dirname "$0")/App/render_start.sh"
