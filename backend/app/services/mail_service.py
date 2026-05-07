import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from backend.app.core.config import settings
from backend.app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _validate_smtp_settings() -> None:
    missing_fields: list[str] = []

    if not settings.SMTP_HOST:
        missing_fields.append("SMTP_HOST")
    if not settings.SMTP_PORT:
        missing_fields.append("SMTP_PORT")
    if not settings.SMTP_USERNAME:
        missing_fields.append("SMTP_USERNAME")
    if not settings.SMTP_PASSWORD:
        missing_fields.append("SMTP_PASSWORD")
    if not settings.MAIL_FROM:
        missing_fields.append("MAIL_FROM")

    if missing_fields:
        raise AppException(msg=f"邮件服务未配置完整，请补充: {', '.join(missing_fields)}")


def _build_from_header() -> str:
    if settings.MAIL_FROM_NAME:
        return f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
    return str(settings.MAIL_FROM)


def _send_email_sync(message: EmailMessage) -> None:
    context = ssl.create_default_context()

    if settings.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
            context=context,
        ) as server:
            server.login(str(settings.SMTP_USERNAME), str(settings.SMTP_PASSWORD))
            server.send_message(message)
        return

    with smtplib.SMTP(
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        timeout=settings.SMTP_TIMEOUT_SECONDS,
    ) as server:
        if settings.SMTP_USE_STARTTLS:
            server.starttls(context=context)
        server.login(str(settings.SMTP_USERNAME), str(settings.SMTP_PASSWORD))
        server.send_message(message)


# 发送密码重置邮件，支持文本和 HTML 格式，异步执行。
async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    _validate_smtp_settings()

    message = EmailMessage()
    message["Subject"] = f"{settings.APP_NAME} 重置密码"
    message["From"] = _build_from_header()
    message["To"] = to_email

    text_content = (
        "你正在申请重置 OffeCopilot 账号密码。\n\n"
        f"请点击下面的链接继续设置新密码：\n{reset_link}\n\n"
        f"该链接将在 {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} 分钟后失效。\n"
        "如果这不是你的操作，请忽略这封邮件。"
    )
    html_content = f"""
    <html>
      <body>
        <p>你正在申请重置 <strong>OfferPilot</strong> 账号密码。</p>
        <p>
          请点击下面的链接继续设置新密码：<br />
          <a href="{reset_link}">{reset_link}</a>
        </p>
        <p>该链接将在 {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} 分钟后失效。</p>
        <p>如果这不是你的操作，请忽略这封邮件。</p>
      </body>
    </html>
    """

    message.set_content(text_content)
    message.add_alternative(html_content, subtype="html")

    try:
        await asyncio.to_thread(_send_email_sync, message)
    except smtplib.SMTPException as exc:
        logger.exception("SMTP send failed")
        raise AppException(msg="邮件发送失败，请稍后重试") from exc
    except OSError as exc:
        logger.exception("SMTP connection failed")
        raise AppException(msg="邮件服务连接失败，请检查 SMTP 配置") from exc
