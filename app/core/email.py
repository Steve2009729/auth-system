import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    """Return True only if SMTP credentials look like real values."""
    from app.config import settings
    placeholder_values = {
        "", "smtp.gmail.com", "your-email@gmail.com",
        "your-app-password", "noreply@authsystem.com"
    }
    # We require at minimum a non-placeholder SMTP_USER and SMTP_PASSWORD
    if settings.SMTP_USER in placeholder_values:
        return False
    if settings.SMTP_PASSWORD in placeholder_values:
        return False
    return True


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    plain_text: str | None = None
) -> bool:
    """Send email via SMTP. Returns False (with a warning) if SMTP is not configured."""
    from app.config import settings

    if not _smtp_configured():
        logger.warning(
            "SMTP is not configured — skipping email to %s (subject: %s). "
            "Set SMTP_USER and SMTP_PASSWORD in your .env to enable email sending.",
            to_email, subject
        )
        return False

    try:
        import aiosmtplib

        if plain_text is None:
            plain_text = subject

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.EMAILS_FROM
        message["To"] = to_email

        message.attach(MIMEText(plain_text, "plain"))
        message.attach(MIMEText(html_content, "html"))

        async with aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT) as smtp:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.EMAILS_FROM, to_email, message.as_string())

        return True
    except Exception as e:
        logger.error("Error sending email to %s: %s", to_email, e)
        return False


async def send_verification_email(email: str, verification_link: str) -> bool:
    """Send email verification link."""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Welcome to AuthSystem!</h2>
            <p>Please verify your email address by clicking the link below:</p>
            <p>
                <a href="{verification_link}"
                   style="background-color: #4CAF50; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Verify Email
                </a>
            </p>
            <p>Or copy this link: <a href="{verification_link}">{verification_link}</a></p>
            <p style="color: #666; font-size: 0.9em;">This link expires in 24 hours.</p>
        </body>
    </html>
    """
    return await send_email(email, "Verify Your Email — AuthSystem", html_content)


async def send_password_reset_email(email: str, reset_link: str) -> bool:
    """Send password reset link."""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Password Reset Request</h2>
            <p>You requested a password reset. Click the link below to reset your password:</p>
            <p>
                <a href="{reset_link}"
                   style="background-color: #2196F3; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 5px; display: inline-block;">
                    Reset Password
                </a>
            </p>
            <p>Or copy this link: <a href="{reset_link}">{reset_link}</a></p>
            <p style="color: #666; font-size: 0.9em;">This link expires in 1 hour.</p>
            <p style="color: #666; font-size: 0.9em;">If you didn't request this, you can safely ignore this email.</p>
        </body>
    </html>
    """
    return await send_email(email, "Reset Your Password — AuthSystem", html_content)
