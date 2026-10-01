# Workshop: Monitor service บน server ด้วย Prometheus + Grafana

ผู้เรียนทุกคนใช้ GPU server (Linux) เครื่องเดียวกัน ผ่าน terminal ของ VS Code (Remote-SSH)
แต่ละคนเปิด monitoring stack ของตัวเอง ซึ่งรันแยกจาก service อื่น ไม่ต้องแก้ compose ของ service ที่จะ monitor

```
vllm-server (127.0.0.1:8000) ── /metrics ─────────────────────┐
hidream / tts / rag-engine / aigeo ── blackbox-exporter ──────┼──▶ Prometheus ของเรา ──▶ Grafana ของเรา ──▶ browser บนเครื่องเรา
                                         (127.0.0.1:19115)     │    127.0.0.1:<PROMETHEUS_PORT>  127.0.0.1:<GRAFANA_PORT>   (VS Code forward port)
```

ทุกคำสั่งในคู่มือนี้รันบน server (terminal ของ VS Code ที่ต่อ Remote-SSH อยู่) ยกเว้นส่วนที่บอกว่าเปิดใน browser

## service บน server นี้

| container | port | มี /metrics ไหม | Prometheus ดูยังไง |
|---|---|---|---|
| vllm-server (vLLM v0.23) | 8000 | มี | ดึง `/metrics` ตรง ได้ทั้งสถานะและตัวเลข |
| hidream-server | 8002 | ไม่มี (ตอบที่ `/docs`) | blackbox ยิง HTTP ไปที่ `/docs` |
| tts-server | 8003 | ไม่มี (ตอบที่ `/docs`) | blackbox ยิง HTTP ไปที่ `/docs` |
| rag-engine | 8080 | ไม่มี (ตอบที่ `/docs`) | blackbox ยิง HTTP ไปที่ `/docs` |
| aigeo-analyzer-v2 | 8011 | ไม่มี (ไม่มี path ไหนตอบ 2xx) | blackbox เช็กว่า port เปิดอยู่ (TCP) |

ทั้งหมดใส่ไว้ใน `prometheus.yml` แล้ว

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | ใช้ทำอะไร | ต้องแก้ไหม |
|---|---|---|
| `init.sh` | สร้าง `.env` จากเลขประจำตัว (port + รหัส Grafana) | ไม่ต้อง รันอย่างเดียว |
| `docker-compose.yml` | Prometheus + Grafana ใช้ `network_mode: host` | ไม่ต้อง |
| `.env.example` | ต้นแบบของ `.env` ถ้าอยากสร้างเองแทน `init.sh` | ไม่ต้อง |
| `prometheus.yml` | บอก Prometheus ว่าไปดึงจากไหน · มีตัวอย่าง service อื่นเป็น comment | ไม่ต้อง (ถ้า service บน server เปลี่ยนค่อยแก้) |
| `service-overview.json` | dashboard สถานะทุก service + vLLM ในหน้าเดียว | import เข้า Grafana |
| `vllm-grafana.json` | template ทางการของ vLLM ([ที่มา](https://github.com/vllm-project/vllm/tree/main/examples/observability/prometheus_grafana)) | import เข้า Grafana |
| `gen_load.py` | ยิง request ใส่ vLLM ให้กราฟขยับ (Python มาตรฐาน) | ไม่ต้อง |
| `exporters/docker-compose.yml` | blackbox-exporter + node-exporter + cAdvisor · ผู้สอนรันชุดเดียว | ไม่ต้อง |

## ผู้สอน: เตรียมก่อนเริ่ม (ครั้งเดียว)

```bash
cd /path/to/monitoring/exporters
docker compose up -d blackbox                         # ต้องมีตัวนี้ ไม่งั้น service อื่นจะไม่มีสถานะ
curl -s '127.0.0.1:19115/probe?module=http_2xx&target=http://127.0.0.1:8080/docs' | grep ^probe_success    # ต้องได้ 1
docker pull prom/prometheus:v3.15.0 && docker pull grafana/grafana:13.2.3                                  # กันทุกคน pull พร้อมกัน
```

node-exporter และ cAdvisor เปิดเพิ่มได้ (`docker compose up -d`) ถ้าจะใช้ตัวอย่างใน `prometheus.yml` ส่วนที่ 3

## ก่อนเริ่ม: ตรวจสิทธิ์บน server

```bash
docker ps >/dev/null && echo "docker OK"     # ต้องรันได้โดยไม่ใช้ sudo (user อยู่ในกลุ่ม docker)
docker compose version                        # ต้องเป็น v2 ขึ้นไป (คำสั่ง docker compose ไม่มีขีด)
python3 --version                             # ใช้รัน gen_load.py
```

## ขั้นที่ 1: เตรียมโฟลเดอร์และ `.env`

ได้เลขประจำตัวจากผู้สอน เช่น `07`

```bash
cp -r /path/to/monitoring ~/monitor-07        # path ที่ผู้สอนบอก · เปลี่ยน 07 เป็นเลขของตัวเอง
cd ~/monitor-07
bash init.sh 07
```

`init.sh` จะสร้าง `.env` ให้ (อ่านได้เฉพาะเรา) และพิมพ์ port กับรหัส Grafana ออกมา จดรหัสไว้

| | สูตร | ตัวอย่างเลข 07 |
|---|---|---|
| Prometheus | 19090 + เลข | 19097 |
| Grafana | 13000 + เลข | 13007 |

## ขั้นที่ 2: ดู service บน server และทดสอบ /metrics

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'      # PORTS: เลขซ้ายของ -> คือ port บน server
curl -s 127.0.0.1:8000/metrics | grep -m 3 '^vllm:'     # vLLM มี /metrics
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8080/metrics    # rag-engine ได้ 404 = ไม่มี /metrics
```

## ขั้นที่ 3: อ่าน `prometheus.yml`

ใส่ target ของ server นี้ไว้ให้แล้ว เปิดดูว่าแต่ละส่วนทำอะไร

- ส่วนที่ 1 `vllm` ดึง `127.0.0.1:8000/metrics` ตรง
- ส่วนที่ 2 `service-http` และ `service-tcp` ให้ blackbox-exporter ยิงไปเช็กแทน เพราะ service พวกนี้ไม่มี `/metrics`
- ส่วนที่ 3 ตัวอย่างอื่นที่เป็น comment

## ขั้นที่ 4: เปิด stack

```bash
docker compose config -q && echo OK      # ตรวจไฟล์ก่อน
docker compose up -d
docker compose ps                        # monitor-07-prometheus-1, monitor-07-grafana-1 ต้องเป็น Up
curl -s 127.0.0.1:19097/api/v1/targets | grep -o '"health":"[a-z]*"'   # ต้องได้ "health":"up" ทุกบรรทัด
```

ชื่อ container ขึ้นต้นด้วย `monitor-<เลข>` ของเราเอง จึงไม่ชนกับคนอื่นบน server เดียวกัน

## ขั้นที่ 5: เปิดดูจากเครื่องเรา

VS Code → แท็บ PORTS (ข้าง TERMINAL) → Forward a Port → ใส่ `19097` และ `13007` (port ของตัวเอง)

| เปิดใน browser บนเครื่องเรา | ต้องเห็น |
|---|---|
| http://localhost:19097/targets | ทุก target เป็น UP |
| http://localhost:13007 | หน้า login ของ Grafana (user `admin`, รหัสจาก `init.sh`) |

พิมพ์ IP ของ server ตรง ๆ จะเปิดไม่ได้ เพราะ Grafana / Prometheus ฟังที่ `127.0.0.1` ของ server เท่านั้น ต้องผ่าน VS Code (หรือ `ssh -L 13007:127.0.0.1:13007 <user>@<server>`)

## ขั้นที่ 6: เชื่อม Grafana แล้ว import dashboard

1. Connections → Add new connection → Prometheus → URL `http://localhost:19097` → Save & test ต้องขึ้น "Successfully queried the Prometheus API"
   (Grafana กับ Prometheus อยู่บน host network เดียวกันบน server จึงใช้ `localhost` ได้)
2. Dashboards → New → Import → Upload `service-overview.json` → เลือก datasource Prometheus → Import
3. ทำซ้ำกับ `vllm-grafana.json` แล้วเลือก `model_name` ที่ dropdown ด้านบน

ไฟล์ `.json` อยู่บน server ถ้าจะใช้ปุ่ม Upload ให้ดาวน์โหลดลงเครื่องก่อน (คลิกขวาที่ไฟล์ใน Explorer ของ VS Code → Download) หรือเปิดไฟล์แล้ว copy เนื้อหาไปวางในช่อง "Import via dashboard JSON model"

## ขั้นที่ 7: ทำให้กราฟขยับ

```bash
python3 gen_load.py --url http://127.0.0.1:8000             # ถามสั้น 20 ครั้ง
python3 gen_load.py --url http://127.0.0.1:8000 --long      # แนบข้อความยาว → prompt tokens / TTFT สูงขึ้น
```

ส่งพร้อมกันหลายตัว (ให้ผู้สอนเป็นคนรัน เพราะ vLLM ใช้ร่วมกันทั้งห้อง)

```bash
python3 gen_load.py --url http://127.0.0.1:8000 -c 16 -n 64     # Num Running / Waiting ขยับ
```

ถ้า vLLM ตั้ง `--api-key` ไว้ ให้เติม `--api-key <key>` · ถ้าเป็น embedding model ใช้ `--embed`

จำลอง service ล่ม: เพิ่ม target ที่ไม่มีอะไรรันอยู่ (เช่น `127.0.0.1:9`) ในส่วน vllm ของ `prometheus.yml` แล้วโหลด config ใหม่ จะเห็นกล่อง DOWN ภายใน 15–30 วินาที (ลบออกแล้ว reload อีกครั้ง)

```bash
curl -X POST 127.0.0.1:19097/-/reload    # โหลด config ใหม่ ไม่ต้อง restart
```

## Monitor service อื่น

Prometheus มี 2 วิธี

| service | วิธี | ได้อะไร |
|---|---|---|
| มี `/metrics` (vLLM, Qdrant, Prometheus, app ที่ใส่ instrumentator) | ใส่เป็น target ตรง | สถานะ + ตัวเลขทุกอย่างที่ service ส่งออกมา |
| ไม่มี `/metrics` (hidream, tts, rag-engine, aigeo) | blackbox-exporter ยิงไปเช็ก | สถานะ UP/DOWN (`probe_success`) + เวลาตอบ (`probe_duration_seconds`) |
| ตัว server / container ทุกตัว | node-exporter / cAdvisor ใน `exporters/` | CPU / RAM / disk / network |

เพิ่ม service ที่ไม่มี `/metrics`: หา path ที่ตอบ 200 ก่อน แล้วเพิ่มใน `service-http` (หรือ `service-tcp` ถ้าไม่มี path ไหนตอบ)

```bash
for path in / /health /docs; do printf "%s -> " $path; curl -s -o /dev/null -m 3 -w '%{http_code}\n' 127.0.0.1:<port>$path; done
```

target ที่ต้องใช้ key หรือรหัส (เช่น Qdrant ที่ตั้ง API key): เก็บในโฟลเดอร์ `secrets/` แล้วเปิดบรรทัด `- ./secrets:/etc/prometheus/secrets:ro` ใน `docker-compose.yml`

```bash
mkdir -p secrets
nano secrets/qdrant_api_key        # ใส่ key บรรทัดเดียว
chmod 644 secrets/qdrant_api_key   # Prometheus ใน container รันเป็น user nobody ถ้า 600 จะอ่านไม่ได้ (ได้ 401)
docker compose up -d
```

ไฟล์ 644 คนอื่นบน server อ่านได้ จึงควรใช้ key ที่ให้สิทธิ์อ่านอย่างเดียว เช่น read-only key ของ Qdrant

## ปัญหาที่เจอบ่อย

| อาการ | สาเหตุ | แก้ |
|---|---|---|
| `docker compose up` ฟ้องว่า STUDENT / PORT / PASSWORD ไม่มีค่า | ยังไม่ได้สร้าง `.env` | `bash init.sh <เลข>` |
| `init.sh` บอกว่า port ถูกใช้อยู่แล้ว | เลขประจำตัวซ้ำกับคนอื่น | ถามเลขจากผู้สอนใหม่ |
| `permission denied ... docker.sock` | user ไม่อยู่ในกลุ่ม docker | ให้ผู้ดูแล server เพิ่มกลุ่ม แล้ว login ใหม่ |
| container ไม่ขึ้น · `docker compose logs` เห็น address already in use | port ชนกับคนอื่น | ตรวจเลขประจำตัวใน `.env` |
| prometheus restart วน · logs เห็น permission denied ที่ prometheus.yml | ไฟล์ config อ่านไม่ได้ (สิทธิ์ 600) | `chmod 644 prometheus.yml` แล้ว `docker compose up -d` |
| target vllm เป็น DOWN, connection refused | port ผิด หรือ vLLM หยุดทำงาน | `docker ps` และ `curl 127.0.0.1:8000/metrics` |
| target service-http / service-tcp เป็น DOWN ทุกตัว | blackbox-exporter ยังไม่ได้เปิด | ผู้สอน `docker compose up -d blackbox` ใน `exporters/` |
| กล่องของ service อื่นเป็น DOWN ทั้งที่ target UP | service นั้นไม่ตอบที่ path ที่ตั้งไว้ | ตรวจ path ด้วย curl แล้วแก้ `prometheus.yml` |
| Grafana Save & test ล้ม | ใส่ port ของ Prometheus ผิด | ใช้ `http://localhost:<PROMETHEUS_PORT>` ของตัวเอง |
| dashboard vLLM ว่าง | ยังไม่มี request เข้า หรือเลือก `model_name` ผิด | รัน `gen_load.py` แล้วรอ 1 นาที |
| บาง panel ของ template ว่างแม้มี request | ชื่อ metric ต่างจาก template (รุ่น vLLM) | ดูชื่อจริงด้วย `curl .../metrics | grep ^vllm:` |
| ลืมรหัส Grafana | | `grep GRAFANA_PASSWORD .env` หรือ `docker compose exec grafana grafana cli admin reset-admin-password <รหัสใหม่>` |

ดู log ของ stack ตัวเอง: `docker compose logs --tail 50 prometheus`

## ข้อควรรู้เมื่อใช้ server ร่วมกัน

- port ที่ bind `127.0.0.1` เข้าจากนอก server ไม่ได้ แต่ user คนอื่นบน server เดียวกันเข้าได้ Grafana มี login กันไว้ ส่วน Prometheus ไม่มี (ข้อมูลเป็นตัวเลข metrics ไม่ใช่ข้อมูลลับ)
- ห้ามสั่ง `docker stop` / `docker rm` กับ container ที่ไม่ใช่ของตัวเอง (`docker ps` เห็นของทุกคน)

## ปิดระบบ

```bash
docker compose down          # ปิดเฉพาะ stack ของเรา (monitor-<เลข>) ข้อมูลใน volume ยังอยู่
docker compose down -v       # ปิดและลบข้อมูลกราฟ / dashboard ของเราทิ้ง
```

ไม่กระทบ vLLM หรือ stack ของคนอื่น เพราะเป็นคนละ compose project
