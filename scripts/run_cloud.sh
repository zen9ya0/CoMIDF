#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
if [ -f /etc/comidf/cloud_env.sh ]; then
  . /etc/comidf/cloud_env.sh
fi
. "$ROOT_DIR/venv/bin/activate"
exec python -m uvicorn cloud_platform.uer_gateway.receiver:app --host 0.0.0.0 --port 9092
