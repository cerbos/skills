#!/usr/bin/env bash
set -euo pipefail
# Python is hidden from the agent; the verifier uses the relocated interpreter.
exec /usr/local/libexec/verifier-python /tests/verify.py
