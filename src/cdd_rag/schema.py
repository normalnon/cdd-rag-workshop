"""Data contract ระหว่างส่วน RAG และ Agent/Service
"""
from typing import TypedDict

DENSE = "dense"    # bge-m3
SPARSE = "sparse"  # จองไว้สำหรับ hybrid search
VECTOR_NAME = DENSE  # ชื่อเดิม (v1)

PIPELINE_VERSION = "v2"


class ChunkPayload(TypedDict):
    # --- ตัวตน ---
    chunk_id: str        # "{doc_id}_c{chunk_index:03d}"
    doc_id: str          # sha1 ของไฟล์ 12 ตัวแรก
    # --- แหล่งที่มา ---
    file_name: str       # ใช้แสดงใน citation
    file_path: str       # path สัมพัทธ์จาก root project — frontend ใช้เปิด PDF
    doc_title: str
    doc_type: str        # ระเบียบ | ประกาศ | คู่มือ | หนังสือเวียน | กำหนดการ | อื่นๆ
    issued_date: str | None  # "YYYY-MM-DD"
    tags: list[str]
    # --- ตำแหน่ง ---
    page: int            # หน้าเริ่ม (นับจาก 1)
    page_end: int        # หน้าสุดท้าย
    chunk_index: int     # ลำดับในเอกสารทั้งเล่ม
    section: str         # หัวข้อที่ครอบคลุม chunk ("" ถ้าไม่มี)
    # --- เนื้อหา ---
    text: str            # ข้อความที่แสดง/อ้างอิง
    context_header: str  # = section — แปะหน้า text ตอน embed (ไม่ใส่ชื่อเอกสาร: ทุก chunk ซ้ำกันทำให้แยกกันยากขึ้น)
    char_count: int
    # --- การ index ---
    pipeline: dict
    ingested_at: str


class Hit(TypedDict):
    chunk_id: str
    text: str
    score: float
    file_name: str
    file_path: str
    page: int
    page_end: int
    section: str
    doc_type: str


def make_chunk_id(doc_id: str, chunk_index: int) -> str:
    return f"{doc_id}_c{chunk_index:03d}"


def embedding_text(chunk: ChunkPayload) -> str:
    """ข้อความที่ส่งไป embed = หัวข้อ + เนื้อหา (ส่วนที่แสดงผลยังเป็น text เฉย ๆ)"""
    header = chunk.get("context_header")
    return f"{header}\n{chunk['text']}" if header else chunk["text"]


def cite_label(hit: Hit, n: int) -> str:
    """รูปแบบ citation ที่ LLM เห็น และที่ frontend แปลงเป็นลิงก์ /files/{file_path}#page={page}"""
    return f"[{n}] {hit['file_name']} หน้า {hit['page']}"
