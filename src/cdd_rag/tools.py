"""Tool สำเร็จรูปให้ฝั่ง agent เรียกใช้ระบบ RAG — ฝั่ง agent ไม่ต้องรู้เรื่อง Qdrant / embedding

ระบบ RAG (ingest / store / search) ไม่ขึ้นกับ framework ใด ๆ — ไฟล์นี้เป็นแค่ "ตัวแปลง"

LangChain:
    from cdd_rag.tools import search_documents, make_llm, collect_sources
    agent = create_agent(make_llm(), tools=[search_documents])

OpenAI SDK (ไม่ใช้ framework):
    from cdd_rag.tools import OPENAI_TOOL, run_search_documents

รหัสอ้างอิง: ใช้รหัส chunk แบบสั้น เช่น [da7f4c_c004] (ไม่ใช่ [1], [2])
เพราะ agent อาจเรียก tool หลายครั้งในคำถามเดียว ถ้าใช้เลข [1] ทุกครั้งจะชนกัน
"""
from .config import settings
from .store import search

TOP_K = 5
TOOL_NAME = "search_documents"
TOOL_DESCRIPTION = """ค้นเอกสารของกรมการพัฒนาชุมชน (ระเบียบ ประกาศ คู่มือ กำหนดการ ฯลฯ) เพื่อใช้ตอบคำถาม

ผลลัพธ์แต่ละชิ้นขึ้นต้นด้วยรหัสอ้างอิงในวงเล็บเหลี่ยม เช่น [da7f4c_c004]
เมื่อตอบ ให้ใส่รหัสนั้นท้ายประโยคที่ใช้ข้อมูลจากชิ้นนั้น"""
TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "คำค้น ภาษาไทยหรืออังกฤษ ใช้คำสำคัญของคำถาม"},
        "doc_type": {"type": "string", "description": 'ไม่บังคับ: จำกัดประเภทเอกสาร เช่น "ระเบียบ", "กำหนดการ"'},
        "file_name": {"type": "string", "description": 'ไม่บังคับ: จำกัดเฉพาะไฟล์นี้ เช่น "กำหนดการโครงการ.pdf"'},
    },
    "required": ["query"],
}


def ref_of(hit: dict) -> str:
    """รหัสอ้างอิงสั้น ไม่ซ้ำข้ามเอกสาร: 6 ตัวแรกของ doc_id + ลำดับ chunk → da7f4c_c004"""
    doc_id, idx = hit["chunk_id"].rsplit("_c", 1)
    return f"{doc_id[:6]}_c{idx}"


def pdf_link(hit: dict) -> str:
    """ลิงก์เปิด PDF ไปหน้าที่อ้างอิง (frontend เสิร์ฟไฟล์ที่ /files/)"""
    return f"/files/{hit['file_path']}#page={hit['page']}"


def format_hits(hits: list[dict]) -> str:
    """ข้อความที่ LLM เห็น: [รหัส] ไฟล์ หน้า + หัวข้อ + เนื้อหา"""
    if not hits:
        return "ไม่พบเอกสารที่เกี่ยวข้อง"
    blocks = []
    for h in hits:
        head = f"[{h['ref']}] {h['file_name']} หน้า {h['page']}"
        if h.get("section"):
            head += f"\nหัวข้อ: {h['section']}"
        blocks.append(f"{head}\n{h['text']}")
    return "\n\n".join(blocks)


def run_search_documents(query: str, doc_type: str | None = None, file_name: str | None = None) -> tuple[str, list[dict]]:
    """ค้นแล้วคืน (ข้อความให้ LLM, hits ให้ frontend) — ไม่ขึ้นกับ framework"""
    hits = search(query, top_k=TOP_K, doc_type=doc_type or None, file_name=file_name or None)
    hits = [dict(h, ref=ref_of(h), link=pdf_link(h)) for h in hits]
    return format_hits(hits), hits


# ---------------------------------------------------------------- OpenAI SDK โดยตรง (ไม่ใช้ LangChain)
OPENAI_TOOL = {
    "type": "function",
    "function": {"name": TOOL_NAME, "description": TOOL_DESCRIPTION, "parameters": TOOL_PARAMETERS},
}


# ---------------------------------------------------------------- LangChain (import เฉพาะตอนมีคนเรียกใช้)
_lc_tool = None


def _build_langchain_tool():
    from langchain_core.tools import StructuredTool

    def _run(query: str, doc_type: str | None = None, file_name: str | None = None):
        return run_search_documents(query, doc_type=doc_type, file_name=file_name)

    return StructuredTool.from_function(
        func=_run,
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        args_schema=TOOL_PARAMETERS,
        response_format="content_and_artifact",  # content → LLM · artifact (hits) → frontend
    )


def __getattr__(name):
    # `from cdd_rag.tools import search_documents` → สร้าง LangChain tool ตอนนั้น
    # เครื่องที่ไม่ได้ลง LangChain ยังใช้ run_search_documents / OPENAI_TOOL ได้ตามปกติ
    global _lc_tool
    if name == "search_documents":
        if _lc_tool is None:
            _lc_tool = _build_langchain_tool()
        return _lc_tool
    raise AttributeError(name)


def make_llm(**kw):
    """LLM บน vLLM (OpenAI-compatible) ตามค่าใน .env — ฝั่ง vLLM ต้องเปิด tool calling"""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=0,
        extra_body=settings.llm_extra_body,
        **kw,
    )


def link_citations(answer: str, sources: dict[str, dict]) -> str:
    """แปลง [da7f4c_c004] ในคำตอบ → [da7f4c_c004](/files/...#page=2) (Markdown) — รหัสที่ไม่รู้จักคงไว้ตามเดิม"""
    import re

    def _sub(m):
        ref = m.group(1)
        return f"[{ref}]({sources[ref]['link']})" if ref in sources else m.group(0)

    return re.sub(r"\[([0-9a-f]{6}_c\d{3})\](?!\()", _sub, answer)


def collect_sources(messages) -> dict[str, dict]:
    """รวม hits จากทุกครั้งที่ agent เรียก search_documents → {รหัสอ้างอิง: hit}
    frontend ใช้แปลง [da7f4c_c004] ในคำตอบเป็นปุ่มเปิด PDF (hit["link"])"""
    sources: dict[str, dict] = {}
    for m in messages:
        if getattr(m, "type", None) == "tool" and getattr(m, "name", None) == TOOL_NAME:
            for h in getattr(m, "artifact", None) or []:
                sources[h["ref"]] = h
    return sources
