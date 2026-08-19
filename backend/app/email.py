"""Email delivery via SMTP — used by scheduled reports and notifications."""

from __future__ import annotations

import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

logger = structlog.get_logger()


def send_email(
    *,
    smtp_config: dict,
    to: list[str],
    subject: str,
    body: str,
    html_body: str | None = None,
    attachment: bytes | str | None = None,
    attachment_filename: str | None = None,
    attachment_mime: str = "application/octet-stream",
) -> dict:
    """Send an email using the provided SMTP configuration.

    smtp_config keys:
        host, port, username, password, from_email,
        use_tls (bool), use_starttls (bool)

    Phase 40 (ALERT-02, D-15): `html_body` is optional and additive -- when
    provided, the message becomes `multipart/alternative` with BOTH the
    plain part (attached first) and the html part (attached second, per RFC
    2046 -- email clients render the LAST part they support, so html must
    come after plain). When `html_body` is None, behavior is byte-for-byte
    unchanged from before this parameter existed (single plain part).

    Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    host = smtp_config.get("host", "")
    port = int(smtp_config.get("port", 587))
    username = smtp_config.get("username", "")
    password = smtp_config.get("password", "")
    from_email = smtp_config.get("from_email") or username
    use_tls = smtp_config.get("use_tls", False)  # implicit TLS (port 465)
    use_starttls = smtp_config.get("use_starttls", True)  # STARTTLS (port 587)

    if not host:
        return {"ok": False, "error": "SMTP host is not configured"}
    if not to:
        return {"ok": False, "error": "No recipients"}

    msg = MIMEMultipart("alternative") if html_body is not None else MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    if html_body is not None:
        msg.attach(MIMEText(html_body, "html"))

    # Attach file if provided
    if attachment is not None and attachment_filename:
        part = MIMEBase("application", "octet-stream")
        data = attachment if isinstance(attachment, bytes) else attachment.encode("utf-8")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={attachment_filename}")
        if attachment_mime.startswith("text/"):
            part.replace_header("Content-Type", attachment_mime)
        msg.attach(part)

    try:
        ctx = ssl.create_default_context()

        if use_tls:
            # Implicit TLS (port 465)
            server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            if use_starttls:
                server.starttls(context=ctx)

        if username and password:
            server.login(username, password)

        server.sendmail(from_email, to, msg.as_string())
        server.quit()

        logger.info("email_sent", to=to, subject=subject)
        return {"ok": True}

    except smtplib.SMTPAuthenticationError as e:
        logger.error("email_auth_failed", error=str(e))
        return {"ok": False, "error": f"Authentication failed: {e}"}
    except smtplib.SMTPException as e:
        logger.error("email_smtp_error", error=str(e))
        return {"ok": False, "error": f"SMTP error: {e}"}
    except Exception as e:
        logger.error("email_send_error", error=str(e))
        return {"ok": False, "error": str(e)}


def test_smtp_connection(smtp_config: dict) -> dict:
    """Test SMTP connectivity without sending an email."""
    host = smtp_config.get("host", "")
    port = int(smtp_config.get("port", 587))
    username = smtp_config.get("username", "")
    password = smtp_config.get("password", "")
    use_tls = smtp_config.get("use_tls", False)
    use_starttls = smtp_config.get("use_starttls", True)

    if not host:
        return {"ok": False, "error": "SMTP host is required"}

    try:
        ctx = ssl.create_default_context()

        if use_tls:
            server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if use_starttls:
                server.starttls(context=ctx)

        if username and password:
            server.login(username, password)

        server.quit()
        return {"ok": True, "message": f"Connected to {host}:{port}"}

    except smtplib.SMTPAuthenticationError as e:
        return {"ok": False, "error": f"Authentication failed: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
