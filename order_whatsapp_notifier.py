"""
WhatsApp Order Confirmation Notifier
-------------------------------------
Receives a "new order" event from your website (via webhook POST) and sends
a WhatsApp template message to the customer with their name, order number,
and date filled in dynamically.
"""

import os
import logging
from datetime import datetime

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("order_notifier")

PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
TEMPLATE_NAME = os.environ.get("WHATSAPP_TEMPLATE_NAME", "jaspers_market_order_confirmation_v1")
TEMPLATE_LANG = os.environ.get("WHATSAPP_TEMPLATE_LANG", "en_US")

GRAPH_API_VERSION = "v25.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PHONE_NUMBER_ID}/messages"


def send_order_confirmation(to_number: str, customer_name: str, order_number: str, order_date: str = None) -> dict:
    if order_date is None:
        order_date = datetime.now().strftime("%b %-d, %Y")

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": TEMPLATE_LANG},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": customer_name},
                        {"type": "text", "text": order_number},
                        {"type": "text", "text": order_date},
                    ],
                }
            ],
        },
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(GRAPH_URL, json=payload, headers=headers, timeout=15)

    try:
        data = response.json()
    except ValueError:
        data = {"raw_response": response.text}

    if response.status_code >= 400:
        log.error("WhatsApp API error (%s): %s", response.status_code, data)
    else:
        log.info("WhatsApp message sent to %s for order %s", to_number, order_number)

    return {"status_code": response.status_code, "body": data}


@app.route("/webhook/order", methods=["POST"])
def handle_new_order():
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"error": "Missing or invalid JSON body"}), 400

    required_fields = ["customer_name", "customer_phone", "order_number"]
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    result = send_order_confirmation(
        to_number=payload["customer_phone"],
        customer_name=payload["customer_name"],
        order_number=payload["order_number"],
        order_date=payload.get("order_date"),
    )

    status = 200 if result["status_code"] < 400 else 502
    return jsonify(result), status


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
