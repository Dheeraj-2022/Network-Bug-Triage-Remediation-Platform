#!/usr/bin/env bash
set -euo pipefail
export NBT_REMEDIATION_MODE="${NBT_REMEDIATION_MODE:-simulate}"
export NBT_VOICE_ALLOW_ANSIBLE="${NBT_VOICE_ALLOW_ANSIBLE:-false}"
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
