#!/usr/bin/env bash
# สร้าง .env จากเลขประจำตัว: port ไม่ชนกับคนอื่นบน server เดียวกัน + สุ่มรหัส Grafana
#
#   ./init.sh 07        → STUDENT=07, Prometheus 19097, Grafana 13007
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -ne 1 ] || ! [[ "$1" =~ ^[0-9]{1,2}$ ]]; then
  echo "ใช้: ./init.sh <เลขประจำตัว 0-99>   เช่น ./init.sh 07" >&2
  exit 1
fi
N=$((10#$1))
STUDENT=$(printf '%02d' "$N")
PROM=$((19090 + N))
GRAF=$((13000 + N))

if [ -f .env ]; then
  echo ".env มีอยู่แล้ว (ลบก่อนถ้าจะสร้างใหม่: rm .env)" >&2
  exit 1
fi

# port ต้องว่าง (ss มีบน Linux ทั่วไป)
if command -v ss >/dev/null && ss -tln | grep -qE "127\.0\.0\.1:($PROM|$GRAF)\b|\*:($PROM|$GRAF)\b|0\.0\.0\.0:($PROM|$GRAF)\b"; then
  echo "port $PROM หรือ $GRAF ถูกใช้อยู่แล้ว (เลข $STUDENT ซ้ำกับคนอื่นหรือเปล่า?)" >&2
  exit 1
fi

PASS=$(head -c 12 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 12)
umask 077
cat > .env <<EOF
STUDENT=$STUDENT
PROMETHEUS_PORT=$PROM
GRAFANA_PORT=$GRAF
GRAFANA_PASSWORD=$PASS
EOF
chmod 644 prometheus.yml     # Prometheus ใน container รันเป็น user nobody ต้องอ่านไฟล์นี้ได้

echo "สร้าง .env แล้ว (อ่านได้เฉพาะเรา)"
echo "  project     monitor-$STUDENT"
echo "  Prometheus  127.0.0.1:$PROM"
echo "  Grafana     127.0.0.1:$GRAF   user: admin   รหัส: $PASS"
echo "ต่อไป: docker compose up -d   แล้ว forward port $PROM และ $GRAF ใน VS Code"
