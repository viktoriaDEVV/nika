#!/usr/bin/env bash
# Manage the Ubuntu NIKA container (full stack on container start, no build of sc-machine).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAGING="$ROOT/.nika-ubuntu-data/nika_cw"
COMPOSE=(docker compose -f "$ROOT/docker/ubuntu-nika/docker-compose.yml")
URL_FILE="$STAGING/.last_open_documentation_url"
URL_WATCHER_PID_FILE="$ROOT/.nika-ubuntu-data/open-url-watcher.pid"

ensure_open_url_watcher() {
  # Opens URLs written by OpenDocumentationAgent inside Docker on the Mac host browser.
  mkdir -p "$(dirname "$URL_FILE")" "$(dirname "$URL_WATCHER_PID_FILE")"
  if [ -f "$URL_WATCHER_PID_FILE" ]; then
    local old_pid
    old_pid="$(cat "$URL_WATCHER_PID_FILE" 2>/dev/null || true)"
    if [ -n "${old_pid:-}" ] && kill -0 "$old_pid" 2>/dev/null \
      && ps -p "$old_pid" -o command= 2>/dev/null | grep -q 'open_docs_url_watcher.sh'; then
      return 0
    fi
    kill "${old_pid:-}" 2>/dev/null || true
    rm -f "$URL_WATCHER_PID_FILE"
  fi
  nohup bash "$ROOT/scripts/open_docs_url_watcher.sh" "$URL_FILE" \
    >"$ROOT/.nika-ubuntu-data/open-url-watcher.log" 2>&1 &
  echo $! >"$URL_WATCHER_PID_FILE"
  echo "Host URL watcher started (pid $(cat "$URL_WATCHER_PID_FILE"))"
}

stop_open_url_watcher() {
  if [ -f "$URL_WATCHER_PID_FILE" ]; then
    local old_pid
    old_pid="$(cat "$URL_WATCHER_PID_FILE" 2>/dev/null || true)"
    if [ -n "${old_pid:-}" ]; then
      kill "$old_pid" 2>/dev/null || true
    fi
    rm -f "$URL_WATCHER_PID_FILE"
  fi
}

sync_kb_to_staging() {
  mkdir -p "$STAGING/kb/extra"
  rsync -a --delete "$ROOT/kb/extra/planets/" "$STAGING/kb/extra/planets/"
  rsync -a --delete "$ROOT/kb/extra/lab_2/" "$STAGING/kb/extra/lab_2/"
  if [ -d "$ROOT/kb/extra/laba" ]; then
    rsync -a --delete "$ROOT/kb/extra/laba/" "$STAGING/kb/extra/laba/"
  fi
  rm -rf "$STAGING/kb/extra/lab_tasks" "$STAGING/kb/extra/art"
  # C++ modules (new agents). Keep container-built generated/ headers.
  rsync -a --delete \
    --exclude 'generated/' \
    --exclude '*.gen_cache' \
    "$ROOT/problem-solver/cxx/" "$STAGING/problem-solver/cxx/"
  # drop macOS junk / old experiments that break builder
  find "$STAGING/kb/extra/planets" "$STAGING/kb/extra/lab_2" "$STAGING/kb/extra/laba" \
    -name '._*' -delete 2>/dev/null || true
  echo "Synced kb/extra/{planets,lab_2,laba} + problem-solver/cxx -> .nika-ubuntu-data"
}

rebuild_kb_in_container() {
  docker exec nika-ubuntu bash -lc '
    set -euo pipefail
    export LD_LIBRARY_PATH=/home/nika/nika_cw/bin:/home/nika/nika_cw/bin/extensions
    cd /home/nika/nika_cw
    source scripts/set_vars.sh
    # Do not use pkill -f: the pattern matches this bash command line and kills the rebuild.
    for p in $(pgrep -x sc-server || true); do kill "$p" || true; done
    sleep 2
    ./scripts/build_kb.sh
  '
}

rebuild_cxx_in_container() {
  docker exec nika-ubuntu bash -lc '
    set -euo pipefail
    export LD_LIBRARY_PATH=/home/nika/nika_cw/bin:/home/nika/nika_cw/bin/extensions
    cd /home/nika/nika_cw
    source scripts/set_vars.sh
    for p in $(pgrep -x sc-server || true); do kill "$p" || true; done
    sleep 2
    ./scripts/build_problem_solver.sh
  '
}

case "${1:-}" in
  up|start)
    "${COMPOSE[@]}" up -d --build
    ensure_open_url_watcher
    echo "UI: http://localhost:3033  sc-web: http://localhost:8000  sc-server: ws://localhost:8090"
    ;;
  down|stop)
    stop_open_url_watcher
    "${COMPOSE[@]}" down
    ;;
  restart)
    "${COMPOSE[@]}" restart
    ensure_open_url_watcher
    ;;
  sync-kb)
    sync_kb_to_staging
    ;;
  rebuild-cxx)
    sync_kb_to_staging
    rebuild_cxx_in_container
    "${COMPOSE[@]}" restart
    ensure_open_url_watcher
    echo "C++ agent rebuilt. Wait ~30s, then try: Я тебя люблю."
    ;;
  rebuild-kb)
    # 1) copy sources from repo  2) sc-builder --clear  3) restart stack
    sync_kb_to_staging
    rebuild_kb_in_container
    "${COMPOSE[@]}" restart
    ensure_open_url_watcher
    echo "KB rebuilt. Wait ~30s for UI, then open http://localhost:3033"
    ;;
  logs)
    "${COMPOSE[@]}" logs -f --tail=100
    ;;
  shell)
    docker exec -it nika-ubuntu bash
    ;;
  status)
    docker ps --filter name=nika-ubuntu --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    curl -s -o /dev/null -w "ui=%{http_code}\n" http://127.0.0.1:3033/ || true
    curl -s -o /dev/null -w "scweb=%{http_code}\n" http://127.0.0.1:8000/ || true
    ;;
  *)
    echo "Usage: $0 {up|start|down|stop|restart|sync-kb|rebuild-kb|rebuild-cxx|logs|shell|status}"
    exit 1
    ;;
esac
