import logging  # Permite registrar errores, advertencias e información útil (logs)
import os       # Manejo del sistema de archivos (rutas, carpetas, etc.)
import uuid     # Genera identificadores únicos (muy útil para nombres de archivos)

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
from .decorators.security import signature_required  # Decorador de seguridad (probablemente valida origen de requests)
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
@signature_required # Asegúrate de que APP_SECRET esté en el WSGI también
def webhook_post():
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
