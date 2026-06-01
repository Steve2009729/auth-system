from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from app.config import settings


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    plain_text: str | None = None
) -> bool:
    """Send email via SMTP."""
    try:
        if plain_text is None:
            plain_text = subject

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.EMAILS_FROM
        message["To"] = to_email

        part1 = MIMEText(plain_text, "plain")
        part2 = MIMEText(html_content, "html")

        message.attach(part1)
        message.attach(part2)

        async with aiosmtplib.SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT) as smtp:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.sendmail(settings.EMAILS_FROM, to_email, message.as_string())

        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


async def send_verification_email(email: str, verification_link: str) -> bool:
    """Send email verification link."""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Welcome to AuthSystem!</h2>
            <p>Please verify your email address by clicking the link below:</p>
            <p><a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
            <p>Or copy this link: <a href="{verification_link}">{verification_link}</a></p>
            <p>This link expires in 24 hours.</p>
        </body>
    </html>
    """
    return await send_email(email, "Verify Your Email", html_content)


async def send_password_reset_email(email: str, reset_link: str) -> bool:
    """Send password reset link."""
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Password Reset Request</h2>
            <p>You requested a password reset. Click the link below to reset your password:</p>
            <p><a href="{reset_link}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>Or copy this link: <a href="{reset_link}">{reset_link}</a></p>
            <p>This link expires in 1 hour.</p>
            <p>If you didn't request this, ignore this email.</p>
        </body>
    </html>
    """
    return await send_email(email, "Reset Your Password", html_content)
