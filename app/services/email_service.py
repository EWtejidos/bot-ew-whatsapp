import logging
import os
import smtplib
from email.message import EmailMessage


def _format_order_data(order_data):
    if not order_data:
        return "Sin datos de orden."
    lines = []
    for key, value in order_data.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def send_order_email(event_type, order_data):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    alert_to = os.getenv("ALERT_TO")

    if not smtp_user or not smtp_pass or not alert_to:
        logging.info("Email alert skipped: SMTP_USER/SMTP_PASS/ALERT_TO not configured.")
        return False

    subject = f"EW Orden: {event_type}"
    body = (
        "Se detecto un cambio en la tabla de ordenes.\n\n"
        f"Evento: {event_type}\n\n"
        "Datos de la orden:\n"
        f"{_format_order_data(order_data)}"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = alert_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logging.exception("Failed to send order email: %s", exc)
        return False
