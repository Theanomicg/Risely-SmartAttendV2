# SmartAttend v2 — Risely Platform
> AI-powered face recognition attendance system with real-time CCTV monitoring, live alerts, and Zoho email notifications.

---

## 🚀 Quick Start (Development)

### Prerequisites

| Tool | Min Version | Install |
|---|---|---|
| Python | 3.10+ | `sudo apt install python3.10 python3.10-venv` |
| Node.js | 18+ | https://nodejs.org |
| Git | any | `sudo apt install git` |

### 1. Clone & configure

```bash
git clone https://github.com/yourorg/smartattend-v2.git
cd smartattend-v2

# Backend config
cp backend/.env.example backend/.env
nano backend/.env   # Fill in SMTP_USER, SMTP_PASSWORD, SECRET_KEY

# Frontend config (optional for dev — proxy is pre-configured)
cp frontend/.env.example frontend/.env
```

### 2. Run

```bash
chmod +x start.sh
./start.sh
```

That's it. Open **http://localhost:5173**

---

## 🔑 First-Time Account Setup

After starting, create your first admin account:

```bash
curl -X POST http://localhost:8000/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"name":"Admin","email":"admin@school.com","password":"yourpassword"}'
```

Then log in at http://localhost:5173/login

---

## 📋 Step-by-Step Usage

### Step 1 — Add Cameras
1. Go to **Cameras** → **Add Camera**
2. Enter camera name, room/location, and RTSP URL
3. Click **Test** — you'll see a live snapshot preview
4. Save — streaming starts immediately

**RTSP URL formats:**
```
rtsp://admin:password@192.168.1.100:554/stream
rtsp://192.168.1.101:554/ch0
rtsp://user:pass@camera-ip/live/main
```

### Step 2 — Register Students
1. Go to **Students** → **Add Student**
2. Fill in Student ID, Name, Batch
3. Click **Enroll** → use webcam to capture 5 face photos
   - Or upload existing photos via the upload button

### Step 3 — Start a Session
1. Go to **Live Sessions** → **Start Session**
2. Enter Subject, Batch, Room, and assign a Camera
3. Session starts — camera begins monitoring

### Step 4 — Student Kiosk Check-In
Students check in using the kiosk endpoint:

```bash
POST /attendance/kiosk/check-in
Headers: x-kiosk-key: YOUR_KIOSK_API_KEY
Body: { "session_id": 1, "image_b64": "..." }
```

The kiosk can be:
- A Raspberry Pi with a webcam
- A tablet running the kiosk web app
- Any device that can POST a base64 JPEG

### Step 5 — Monitoring Kicks In
Every **5 minutes**, the camera:
1. Captures a frame
2. Runs InsightFace recognition
3. Updates **last_seen** for found students
4. Triggers alerts for missing students

**Alert flow:**
- **15 min absent** → 🔔 Bell rings on admin panel
- **20 min absent** → 📧 Email sent to all configured recipients

### Step 6 — Configure Alert Emails
1. Go to **Alerts** → **Email Recipients**
2. Add up to 3 email addresses
3. Click **Send Test Email** to verify Zoho is working

---

## 📧 Zoho SMTP Setup

1. Log in to mail.zoho.in
2. Go to **Settings → Security → App Passwords**
3. Generate a new password (name it "SmartAttend")
4. Add to `backend/.env`:

```env
SMTP_HOST=smtp.zoho.in
SMTP_PORT=587
SMTP_USER=alerts@yourdomain.com
SMTP_PASSWORD=<generated-app-password>
ALERT_EMAIL_RECIPIENTS=principal@school.com,coordinator@school.com
```

---

## 🌐 Production Deployment (Internet-Accessible)

### Server requirements
- Ubuntu 22.04 LTS (recommended)
- 2 CPU cores, 4GB RAM minimum
- Static IP or domain pointing to your server

### Deploy steps

```bash
# 1. Clone to server
sudo mkdir -p /var/www/smartattend
sudo chown $USER:$USER /var/www/smartattend
git clone https://github.com/yourorg/smartattend-v2.git /var/www/smartattend
cd /var/www/smartattend

# 2. Configure
cp backend/.env.example backend/.env
nano backend/.env   # Set all values including ALLOWED_ORIGINS=https://yourdomain.com

# 3. Build frontend
cd frontend
npm install && npm run build
cd ..

# 4. Install Nginx + SSL
sudo apt install nginx certbot python3-certbot-nginx
sudo cp docs/nginx.conf /etc/nginx/sites-available/smartattend
# Edit the file: replace yourdomain.com with your domain
sudo nano /etc/nginx/sites-available/smartattend
sudo ln -s /etc/nginx/sites-available/smartattend /etc/nginx/sites-enabled/
sudo nginx -t

# 5. Get SSL certificate
sudo certbot --nginx -d yourdomain.com

# 6. Install as systemd service
sudo cp docs/smartattend.service /etc/systemd/system/
# Edit WorkingDirectory paths if needed
sudo systemctl daemon-reload
sudo systemctl enable smartattend
sudo systemctl start smartattend

# 7. Check status
sudo systemctl status smartattend
sudo journalctl -u smartattend -f
```

### Update frontend .env for production:
```env
VITE_API_URL=https://yourdomain.com/api
VITE_WS_URL=wss://yourdomain.com/ws
VITE_KIOSK_API_KEY=your_kiosk_api_key
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | CHANGE ME | JWT signing key — run `openssl rand -hex 32` |
| `KIOSK_API_KEY` | CHANGE ME | Key for kiosk devices |
| `FACE_MODEL` | `buffalo_l` | InsightFace model: `buffalo_l` (accurate) or `buffalo_s` (fast) |
| `FACE_THRESHOLD` | `0.45` | Cosine similarity threshold (0–1) |
| `FACE_ENROLLMENT_SAMPLES` | `5` | Photos required per student |
| `MONITORING_INTERVAL_SECONDS` | `300` | How often camera scans (300 = 5 min) |
| `ABSENT_WARN_MINUTES` | `15` | Minutes absent before panel bell |
| `ABSENT_EMAIL_MINUTES` | `20` | Minutes absent before email alert |
| `DATABASE_URL` | SQLite | Change to PostgreSQL URL for production scale |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SmartAttend v2                        │
├──────────────┬────────────────────────┬─────────────────┤
│   React SPA  │    FastAPI Backend     │  InsightFace    │
│  (Vite)      │                        │  Buffalo_L      │
│              │  ┌─────────────────┐   │  ArcFace 512-d  │
│  Dashboard   │  │  APScheduler    │   │                 │
│  Sessions    │  │  Every 5 min:   │◄──┤  RTSP Streams   │
│  Students    │  │  • Grab frame   │   │  (OpenCV)       │
│  Cameras     │  │  • Face recog   │   │                 │
│  Alerts      │  │  • Update DB    │   │                 │
│  Attendance  │  │  • Fire alerts  │   │                 │
│              │  └─────────────────┘   │                 │
│              │                        │                 │
│  WebSocket ◄─┤  SQLite / PostgreSQL   │  Zoho SMTP      │
│  Live alerts │                        │  HTML emails    │
└──────────────┴────────────────────────┴─────────────────┘
```

---

## 📁 Project Structure

```
smartattend-v2/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + WebSocket
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── config.py            # Settings from .env
│   │   ├── deps.py              # Auth dependencies
│   │   ├── routers/
│   │   │   ├── auth.py          # Login, register
│   │   │   ├── students.py      # Student CRUD + face enrollment
│   │   │   ├── cameras.py       # Camera management
│   │   │   ├── attendance.py    # Sessions, kiosk, records
│   │   │   └── alerts.py        # Alerts + email recipients
│   │   └── services/
│   │       ├── face_service.py      # InsightFace recognition
│   │       ├── camera_service.py    # RTSP stream management
│   │       ├── email_service.py     # Zoho SMTP + HTML templates
│   │       └── scheduler_service.py # 5-min monitoring loop
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/               # Dashboard, Students, Cameras, etc.
│       ├── components/          # Sidebar, AlertPanel
│       ├── store/               # Zustand stores (auth, ws/alerts)
│       ├── hooks/               # useWebSocket
│       └── lib/                 # Axios API client
├── docs/
│   ├── nginx.conf               # Production Nginx config
│   └── smartattend.service      # Systemd service
├── start.sh                     # One-command startup
└── README.md
```

---

## 🐛 Troubleshooting

**InsightFace fails to load:**
```bash
pip install insightface onnxruntime --upgrade
# First run downloads Buffalo_L model (~200MB) — needs internet
```

**Camera not connecting:**
- Test with VLC: Media → Open Network Stream → paste RTSP URL
- Check camera credentials and IP
- Try `rtsp://ip/stream1` or `rtsp://ip:554/h264Preview_01_main`

**Emails not sending:**
- Use Zoho **App Password**, not your login password
- Check `SMTP_USER` matches your Zoho account email exactly
- Try `smtp.zoho.com` instead of `smtp.zoho.in` depending on your region

**WebSocket disconnects:**
- Normal — it auto-reconnects every 5 seconds
- In production, ensure Nginx has `proxy_read_timeout 3600`
