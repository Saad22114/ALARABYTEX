# WhatsApp welcome message setup

The customer form records explicit WhatsApp opt-in. A welcome template is submitted only for a newly created customer who opted in. Customer creation succeeds even when the WhatsApp API is unavailable; the response records `not_configured` or `failed` so the customer remains saved.

## Meta setup

1. Set up a WhatsApp Business Platform Cloud API number in a Meta business portfolio and create a permanent access token with the `whatsapp_business_messaging` permission.
2. Create and get approval for a welcome message template in WhatsApp Manager. The integration sends the customer's name as the template's first body text parameter, so the approved template must contain exactly one body parameter in that position.
3. Configure the backend environment using the variables below. Keep the access token in the deployment's secret manager or server environment; do not commit it to the repository or expose it to the frontend.
4. Restart the backend after setting the environment. On customer creation, the backend submits a template message to `/{PHONE_NUMBER_ID}/messages` and stores the returned message ID.

| Variable | Value |
| --- | --- |
| `WHATSAPP_CLOUD_API_TOKEN` | Permanent Meta access token |
| `WHATSAPP_PHONE_NUMBER_ID` | Registered Cloud API phone number ID |
| `WHATSAPP_GRAPH_API_VERSION` | A currently supported Graph API version, such as `vXX.0` |
| `WHATSAPP_WELCOME_TEMPLATE_NAME` | Exact approved template name; defaults in `.env.example` to `customer_welcome` |
| `WHATSAPP_WELCOME_TEMPLATE_LANGUAGE` | Approved template language code; defaults to `ar` |
| `WHATSAPP_DEFAULT_COUNTRY_CODE` | Country code for local eight-digit phone numbers; defaults to Oman (`968`) |

If the API accepts a message, the customer record reports `sent`; delivery confirmation requires a WhatsApp webhook and is not included in this first integration. If configuration is missing, the opt-in is saved but no API request is made.
