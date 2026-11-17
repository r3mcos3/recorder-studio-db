#!/usr/bin/env sh
set -e
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1
exec python3 -m studio.server
