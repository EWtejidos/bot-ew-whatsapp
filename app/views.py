import logging
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required

# Importaciones relativas (usando el punto .)
from .decorators.security import signature_required
from .models import Order
from .utils.whatsapp_utils import (
    process_whatsapp_message,
    is_valid_whatsapp_message,)

webhook_blueprint = Blueprint("webhook", __name__)

def handle_message():
    """
    Recibe el paquete de Meta y decide si enviarlo al proceso del bot.
    """
    body = request.get_json()

    # 1. Usamos el filtro que ya tiene el try/except y detecta si es un mensaje real
    if is_valid_whatsapp_message(body):
        try:
            process_whatsapp_message(body)
            # Respondemos OK a Meta para que sepa que recibimos el mensaje
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            logging.error(f"Error procesando la lógica del bot: {e}")
            return jsonify({"status": "error", "message": "Internal processing error"}), 500

    # 2. Si no es un mensaje (es un 'visto', 'entregado' o notificación de Meta)
    # Respondemos 200 para que Meta no reintente, pero marcamos como ignorado.
    return jsonify({"status": "ignored", "message": "Not a valid user message"}), 200


def verify():
    """
    Verificación del Webhook requerida por Meta.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        # Aquí usa el token que inyectamos en el WSGI
        if mode == "subscribe" and token == current_app.config.get("VERIFY_TOKEN"):
            logging.info("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            logging.warning("VERIFICATION_FAILED: Tokens do not match")
            return jsonify({"status": "error", "message": "Verification failed"}), 403

    logging.warning("MISSING_PARAMETER: hub.mode or hub.verify_token")
    return jsonify({"status": "error", "message": "Missing parameters"}), 400

# RUTAS
@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
@signature_required # Asegúrate de que APP_SECRET esté en el WSGI también
def webhook_post():
    return handle_message()


@webhook_blueprint.route("/api/admin/recent-orders", methods=["GET"])
@login_required
def recent_orders():
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    return jsonify([order.to_dashboard_dict() for order in orders]), 200


