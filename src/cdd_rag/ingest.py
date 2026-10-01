"""อ่าน PDF → normalize ภาษาไทย → แบ่ง chunk + metadata (schema v2: docs/index-schema.md)"""
import csv
import hashlib
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from .config import ROOT
from .schema import PIPELINE_VERSION, ChunkPayload, make_chunk_id
from .sparse import SPARSE_PIPELINE

# สระบน/ล่าง วรรณยุกต์ ไม้หันอากาศ — ไม่ควรมีช่องว่างอยู่ข้างหน้า
_THAI_MARKS = "ัิ-ฺ็-๎"
_SPACE_BEFORE_MARK = re.compile(rf" +([{_THAI_MARKS}]+) ?")
_SPACE_BEFORE_AM = re.compile(r" +ำ")


def has_broken_sara_aa(text: str) -> bool:
    """อาการฟอนต์ราชการ (TH Sarabun) บางไฟล์: สระ า ถูกดึงออกมาเป็น ำ ทั้งหมด
    สังเกตได้จาก: มี ำ เยอะ แต่ไม่มี า เลย"""
    return text.count("ำ") > 5 and text.count("า") == 0


def normalize_thai(text: str) -> str:
    if has_broken_sara_aa(text):
        # ำ จริงมีช่องว่างนำหน้า ("ก ำหนด") ส่วน ำ ที่ไม่มีช่องว่างคือ า ที่ถูกแปลงผิด ("กำร")
        text = _SPACE_BEFORE_AM.sub("\x00", text)
        text = text.replace("ำ", "า").replace("\x00", "ำ")
    else:
        text = _SPACE_BEFORE_AM.sub("ำ", text)
    # "นนทบุร ี", "เร ี ยน" → "นนทบุรี", "เรียน"
    text = _SPACE_BEFORE_MARK.sub(r"\1", text)
    # นิคหิต + า ที่แยกกัน → ำ
    text = text.replace("ํา", "ำ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def list_pdfs(data_dir: Path) -> list[Path]:
    """PDF ทุกไฟล์ในโฟลเดอร์ (ไม่รวมโฟลเดอร์ย่อย) ไม่สนตัวพิมพ์เล็ก/ใหญ่ของนามสกุล (.pdf / .PDF)"""
    return sorted(p for p in Path(data_dir).iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def file_doc_id(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def read_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """คืน [(page_number เริ่มที่ 1, ข้อความดิบ)]"""
    with pymupdf.open(path) as doc:
        return [(i + 1, page.get_text()) for i, page in enumerate(doc)]


def split_spans(text: str, chunk_size: int = 800, overlap: int = 150) -> list[tuple[int, int]]:
    """แบ่งตามจำนวนตัวอักษร คืนตำแหน่ง (start, end) ของแต่ละชิ้น
    พยายามตัดที่ขึ้นบรรทัดใหม่/ช่องว่าง (ภาษาไทยไม่เว้นวรรคระหว่างคำ จึงไม่ตัดตามคำ)"""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [(0, len(text))]
    spans, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if cut > start + chunk_size // 2:
                end = cut
        spans.append((start, end))
        if end >= len(text):
            break
        # เริ่ม chunk ถัดไปย้อนหลัง overlap ตัวอักษร แล้วเลื่อนไปต้นบรรทัด/คำ จะได้ไม่เริ่มกลางคำ
        nxt = max(end - overlap, start + 1)
        brk = text.find("\n", nxt, end)
        if brk == -1:
            brk = text.find(" ", nxt, end)
        start = brk + 1 if brk != -1 else nxt
    return spans


def split_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    return [c for s, e in split_spans(text, chunk_size, overlap) if (c := text[s:e].strip())]


# ---------------------------------------------------------------- หัวข้อ (section)
# บรรทัดที่ถือเป็นหัวข้อ: "วันที่ 3 (30 กันยายน 2569)", "หมวด 2 ...", "ส่วนที่ 1 ...", "ข้อ 12 ..."
HEADING = re.compile(r"^(วันที่ \d+ ?\(.+\)|หมวด ?\d+.*|ส่วนที่ ?\d+.*|ข้อ ?\d+\b.*)$", re.M)


def find_headings(text: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(1)[:80].strip()) for m in HEADING.finditer(text)]


def pick_section(start: int, end: int, headings: list[tuple[int, str]], carried: str) -> str:
    """หัวข้อทั้งหมดที่ครอบคลุม chunk: หัวข้อที่ค้างมาก่อน chunk เริ่ม (ถ้ามีเนื้อหาก่อนหัวข้อใหม่)
    + หัวข้อใหม่ที่อยู่ใน chunk — เช่น "วันที่ 1 (...) · วันที่ 2 (...)" """
    current, inside = carried, []
    for pos, h in headings:
        if pos <= start:
            current = h
        elif pos < end:
            inside.append((pos, h))
    lead_in = inside[0][0] - start if inside else end - start
    parts = ([current] if current and lead_in > 40 else []) + [h for _, h in inside]
    return " · ".join(parts)


def strip_repeated_headers(pages: list[str], zone: int = 8) -> list[str]:
    """ลบบรรทัดหัวกระดาษที่ซ้ำทุกหน้า (ดูเฉพาะ `zone` บรรทัดแรกของหน้า) — เก็บไว้เฉพาะหน้าแรกที่เจอ
    ถ้าไม่ลบ chunk ต้นหน้าจะมีแต่หัวกระดาษ และทุก chunk จะ "คล้ายกัน" ไปหมด"""
    if len(pages) < 2:
        return pages
    tops = [set(l.strip() for l in p.splitlines()[:zone] if len(l.strip()) >= 8) for p in pages]
    counts: dict[str, int] = {}
    for t in tops:
        for line in t:
            counts[line] = counts.get(line, 0) + 1
    repeated = {l for l, c in counts.items() if c >= max(2, len(pages) / 2)}
    out, seen = [], set()
    for p in pages:
        lines = p.splitlines()
        keep = []
        for i, line in enumerate(lines):
            key = line.strip()
            if i < zone and key in repeated:
                if key in seen:
                    continue
                seen.add(key)
            keep.append(line)
        out.append("\n".join(keep).strip())
    return out


# ---------------------------------------------------------------- metadata ระดับเอกสาร
DOC_DEFAULTS = {"doc_title": "", "doc_type": "อื่นๆ", "issued_date": None, "tags": []}


def load_manifest(data_dir: Path) -> dict[str, dict]:
    """data/raw/_manifest.csv: file_name,doc_title,doc_type,issued_date,tags (tags คั่นด้วย |)"""
    path = Path(data_dir) / "_manifest.csv"
    if not path.exists():
        return {}
    rows = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows[r["file_name"]] = {
                "doc_title": (r.get("doc_title") or "").strip(),
                "doc_type": (r.get("doc_type") or "").strip() or "อื่นๆ",
                "issued_date": (r.get("issued_date") or "").strip() or None,
                "tags": [t.strip() for t in (r.get("tags") or "").split("|") if t.strip()],
            }
    return rows


def guess_title(first_page: str) -> str:
    """ไม่มีใน manifest → ใช้บรรทัดแรกที่ยาวพอในหน้าแรก"""
    for line in first_page.splitlines()[:8]:
        if len(line.strip()) >= 15:
            return line.strip()[:120]
    return ""


def file_rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- PDF → chunks
def chunk_pdf(path: Path, chunk_size: int = 600, overlap: int = 120, meta: dict | None = None) -> list[ChunkPayload]:
    path = Path(path).resolve()
    doc_id = file_doc_id(path)
    raw_pages = read_pdf_pages(path)
    cleaned = strip_repeated_headers([normalize_thai(raw) for _, raw in raw_pages])
    pages = [(no, text) for (no, _), text in zip(raw_pages, cleaned)]
    if pages and sum(len(t) for _, t in pages) < 50 * len(pages):
        warnings.warn(f"{path.name}: แทบไม่มีข้อความ — น่าจะเป็น PDF สแกน (รูปภาพ) ต้องทำ OCR ก่อน", stacklevel=2)
    meta = {**DOC_DEFAULTS, **(meta if meta is not None else load_manifest(path.parent).get(path.name, {}))}
    title = meta["doc_title"] or (guess_title(pages[0][1]) if pages else "") or path.stem
    pipeline = {
        "version": PIPELINE_VERSION,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "normalizer": "thai-v1",
        "sparse": SPARSE_PIPELINE,
    }
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    chunks: list[ChunkPayload] = []
    section = ""  # หัวข้อต่อเนื่องข้ามหน้า
    for page, text in pages:
        headings = find_headings(text)
        for start, end in split_spans(text, chunk_size, overlap):
            body = text[start:end].strip()
            if not body:
                continue
            sec = pick_section(start, end, headings, section)
            idx = len(chunks)
            chunks.append(
                ChunkPayload(
                    chunk_id=make_chunk_id(doc_id, idx),
                    doc_id=doc_id,
                    file_name=path.name,
                    file_path=file_rel_path(path),
                    doc_title=title,
                    doc_type=meta["doc_type"],
                    issued_date=meta["issued_date"],
                    tags=meta["tags"],
                    page=page,
                    page_end=page,  # chunk ไม่คร่อมหน้า (แบ่งทีละหน้า) — field จองไว้
                    chunk_index=idx,
                    section=sec,
                    text=body,
                    # วัดแล้ว (Lab 01): ใส่ชื่อเอกสารทุก chunk ทำ hit@1 ตก 0.88→0.75 จึงใช้แค่หัวข้อ
                    context_header=sec,
                    char_count=len(body),
                    pipeline=pipeline,
                    ingested_at=now,
                )
            )
        if headings:
            section = headings[-1][1]
    return chunks
