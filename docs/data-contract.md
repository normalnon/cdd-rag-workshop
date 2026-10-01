# Data contract: ระบบ RAG กับฝั่ง Agent / Service

ข้อมูลไหลต่อเนื่องจาก notebook 01 → docs agent → MCP → service ถ้าจะเปลี่ยน field ด้านล่าง ต้องตกลงกันก่อน
โค้ดอ้างอิง: `src/cdd_rag/schema.py` · เหตุผลการออกแบบ: `docs/index-schema.md`

## 1. Qdrant collection

| รายการ | ค่า |
|---|---|
| ชื่อ | `cdd_docs_{GROUP}` (ทั้งกลุ่มใช้ร่วมกัน) |
| vector | `dense` 1024 มิติ (bge-m3), Cosine · `sparse` BM25 (ตัดคำ pythainlp, Qdrant คิด IDF) |
| payload index | `doc_id`, `file_name`, `doc_type` (keyword) · `issued_date` (datetime) · `page`, `chunk_index` (integer) |
| point id | `uuid5(chunk_id)` |
| ingest | `ingest_file()` / `ingest_dir()` — ไฟล์เดิมข้าม, ไฟล์เปลี่ยนลบของเก่าก่อนใส่ใหม่ |

## 2. Payload ต่อ chunk (schema v2)

```json
{
  "chunk_id": "da7f4c1dbda6_c004",
  "doc_id": "da7f4c1dbda6",
  "file_name": "กำหนดการโครงการ.pdf",
  "file_path": "data/raw/กำหนดการโครงการ.pdf",
  "doc_title": "กำหนดการโครงการประชุมเชิงปฏิบัติการ CDD AI ...",
  "doc_type": "กำหนดการ",
  "issued_date": "2026-09-28",
  "tags": ["อบรม", "AI"],
  "page": 2,
  "page_end": 2,
  "chunk_index": 4,
  "section": "วันที่ 3 (30 กันยายน 2569) · วันที่ 4 (1 ตุลาคม 2569)",
  "text": "ข้อความที่ normalize แล้ว (ใช้แสดง/อ้างอิง)",
  "context_header": "วันที่ 3 (30 กันยายน 2569) · วันที่ 4 (1 ตุลาคม 2569)",
  "char_count": 583,
  "pipeline": {"version": "v2", "chunk_size": 600, "overlap": 120, "normalizer": "thai-v1", "sparse": "bm25-newmm-v2"},
  "ingested_at": "2026-09-28T14:30:00+07:00"
}
```

- `page` เริ่มนับที่ 1 (ตรงกับ `#page=` ของ PDF viewer ใน browser)
- `file_path` สัมพัทธ์จาก root project → API เสิร์ฟที่ `/files/{file_path}`
- `chunk_id` ใช้เป็น id อย่างเดียว **frontend ไม่ควรแยกวิเคราะห์ส่วนประกอบ**
- สิ่งที่ถูก embed (ทั้ง dense และ sparse) = `context_header + "\n" + text` (ดู `schema.embedding_text`)
- `doc_type`, `issued_date`, `tags`, `doc_title` มาจาก `data/raw/_manifest.csv`

## 3. ฟังก์ชัน (ใช้ signature เดียวทุกที่)

```python
from cdd_rag.store import search, expand

search(query: str, top_k: int = 5, file_name: str | None = None,
       doc_type: str | None = None, date_from: str | None = None,
       mode: str = "hybrid") -> list[Hit]
# mode: "dense" (ความหมาย) · "sparse" (คำตรงตัว, BM25) · "hybrid" (รวมด้วย RRF — ค่าเริ่มต้น)
# hybrid: score เป็นคะแนน RRF (ใช้เรียงอันดับเท่านั้น ไม่ใช่ความคล้าย 0–1)
# Hit = {chunk_id, text, score, file_name, file_path, page, page_end, section, doc_type}

expand(hit: Hit, window: int = 1) -> list[Hit]   # chunk ก่อน/หลังในเอกสารเดียวกัน
```

| ที่ใช้ | รูปแบบ |
|---|---|
| notebook 01 | เรียกตรง |
| docs agent | tool ชื่อ `search_documents` (ส่ง `doc_type` / `file_name` เป็น argument ได้ · ใช้ `mode` ค่าเริ่มต้น) |
| MCP (บ่าย 1/10) | MCP tool ชื่อ `search_documents` |

## 4. Tool สำหรับ agent (`src/cdd_rag/tools.py`) และ citation

| | |
|---|---|
| ชื่อ | `search_documents(query, doc_type=None, file_name=None)` — hybrid top 5 |
| LangChain | `from cdd_rag.tools import search_documents` (response_format = content_and_artifact) |
| ไม่ใช้ framework | `run_search_documents()` → `(text, hits)` · schema: `OPENAI_TOOL` |
| content (ให้ LLM) | `[da7f4c_c004] ไฟล์ หน้า p` + `หัวข้อ: ...` + เนื้อหา |
| artifact (ให้ frontend) | Hit + `ref` (รหัสอ้างอิง) + `link` (`/files/{file_path}#page={page}`) |

- **รหัสอ้างอิง** = 6 ตัวแรกของ `doc_id` + `_c` + ลำดับ chunk (เช่น `da7f4c_c004`) — ไม่ชนกันแม้ agent ค้นหลายครั้ง
- `collect_sources(messages)` รวม hits จากทุกครั้งที่ค้น → `{ref: hit}` · `link_citations(answer, sources)` แปลงรหัสเป็นลิงก์ Markdown
- `rag.answer()` (ไม่มี agent, ใช้ใน Lab 01) ยังใช้ `[n]` → `sources[n-1]` เหมือนเดิม

คู่มือเริ่มใช้งานฝั่ง agent: `docs/HANDOFF.md`

## 5. Config

ใช้ `.env` ไฟล์เดียว (คัดลอกจาก `.env.example`) — แต่ละคนต่างกันแค่เลขประจำตัว (port Qdrant / collection)
