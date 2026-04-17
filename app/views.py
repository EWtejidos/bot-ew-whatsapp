import json
import logging  # Permite registrar errores, advertencias e información útil (logs)
import os       # Manejo del sistema de archivos (rutas, carpetas, etc.)
import re
import uuid     # Genera identificadores únicos (muy útil para nombres de archivos)
from datetime import datetime

import requests

# Importaciones principales de Flask para manejar rutas, requests y respuestas
from flask import Blueprint, request, jsonify, current_app

# Manejo de autenticación (usuarios logueados)
from flask_login import login_required, current_user

# Para encriptar contraseñas de forma segura antes de guardarlas en BD
from werkzeug.security import generate_password_hash

# Para sanitizar nombres de archivos (evita ataques o errores con nombres raros)
from werkzeug.utils import secure_filename

# Importaciones internas de tu proyecto (arquitectura modular)
from app import db  # Instancia de la base de datos
from .decorators.security import signature_required, validate_signature  # Decorador de seguridad y validación de firma
from .models import Customer, Order, Product, User  # Modelos de base de datos (tablas)
from .utils.whatsapp_utils import (
    process_whatsapp_message,  # Función que procesa lógica del bot
    is_valid_whatsapp_message, # Función que valida si el mensaje es real
)

# Se crea un Blueprint (módulo de rutas) llamado "webhook"
# Esto permite organizar el backend por funcionalidades
webhook_blueprint = Blueprint("webhook", __name__)

# Extensiones de imagen permitidas para subir archivos
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Categorías disponibles para productos (esto probablemente alimenta formularios o lógica de negocio)
PRODUCT_CATEGORIES = [
    "Prenda de vestir",
    "Vestido de baño",
    "Amigurumi o peluche",
    "Llavero o flores",
]


def save_reference_image(file_storage, order_id):
    # Guarda la referencia manual en una carpeta estática pública del sitio.

    # Limpia el nombre del archivo para evitar problemas de seguridad
    filename = secure_filename(file_storage.filename or "")

    # Obtiene la extensión del archivo (.jpg, .png, etc.)
    extension = os.path.splitext(filename)[1].lower()

    # Valida que la extensión esté permitida
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Formato de imagen no permitido.")

    # Define la carpeta raíz estática (donde Flask sirve archivos públicos)
    static_root = current_app.static_folder or current_app.root_path

    # Define la carpeta destino para guardar imágenes de referencia
    target_folder = os.path.join(static_root, "img", "referencias")

    # Crea la carpeta si no existe
    os.makedirs(target_folder, exist_ok=True)

    # Genera un nombre único para evitar colisiones
    unique_name = f"order_{order_id}_{uuid.uuid4().hex[:10]}{extension}"

    # Ruta absoluta donde se guardará el archivo
    absolute_path = os.path.join(target_folder, unique_name)

    # Guarda el archivo en el servidor
    file_storage.save(absolute_path)

    # Retorna la ruta relativa (para guardar en BD o usar en frontend)
    return f"img/referencias/{unique_name}".replace("\\", "/")


def delete_reference_image_file(relative_path):
    # Elimina una imagen previamente guardada

    # Si no hay ruta, no hace nada
    if not relative_path:
        return

    # Normaliza la ruta (evita problemas con slashes)
    normalized_path = relative_path.replace("\\", "/").lstrip("/")

    # Define la raíz estática
    static_root = current_app.static_folder or current_app.root_path

    # Construye la ruta absoluta del archivo
    absolute_path = os.path.abspath(os.path.join(static_root, normalized_path))

    # Ruta absoluta de la carpeta estática
    static_root_abs = os.path.abspath(static_root)

    # Seguridad: evita que se eliminen archivos fuera del directorio permitido
    if not absolute_path.startswith(static_root_abs):
        return

    # Si el archivo existe, lo elimina
    if os.path.isfile(absolute_path):
        os.remove(absolute_path)


def parse_product_id(product_id):
    if product_id is None:
        return None
    match = re.search(r"(\d+)$", str(product_id))
    if match:
        return int(match.group(1))
    return None


def generate_order_code():
    return f"ORD-{uuid.uuid4().hex[:12].upper()}"


def get_mp_access_token():
    return os.getenv("MP_ACCESS_TOKEN")


def get_mp_public_key():
    return os.getenv("MP_PUBLIC_KEY")


def get_mp_base_url():
    base_url = os.getenv("MP_BASE_URL")
    if base_url:
        return base_url.rstrip("/")
    if request:
        inferred = request.url_root or request.host_url
        return inferred.rstrip("/") if inferred else None
    return None


def get_mp_webhook_url():
    webhook_url = os.getenv("MP_WEBHOOK_URL")
    if webhook_url:
        return webhook_url
    if request:
        inferred = request.url_root or request.host_url
        return inferred.rstrip("/") + "/webhook"
    return None


def create_mercadopago_preference(order_info):
    access_token = get_mp_access_token()
    if not access_token:
        raise ValueError("MP_ACCESS_TOKEN no configurado en el entorno.")

    url = "https://api.mercadopago.com/checkout/preferences"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    base_url = order_info.get("base_url") or get_mp_base_url()
    logging.debug("Mercado Pago base_url inicial: %s", base_url)
    if not base_url:
        raise ValueError("No se pudo determinar la URL base para Mercado Pago. Configure MP_BASE_URL o use una URL válida.")

    success_url = f"{base_url}/success"
    failure_url = f"{base_url}/failure"
    pending_url = f"{base_url}/pending"

    if not (success_url.startswith("http://") or success_url.startswith("https://")):
        raise ValueError(f"La URL de éxito de Mercado Pago no es válida: {success_url}")

    cleaned_items = []
    for item in order_info["items"]:
        title = str(item.get("title") or item.get("name") or "").strip()
        if not title:
            raise ValueError("Cada item debe incluir un title válido.")

        quantity = item.get("quantity")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise ValueError(f"Cantidad inválida para el item {title}: {quantity}")
        if quantity <= 0:
            raise ValueError(f"La cantidad debe ser mayor a cero para el item {title}.")

        unit_price = item.get("price")
        try:
            unit_price = float(unit_price)
        except (TypeError, ValueError):
            raise ValueError(f"Precio inválido para el item {title}: {unit_price}")
        if unit_price <= 0:
            raise ValueError(f"El precio debe ser mayor a cero para el item {title}.")

        cleaned_items.append({
            "id": str(item.get("id") or title),
            "title": title,
            "quantity": quantity,
            "unit_price": unit_price,
            "currency_id": "COP"
        })

    phone_raw = str(order_info["customer"].get("phone") or "").strip()
    phone_digits = re.sub(r"\D", "", phone_raw)
    if len(phone_digits) < 7:
        phone_digits = "3000000000"

    payload = {
        "items": cleaned_items,
        "external_reference": order_info["id_orden"],
        "payer": {
            "name": str(order_info["customer"]["full_name"]).strip(),
            "email": order_info["customer"].get("email") or "no-reply@ewtejidos.com",
            "phone": {
                "area_code": "57",
                "number": phone_digits[:20]
            }
        },
        "payment_methods": {
            "excluded_payment_types": [],
            "excluded_payment_methods": []
        },
        "notification_url": get_mp_webhook_url(),
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url
        },
        "auto_return": "approved"
    }

    logging.debug("Mercado Pago preference payload: %s", json.dumps(payload, ensure_ascii=False))

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    logging.debug("Mercado Pago response status: %s", response.status_code)
    logging.debug("Mercado Pago response body: %s", response.text)
    if response.status_code not in {200, 201}:
        raise ValueError(f"Mercado Pago no pudo crear la preferencia: {response.status_code} {response.text}")

    data = response.json()
    preference_id = data.get("id")
    if not preference_id:
        raise ValueError("Mercado Pago retornó preferencia inválida.")

    return preference_id


def is_mercadopago_webhook(body):
    if not isinstance(body, dict):
        return False
    if body.get("type") == "payment":
        return True
    data = body.get("data")
    if isinstance(data, dict) and (data.get("id") or data.get("object")):
        return True
    return False


def get_mp_payment_info(payment_id):
    access_token = get_mp_access_token()
    if not access_token:
        raise ValueError("MP_ACCESS_TOKEN no configurado en el entorno.")

    url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers, timeout=15)

    if response.status_code != 200:
        raise ValueError(f"No fue posible validar el pago en Mercado Pago: {response.status_code}")

    return response.json()


def find_order_by_mp_reference(payment_info, payment_id=None):
    order = None
    external_reference = payment_info.get("external_reference")
    if external_reference:
        order = Order.query.filter_by(id_orden=external_reference).first()
    if not order and payment_id:
        order = Order.query.filter_by(mp_payment_id=payment_id).first()
    if not order:
        preference_id = payment_info.get("preference_id") or payment_info.get("order", {}).get("external_reference")
        order = Order.query.filter_by(mp_preference_id=preference_id).first() if preference_id else None
    return order


def handle_mercadopago_webhook(body):
    data = body.get("data") or {}
    payment_id = None
    if isinstance(data, dict):
        payment_id = data.get("id") or (data.get("object") or {}).get("id")
    if not payment_id:
        payment_id = body.get("id")

    if not payment_id:
        return jsonify({"status": "ignored", "message": "No se encontro identificador de pago."}), 400

    try:
        payment_info = get_mp_payment_info(payment_id)
    except Exception as error:
        logging.exception("Error consultando pago Mercado Pago %s", payment_id)
        return jsonify({"status": "error", "message": str(error)}), 500

    if payment_info.get("status") != "approved":
        return jsonify({"status": "ignored", "message": "Pago no aprobado."}), 200

    order = find_order_by_mp_reference(payment_info, payment_id)
    if order is None:
        logging.warning("No se encontro orden para pago Mercado Pago %s", payment_id)
        return jsonify({"status": "ignored", "message": "Orden no encontrada."}), 200

    try:
        order.status = "pagado"
        order.mp_payment_id = payment_id
        order.payment_received_at = datetime.utcnow()
        db.session.commit()
    except Exception as error:
        logging.exception("No se pudo actualizar la orden pagada %s", order.id)
        db.session.rollback()
        return jsonify({"status": "error", "message": str(error)}), 500

    return jsonify({"status": "success", "order_id": order.id_orden}), 200


def save_catalog_image(file_storage, owner_username):
    # Guarda imágenes del catálogo de productos

    # Limpia el nombre del archivo
    filename = secure_filename(file_storage.filename or "")

    # Obtiene la extensión
    extension = os.path.splitext(filename)[1].lower()

    # Valida extensión permitida
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Formato de imagen no permitido.")

    # Define carpeta estática
    static_root = current_app.static_folder or current_app.root_path

    # Carpeta destino para catálogo
    target_folder = os.path.join(static_root, "img", "catalogo")

    # Crea carpeta si no existe
    os.makedirs(target_folder, exist_ok=True)

    # Genera nombre único usando el usuario dueño
    unique_name = f"{owner_username}_{uuid.uuid4().hex[:10]}{extension}"

    # Ruta absoluta
    absolute_path = os.path.join(target_folder, unique_name)

    # Guarda archivo
    file_storage.save(absolute_path)

    # Retorna ruta relativa
    return f"img/catalogo/{unique_name}".replace("\\", "/")


def handle_message():
    """
    Recibe el paquete de Meta (WhatsApp) y decide si enviarlo al proceso del bot.
    """

    # Obtiene el JSON enviado por Meta (Webhook)
    body = request.get_json()

    # 1. Valida si el mensaje realmente es un mensaje de usuario
    if is_valid_whatsapp_message(body):
        try:
            # Procesa el mensaje usando tu lógica del bot
            process_whatsapp_message(body)

            # Responde OK a Meta (importante: evita reintentos)
            return jsonify({"status": "ok"}), 200

        except Exception as e:
            # Si falla el procesamiento, lo registra en logs
            logging.error(f"Error procesando la lógica del bot: {e}")

            # Devuelve error al cliente
            return jsonify({"status": "error", "message": "Internal processing error"}), 500

    # 2. Si no es un mensaje válido (puede ser "visto", "entregado", etc.)
    # Igual se responde 200 para que Meta no reintente
    return jsonify({"status": "ignored", "message": "Not a valid user message"}), 200


def verify():
    """
    Verificación del Webhook requerida por Meta (Facebook/WhatsApp).
    """

    # Obtiene parámetros enviados por Meta
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    # Verifica que existan los parámetros
    if mode and token:
        # Compara el token recibido con el configurado en tu app
        if mode == "subscribe" and token == current_app.config.get("VERIFY_TOKEN"):
            logging.info("WEBHOOK_VERIFIED")  # Log de éxito

            # Devuelve el challenge (Meta lo necesita para validar el webhook)
            return challenge, 200
        else:
            logging.warning("VERIFICATION_FAILED: Tokens do not match")

            # Token incorrecto → acceso denegado
            return jsonify({"status": "error", "message": "Verification failed"}), 403

    # Si faltan parámetros
    logging.warning("MISSING_PARAMETER: hub.mode or hub.verify_token")

    return jsonify({"status": "error", "message": "Missing parameters"}), 400

# RUTAS
@webhook_blueprint.route("/webhook", methods=["GET"])
def webhook_get():
    return verify()

@webhook_blueprint.route("/webhook", methods=["POST"])
def webhook_post():
    body = request.get_json(silent=True) or {}

    if is_mercadopago_webhook(body):
        return handle_mercadopago_webhook(body)

    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not validate_signature(request.data, signature):
        return jsonify({"status": "error", "message": "Invalid signature"}), 403

    return handle_message()


@webhook_blueprint.route("/api/admin/recent-orders", methods=["GET"])
@login_required
def recent_orders():
    orders = Order.query.order_by(Order.created_at.desc()).limit(50).all()
    return jsonify([order.to_dashboard_dict() for order in orders]), 200


@webhook_blueprint.route("/api/admin/customers", methods=["GET"])
@login_required
def customers():
    customers_list = Customer.query.order_by(Customer.created_at.desc()).limit(100).all()
    return jsonify([customer.to_base_dict() for customer in customers_list]), 200


@webhook_blueprint.route("/api/admin/users", methods=["GET"])
@login_required
def admin_users():
    if current_user.role != 'admin':
        return jsonify({"error": "No autorizado"}), 403

    users = User.query.order_by(User.username).all()
    return jsonify([
        {"id": user.id, "username": user.username, "role": user.role}
        for user in users
    ]), 200


@webhook_blueprint.route("/api/admin/users", methods=["POST"])
@login_required
def create_admin_user():
    if current_user.role != 'admin':
        return jsonify({"error": "No autorizado"}), 403

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    role = (request.form.get("role") or "tejedor").strip()

    if not username or not password or role not in {"admin", "transportista", "tejedor"}:
        return jsonify({"error": "Username, password and role are required."}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "El usuario ya existe."}), 400

    try:
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"id": new_user.id, "username": new_user.username, "role": new_user.role}), 201
    except Exception as error:
        db.session.rollback()
        return jsonify({"error": f"No fue posible crear el usuario: {error}"}), 500


@webhook_blueprint.route("/api/users/me", methods=["GET", "PUT"])
@login_required
def user_profile():
    if request.method == "GET":
        return jsonify(current_user.to_profile_dict()), 200

    payload = request.get_json(silent=True) or {}
    current_user.email = payload.get("email", current_user.email)
    current_user.phone = payload.get("phone", current_user.phone)
    current_user.address = payload.get("address", current_user.address)
    current_user.photo_url = payload.get("photo_url", current_user.photo_url)

    if "social_links" in payload:
        social_links = payload.get("social_links") or []
        current_user.social_links = json.dumps(social_links) if isinstance(social_links, list) else json.dumps([])

    try:
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        return jsonify({"error": f"No fue posible actualizar el perfil: {error}"}), 500

    return jsonify(current_user.to_profile_dict()), 200


@webhook_blueprint.route("/api/checkout", methods=["POST"])
def create_checkout():
    payload = request.get_json(silent=True) or {}
    customer_data = payload.get("customer", {})
    items = payload.get("items", [])
    delivery = (payload.get("delivery") or payload.get("delivery_address") or "").strip()
    total = payload.get("total")

    if not customer_data.get("full_name"):
        return jsonify({"error": "El nombre del cliente es requerido."}), 400
    if not customer_data.get("email"):
        return jsonify({"error": "El correo electronico del cliente es requerido."}), 400
    if not customer_data.get("phone"):
        return jsonify({"error": "El telefono de contacto es requerido."}), 400
    if not delivery:
        return jsonify({"error": "La direccion de entrega es obligatoria."}), 400
    if not items or not isinstance(items, list):
        return jsonify({"error": "El carrito debe contener al menos un producto."}), 400
    if total is None:
        return jsonify({"error": "El total de la orden es requerido."}), 400

    line_items = []
    owner_usernames = set()

    for item in items:
        item_id = parse_product_id(item.get("id"))
        if item_id is None:
            return jsonify({"error": f"ID de producto invalido: {item.get('id')}"}), 400

        product = Product.query.get(item_id)
        if product is None:
            return jsonify({"error": f"No se encontro el producto {item_id}."}), 404

        quantity = int(item.get("quantity", 1))
        unit_price = int(item.get("price", product.price))
        if quantity <= 0 or unit_price < 0:
            return jsonify({"error": "Cantidad o precio inválido."}), 400

        owner_usernames.add(product.owner_username)
        line_items.append({
            "id": item_id,
            "name": product.name,
            "quantity": quantity,
            "price": unit_price,
        })

    customer_wa_id = customer_data.get("email") or customer_data.get("phone") or f"web_{uuid.uuid4().hex[:12]}"
    customer = Customer.query.filter_by(wa_id=customer_wa_id).first()
    if customer is None:
        customer = Customer(wa_id=customer_wa_id, full_name=customer_data.get("full_name"))
        db.session.add(customer)
        db.session.commit()
    else:
        customer.full_name = customer_data.get("full_name", customer.full_name)
        db.session.commit()

    order_code = generate_order_code()
    assigned_to = ", ".join(sorted(owner_usernames)) if owner_usernames else None

    order = Order(
        id_orden=order_code,
        customer_id=customer.id,
        wa_id=customer_wa_id,
        product_name=line_items[0]["name"] if line_items else None,
        delivery=delivery,
        contact_phone=customer_data.get("phone"),
        contact_email=customer_data.get("email"),
        total=int(total),
        payment_method="mercadopago",
        status="pendiente_pago",
        items_json=json.dumps(line_items, ensure_ascii=False),
        assigned_to=assigned_to,
        full_name=customer.full_name,
        date=datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    )

    try:
        db.session.add(order)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        return jsonify({"error": f"No fue posible crear la orden inicial: {error}"}), 500

    try:
        preference_id = create_mercadopago_preference({
            "id_orden": order_code,
            "customer": customer_data,
            "items": line_items,
            "base_url": request.url_root.rstrip("/")
        })
        order.mp_preference_id = preference_id
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible crear la preferencia de pago para la orden %s", order_code)
        return jsonify({"error": str(error)}), 500

    public_key = get_mp_public_key()
    return jsonify({"preference_id": preference_id, "public_key": public_key, "order_id": order_code}), 201


@webhook_blueprint.route("/api/transport/orders", methods=["GET"])
@login_required
def transport_orders():
    if current_user.role not in {"admin", "transportista"}:
        return jsonify({"error": "No autorizado"}), 403

    orders = Order.query.filter(Order.status.in_(["listo_envio", "en_camino", "entregado"]))
    orders = orders.order_by(Order.created_at.desc()).all()
    response = []

    for order in orders:
        pickup_address = None
        weaver_name = None
        if order.assigned_to:
            weaver_name = order.assigned_to.split(",")[0].strip()
            weaver = User.query.filter_by(username=weaver_name).first()
            pickup_address = weaver.address if weaver else None

        response.append({
            "id": order.id,
            "id_orden": order.id_orden,
            "cliente": order.customer.full_name if order.customer else order.full_name,
            "weaver": order.assigned_to,
            "pickup_address": pickup_address,
            "delivery_address": order.delivery,
            "status": order.status,
            "contact_phone": order.contact_phone,
            "contact_email": order.contact_email,
            "items": json.loads(order.items_json or "[]"),
            "created_at": order.created_at.strftime("%d/%m/%Y %H:%M"),
        })

    return jsonify(response), 200


@webhook_blueprint.route("/api/admin/orders", methods=["GET"])
@login_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([order.to_admin_dict() for order in orders]), 200


@webhook_blueprint.route("/api/orders", methods=["GET"])
def orders_for_panel():
    """
    Endpoint público que retorna todas las órdenes para el panel de administración.
    Utilizado por productosadmin.js para cargar órdenes de clientes.
    Retorna datos con estructura compatible con el frontend.
    """
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify([order.to_admin_dict() for order in orders]), 200


@webhook_blueprint.route("/api/product-categories", methods=["GET"])
def product_categories():
    return jsonify(PRODUCT_CATEGORIES), 200


@webhook_blueprint.route("/api/productos", methods=["GET"])
@login_required
def my_products():
    if current_user.role not in {"admin", "tejedor"}:
        return jsonify({"error": "No autorizado"}), 403

    products = Product.query.filter_by(owner_username=current_user.username).order_by(Product.created_at.desc()).all()
    return jsonify([product.to_dict() for product in products]), 200


@webhook_blueprint.route("/api/public/productos", methods=["GET"])
def public_products():
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
    return jsonify([product.to_dict() for product in products]), 200


@webhook_blueprint.route("/api/productos", methods=["POST"])
@login_required
def create_product():
    if current_user.role not in {"admin", "tejedor"}:
        return jsonify({"error": "No autorizado"}), 403

    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    price = request.form.get("price", type=int)
    image = request.files.get("image")

    if not name or not category or price is None:
        return jsonify({"error": "Debes enviar nombre, categoria y precio."}), 400

    if category not in PRODUCT_CATEGORIES:
        return jsonify({"error": "La categoria seleccionada no es valida."}), 400

    try:
        saved_image = save_catalog_image(image, current_user.username) if image else None
        product = Product(
            owner_username=current_user.username,
            name=name,
            category=category,
            price=price,
            image_path=saved_image,
            is_active=True,
        )
        db.session.add(product)
        db.session.commit()
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logging.exception("No fue posible crear el producto")
        db.session.rollback()
        return jsonify({"error": f"No fue posible crear el producto: {error}"}), 500

    return jsonify(product.to_dict()), 201


@webhook_blueprint.route("/api/productos/<int:product_id>", methods=["PUT"])
@login_required
def update_product(product_id):
    if current_user.role not in {"admin", "tejedor"}:
        return jsonify({"error": "No autorizado"}), 403

    product = Product.query.filter_by(id=product_id, owner_username=current_user.username).first()
    if product is None:
        return jsonify({"error": "No se encontro el producto solicitado."}), 404

    name = (request.form.get("name") or product.name).strip()
    category = (request.form.get("category") or product.category).strip()
    raw_price = request.form.get("price")
    remove_image = (request.form.get("remove_image") or "").strip().lower() == "true"
    image = request.files.get("image")

    try:
        if raw_price is not None and raw_price != "":
            product.price = int(raw_price)
        product.name = name
        product.category = category

        if category not in PRODUCT_CATEGORIES:
            return jsonify({"error": "La categoria seleccionada no es valida."}), 400

        if remove_image:
            delete_reference_image_file(product.image_path)
            product.image_path = None

        if image:
            delete_reference_image_file(product.image_path)
            product.image_path = save_catalog_image(image, current_user.username)

        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logging.exception("No fue posible actualizar el producto %s", product_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible actualizar el producto: {error}"}), 500

    return jsonify(product.to_dict()), 200


@webhook_blueprint.route("/api/productos/<int:product_id>/toggle", methods=["POST"])
@login_required
def toggle_product(product_id):
    if current_user.role not in {"admin", "tejedor"}:
        return jsonify({"error": "No autorizado"}), 403

    product = Product.query.filter_by(id=product_id, owner_username=current_user.username).first()
    if product is None:
        return jsonify({"error": "No se encontro el producto solicitado."}), 404

    try:
        product.is_active = not product.is_active
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible cambiar el estado del producto %s", product_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible cambiar el estado del producto: {error}"}), 500

    return jsonify(product.to_dict()), 200


@webhook_blueprint.route("/api/pedidos/aprobados", methods=["GET"])
@login_required
def approved_orders_for_weaver():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return jsonify({
        "current_user": current_user.username,
        "orders": [order.to_admin_dict() for order in orders],
    }), 200


@webhook_blueprint.route("/api/admin/orders/reference-image", methods=["POST"])
@login_required
def upload_reference_image():
    # Endpoint para el boton por fila de la columna Referencia.
    order_id = request.form.get("order_id", type=int)
    reference_image = request.files.get("reference_image")

    if not order_id or reference_image is None:
        return jsonify({"error": "Debes enviar la orden y la imagen de referencia."}), 400

    order = Order.query.get(order_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    try:
        delete_reference_image_file(order.reference_image)
        order.reference_image = save_reference_image(reference_image, order.id)
        db.session.commit()
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logging.exception("No fue posible guardar la referencia de la orden %s", order.id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible guardar la imagen: {error}"}), 500

    return jsonify(order.to_admin_dict()), 200


@webhook_blueprint.route("/api/pedidos/subir-referencia/<int:pedido_id>", methods=["POST"])
@webhook_blueprint.route("/api/upload-reference/<int:pedido_id>", methods=["POST"])
@login_required
def upload_reference_image_for_order(pedido_id):
    # Ruta explicita por pedido para que el frontend suba una imagen y la persista.
    reference_image = request.files.get("foto")

    if reference_image is None:
        return jsonify({"error": "Debes enviar una imagen en el campo foto."}), 400

    order = Order.query.get(pedido_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    try:
        saved_path = save_reference_image(reference_image, order.id)
        delete_reference_image_file(order.reference_image)
        order.reference_image = saved_path
        db.session.commit()
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logging.exception("No fue posible guardar la referencia del pedido %s", pedido_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible guardar la imagen: {error}"}), 500

    return jsonify({"status": "success", "url": saved_path, "order": order.to_admin_dict()}), 200


@webhook_blueprint.route("/api/admin/orders/<int:pedido_id>/reference-image", methods=["DELETE"])
@login_required
def delete_reference_image_for_order(pedido_id):
    order = Order.query.get(pedido_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    try:
        delete_reference_image_file(order.reference_image)
        order.reference_image = None
        if order.status == "comprado":
            order.status = "anticipo_pendiente"
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible eliminar la referencia del pedido %s", pedido_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible eliminar la referencia: {error}"}), 500

    return jsonify({"status": "success", "order": order.to_admin_dict()}), 200


@webhook_blueprint.route("/api/admin/orders/<int:pedido_id>/approve-anticipo", methods=["POST"])
@login_required
def approve_anticipo_for_order(pedido_id):
    order = Order.query.get(pedido_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    try:
        order.status = "comprado"
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible aprobar el anticipo del pedido %s", pedido_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible aprobar el anticipo: {error}"}), 500

    return jsonify({"status": "success", "order": order.to_admin_dict()}), 200


@webhook_blueprint.route("/api/admin/orders/<int:pedido_id>/reject-anticipo", methods=["POST"])
@login_required
def reject_anticipo_for_order(pedido_id):
    order = Order.query.get(pedido_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    try:
        order.status = "rechazado"
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible rechazar el anticipo del pedido %s", pedido_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible rechazar el anticipo: {error}"}), 500

    return jsonify({"status": "success", "order": order.to_admin_dict()}), 200


@webhook_blueprint.route("/api/pedidos/<int:pedido_id>/accept", methods=["POST"])
@login_required
def accept_order_for_weaver(pedido_id):
    order = Order.query.get(pedido_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    payload = request.get_json(silent=True) or {}
    deadline = (payload.get("deadline") or "").strip()

    if not deadline:
        return jsonify({"error": "Debes seleccionar una fecha de entrega."}), 400

    try:
        order.deadline = deadline
        order.assigned_to = current_user.username
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible aceptar el pedido %s", pedido_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible aceptar el pedido: {error}"}), 500

    return jsonify({"status": "success", "order": order.to_admin_dict()}), 200


@webhook_blueprint.route("/api/admin/orders/reference-images", methods=["POST"])
@login_required
def upload_reference_images():
    # Endpoint para la carga multiple desde el boton superior del panel.
    order_ids = request.form.getlist("order_ids")
    reference_images = request.files.getlist("reference_images")

    if not order_ids or not reference_images:
        return jsonify({"error": "Debes enviar ordenes e imagenes para la carga masiva."}), 400

    if len(order_ids) != len(reference_images):
        return jsonify({"error": "La cantidad de ordenes debe coincidir con la cantidad de imagenes."}), 400

    updated_orders = []

    try:
        for raw_order_id, reference_image in zip(order_ids, reference_images):
            order = Order.query.get(int(raw_order_id))
            if order is None:
                raise ValueError(f"La orden {raw_order_id} no existe.")

            delete_reference_image_file(order.reference_image)
            order.reference_image = save_reference_image(reference_image, order.id)
            updated_orders.append(order)

        db.session.commit()
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        logging.exception("No fue posible guardar la carga masiva de referencias")
        db.session.rollback()
        return jsonify({"error": f"No fue posible guardar las imagenes: {error}"}), 500

    return jsonify([order.to_admin_dict() for order in updated_orders]), 200


@webhook_blueprint.route("/api/admin/orders/<int:order_id>", methods=["PUT"])
@login_required
def update_order(order_id):
    """
    Actualiza una orden existente.
    Permite editar todos los campos relevantes de la orden.
    """
    order = Order.query.get(order_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    payload = request.get_json(silent=True) or {}

    try:
        # Actualizar campos si están presentes en el payload
        if "product_type" in payload:
            order.product_type = payload["product_type"]
        if "product_name" in payload:
            order.product_name = payload["product_name"]
        if "colors" in payload:
            order.colors = payload["colors"]
        if "length_cm" in payload:
            order.length_cm = payload["length_cm"]
        if "width_cm" in payload:
            order.width_cm = payload["width_cm"]
        if "description" in payload:
            order.description = payload["description"]
        if "full_name" in payload:
            order.full_name = payload["full_name"]
        if "delivery" in payload:
            order.delivery = payload["delivery"]
        if "date" in payload:
            order.date = payload["date"]
        if "deadline" in payload:
            order.deadline = payload["deadline"]
        if "quote_min" in payload:
            order.quote_min = payload["quote_min"]
        if "quote_max" in payload:
            order.quote_max = payload["quote_max"]
        if "advance_payment" in payload:
            order.advance_payment = payload["advance_payment"]

        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible actualizar la orden %s", order_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible actualizar la orden: {error}"}), 500

    return jsonify({"status": "success", "order": order.to_admin_dict()}), 200


@webhook_blueprint.route("/api/admin/orders/<int:order_id>", methods=["DELETE"])
@login_required
def delete_order(order_id):
    """
    Elimina una orden de la base de datos.
    Usa el ID numérico de la orden.
    """
    order = Order.query.get(order_id)
    if order is None:
        return jsonify({"error": "No se encontro la orden solicitada."}), 404

    try:
        # Eliminar imagenes asociadas antes de borrar la orden
        delete_reference_image_file(order.reference_image)
        delete_reference_image_file(order.product_image)
        
        db.session.delete(order)
        db.session.commit()
    except Exception as error:
        logging.exception("No fue posible eliminar la orden %s", order_id)
        db.session.rollback()
        return jsonify({"error": f"No fue posible eliminar la orden: {error}"}), 500

    return jsonify({"status": "success", "message": "Orden eliminada correctamente."}), 200
