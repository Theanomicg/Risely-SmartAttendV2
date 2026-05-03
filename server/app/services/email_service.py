"""
Email Service — Zoho SMTP via aiosmtplib
─────────────────────────────────────────
Sends HTML alert emails for:
• 15-min absence warning
• 20-min absence email alert
• Daily attendance report
"""

import logging
from datetime import datetime
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings

log = logging.getLogger("smartattend.email")


# ── HTML Templates ─────────────────────────────────────────────────────────────

_BASE_STYLE = """
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f1a; color: #e2e8f0; margin: 0; padding: 0; }
  .container { max-width: 600px; margin: 30px auto; background: #1a1a2e; border-radius: 12px; overflow: hidden; border: 1px solid #2d2d4e; }
  .header { background: linear-gradient(135deg, #7c3aed, #4f46e5); padding: 28px 32px; }
  .header h1 { margin: 0; font-size: 22px; color: #fff; letter-spacing: 0.5px; }
  .header p  { margin: 6px 0 0; color: #c4b5fd; font-size: 13px; }
  .body { padding: 28px 32px; }
  .alert-box { background: #2d1b4e; border-left: 4px solid #7c3aed; border-radius: 8px; padding: 16px 20px; margin: 16px 0; }
  .alert-box.urgent { border-left-color: #ef4444; background: #2d1b1b; }
  .info-row { display: flex; margin: 8px 0; }
  .info-label { color: #94a3b8; min-width: 140px; font-size: 14px; }
  .info-value { color: #e2e8f0; font-size: 14px; font-weight: 600; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-left: 8px; }
  .badge-warning { background: #78350f; color: #fcd34d; }
  .badge-urgent  { background: #7f1d1d; color: #fca5a5; }
  .footer { background: #111827; padding: 16px 32px; text-align: center; color: #64748b; font-size: 12px; }
  .footer a { color: #7c3aed; text-decoration: none; }
  hr { border: none; border-top: 1px solid #2d2d4e; margin: 20px 0; }
</style>
"""


def _build_absent_warning_html(
    student_name: str,
    student_id: str,
    subject: str,
    room: str,
    batch: str,
    absent_minutes: int,
    teacher_name: str,
    timestamp: str,
) -> str:
    is_urgent = absent_minutes >= 20
    badge_cls = "badge-urgent" if is_urgent else "badge-warning"
    badge_txt = "URGENT" if is_urgent else "WARNING"
    box_cls = "urgent" if is_urgent else ""
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header">
    <h1>🔔 SmartAttend — Absence Alert</h1>
    <p>Automated attendance monitoring system</p>
  </div>
  <div class="body">
    <div class="alert-box {box_cls}">
      <strong>Student has been absent from class for {absent_minutes} minutes</strong>
      <span class="badge {badge_cls}">{badge_txt}</span>
    </div>
    <div class="info-row"><span class="info-label">Student Name</span><span class="info-value">{student_name}</span></div>
    <div class="info-row"><span class="info-label">Student ID</span><span class="info-value">{student_id}</span></div>
    <div class="info-row"><span class="info-label">Batch</span><span class="info-value">{batch}</span></div>
    <div class="info-row"><span class="info-label">Subject</span><span class="info-value">{subject}</span></div>
    <div class="info-row"><span class="info-label">Room</span><span class="info-value">{room or "N/A"}</span></div>
    <div class="info-row"><span class="info-label">Class Teacher</span><span class="info-value">{teacher_name}</span></div>
    <div class="info-row"><span class="info-label">Alert Time</span><span class="info-value">{timestamp}</span></div>
    <hr>
    <p style="color:#94a3b8;font-size:13px;">
      The student checked in at the classroom entrance but has not been detected by the classroom 
      camera for <strong style="color:#e2e8f0">{absent_minutes} consecutive minutes</strong>. 
      Please investigate immediately.
    </p>
  </div>
  <div class="footer">SmartAttend by Risely &bull; <a href="#">Admin Panel</a></div>
</div>
</body></html>
"""


def _build_daily_report_html(rows: list, report_date: str) -> str:
    rows_html = ""
    for r in rows:
        pct = round((r["present"] or 0) / max(r["total"], 1) * 100, 1)
        color = "#22c55e" if pct >= 75 else "#f59e0b" if pct >= 50 else "#ef4444"
        rows_html += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #2d2d4e">{r["subject"]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #2d2d4e">{r["batch"]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #2d2d4e;text-align:center">{r["present"]}/{r["total"]}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #2d2d4e;text-align:center;color:{color};font-weight:700">{pct}%</td>
        </tr>"""
    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8">{_BASE_STYLE}</head><body>
<div class="container">
  <div class="header">
    <h1>📊 SmartAttend — Daily Report</h1>
    <p>{report_date}</p>
  </div>
  <div class="body">
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#2d2d4e">
          <th style="padding:10px 12px;text-align:left;color:#94a3b8">Subject</th>
          <th style="padding:10px 12px;text-align:left;color:#94a3b8">Batch</th>
          <th style="padding:10px 12px;text-align:center;color:#94a3b8">Present</th>
          <th style="padding:10px 12px;text-align:center;color:#94a3b8">%</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
  <div class="footer">SmartAttend by Risely &bull; Automated Daily Summary</div>
</div>
</body></html>
"""


# ── Sender ─────────────────────────────────────────────────────────────────────

async def _send(subject: str, html: str, recipients: List[str]):
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not recipients:
        log.warning("Email not sent — SMTP not configured or no recipients.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        log.info("Email sent to %s: %s", recipients, subject)
    except Exception as e:
        log.error("Email failed: %s", e)


async def send_absence_warning(
    student_name: str,
    student_id: str,
    subject: str,
    room: str,
    batch: str,
    absent_minutes: int,
    teacher_name: str,
):
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p IST")
    html = _build_absent_warning_html(
        student_name, student_id, subject, room, batch,
        absent_minutes, teacher_name, timestamp,
    )
    subject_line = f"⚠️ SmartAttend: {student_name} absent {absent_minutes}min — {subject} ({batch})"
    await _send(subject_line, html, settings.alert_email_list)


async def send_daily_report(rows: list, report_date: str):
    html = _build_daily_report_html(rows, report_date)
    await _send(
        f"📊 SmartAttend Daily Report — {report_date}",
        html,
        settings.alert_email_list,
    )
