"""Admin settings router — email config, system settings."""

from fastapi import APIRouter, Depends
from app.deps import require_admin
from app.models import Teacher
from app.schemas import SystemSettings
from app.config import settings as app_settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings")
async def get_settings(_: Teacher = Depends(require_admin)):
    return {
        "smtp_host": app_settings.SMTP_HOST,
        "smtp_port": app_settings.SMTP_PORT,
        "smtp_user": app_settings.SMTP_USER,
        "smtp_from_name": app_settings.SMTP_FROM_NAME,
        "alert_emails": app_settings.alert_email_list,
        "monitoring_interval": app_settings.MONITORING_INTERVAL,
        "absent_warning_seconds": app_settings.ABSENT_WARNING_SECONDS,
        "absent_email_seconds": app_settings.ABSENT_EMAIL_SECONDS,
        "face_threshold": app_settings.FACE_THRESHOLD,
        "face_enrollment_samples": app_settings.FACE_ENROLLMENT_SAMPLES,
    }


@router.patch("/settings")
async def update_settings(
    body: SystemSettings,
    _: Teacher = Depends(require_admin),
):
    """
    Update runtime settings (persists for this session; write to .env for permanence).
    For production: use a settings table in DB.
    """
    app_settings.SMTP_HOST = body.smtp_host
    app_settings.SMTP_PORT = body.smtp_port
    app_settings.SMTP_USER = body.smtp_user
    if body.smtp_password:
        app_settings.SMTP_PASSWORD = body.smtp_password
    app_settings.SMTP_FROM_NAME = body.smtp_from_name
    app_settings.ALERT_EMAILS = ",".join(body.alert_emails)
    app_settings.MONITORING_INTERVAL = body.monitoring_interval
    app_settings.ABSENT_WARNING_SECONDS = body.absent_warning_seconds
    app_settings.ABSENT_EMAIL_SECONDS = body.absent_email_seconds
    app_settings.FACE_THRESHOLD = body.face_threshold
    app_settings.FACE_ENROLLMENT_SAMPLES = body.face_enrollment_samples
    return {"message": "Settings updated."}


@router.post("/test-email")
async def test_email(_: Teacher = Depends(require_admin)):
    """Send a test email to all configured recipients."""
    from app.services.email_service import _send
    await _send(
        subject="SmartAttend — Email Test",
        html="<h2 style='color:#7c3aed'>SmartAttend Email Test</h2><p>Your email alerts are configured correctly!</p>",
        recipients=app_settings.alert_email_list,
    )
    return {"message": f"Test email sent to: {app_settings.alert_email_list}"}
