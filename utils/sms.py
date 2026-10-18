"""
utils/sms.py  —  Semaphore SMS Gateway integration
====================================================
Semaphore API docs: https://semaphore.co/docs

Usage:
    from utils.sms import send_sms, notify_admins_sms

    # Send to one number
    send_sms("+639171234567", "Hello from e-Palengke!")

    # Blast to all admin phones
    notify_admins_sms("New complaint #C-0042 filed for Overpricing.")
"""

import logging
import threading
import urllib.request
import urllib.parse
import json

from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(number: str, message: str) -> dict:
    """
    Send a single SMS via the Semaphore REST API.

    Args:
        number  : Philippine mobile number (e.g. '09171234567' or '+639171234567')
        message : Plain-text message body (max 160 chars per segment)

    Returns:
        Parsed JSON response dict from Semaphore, or an error dict on failure.
    """
    api_key = getattr(settings, "SEMAPHORE_API_KEY", None)
    if not api_key:
        logger.warning("SEMAPHORE_API_KEY not configured — SMS skipped.")
        return {"error": "SEMAPHORE_API_KEY not set"}

    sender_name = getattr(settings, "SEMAPHORE_SENDER_NAME", "ePalengke")

    # Normalize number format
    number = number.strip().replace(" ", "").replace("-", "")
    if number.startswith("+63"):
        number = "0" + number[3:]
    elif number.startswith("63") and len(number) == 12:
        number = "0" + number[2:]

    payload = urllib.parse.urlencode({
        "apikey":      api_key,
        "number":      number,
        "message":     message[:1600],   # Semaphore allows up to 10 segments
        "sendername":  sender_name,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.semaphore.co/api/v4/messages",
        data=payload,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            result = json.loads(body)
            logger.info("SMS sent to %s: %s", number, result)
            return result
    except Exception as exc:
        logger.error("SMS send failed to %s: %s", number, exc)
        return {"error": str(exc)}


def send_sms_async(number: str, message: str) -> None:
    """Fire-and-forget wrapper — sends in a background thread so it never
    blocks the HTTP request/response cycle."""
    t = threading.Thread(target=send_sms, args=(number, message), daemon=True)
    t.start()


def notify_admins_sms(message: str) -> None:
    """
    Send an SMS notification to every admin user that has a phone number set.
    Runs in a background thread so it does not delay the API response.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    admins = User.objects.filter(role="admin").exclude(phone="").values_list("phone", flat=True)
    if not admins:
        logger.info("No admin phone numbers configured — SMS skipped.")
        return

    for phone in admins:
        send_sms_async(phone, message)
