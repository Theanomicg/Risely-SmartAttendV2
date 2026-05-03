# SmartAttend v2

SmartAttend v2 is an attendance and classroom monitoring platform built with FastAPI and React. It combines face-based student enrollment, kiosk check-in, live session monitoring, RTSP camera integration, WebSocket alerts, and Zoho SMTP notifications.

## Overview

SmartAttend provides:

- Admin authentication and dashboard access
- Student registration and face enrollment
- Camera registration and live snapshot testing
- Session creation and classroom monitoring
- Kiosk-based face check-in
- Real-time alert delivery in the dashboard
- Email alerts and daily reports through Zoho SMTP

## Tech Stack

- Backend: FastAPI, SQLAlchemy, APScheduler, aiosqlite
- Frontend: React, Vite, TypeScript, Zustand
- Computer vision: OpenCV, InsightFace, ONNX Runtime
- Notifications: WebSocket and Zoho SMTP
- Database: SQLite by default, PostgreSQL optional for production

## Project Structure

```text
smartattend-v2/
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- models.py
|   |   |-- schemas.py
|   |   |-- config.py
|   |   |-- deps.py
|   |   |-- routers/
|   |   `-- services/
|   |-- requirements.txt
|   `-- .env.example
|-- frontend/
|   |-- src/
|   |-- package.json
|   `-- .env.example
|-- docs/
|   |-- nginx.conf
|   `-- smartattend.service
`-- start.sh
```

## Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- Git

## Local Development

### Linux or macOS

1. Clone the repository and enter the project directory.
2. Copy the backend environment template.
3. Run the startup script.

```bash
git clone https://github.com/Theanomicg/Risely-SmartAttendV2.git
cd Risely-SmartAttendV2
cp backend/.env.example backend/.env
chmod +x start.sh
./start.sh
```

The development UI is available at `http://localhost:5173` and the backend API at `http://localhost:8000`.

### Windows PowerShell

The bundled `start.sh` script is intended for Bash environments. On Windows, run the backend and frontend separately.

```powershell
cd C:\path\to\Risely-SmartAttendV2
Copy-Item backend\.env.example backend\.env

cd backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

cd ..\frontend
npm install
```

Start the backend in one terminal:

```powershell
cd C:\path\to\Risely-SmartAttendV2\backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Start the frontend in a second terminal:

```powershell
cd C:\path\to\Risely-SmartAttendV2\frontend
npm run dev
```

## Initial Admin Setup

After the backend is running, create the first admin account:

```bash
curl -X POST http://localhost:8000/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"name":"Admin","email":"admin@school.com","password":"yourpassword"}'
```

On Windows PowerShell, the equivalent command is:

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/auth/setup" `
  -ContentType "application/json" `
  -Body '{"name":"Admin","email":"admin@school.com","password":"yourpassword"}'
```

Then sign in at `http://localhost:5173/login`.

## Usage Flow

### 1. Add Cameras

Add RTSP-enabled classroom cameras from the Cameras page. Each camera can be tested before saving.

Example RTSP formats:

```text
rtsp://admin:password@192.168.1.100:554/stream
rtsp://192.168.1.101:554/ch0
rtsp://user:pass@camera-ip/live/main
```

### 2. Register Students

Create student records from the Students page and capture or upload face samples for enrollment.

### 3. Start Sessions

Create a classroom session by subject, batch, room, and optional camera assignment.

### 4. Student Check-In

Students do not use a username/password flow. Check-in is performed through the kiosk endpoint with a kiosk API key and a captured image.

```text
POST /attendance/kiosk/check-in
Header: x-kiosk-key: YOUR_KIOSK_API_KEY
Body: { "session_id": 1, "image_b64": "..." }
```

### 5. Monitoring and Alerts

The scheduler periodically captures frames, runs recognition, updates last-seen data, and triggers alerts according to the configured thresholds.

## Configuration

Key backend environment values:

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing key |
| `KIOSK_API_KEY` | Device key for kiosk check-in |
| `DATABASE_URL` | Database connection string |
| `FACE_MODEL` | InsightFace model name |
| `FACE_THRESHOLD` | Face matching threshold |
| `FACE_ENROLLMENT_SAMPLES` | Required face samples per student |
| `MONITORING_INTERVAL_SECONDS` | Camera scan interval |
| `ABSENT_WARN_MINUTES` | Warning threshold |
| `ABSENT_EMAIL_MINUTES` | Email alert threshold |
| `SMTP_HOST` | SMTP server host |
| `SMTP_PORT` | SMTP server port |
| `SMTP_USER` | SMTP mailbox address |
| `SMTP_PASSWORD` | SMTP app password |
| `ALERT_EMAIL_RECIPIENTS` | Default alert email recipients |

## Zoho SMTP Setup

For Zoho SMTP:

1. Enable two-factor authentication on the Zoho account.
2. Generate an app password from the Zoho account security settings.
3. Set the backend environment values accordingly.

Example:

```env
SMTP_HOST=smtp.zoho.in
SMTP_PORT=587
SMTP_USER=alerts@yourdomain.com
SMTP_PASSWORD=your_generated_app_password
SMTP_FROM_NAME=SmartAttend Alerts
ALERT_EMAIL_RECIPIENTS=principal@school.com,coordinator@school.com
```

Use the Zoho app password, not the mailbox login password.

## Production Deployment

Recommended target:

- Ubuntu 22.04 LTS
- 2 CPU cores minimum
- 4 GB RAM minimum
- Domain or static public IP

Typical deployment flow:

```bash
sudo mkdir -p /var/www/smartattend
sudo chown $USER:$USER /var/www/smartattend
git clone https://github.com/Theanomicg/Risely-SmartAttendV2.git /var/www/smartattend
cd /var/www/smartattend

cp backend/.env.example backend/.env

cd frontend
npm install
npm run build
cd ..

sudo apt install nginx certbot python3-certbot-nginx
sudo cp docs/nginx.conf /etc/nginx/sites-available/smartattend
sudo cp docs/smartattend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable smartattend
sudo systemctl start smartattend
```

Adjust domain names, environment values, and service paths before enabling the deployment.

## Troubleshooting

### InsightFace download or load issues

```bash
pip install insightface onnxruntime --upgrade
```

The first run may download the model files and requires internet access.

### Camera connection failures

- Verify the RTSP URL in VLC or another RTSP client
- Confirm the camera IP address and credentials
- Try alternate vendor-specific RTSP paths

### Email delivery failures

- Use a Zoho app password
- Confirm `SMTP_USER` exactly matches the Zoho mailbox
- Try `smtp.zoho.com` instead of `smtp.zoho.in` if your account region requires it

### Frontend issues on Windows

- Restart the Vite dev server after dependency or source changes
- Ensure both backend and frontend are running
- Open `http://localhost:5173/login` directly if the root route has stale browser state

## Notes

- Local `.env` files, SQLite databases, snapshots, virtual environments, and build artifacts are excluded from version control.
- Student and camera deletion now perform hard deletes in the backend rather than only marking records inactive.
