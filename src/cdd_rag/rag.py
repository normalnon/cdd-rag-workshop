"""Retrieve → สร้าง prompt พร้อม citation → ให้ LLM ตอบ"""
from openai import OpenAI

from .config import settings
from .schema import Hit, cite_label
from .store import search

_llm = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

SYSTEM_PROMPT = """คุณเป็นผู้ช่วยตอบคำถามจากเอกสารของกรมการพัฒนาชุมชน
- ตอบจาก "เอกสารอ้างอิง" ที่ให้เท่านั้น ถ้าไม่มีข้อมูลให้ตอบว่า "ไม่พบข้อมูลในเอกสาร"
- ทุกประโยคที่ใช้ข้อมูลจากเอกสาร ให้ใส่เลขอ้างอิงท้ายประโยค เช่น [1] หรือ [1][3]
- ตอบเป็นภาษาไทย กระชับ"""


def build_context(hits: list[Hit]) -> str:
    """[n] ไฟล์ หน้า p + หัวข้อ (ถ้ามี) + เนื้อหา — หัวข้อช่วยให้ LLM รู้ว่าเนื้อหาอยู่ใต้ "วันที่/หมวด" ไหน"""
    blocks = []
    for i, h in enumerate(hits, 1):
        header = cite_label(h, i) + (f"\nหัวข้อ: {h['section']}" if h.get("section") else "")
        blocks.append(f"{header}\n{h['text']}")
    return "\n\n".join(blocks)


def chat(messages: list[dict], **kw) -> str:
    resp = _llm.chat.completions.create(
        model=settings.llm_model, messages=messages, temperature=0, extra_body=settings.llm_extra_body, **kw
    )
    return resp.choices[0].message.content


def answer(question: str, top_k: int = 5) -> dict:
    hits = search(question, top_k=top_k)
    content = chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"เอกสารอ้างอิง:\n{build_context(hits)}\n\nคำถาม: {question}"},
        ]
    )
    return {"answer": content, "sources": hits}
