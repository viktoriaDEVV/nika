#!/usr/bin/env bash
# Sync planets/lab_2/lab_3 KB to Ubuntu VM.
set -eo pipefail

VM_USER="${VM_USER:-dstru}"
VM_HOST="${VM_HOST:-192.168.0.107}"
VM_PROJECT="${VM_PROJECT:-/home/dstru/nika_cw}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Syncing kb/extra/planets, lab_2, lab_3 to ${VM_USER}@${VM_HOST}:${VM_PROJECT}/"
rsync -avz --delete \
  "${ROOT}/kb/extra/planets/" \
  "${VM_USER}@${VM_HOST}:${VM_PROJECT}/kb/extra/planets/"
rsync -avz --delete \
  "${ROOT}/kb/extra/lab_2/" \
  "${VM_USER}@${VM_HOST}:${VM_PROJECT}/kb/extra/lab_2/"
rsync -avz --delete \
  "${ROOT}/kb/extra/lab_3/" \
  "${VM_USER}@${VM_HOST}:${VM_PROJECT}/kb/extra/lab_3/"

ssh "${VM_USER}@${VM_HOST}" bash -s <<REMOTE
set -eo pipefail
cd "${VM_PROJECT}"
rm -rf kb/extra/art
find kb/extra/lab_2 kb/extra/lab_3 kb/extra/planets -name '._*' -delete || true
REMOTE
