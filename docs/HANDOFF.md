# สำหรับฝั่ง Agent: เริ่มใช้ระบบ RAG ใน 5 นาที

ระบบ RAG (อ่าน PDF → index → hybrid search) พร้อมแล้ว ฝั่ง agent **เรียกผ่าน tool อย่างเดียว** ไม่ต้องยุ่งกับ Qdrant / embedding

```
Agent (LangChain / อะไรก็ได้) ──▶ search_documents ──▶ ระบบ RAG (src/cdd_rag) ──▶ Qdrant
      ฝั่ง Agent ดูแล                tools.py              ฝั่ง RAG ดูแล
```

## 1. ติดตั้ง (ครั้งเดียว)

```bash
cp .env.example .env       # แก้ XX เป็นเลขประจำตัว + ตั้ง QDRANT_API_KEY (ใช้ .env เดียวกับ Lab 01)
docker compose up -d       # Qdrant ของเรา
uv sync
uv run python scripts/check_env.py
```

ต้องมีข้อมูลใน Qdrant แล้ว (รัน `notebooks/01_basic_rag.ipynb` หรือ `uv run python -c "from cdd_rag.store import ingest_dir; print(ingest_dir())"`)

## 2. ใช้งาน (LangChain)

```python
from langchain.agents import create_agent
from cdd_rag.tools import search_documents, make_llm, collect_sources, link_citations

agent = create_agent(make_llm(), tools=[search_documents], system_prompt=SYSTEM_PROMPT)
result = agent.invoke({"messages": [("user", "การอบรมเรื่อง Docker จัดวันไหน")]})

answer  = result["messages"][-1].content              # "... [da7f4c_c004]"
sources = collect_sources(result["messages"])         # {"da7f4c_c004": {file_name, page, link, ...}}
markdown = link_citations(answer, sources)            # รหัส → ลิงก์เปิด PDF
```

ตัวอย่างเต็ม + system prompt: `notebooks/03_agent_starter.ipynb`

## 3. Tool คืนอะไร

| ส่วน | ใครใช้ | หน้าตา |
|---|---|---|
| content (ข้อความ) | LLM | `[da7f4c_c004] กำหนดการโครงการ.pdf หน้า 2` + `หัวข้อ: ...` + เนื้อหา |
| artifact (list ของ hit) | frontend | `ref, chunk_id, file_name, file_path, page, page_end, section, doc_type, text, score, link` |

- `link` = `/files/{file_path}#page={page}` → **frontend ต้องเสิร์ฟไฟล์ PDF ที่ path `/files/`**
- tool รับ `query` (บังคับ), `doc_type`, `file_name` (ไม่บังคับ — agent เลือกเองจากคำถาม)
- ค้นด้วย hybrid (dense + BM25) top 5

## 4. กฎรหัสอ้างอิง

- ใช้รหัส `[da7f4c_c004]` (6 ตัวแรกของ doc_id + ลำดับ chunk) **ไม่ใช่ `[1]`** — agent ค้นหลายครั้งได้โดยรหัสไม่ชนกัน
- `collect_sources()` รวมผลจากทุกครั้งที่ agent ค้น · รหัสที่ LLM แต่งขึ้นเองจะไม่อยู่ใน sources → frontend ไม่ต้องทำลิงก์
- `score` ของ hybrid เป็นคะแนน RRF ใช้เรียงอันดับเท่านั้น **อย่าใช้เป็นเกณฑ์ตัด** (ไม่ใช่ความคล้าย 0–1)

## 5. ห้ามทำ

1. **ห้าม ingest เอกสารผ่าน LangChain / LlamaIndex** — payload จะเปลี่ยนรูปแบบ ปุ่มเปิด PDF พัง
2. **ห้ามเปลี่ยนชื่อ field ใน Qdrant** — ดู `docs/data-contract.md`
3. **ห้ามใช้ `.env` คนละ `GROUP` กับ Lab 01** — agent จะค้นใน collection ว่าง

## 6. ไม่ใช้ LangChain (OpenAI SDK ตรง ๆ)

```python
from cdd_rag.tools import OPENAI_TOOL, run_search_documents

resp = client.chat.completions.create(model=..., messages=msgs, tools=[OPENAI_TOOL])
for call in resp.choices[0].message.tool_calls or []:
    text, hits = run_search_documents(**json.loads(call.function.arguments))
    msgs.append({"role": "tool", "tool_call_id": call.id, "content": text})
```

## 7. ฝั่ง LLM (vLLM) ต้องเปิด tool calling

```bash
vllm serve <model> --enable-auto-tool-choice --tool-call-parser <parser ของโมเดล เช่น hermes สำหรับ Qwen>
```

ถ้าไม่เปิด agent จะตอบเลยโดยไม่เรียก tool (ไม่มี error ให้เห็น — ดูจากว่ามีรหัสอ้างอิงในคำตอบไหม)

## ใครดูแลอะไร

| ไฟล์ | ผู้ดูแล |
|---|---|
| `src/cdd_rag/` ยกเว้น `tools.py`, `notebooks/01`, `02` | ฝั่ง RAG |
| `src/cdd_rag/tools.py` | ร่วมกัน (เปลี่ยน input/output ต้องคุยกันก่อน) |
| `notebooks/03` เป็นต้นไป, frontend, agent | ฝั่ง Agent |
