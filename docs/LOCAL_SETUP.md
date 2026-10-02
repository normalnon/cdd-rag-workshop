# รัน notebook บนเครื่องตัวเอง (Mac / Windows)

notebook และ Qdrant (ฐานข้อมูลเวกเตอร์) อยู่บนเครื่องของเรา ส่วน LLM และ bge-m3 ใช้ตัวกลางบน server
เราใช้ SSH tunnel พาพอร์ต 8000 และ 8001 ของ server มาไว้ที่เครื่องตัวเอง

```
เครื่องเรา                                      server
  VS Code + notebook
  Qdrant ใน Docker  127.0.0.1:163XX
  127.0.0.1:8000  ──── SSH tunnel ────▶  LLM (qwen3-27b)
  127.0.0.1:8001  ──── SSH tunnel ────▶  bge-m3
```

ในคู่มือนี้ใช้เลขประจำตัว 13 เป็นตัวอย่าง ให้เปลี่ยน `cdd13` และ `16313` เป็นเลขของตัวเองทุกจุด

ทำตามลำดับ ห้ามข้ามขั้น

---

## ขั้นที่ 1 ติดตั้งโปรแกรม (ครั้งเดียว)

1. **VS Code** พร้อม extension **Python** และ **Jupyter** (ค้นในแถบ Extensions แล้วกด Install)
2. **Docker Desktop** ดาวน์โหลดจาก https://www.docker.com/products/docker-desktop/ ติดตั้งแล้วเปิดโปรแกรมทิ้งไว้ (รูปวาฬที่แถบเมนูต้องขึ้นว่า running)
   - Windows: ตัวติดตั้งจะให้เปิด WSL 2 และอาจต้อง restart เครื่อง
3. **uv**

   Mac เปิด Terminal แล้วรัน

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   Windows เปิด PowerShell แล้วรัน

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

ติดตั้งเสร็จให้ปิด Terminal / PowerShell แล้วเปิดใหม่ จากนั้นลองพิมพ์ `uv --version` และ `docker --version` ต้องขึ้นเลขเวอร์ชันทั้งคู่

---

## ขั้นที่ 2 ดาวน์โหลดโปรเจกต์และสร้าง .venv

วางโปรเจกต์ไว้ที่ home
- Mac ห้ามวางใน Desktop หรือ Documents (ถ้าสองโฟลเดอร์นี้ sync กับ iCloud จะทำให้ `.venv` ใช้ไม่ได้)
- Windows ห้ามวางในโฟลเดอร์ที่ sync กับ OneDrive

```bash
cd ~
git clone https://github.com/normalnon/cdd-rag-workshop.git cdd-rag
cd cdd-rag
uv sync
```

`uv sync` สร้างโฟลเดอร์ `.venv` (Python + library ทั้งหมด) ครั้งแรกใช้เวลาไม่กี่นาที ต้องต่ออินเทอร์เน็ต

---

## ขั้นที่ 3 ตั้งค่า .env

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

เปิดไฟล์ `.env` ใน VS Code แล้ว
- แก้ `XX` ทุกจุดเป็นเลขประจำตัว 2 หลัก
- ตั้ง `QDRANT_API_KEY` เป็นรหัสอะไรก็ได้ เช่น `1234` (Qdrant ตัวนี้เป็นของเราเอง เราตั้งรหัสเอง)

---

## ขั้นที่ 4 เปิด Qdrant บนเครื่องตัวเอง

ต้องเปิด Docker Desktop ไว้ก่อน แล้วรันในโฟลเดอร์ `cdd-rag`

```bash
docker compose up -d
```

จะได้ container `cdd-rag-13` ที่พอร์ต `16313` ทำครั้งเดียว ครั้งต่อไปขอแค่ Docker Desktop เปิดอยู่ container จะเปิดตามเอง

ถ้าแก้ `QDRANT_API_KEY` ภายหลัง ต้องรัน `docker compose up -d` ใหม่ รหัสจึงจะเปลี่ยนตาม

---

## ขั้นที่ 5 เปิด tunnel ไปหา LLM (เปิดค้างไว้ตลอดคาบ)

เปิด Terminal / PowerShell หน้าต่างใหม่ แล้วรัน (คำสั่งเดียวกันทั้ง Mac และ Windows)

```bash
ssh -N -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001 cdd13@<IP server>
```

ใส่รหัสผ่านแล้วหน้าจอจะนิ่ง ไม่มีอะไรขึ้นมา นั่นแปลว่าทำงานอยู่ ห้ามปิดหน้าต่างนี้

tunnel มีแค่ 2 พอร์ต ห้ามใส่พอร์ต 163XX เพิ่ม เพราะพอร์ตนั้นเป็นของ Qdrant บนเครื่องเราแล้ว ถ้าใส่จะชนกัน

---

## ขั้นที่ 6 ตรวจว่าต่อได้ครบ และโหลดข้อมูล Lab 02

ใช้ Terminal / PowerShell อีกหน้าต่างหนึ่ง (ไม่ใช่หน้าต่าง tunnel)

```bash
cd ~/cdd-rag
uv run python scripts/check_env.py
```

ต้องได้เครื่องหมายถูกครบทั้ง 3 บรรทัด คือ Embedding, LLM และ Qdrant

จากนั้นโหลดข้อมูล Mr. TyDi สำหรับ Lab 02 (ทำครั้งเดียว ใช้เวลาประมาณ 3–5 นาที ต้องเปิด tunnel ไว้)

```bash
uv run python scripts/index_tydi.py
```

เสร็จแล้วจะขึ้น `รวม 10000 points`

---

## ขั้นที่ 7 เปิด notebook ใน VS Code

1. File → Open Folder → เลือกโฟลเดอร์ `cdd-rag` (ต้องเป็นโฟลเดอร์นี้ตรงๆ)
2. เปิดไฟล์ใน `notebooks/`
3. กดชื่อ kernel มุมขวาบน → Select Another Kernel → Python Environments → เลือก `.venv`
   - ถ้าไม่เห็น `.venv` ให้กด Enter interpreter path แล้วใส่
     - Mac: `~/cdd-rag/.venv/bin/python`
     - Windows: `C:\Users\<ชื่อเรา>\cdd-rag\.venv\Scripts\python.exe`
   - ชื่อ kernel ต้องเป็น `.venv` ไม่ใช่ `base` หรือ conda
4. รัน cell แรก ต้องเห็น `collection : cdd_docs_g13` และ `qdrant : http://127.0.0.1:16313`

---

## ทุกครั้งที่กลับมาเรียน

1. เปิด Docker Desktop
2. เปิด tunnel (ขั้นที่ 5)
3. เปิด notebook

---

## เจอปัญหา

| อาการ | สาเหตุ | แก้ |
|---|---|---|
| หา `.venv` ไม่เจอ หรือ `No module named 'cdd_rag'` | ยังไม่ได้ `uv sync` หรือเลือก kernel ผิด | รัน `uv sync` ในโฟลเดอร์ `cdd-rag` แล้วเลือก kernel ใหม่ตามขั้นที่ 7 แล้ว Restart kernel |
| Mac: เลือก `.venv` แล้วยังขึ้น `No module named 'cdd_rag'` | โปรเจกต์อยู่ใน Desktop / Documents | ย้ายโฟลเดอร์ไปไว้ที่ `~/cdd-rag` แล้วรัน `uv sync` ใหม่ |
| Embedding / LLM ขึ้น `Connection error` | หน้าต่าง tunnel ปิดไปแล้ว หรือหลุด | เปิด tunnel ใหม่ (ขั้นที่ 5) |
| Qdrant ขึ้น `Connection refused` | Docker Desktop ไม่ได้เปิด หรือยังไม่ได้ `docker compose up -d` | เปิด Docker Desktop แล้วทำขั้นที่ 4 |
| Qdrant ขึ้น `401 Unauthorized` | รหัสใน `.env` ไม่ตรงกับตอนเปิด container | รัน `docker compose up -d` ใหม่ แล้ว Restart kernel |
| `Collection tydi_th_bge_m3 doesn't exist` | ยังไม่ได้โหลดข้อมูล Lab 02 | ทำขั้นที่ 6 (`index_tydi.py`) |
| tunnel ขึ้น `Address already in use` | มีโปรแกรมอื่นใช้พอร์ต 8000 / 8001 หรือใส่พอร์ต 163XX ใน tunnel | ปิดโปรแกรมนั้น และใช้คำสั่ง tunnel ตามขั้นที่ 5 เป๊ะๆ |
| `docker compose up` ขึ้น `Cannot connect to the Docker daemon` | Docker Desktop ยังไม่ได้เปิด | เปิด Docker Desktop รอจนขึ้น running แล้วรันใหม่ |
| แก้ `.env` แล้วค่าใน notebook ยังเหมือนเดิม | notebook อ่าน `.env` ครั้งเดียวตอนเริ่ม kernel | กดปุ่ม Restart (↻) บนแถบ notebook แล้วรันจาก cell แรก |
| Windows: `uv` ไม่รู้จักคำสั่ง | ยังไม่ได้เปิด PowerShell ใหม่หลังติดตั้ง | ปิดแล้วเปิด PowerShell ใหม่ |
