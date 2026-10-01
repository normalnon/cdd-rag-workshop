# Index schema v2 (ใช้งานแล้วใน `src/cdd_rag/`)

> v2 เพิ่ม field โดย **ไม่ลบ/ไม่เปลี่ยนชื่อ field เดิม** ของ v1 · รูปแบบ `chunk_id` เปลี่ยนเป็น `{doc_id}_c{idx:03d}`

## ผลการวัดที่ใช้ตัดสินค่า default (golden set Lab 01, 8 ข้อ)

| การตั้งค่า | hit@1 | สรุป |
|---|---|---|
| chunk 800 · embed text | 0.88 | หน้า 3 ทั้งหน้าเป็น chunk เดียว หมายเหตุ "อาหารว่าง" ถูกกลบ |
| chunk 800 · embed ชื่อเอกสาร › หัวข้อ + text | 0.75 | ชื่อเอกสารซ้ำทุก chunk → ทุก chunk ดูคล้ายกัน |
| chunk 400–600 · embed text หรือ หัวข้อ + text | 1.00 | |
| **ค่าที่ใช้: chunk 600 / overlap 120 · embed หัวข้อ + text** | **1.00** | หัวข้อไม่ทำคะแนนตก และช่วย LLM รู้ว่าเนื้อหาอยู่ใต้หัวข้อไหน |

ข้อมูลยังน้อย (เอกสาร 1 ไฟล์) — ต้องวัดซ้ำเมื่อมีเอกสารจริงของกรมฯ

## หลักคิด: เก็บเพื่อใคร

| ผู้ใช้ข้อมูล | ต้องการ | field ที่ตอบโจทย์ |
|---|---|---|
| **Retriever** | หาเจอ + กรองได้ | vector, `doc_type`, `issued_date`, `section` |
| **LLM** | บริบทพอจะตอบ | `text` + `context_header`, chunk ข้างเคียง |
| **Frontend / citation** | เปิดไฟล์หน้าที่ถูก | `file_path`, `page`, `page_end` |
| **Eval / ops** | รู้ว่า index ด้วยอะไร, ingest ซ้ำได้ | `doc_id`, `pipeline`, `ingested_at` |

## 1. Collection

```
collection: cdd_docs_{group}
vectors:
  dense  : 1024, Cosine          (bge-m3 — ใช้ตอนนี้)
sparse_vectors:
  sparse : (สำรองไว้ทำ hybrid)   ← ต้องประกาศตั้งแต่สร้าง collection
```

**sparse ใช้งานแล้ว (hybrid search):** BM25 — ตัดคำด้วย pythainlp (newmm), เลขมิติ = crc32(คำ), ค่าฝั่งเอกสาร = BM25 TF (k1=1.2, b=0.75, avgdl=256), IDF ให้ Qdrant คำนวณ (`Modifier.IDF`) · โค้ด: `src/cdd_rag/sparse.py`

ผลวัด hit@1 (golden set 11 ข้อ รวมคำถามยาก "ห้อง 303", "อูบุนตู", "คอนเทนเนอร์"):

| chunk_size | dense | sparse | hybrid |
|---|---|---|---|
| 400 / 600 | 0.91 | 0.82 | **1.00** |
| 800 | 0.82 | 0.82 | **1.00** |

→ `search()` ค่าเริ่มต้น `mode="hybrid"` · บน Mr. TyDi (Lab 02) dense อย่างเดียวดีกว่า → ต้องวัดซ้ำเมื่อมีเอกสารจริงของกรมฯ

**ทำไมประกาศ sparse ตั้งแต่สร้าง collection:** ภาษาไทยมีคำเฉพาะ (ชื่อโครงการ เลขระเบียบ "ข้อ 12") ที่ dense หาพลาดได้ — hybrid (dense + keyword) คือขั้นถัดไปที่ใช้สอนได้ และการเพิ่ม vector ใหม่ทีหลังต้องสร้าง collection ใหม่ + index ใหม่ทั้งหมด

## 2. Payload ต่อ chunk

```jsonc
{
  // --- ตัวตน (v1) ---
  "chunk_id":    "da7f4c1dbda6_c007",   // v2: ใช้ลำดับทั้งเอกสาร (ดูข้อ 4)
  "doc_id":      "da7f4c1dbda6",        // sha1 ของไฟล์ → ไฟล์เปลี่ยน = doc_id ใหม่

  // --- แหล่งที่มา ---
  "file_name":   "กำหนดการโครงการ.pdf",
  "file_path":   "data/raw/กำหนดการโครงการ.pdf",
  "doc_title":   "กำหนดการโครงการประชุมเชิงปฏิบัติการ ... CDD AI",
  "doc_type":    "กำหนดการ",            // ระเบียบ | ประกาศ | คู่มือ | หนังสือเวียน | กำหนดการ | อื่นๆ
  "issued_date": "2026-09-28",          // null ได้ — ใช้ตอบ "ฉบับล่าสุด"
  "tags":        ["อบรม", "AI"],

  // --- ตำแหน่ง (สำหรับ citation) ---
  "page":        2,                     // หน้าเริ่ม (v1)
  "page_end":    2,                     // หน้าสุดท้าย (chunk คร่อมหน้า)
  "chunk_index": 7,                     // ลำดับในเอกสารทั้งเล่ม → หา chunk ก่อน/หลังได้
  "section":     "วันที่ 3 (30 กันยายน 2569)",   // หัวข้อล่าสุดที่อยู่เหนือ chunk

  // --- เนื้อหา ---
  "text":           "15.30 - 17.00 น. การติดตั้งและดูแลบริการด้วย Docker ...",  // แสดง/อ้างอิง (v1)
  "context_header": "กำหนดการโครงการ › วันที่ 3 (30 กันยายน 2569)",
  "char_count":     612,

  // --- การ index ---
  "pipeline":    {"version": "v2", "chunk_size": 800, "overlap": 150, "embed_model": "BAAI/bge-m3", "normalizer": "thai-v1"},
  "ingested_at": "2026-09-28T14:00:00+07:00"
}
```

### 2.1 `text` vs สิ่งที่ embed (สำคัญที่สุด)

```
ที่ embed  = context_header + "\n" + text      (context_header = section)
ที่เก็บ/แสดง = text
```

ingest ยังตัด **หัวกระดาษที่ซ้ำทุกหน้า** (บรรทัดใน 8 บรรทัดแรกที่ซ้ำ ≥ ครึ่งหนึ่งของจำนวนหน้า) ก่อนแบ่ง chunk
`section` = หัวข้อทั้งหมดที่ chunk ครอบคลุม เช่น `วันที่ 3 (...) · วันที่ 4 (...)`

**ปัญหาที่เจอจริงใน Lab 01:** chunk เรื่อง Docker ไม่มีคำว่า "วันที่ 3 (30 กันยายน)" เพราะหัวข้อไปอยู่ chunk ก่อนหน้า
→ retriever หาหน้าถูก แต่ LLM ตอบไม่ได้ว่า "วันไหน"
→ แก้ด้วย `section` ที่ ingest จับจากบรรทัดหัวข้อ (regex: `^วันที่ \d+ (...)`, `^หมวด`, `^ส่วนที่`, `^ข้อ \d+`) แล้วแปะหน้า chunk ตอน embed และตอนส่งให้ LLM

ใช้เป็นเนื้อหาสอน "contextual chunking" ได้: วัด hit@k + ความถูกต้องของคำตอบ ก่อน/หลังเพิ่ม header

### 2.2 เมทาดาทาระดับเอกสารมาจากไหน

| field | วิธีได้มา |
|---|---|
| `doc_title` | PDF metadata → ถ้าว่าง ใช้บรรทัดแรกของหน้า 1 |
| `doc_type`, `issued_date`, `tags` | ไฟล์ `data/raw/_manifest.csv` ที่คนกรอก (ชื่อไฟล์, ประเภท, วันที่, tag) — ถ้าไม่มีแถว ใช้ค่า default |

ไม่ให้ LLM เดา metadata ตอน ingest ใน workshop — ช้า ไม่แน่นอน และทำให้ index ซ้ำได้ผลไม่เท่าเดิม

## 3. Payload index (สร้างครั้งเดียวตอนสร้าง collection)

| field | ชนิด | ใช้ทำอะไร |
|---|---|---|
| `doc_id` | keyword | ลบ/แทนเอกสาร, ดึง chunk ข้างเคียง |
| `file_name` | keyword | จำกัดการค้นในไฟล์เดียว (tool `search_documents(file_name=...)`) |
| `doc_type` | keyword | "ค้นเฉพาะระเบียบ" — agent ใช้เป็น filter |
| `issued_date` | datetime | "ฉบับหลังปี 2567" |
| `page`, `chunk_index` | integer | ดึง chunk ข้างเคียง |

## 4. การ ingest ซ้ำ (idempotent)

ปัญหาของ v1: upsert ทับ id เดิมได้ แต่ถ้าไฟล์ถูกแก้แล้ว chunk น้อยลง chunk เก่าส่วนเกินจะค้างอยู่

v2:
1. คำนวณ `doc_id` = sha1(ไฟล์)
2. ถ้ามี `doc_id` นี้ใน collection แล้ว และ `pipeline.version` ตรง → **ข้าม** (ไม่ embed ซ้ำ ประหยัด GPU ตอนทั้งห้องรันพร้อมกัน)
3. ถ้าไฟล์ชื่อเดิมแต่ `doc_id` ใหม่ → ลบ points ที่ `file_name` นี้ทั้งหมด แล้ว insert ใหม่
4. `chunk_id = {doc_id}_c{chunk_index:03d}` (นับทั้งเล่ม แทนนับรายหน้า)

## 5. สิ่งที่ retrieval ได้เพิ่มจาก schema นี้

```python
search(query, top_k=5, file_name=None, doc_type=None, date_from=None) -> list[Hit]
expand(hit, window=1) -> list[Hit]        # ดึง chunk_index ±1 ของเอกสารเดียวกัน
```

`Hit` เพิ่ม `section`, `page_end`, `doc_type` — field เดิมอยู่ครบ

## 6. ที่ตั้งใจ **ไม่** ทำใน workshop

| ไม่ทำ | เหตุผล |
|---|---|
| เก็บไฟล์ PDF ใน Qdrant | Qdrant คือ index — ไฟล์อยู่ใน `data/raw/` ให้ API เสิร์ฟ |
| Multitenancy ด้วย payload `group` ใน collection เดียว | แยก collection ต่อกลุ่มง่ายกว่าสำหรับห้องเรียน (ของจริงค่อยใช้ `group` + `is_tenant`) |
| bbox (พิกัดบนหน้า) สำหรับ highlight | ทำได้ด้วย pymupdf แต่เกินเวลาของ Lab 03 |
| LLM สร้าง metadata / สรุปต่อ chunk | ช้าและไม่ deterministic |

## เรื่องที่ตัดสินใจไปแล้ว (แก้ได้)

1. `doc_type` ค่าเริ่มต้น "อื่นๆ" — รายการประเภทจริงรอเอกสารของกรมฯ แล้วใส่ใน `_manifest.csv`
2. `chunk_id` รูปแบบใหม่ — frontend ใช้เป็น id อย่างเดียว ไม่แยกวิเคราะห์
3. หัวข้อ (section) เป็น **default** ตั้งแต่ Lab 01 โดยสอนผ่านจุดที่เจอปัญหาจริง (chunk Docker ไม่มีวันที่)
