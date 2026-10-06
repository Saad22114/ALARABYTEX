"""Sending an opted-in customer's welcome template through WhatsApp Cloud API."""

import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import Customer

logger = logging.getLogger(__name__)


def _normalized_whatsapp_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    country_code = re.sub(r"\D", "", getattr(settings, "WHATSAPP_DEFAULT_COUNTRY_CODE", "968"))
    if len(digits) == 8 and country_code:
        digits = f"{country_code}{digits}"
    elif digits.startswith("0") and len(digits) == 9 and country_code:
        digits = f"{country_code}{digits[1:]}"
    if not 8 <= len(digits) <= 15:
        return None
    return digits


def _save_status(customer, status, *, error="", message_id=""):
    customer.whatsapp_welcome_status = status
    customer.whatsapp_welcome_error = error[:500]
    customer.whatsapp_welcome_message_id = message_id[:150]
    fields = ["whatsapp_welcome_status", "whatsapp_welcome_error", "whatsapp_welcome_message_id"]
    if status == Customer.WhatsAppWelcomeStatus.SENT:
        customer.whatsapp_welcome_sent_at = timezone.now()
        fields.append("whatsapp_welcome_sent_at")
    customer.save(update_fields=fields)


def send_customer_welcome(customer):
    """Submit one approved template after explicit opt-in; never fail customer creation."""
    if not customer.whatsapp_opt_in:
        return

    token = getattr(settings, "WHATSAPP_CLOUD_API_TOKEN", "")
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    graph_version = getattr(settings, "WHATSAPP_GRAPH_API_VERSION", "")
    template_name = getattr(settings, "WHATSAPP_WELCOME_TEMPLATE_NAME", "")
    template_language = getattr(settings, "WHATSAPP_WELCOME_TEMPLATE_LANGUAGE", "ar")
    if not all((token, phone_number_id, graph_version, template_name)):
        _save_status(customer, Customer.WhatsAppWelcomeStatus.NOT_CONFIGURED, error="WhatsApp Cloud API settings are incomplete")
        return

    recipient = _normalized_whatsapp_phone(customer.phone)
    if not recipient:
        _save_status(customer, Customer.WhatsAppWelcomeStatus.FAILED, error="Invalid recipient phone number")
        return

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": template_language},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": customer.name}],
            }],
        },
    }
    request = Request(
        f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        message_id = (data.get("messages") or [{}])[0].get("id", "")
        if not message_id:
            _save_status(customer, Customer.WhatsAppWelcomeStatus.FAILED, error="WhatsApp API returned no message ID")
            return
        _save_status(customer, Customer.WhatsAppWelcomeStatus.SENT, message_id=message_id)
    except HTTPError as exc:
        _save_status(customer, Customer.WhatsAppWelcomeStatus.FAILED, error=f"WhatsApp API HTTP {exc.code}")
        logger.warning("WhatsApp welcome send failed with HTTP %s for customer %s", exc.code, customer.pk)
    except (URLError, TimeoutError, OSError) as exc:
        _save_status(customer, Customer.WhatsAppWelcomeStatus.FAILED, error="WhatsApp API connection failed")
        logger.warning("WhatsApp welcome send connection failed for customer %s: %s", customer.pk, type(exc).__name__)
    except (ValueError, TypeError, KeyError) as exc:
        _save_status(customer, Customer.WhatsAppWelcomeStatus.FAILED, error="Invalid WhatsApp API response")
        logger.warning("WhatsApp welcome response invalid for customer %s: %s", customer.pk, type(exc).__name__)
