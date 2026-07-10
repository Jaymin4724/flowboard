import logging
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings
from pathlib import Path

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.conf = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates/email",
        )
        self.fastmail = FastMail(self.conf)

    async def send_otp_email(self, email_to: str, otp: str):
        """Sends a 6-digit OTP email to the user."""
        body = f"""
        <html>
            <body>
                <h1>Verify Your Account</h1>
                <p>Thank you for registering. Please use the following One-Time Password (OTP) to complete your signup:</p>
                <h2 style="color: #4CAF50;">{otp}</h2>
                <p>This code is valid for 10 minutes. If you did not request this, please ignore this email.</p>
            </body>
        </html>
        """

        message = MessageSchema(
            subject="Your Verification Code",
            recipients=[email_to],
            body=body,
            subtype=MessageType.html,
        )

        try:
            await self.fastmail.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email_to}: {e}")

    async def send_reminder_email(self, email_to: str, subject: str, body: str):
        """Internal async method to send the actual email"""
        message = MessageSchema(
            subject=subject,
            recipients=[email_to],
            body=body,
            subtype=MessageType.html,
        )
        await self.fastmail.send_message(message)