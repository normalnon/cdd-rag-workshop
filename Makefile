# make setup — ติดตั้ง/อัปเดต environment แล้วตรวจความพร้อม
# Mac: ถ้าโปรเจกต์อยู่ใน Desktop/Documents (sync กับ iCloud) ไฟล์ใน .venv จะถูกตั้ง flag hidden
#      แล้ว Python 3.13 ข้ามไฟล์ .pth → import cdd_rag ไม่เจอ
#      แก้: ให้ .venv เป็น symlink ไปไว้นอก Desktop (make mac-venv ครั้งเดียว)
setup:
	uv sync
	uv run python scripts/check_env.py

mac-venv:
	rm -rf .venv
	mkdir -p $$HOME/.venvs
	ln -s $$HOME/.venvs/cdd-rag .venv
	uv sync

# make pack — ผู้สอน: ส่งโปรเจกต์ขึ้น home ของ user01 บน server (เตรียม / export snapshot ที่นี่ แล้วค่อย copy ไป /tmp/cdd-rag)
# ไม่ส่ง .venv (symlink ของ Mac), .env (key ของเรา), สื่อสอน, monitoring (สอนจาก ~/workshop-monitoring) · ไม่ลบ snapshot TyDi ที่สร้างไว้บน server
SERVER ?= cdd-admin
DEST ?= ~/cdd-rag
pack:
	rsync -av --delete --chmod=Da+rx,Fa+r \
		--exclude .git --exclude '.venv*' --exclude .env --exclude '*.swp' \
		--exclude 'เนื้อหาการสอน' --exclude monitoring --exclude __pycache__ \
		--exclude .ipynb_checkpoints --exclude .DS_Store --exclude '*.snapshot' \
		./ $(SERVER):$(DEST)/

.PHONY: setup mac-venv pack
