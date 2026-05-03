"""
Email Service - Zoho SMTP

- Async email sending via aiosmtplib
- HTML templates for 15-minute warning and 20-minute absence alerts
- Daily attendance report
- Configurable recipients (from DB + .env fallback)
"""

import logging
from datetime import datetime
from typing import List

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

log = logging.getLogger("smartattend.email")


def _base_template(content: str, color: str = "#E53E3E") -> str:
    rgb = ",".join(str(int(color.lstrip("#")[i:i + 2], 16)) for i in (0, 2, 4))
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{ margin:0; padding:0; background:#0A0E1A; font-family:'Segoe UI',Arial,sans-serif; }}
    .wrapper {{ max-width:620px; margin:0 auto; padding:24px 16px; }}
    .card {{ background:#131929; border-radius:16px; overflow:hidden; border:1px solid #1E2A45; }}
    .header {{ background:{color}; padding:28px 32px; }}
    .header h1 {{ margin:0; color:#fff; font-size:22px; font-weight:700; letter-spacing:-0.5px; }}
    .header p {{ margin:6px 0 0; color:rgba(255,255,255,0.85); font-size:14px; }}
    .badge {{ display:inline-block; background:rgba(0,0,0,0.25); border-radius:6px;
              padding:3px 10px; font-size:12px; color:#fff; margin-top:10px; }}
    .body {{ padding:28px 32px; }}
    .row {{ display:flex; justify-content:space-between; padding:12px 0;
            border-bottom:1px solid #1E2A45; }}
    .row:last-child {{ border-bottom:none; }}
    .label {{ color:#6B7A99; font-size:13px; }}
    .value {{ color:#E2E8F0; font-size:13px; font-weight:600; text-align:right; }}
    .alert-box {{ background:rgba({rgb},0.12);
                  border:1px solid {color}40; border-radius:10px; padding:16px 20px; margin:20px 0; }}
    .alert-box p {{ margin:0; color:#E2E8F0; font-size:14px; line-height:1.6; }}
    .footer {{ padding:20px 32px; text-align:center; color:#3A4A6B; font-size:12px;
               border-top:1px solid #1E2A45; }}
    .logo {{ font-weight:800; color:#4A90D9; letter-spacing:-0.5px; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="card">
      {content}
      <div class="footer">
        <span class="logo">SmartAttend</span> · Risely Attendance System<br>
        This is an automated alert. Do not reply to this email.
      </div>
    </div>
  </div>
</body>
</html>
"""


def _missing_15_html(
    student_name: str,
    student_id: str,
    session: str,
    room: str,
    teacher: str,
    checked_in: str,
    last_seen: str,
) -> str:
    content = f"""
    <div class="header" style="background:#D97706;">
      <h1>Warning: Student Missing - 15 Minutes</h1>
      <p>A student has not been detected by the classroom camera for 15 minutes.</p>
      <span class="badge">WARNING</span>
    </div>
    <div class="body">
      <div class="alert-box">
        <p><strong style="color:#FCD34D;">{student_name}</strong> ({student_id}) checked into
        <strong style="color:#FCD34D;">{session}</strong> but has not been seen by the camera
        for the last 15 minutes. Please verify their presence.</p>
      </div>
      <div class="row"><span class="label">Student</span><span class="value">{student_name} ({student_id})</span></div>
      <div class="row"><span class="label">Session / Subject</span><span class="value">{session}</span></div>
      <div class="row"><span class="label">Room / Location</span><span class="value">{room}</span></div>
      <div class="row"><span class="label">Teacher</span><span class="value">{teacher}</span></div>
      <div class="row"><span class="label">Checked In At</span><span class="value">{checked_in}</span></div>
      <div class="row"><span class="label">Last Detected</span><span class="value">{last_seen}</span></div>
      <div class="row"><span class="label">Alert Time</span><span class="value">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</span></div>
    </div>
    """
    return _base_template(content, "#D97706")


def _missing_20_html(
    student_name: str,
    student_id: str,
    session: str,
    room: str,
    teacher: str,
    checked_in: str,
    last_seen: str,
) -> str:
    content = f"""
    <div class="header" style="background:#DC2626;">
      <h1>Urgent: Student Absent - 20 Minutes</h1>
      <p>A student has been absent from the classroom for over 20 minutes.</p>
      <span class="badge">URGENT ACTION REQUIRED</span>
    </div>
    <div class="body">
      <div class="alert-box">
        <p><strong style="color:#FCA5A5;">{student_name}</strong> ({student_id}) checked into
        <strong style="color:#FCA5A5;">{session}</strong> and has now been absent for
        <strong style="color:#FCA5A5;">more than 20 minutes</strong>.
        Immediate action is required - please locate the student.</p>
      </div>
      <div class="row"><span class="label">Student</span><span class="value">{student_name} ({student_id})</span></div>
      <div class="row"><span class="label">Session / Subject</span><span class="value">{session}</span></div>
      <div class="row"><span class="label">Room / Location</span><span class="value">{room}</span></div>
      <div class="row"><span class="label">Teacher</span><span class="value">{teacher}</span></div>
      <div class="row"><span class="label">Checked In At</span><span class="value">{checked_in}</span></div>
      <div class="row"><span class="label">Last Detected</span><span class="value">{last_seen}</span></div>
      <div class="row"><span class="label">Alert Time</span><span class="value">{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</span></div>
    </div>
    """
    return _base_template(content, "#DC2626")


def _daily_report_html(date_str: str, rows: list) -> str:
    rows_html = ""
    for row in rows:
        pct = row.get("percentage", 0)
        color = "#22C55E" if pct >= 75 else "#F59E0B" if pct >= 50 else "#EF4444"
        rows_html += f"""
        <tr>
          <td style="padding:10px 12px;color:#E2E8F0;">{row['subject']}</td>
          <td style="padding:10px 12px;color:#E2E8F0;">{row['batch']}</td>
          <td style="padding:10px 12px;color:#E2E8F0;">{row['total']}</td>
          <td style="padding:10px 12px;color:#22C55E;">{row['present']}</td>
          <td style="padding:10px 12px;color:#EF4444;">{row['absent']}</td>
          <td style="padding:10px 12px;color:{color};font-weight:700;">{pct:.1f}%</td>
        </tr>"""

    content = f"""
    <div class="header" style="background:#1E40AF;">
      <h1>Daily Attendance Report</h1>
      <p>Summary for {date_str}</p>
      <span class="badge">DAILY REPORT</span>
    </div>
    <div class="body">
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="background:#1E2A45;">
            <th style="padding:10px 12px;text-align:left;color:#6B7A99;">Subject</th>
            <th style="padding:10px 12px;text-align:left;color:#6B7A99;">Batch</th>
            <th style="padding:10px 12px;text-align:left;color:#6B7A99;">Total</th>
            <th style="padding:10px 12px;text-align:left;color:#6B7A99;">Present</th>
            <th style="padding:10px 12px;text-align:left;color:#6B7A99;">Absent</th>
            <th style="padding:10px 12px;text-align:left;color:#6B7A99;">%</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
    return _base_template(content, "#1E40AF")


async def _send(to: List[str], subject: str, html: str) -> bool:
    if not to:
        log.warning("No recipients configured; skipping email.")
        return False
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        log.warning("SMTP is not configured; skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"] = ", ".join(to)
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
        log.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        log.exception("Email failed (%s)", subject)
        raise


async def send_missing_15_alert(
    recipients: List[str],
    student_name: str,
    student_id: str,
    session: str,
    room: str,
    teacher: str,
    checked_in: str,
    last_seen: str,
):
    html = _missing_15_html(student_name, student_id, session, room, teacher, checked_in, last_seen)
    await _send(recipients, f"SmartAttend: {student_name} missing 15 min - {session}", html)


async def send_missing_20_alert(
    recipients: List[str],
    student_name: str,
    student_id: str,
    session: str,
    room: str,
    teacher: str,
    checked_in: str,
    last_seen: str,
):
    html = _missing_20_html(student_name, student_id, session, room, teacher, checked_in, last_seen)
    await _send(recipients, f"URGENT SmartAttend: {student_name} absent 20 min - {session}", html)


async def send_daily_report(recipients: List[str], date_str: str, rows: list):
    html = _daily_report_html(date_str, rows)
    await _send(recipients, f"SmartAttend Daily Report - {date_str}", html)


async def send_test_email(recipients: List[str]) -> bool:
    content = """
    <div class="header" style="background:#16A34A;">
      <h1>SmartAttend Email Test</h1>
      <p>Your Zoho SMTP configuration is working correctly.</p>
    </div>
    <div class="body">
      <p style="color:#E2E8F0;">This is a test email from SmartAttend.
      If you received this, your email alerts are configured correctly.</p>
    </div>"""
    html = _base_template(content, "#16A34A")
    return await _send(recipients, "SmartAttend - Email Test Successful", html)
