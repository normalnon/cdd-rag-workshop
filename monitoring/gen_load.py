"""ยิง request ใส่ vLLM ให้กราฟใน Grafana ขยับ (ใช้ใน Lab) — ใช้แค่ Python มาตรฐาน ไม่ต้องติดตั้งอะไร

    python3 gen_load.py --url http://127.0.0.1:8000                      # ถามสั้น 20 ครั้ง ทีละ 1
    python3 gen_load.py --url http://127.0.0.1:8000 --long               # แนบข้อความยาว → prompt tokens / TTFT สูงขึ้น
    python3 gen_load.py --url http://127.0.0.1:8000 -c 16 -n 64          # ส่งพร้อมกัน 16 → Num Running / Waiting ขยับ
    python3 gen_load.py --url http://127.0.0.1:8001 --embed              # vLLM ที่เป็น embedding model

ถ้า vLLM ตั้ง --api-key ไว้ ให้ใส่ --api-key หรือตั้ง env VLLM_API_KEY
"""
import argparse
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

QUESTIONS = [
    "สรุปขั้นตอนการขอรับเงินอุดหนุนกลุ่มอาชีพให้สั้นที่สุด",
    "อธิบายว่า Docker volume คืออะไร ใน 3 ประโยค",
    "ยกตัวอย่างตัวชี้วัดความสำเร็จของโครงการพัฒนาชุมชน 5 ข้อ",
    "เขียนคำทักทายสำหรับเปิดประชุมหมู่บ้านสั้น ๆ",
    "What is the difference between latency and throughput?",
]
# ข้อความยาวจำลอง chunk จาก RAG ที่แนบไปกับคำถาม
LONG_CONTEXT = ("เอกสารอ้างอิง: กองทุนหมู่บ้านและชุมชนเมืองมีวัตถุประสงค์เพื่อเป็นแหล่งเงินทุนหมุนเวียน "
                "สำหรับการลงทุนเพื่อพัฒนาอาชีพ สร้างงาน สร้างรายได้ และบรรเทาเหตุฉุกเฉินของสมาชิก ") * 60


def request(url, path, body, api_key):
    req = urllib.request.Request(url.rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {api_key}"} if api_key else {})})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            r.read()
            return r.status, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t0
    except (urllib.error.URLError, TimeoutError) as e:
        return f"ERR {e}", time.time() - t0


def first_model(url, api_key):
    req = urllib.request.Request(url.rstrip("/") + "/v1/models",
                                 headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["data"][0]["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="เช่น http://127.0.0.1:8000")
    ap.add_argument("--model", help="ไม่ใส่ = ใช้ model ตัวแรกจาก /v1/models")
    ap.add_argument("-n", "--requests", type=int, default=20)
    ap.add_argument("-c", "--concurrency", type=int, default=1)
    ap.add_argument("--long", action="store_true", help="แนบข้อความยาว (จำลอง RAG ที่ส่ง chunk เยอะ)")
    ap.add_argument("--embed", action="store_true", help="ยิง /v1/embeddings แทน chat")
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--api-key", default=os.getenv("VLLM_API_KEY", ""))
    args = ap.parse_args()

    try:
        model = args.model or first_model(args.url, args.api_key)
    except Exception as e:
        raise SystemExit(f"เรียก {args.url}/v1/models ไม่ได้: {e}\nตรวจ port ของ vLLM ด้วย docker ps หรือใส่ --api-key")
    kind = "embeddings" if args.embed else "chat"
    print(f"ยิง {args.requests} request ({kind}) พร้อมกัน {args.concurrency} → {args.url} · model={model}")

    def one(i):
        q = random.choice(QUESTIONS)
        if args.long:
            q = LONG_CONTEXT + "\n\nคำถาม: " + q
        if args.embed:
            return request(args.url, "/v1/embeddings", {"model": model, "input": q}, args.api_key)
        return request(args.url, "/v1/chat/completions",
                       {"model": model, "max_tokens": args.max_tokens,
                        "messages": [{"role": "user", "content": q}]}, args.api_key)

    lock, done, results = threading.Lock(), [0], []

    def run(i):
        res = one(i)
        with lock:
            done[0] += 1
            results.append(res)
            print(f"\r  เสร็จ {done[0]}/{args.requests}", end="", flush=True)
        return res

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(run, range(args.requests)))
    print()
    status = {}
    for s, _ in results:
        status[s] = status.get(s, 0) + 1
    lat = sorted(t for _, t in results)
    p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]
    print(f"ใช้เวลารวม {time.time() - t0:.1f} s · status {status}")
    print(f"เวลาตอบ (วัดฝั่งเรา) P50 {p(0.5):.2f} s · P95 {p(0.95):.2f} s · สูงสุด {lat[-1]:.2f} s")


if __name__ == "__main__":
    main()
