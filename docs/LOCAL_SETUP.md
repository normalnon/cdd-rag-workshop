# รัน notebook บนเครื่องตัวเอง (Mac / Windows)

notebook รันบนเครื่องของเรา ส่วน LLM, bge-m3 และ Qdrant ของเรายังอยู่บน server
เราใช้ SSH tunnel พาพอร์ตของ server มาไว้ที่เครื่องตัวเอง โค้ดและไฟล์ `.env` จึงไม่ต้องแก้อะไร

```
เครื่องเรา (VS Code + notebook)                server
127.0.0.1:8000  ──── SSH tunnel ────▶  LLM (qwen3-27b)
127.0.0.1:8001  ──── SSH tunnel ────▶  bge-m3
127.0.0.1:163XX ──── SSH tunnel ────▶  Qdrant ของเรา
```

ในคู่มือนี้ใช้เลขประจำตัว 13 เป็นตัวอย่าง ให้เปลี่ยน `cdd13` และ `16313` เป็นเลขของตัวเองทุกจุด

---

## ขั้นที่ 1 ติดตั้งครั้งเดียว

ทั้ง Mac และ Windows ต้องมี VS Code พร้อม extension **Python** และ **Jupyter** (ค้นในแถบ Extensions แล้วกด Install)

**Mac** เปิด Terminal แล้วรัน

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** เปิด PowerShell แล้วรัน

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

ติดตั้งเสร็จให้ปิด Terminal / PowerShell แล้วเปิดใหม่ จากนั้นลองพิมพ์ `uv --version` ต้องขึ้นเลขเวอร์ชัน

---

## ขั้นที่ 2 เอาโปรเจกต์ลงมาที่เครื่อง

เลือกทางใดทางหนึ่ง

**ทาง ก ดาวน์โหลดจาก git** (ได้ไฟล์ชุดล่าสุด)

```bash
git clone <URL ของ repo> cdd-rag
cd cdd-rag
cp .env.example .env        # Windows: copy .env.example .env
uv sync
```

จากนั้นเปิด `.env` แก้ XX เป็นเลขประจำตัว และตั้ง `QDRANT_API_KEY` ให้ตรงกับที่ใช้ตอนเปิด Qdrant บน server (ดูได้จาก `grep QDRANT_API_KEY ~/cdd-rag/.env` บน server) ถ้าไม่ตรง Qdrant จะขึ้น `Unauthorized`

**ทาง ข ดึงโฟลเดอร์ของเราจาก server ด้วย scp** (ได้ `.env` ที่ตั้งไว้แล้วติดมาด้วย แต่เป็นไฟล์ชุดที่อยู่บน server)

`.venv` ของ server ใช้บนเครื่องเราไม่ได้ ต้องลบแล้วสร้างใหม่

**Mac** วางโปรเจกต์ไว้ที่ home ห้ามวางใน Desktop หรือ Documents (ถ้าสองโฟลเดอร์นี้ sync กับ iCloud จะทำให้ `.venv` ใช้ไม่ได้)

```bash
cd ~
scp -r cdd13@<IP server>:~/cdd-rag ./cdd-rag
cd cdd-rag
rm -rf .venv
uv sync
```

**Windows** วางโปรเจกต์ไว้ที่ `C:\Users\<ชื่อเรา>\cdd-rag` ห้ามวางในโฟลเดอร์ที่ sync กับ OneDrive

```powershell
cd $HOME
scp -r cdd13@<IP server>:~/cdd-rag ./cdd-rag
cd cdd-rag
Remove-Item -Recurse -Force .venv
uv sync
```

`uv sync` ครั้งแรกจะดาวน์โหลด Python และ library ใช้เวลาไม่กี่นาที ต้องต่ออินเทอร์เน็ต

---

## ขั้นที่ 3 เปิด tunnel (เปิดค้างไว้ตลอดคาบ)

เปิด Terminal / PowerShell หน้าต่างใหม่ แล้วรัน (คำสั่งเดียวกันทั้ง Mac และ Windows)

```bash
ssh -N -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001 -L 16313:127.0.0.1:16313 cdd13@<IP server>
```

ใส่รหัสผ่านแล้วหน้าจอจะนิ่ง ไม่มีอะไรขึ้นมา นั่นแปลว่าทำงานอยู่ ห้ามปิดหน้าต่างนี้ ถ้าปิด notebook จะต่อ server ไม่ได้ทันที

---

## ขั้นที่ 4 ตรวจว่าต่อได้ครบ

ใช้ Terminal / PowerShell อีกหน้าต่างหนึ่ง (ไม่ใช่หน้าต่าง tunnel)

```bash
cd ~/cdd-rag
uv run python scripts/check_env.py
```

ต้องได้เครื่องหมายถูกครบทั้ง 3 บรรทัด คือ Embedding, LLM และ Qdrant

ถ้ายังไม่เคยโหลดข้อมูล Mr. TyDi สำหรับ Lab 02 ให้รันเพิ่ม (ถ้าโหลดไว้แล้วบน server จะข้ามให้เอง)

```bash
uv run python scripts/index_tydi.py
```

---

## ขั้นที่ 5 เปิด notebook ใน VS Code

1. File → Open Folder → เลือกโฟลเดอร์ `cdd-rag` บนเครื่องเรา
2. เปิดไฟล์ใน `notebooks/`
3. กดชื่อ kernel มุมขวาบน → Select Another Kernel → Python Environments → เลือก `.venv`
   - Mac: path จะเป็น `~/cdd-rag/.venv/bin/python`
   - Windows: path จะเป็น `cdd-rag\.venv\Scripts\python.exe`
4. รัน cell แรก ต้องเห็น `collection : cdd_docs_g13` และ `qdrant : http://127.0.0.1:16313`

---

## เจอปัญหา

| อาการ | สาเหตุ | แก้ |
|---|---|---|
| `check_env` ขึ้นกากบาททั้ง 3 บรรทัด หรือ `Connection refused` | หน้าต่าง tunnel ปิดไปแล้ว หรือหลุด | เปิด tunnel ใหม่ (ขั้นที่ 3) |
| Qdrant กากบาทอย่างเดียว | Qdrant ของเราบน server ไม่ได้เปิด | แจ้งผู้สอน หรือ ssh เข้า server แล้วรัน `cd ~/cdd-rag && docker compose up -d` |
| tunnel ขึ้น `Address already in use` | มีโปรแกรมอื่นบนเครื่องเราใช้พอร์ตนั้นอยู่ | ปิดโปรแกรมนั้น หรือแจ้งผู้สอน |
| notebook ขึ้น `No module named 'cdd_rag'` | เลือก kernel ไม่ใช่ `.venv` ของโปรเจกต์ | เลือก kernel ใหม่ตามขั้นที่ 5 แล้วกด Restart |
| Mac: เลือก `.venv` แล้วยังขึ้น `No module named 'cdd_rag'` | โปรเจกต์อยู่ใน Desktop / Documents | ย้ายโฟลเดอร์ไปไว้ที่ `~/cdd-rag` แล้วทำขั้นที่ 2 ใหม่ |
| Windows: `uv` ไม่รู้จักคำสั่ง | ยังไม่ได้เปิด PowerShell ใหม่หลังติดตั้ง | ปิดแล้วเปิด PowerShell ใหม่ |
| cell แรกขึ้นเลขของคนอื่น (เช่น `g00`) | ไฟล์ `.env` ที่ดึงลงมาไม่ใช่ของเรา | เปิด `.env` แก้เลขให้เป็นของตัวเอง แล้วกด Restart kernel |
