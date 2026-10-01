# CDD RAG & Agent Workshop (1–2 ต.ค. 2569)

```
src/cdd_rag/      โค้ดจริง (notebook, agent, service import จากที่นี่)
  config.py       อ่าน .env
  schema.py       data contract (ChunkPayload, Hit, citation)
  ingest.py       PDF → normalize ไทย → ตัดหัวกระดาษ → chunk + section + metadata
  embed.py        เรียก bge-m3 ผ่าน OpenAI-compatible API
  sparse.py       BM25 sparse vector (ตัดคำ pythainlp) สำหรับ hybrid search
  store.py        Qdrant: ensure_collection / ingest_file / search(mode=dense|sparse|hybrid) / expand
  rag.py          build_context / answer (RAG แบบไม่มี agent)
  tools.py        tool สำเร็จรูปให้ agent: search_documents (LangChain) / OPENAI_TOOL
notebooks/
  01_basic_rag.ipynb       1/10 เช้า — PDF → dense + sparse → Qdrant → hybrid search → hit@k
  02_retrieval_eval.ipynb  2/10 เช้า — Mr. TyDi: BM25 vs Dense vs Hybrid
  03_agent_starter.ipynb   1/10 10.00 — จุดเริ่มต้น agent ที่เรียก RAG ผ่าน tool
scripts/
  check_env.py             ตรวจ embedding / LLM / Qdrant
  prepare_tydi.py          ผู้สอน: เตรียม Mr. TyDi ชุดย่อย → data/tydi/
  index_tydi.py            index Mr. TyDi → tydi_th_bge_m3 (ผู้สอน --export snapshot / ผู้เรียนโหลดจาก snapshot)
server/                    ผู้สอนเท่านั้น (ไม่ถูก copy ไป /tmp)
  embed.yml                bge-m3 ตัวกลางบน vLLM
  publish.sh               ~/cdd-rag → /tmp/cdd-rag
.env.example               ต้นแบบ .env — cp แล้วแก้ XX เป็นเลขประจำตัว
docker-compose.yml         Qdrant ของแต่ละคน (cdd-rag-<เลข>)
docs/
  HANDOFF.md               สำหรับฝั่ง agent: เริ่มใช้ระบบฝั่ง agent ใน 5 นาที
  data-contract.md         field / tool / citation ที่ตกลงกัน
  index-schema.md          ออกแบบ payload / index + ผลการวัด
data/raw/                  PDF + _manifest.csv (ประเภท/วันที่ของเอกสาร)
```

## เริ่มใช้งาน (ผู้เรียน)

ทุกคนใช้ server เครื่องเดียวกันผ่าน VS Code (Remote-SSH) แต่ละคนมี Qdrant ของตัวเอง
ส่วน LLM (port 8000) และ bge-m3 (port 8001) ใช้ตัวกลางร่วมกันทั้งห้อง

```bash
cp -r /tmp/cdd-rag ~/cdd-rag && cd ~/cdd-rag
cp .env.example .env
nano .env                                 # แก้ XX เป็นเลขประจำตัว (cdd07 → 07) + ตั้ง QDRANT_API_KEY
docker compose up -d                      # Qdrant ของเรา: project cdd-rag-07, port 16307
uv sync
uv run python scripts/check_env.py        # ต้องเขียวทั้ง 3 บรรทัด
uv run python scripts/index_tydi.py       # โหลด Mr. TyDi สำหรับ Lab 02 เข้า Qdrant ของเรา (จาก snapshot)
```

เปิด notebook ใน VS Code
1. File → Open Folder → `~/cdd-rag` (ต้องเปิดที่โฟลเดอร์นี้ ไม่ใช่ home · VS Code หา `.venv` จากโฟลเดอร์ที่เปิด)
2. เปิด `notebooks/01_basic_rag.ipynb` → กดชื่อ kernel มุมขวาบน → Select Another Kernel → Python Environments → `.venv`
   (ถ้าไม่มีในรายการ: Enter interpreter path → `~/cdd-rag/.venv/bin/python`)

`.env` กับ `.venv` เป็นคนละอย่าง: `.env` = ค่าตั้ง (port / key) ที่เราแก้เอง · `.venv` = Python + library ที่ `uv sync` สร้างให้

| | สูตร | ตัวอย่างเลข 07 |
|---|---|---|
| Qdrant | `127.0.0.1:16300 + เลข` | 16307 |
| collection | `cdd_docs_g<เลข>` | `cdd_docs_g07` |
| LLM | ตัวกลาง `127.0.0.1:8000` model `qwen3-27b` | เหมือนกันทุกคน |
| Embedding | ตัวกลาง `127.0.0.1:8001` model `BAAI/bge-m3` | เหมือนกันทุกคน |

ปิด: `docker compose down` (ข้อมูลยังอยู่) · `docker compose down -v` (ลบทิ้ง) · ไม่กระทบคนอื่นเพราะเป็นคนละ project

## แก้ปัญหา

| อาการ | สาเหตุ | แก้ |
|---|---|---|
| `docker compose up` ฟ้อง `ยังไม่มี .env` | ยังไม่ได้ cp | `cp .env.example .env` แล้วแก้ XX |
| `check_env` บอกว่า `.env ยังมี XX` | แก้ไม่ครบ | แก้ทุกบรรทัดที่บอก |
| `invalid ... port` ตอน `docker compose up` | ยังเหลือ `163XX` | ใส่เลข เช่น `16307` |
| `address already in use` | เลขซ้ำกับคนอื่น | ตรวจเลขประจำตัวใน `.env` |
| notebook: `No module named 'cdd_rag'` | kernel ไม่ใช่ `.venv` ของโปรเจกต์ | เลือก kernel ใหม่ตามขั้นข้างบน แล้ว Restart |
| `permission denied ... docker.sock` | user ไม่อยู่ในกลุ่ม docker | แจ้งผู้สอน |
| Qdrant ✘ `Unauthorized` | `QDRANT_API_KEY` ใน `.env` ไม่ตรงกับตอนเปิด container | แก้ `.env` แล้ว `docker compose up -d` ใหม่ |
| Embedding ✘ `Connection error` | bge-m3 ตัวกลางยังไม่เปิด | แจ้งผู้สอน |
| agent ตอบเลยโดยไม่เรียก tool | vLLM ไม่ได้เปิด tool calling | ผู้สอนดู `docs/HANDOFF.md` ข้อ 7 |

ห้ามสั่ง `docker stop` / `docker rm` กับ container ที่ไม่ใช่ของตัวเอง (`docker ps` เห็นของทุกคน)

## ผู้สอน: เตรียมก่อนวันสอน

บนเครื่องตัวเอง
```bash
make pack                                 # rsync ขึ้น cdd-admin:~/cdd-rag (ไม่ส่ง .venv / .env / สื่อสอน / monitoring)
```

บน server ในฐานะ user01 (ครั้งเดียว)
```bash
uvx --from huggingface_hub hf download BAAI/bge-m3 --exclude "onnx/*" --exclude "imgs/*"
cd ~/cdd-rag
docker compose -f server/embed.yml up -d  # bge-m3 ตัวกลางที่ 127.0.0.1:8001 (GPU ~14 GB) รอ log "Application startup complete"
sed 's/XX/00/g' .env.example > .env && nano .env    # เลข 00 = ผู้สอน · ตั้ง QDRANT_API_KEY
docker compose up -d && uv sync
uv run python scripts/check_env.py
uv run python scripts/index_tydi.py --export   # embed 10,000 passages แล้วเก็บ snapshot ไว้ใน data/tydi/ ให้ผู้เรียนโหลด
bash server/publish.sh                    # copy ไป /tmp/cdd-rag เฉพาะไฟล์ที่ผู้เรียนใช้ + เปิดสิทธิ์อ่าน
```

vLLM ต้องเปิด tool calling ก่อนถึง Lab agent (`--enable-auto-tool-choice --tool-call-parser hermes`) ดู `docs/HANDOFF.md` ข้อ 7

`/tmp` อาจถูกล้างเมื่อ server reboot ถ้าหายให้รัน `bash server/publish.sh` ใหม่
