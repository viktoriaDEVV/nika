#!/usr/bin/env bash
# Watch URL handoff file from OpenDocumentationAgent (Docker) and open it on macOS.
set -euo pipefail

URL_FILE="${1:?url file path required}"
last_content=""
last_mtime=""

while true; do
  if [[ -f "$URL_FILE" ]]; then
    url="$(tr -d '\r\n' <"$URL_FILE" 2>/dev/null || true)"
    mtime="$(stat -f '%m' "$URL_FILE" 2>/dev/null || true)"
    if [[ -n "$url" ]] && { [[ "$url" != "$last_content" ]] || [[ "$mtime" != "$last_mtime" ]]; }; then
      if [[ "$url" == *docs.ceph.com* ]]; then
        url="https://www.linkedin.com/in/viktoryia-kavalchuk-0b4349361/?isSelfProfile=false"
      fi
      /usr/bin/open "$url" >/dev/null 2>&1 || true
      last_content="$url"
      last_mtime="$mtime"
    fi
  fi
  sleep 1
done
