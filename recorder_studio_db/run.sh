#!/usr/bin/with-contenv sh
# with-contenv exposes the container environment (SUPERVISOR_TOKEN) that s6-overlay otherwise hides.
set -e
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1
if [ -z "$SUPERVISOR_TOKEN" ] && [ -z "$STUDIO_DEV" ]; then echo "WARNING: SUPERVISOR_TOKEN is not set; Home Assistant API calls will fail"; fi
exec python3 -m studio.server
