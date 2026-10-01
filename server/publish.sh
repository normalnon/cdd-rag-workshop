#!/usr/bin/env bash
# ผู้สอนรันบน server: copy ~/cdd-rag → /tmp/cdd-rag เฉพาะไฟล์ที่ผู้เรียนใช้ แล้วเปิดให้ทุกคนอ่านได้
#
#   bash server/publish.sh               → /tmp/cdd-rag
#   bash server/publish.sh /srv/cdd-rag  → ที่อื่น
#
# ผู้เรียน: cp -r /tmp/cdd-rag ~/cdd-rag
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=${1:-/tmp/cdd-rag}

if [ ! -f data/tydi/tydi_th_bge_m3.snapshot ]; then
  echo "ยังไม่มี snapshot ของ TyDi — รันก่อน: uv run python scripts/index_tydi.py --export" >&2
  exit 1
fi

# ไม่ส่ง: .env / .venv ของผู้สอน · ไฟล์ที่ผู้สอนใช้คนเดียว (bge-m3 ตัวกลาง, เตรียม TyDi, pack) · ไฟล์สำหรับเครื่อง dev
rsync -a --delete \
  --exclude .env --exclude .venv --exclude __pycache__ --exclude .ipynb_checkpoints \
  --exclude Makefile --exclude .gitignore --exclude monitoring \
  --exclude server/ \
  --exclude scripts/prepare_tydi.py --exclude scripts/local_embed_server.py \
  --exclude requirements.txt \
  ./ "$DEST"/
chmod -R a+rX "$DEST"

echo "วางไว้ที่ $DEST แล้ว ($(du -sh "$DEST" | cut -f1))"
echo "ผู้เรียน: cp -r $DEST ~/cdd-rag && cd ~/cdd-rag && cp .env.example .env"
