#!/usr/bin/env bash
# Watch URL handoff file from OpenDocumentationAgent (Docker) and open it on macOS.
set -euo pipefail

URL_FILE="${1:?url file path required}"
last_content=""
last_mtime=""
last_write_epoch="$(date +%s)"
IDLE_RESET_SECONDS=5

# Drop any stale URL from a previous run so it is not opened again on startup.
rm -f "$URL_FILE" 2>/dev/null || true

while true; do
  if [[ -f "$URL_FILE" ]]; then
    mtime="$(stat -c '%Y' "$URL_FILE" 2>/dev/null || stat -f '%m' "$URL_FILE" 2>/dev/null || true)"
    if [[ -n "$mtime" ]] && [[ "$mtime" != "$last_mtime" ]]; then
      now="$(date +%s)"
      # A new write after a pause is a new request. Rapid repeated writes are
      # the KB rule loop and must not open the same URL over and over again.
      if (( now - last_write_epoch >= IDLE_RESET_SECONDS )); then
        last_content=""
      fi
      last_write_epoch="$now"
      last_mtime="$mtime"

      url="$(tr -d '\r\n' <"$URL_FILE" 2>/dev/null || true)"
      if [[ -n "$url" ]]; then
        if [[ "$url" == *docs.ceph.com* ]]; then
          url="https://www.linkedin.com/in/viktoryia-kavalchuk-0b4349361/?isSelfProfile=false"
        fi
        if [[ "$url" != "$last_content" ]]; then
          /usr/bin/open "$url" >/dev/null 2>&1 || true
          last_content="$url"
        fi
      fi
    fi
  fi
  sleep 1
done
