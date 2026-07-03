#!/bin/bash
# SessionStart hook (Claude Code on the web only): ensure Python 3.14.4 and a
# current uv are installed, then sync project dependencies from uv.lock.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# uv's bundled Python-download manifest can lag behind the latest CPython
# patch releases -- the version shipped in some base images doesn't know
# about 3.14.4 ("No download found for request: cpython-3.14.4-...").
# `uv self update` fixes this but calls api.github.com, which the sandbox
# proxy blocks with a 403 even when GITHUB_TOKEN is set. Installing uv from
# PyPI instead avoids GitHub entirely and needs no extra env vars/tokens.
python3 -m pip install --user --upgrade uv
export PATH="$HOME/.local/bin:$PATH"
# Persist the PATH addition for the rest of the session (this hook's PATH
# export doesn't survive into the agent's own shell otherwise).
echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"

uv python install 3.14.4
uv python pin 3.14.4
uv sync
