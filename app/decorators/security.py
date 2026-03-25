import functools
import hashlib
import hmac
import logging
from flask import request, jsonify, current_app

def validate_signature(payload, signature):
    # Lee el secreto que pusiste en el archivo WSGI /var/www/...
    app_secret = current_app.config.get("APP_SECRET")

    if not app_secret:
        logging.error("ERROR: APP_SECRET no encontrado en la configuración.")
        return False

    if not signature:
        return False

    sha_name, signature_hash = signature.split('=')
    if sha_name != 'sha256':
        return False

    expected_hash = hmac.new(
        app_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature_hash, expected_hash)

def signature_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature or not validate_signature(request.data, signature):
            logging.info("Firma de Meta inválida o ausente.")
            return jsonify({"status": "error", "message": "Invalid signature"}), 403
        return f(*args, **kwargs)
    return decorated_function
