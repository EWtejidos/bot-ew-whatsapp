from flask import current_app
import requests
import os
import csv
from datetime import datetime
from app import db
from app.models import Order
from app.services.mood_service import detect_mood, build_mood_reply
from app.services.precios import calcular_precio
from app.services.email_service import send_order_email

# --------------------------------------------------------------
# Configuración de carpetas
# --------------------------------------------------------------

BASE_DIR = os.getcwd()
CSV_FILE = os.path.join(BASE_DIR, "ordenes", "ordenes.csv")

os.makedirs("ordenes", exist_ok=True)
os.makedirs("img", exist_ok=True)
os.makedirs("comprobante", exist_ok=True)

# --------------------------------------------------------------
# Estados
# --------------------------------------------------------------

user_states = {}
orders_temp = {}


def send_main_menu(wa_id):
    send_text(
        wa_id,
        "Soy AO y te aisteire hoy, bienvenida a EW tejidos o Etherial Whispers.\n"
        "Puedes escribir menu para volver a ver esta opción.\n"
        "Que buscas el dia de hoy?\n"
        "1️⃣ Tejido personalizado\n"
        "2️⃣ Tejidos disponibles para comprar ya\n"
        "3️⃣ Ayuda / Asistencia "
    )

# --------------------------------------------------------------
# Enviar mensaje
# --------------------------------------------------------------

def send_text(recipient, text):

    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    data = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    requests.post(url, headers=headers, json=data)

# --------------------------------------------------------------
# Guardar orden en CSV
# --------------------------------------------------------------

def save_order(order_data):
    saved_order = Order(
        wa_id=order_data.get("wa_id"),
        product_type=order_data.get("product_type"),
        product_name=order_data.get("product_name"),
        colors=order_data.get("colors"),
        length_cm=order_data.get("length_cm"),
        width_cm=order_data.get("width_cm"),
        description=order_data.get("description"),
        full_name=order_data.get("full_name"),
        delivery=order_data.get("delivery"),
        product_image=order_data.get("product_image"),
        payment_proof=order_data.get("payment_proof"),
        quote_min=order_data.get("quote_min"),
        quote_max=order_data.get("quote_max"),
        advance_payment=order_data.get("advance_payment"),
        status=order_data.get("status", "cotizacion"),
    )
    db.session.add(saved_order)
    db.session.commit()

    file_exists = os.path.isfile(CSV_FILE)

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:

        writer = csv.DictWriter(file, fieldnames=[
            "date",
            "wa_id",
            "product_type",
            "product_name",
            "colors",
            "length_cm",
            "width_cm",
            "description",
            "full_name",
            "deadline",
            "delivery",
            "product_image",
            "payment_proof",
            "quote_min",
            "quote_max",
            "advance_payment",
            "status"
        ])

        if not file_exists:
            writer.writeheader()

        writer.writerow(order_data)

    send_order_email("nueva_orden", order_data)
    return saved_order


def mark_order_as_paid(wa_id, payment_proof):
    target_order = (
        Order.query.filter_by(wa_id=wa_id, status="cotizacion")
        .order_by(Order.created_at.desc())
        .first()
    )

    if target_order:
        target_order.payment_proof = payment_proof
        target_order.payment_received_at = datetime.utcnow()
        target_order.status = "comprado"
        db.session.commit()

    updated_order = None

    if not os.path.isfile(CSV_FILE):
        return bool(target_order)

    with open(CSV_FILE, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not fieldnames:
        return False

    target_index = None
    for i in range(len(rows) - 1, -1, -1):
        if rows[i].get("wa_id") == wa_id and rows[i].get("status") == "cotizacion":
            target_index = i
            break

    if target_index is None:
        return bool(target_order)

    rows[target_index]["payment_proof"] = payment_proof
    rows[target_index]["status"] = "comprado"
    updated_order = rows[target_index].copy()

    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if updated_order:
        send_order_email("orden_actualizada_comprado", updated_order)

    return bool(target_order or updated_order)

# --------------------------------------------------------------
# Descargar imagen
# --------------------------------------------------------------

def download_media(media_id, folder):

    headers = {"Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}"}
    version = current_app.config["VERSION"]

    url = f"https://graph.facebook.com/{version}/{media_id}"

    response = requests.get(url, headers=headers)
    media_url = response.json()["url"]

    media_response = requests.get(media_url, headers=headers)

    filename = f"{folder}/{media_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"

    with open(filename, "wb") as f:
        f.write(media_response.content)

    return filename

# --------------------------------------------------------------
# Procesar mensaje principal
# --------------------------------------------------------------

def process_whatsapp_message(body):

    value = body["entry"][0]["changes"][0]["value"]
    wa_id = value["contacts"][0]["wa_id"]
    message = value["messages"][0]

    message_type = message["type"]

    message_text = None
    media_id = None

    if message_type == "text":
        message_text = message["text"]["body"]

    elif message_type == "image":
        media_id = message["image"]["id"]

    if message_text and message_text.strip().lower() == "menu":
        send_main_menu(wa_id)
        user_states[wa_id] = "menu_choice"
        return

    # ---------------- MENU ----------------

    if wa_id not in user_states:
        user_states[wa_id] = "mood_check"
        send_text(wa_id, "Hola. Como te encuentras el dia de hoy?")
        return

    state = user_states[wa_id]

    if state == "mood_check":
        if not message_text:
            send_text(wa_id, "Escribeme con texto como te sientes hoy.")
            return

        mood = detect_mood(message_text)
        send_text(wa_id, build_mood_reply(mood))
        send_main_menu(wa_id)
        user_states[wa_id] = "menu_choice"
        return

    if state == "menu":
        send_main_menu(wa_id)
        user_states[wa_id] = "menu_choice"
        return

    # ---------------- OPCION 1 ----------------

    if state == "menu_choice" and message_text == "1":
        orders_temp[wa_id] = {}
        send_text(
            wa_id,
            "¿Qué tipo de tejido deseas solicitar?\n"
            "Presiona el número según la opción:\n"
            "1️⃣ Prenda de vestir\n"
            "2️⃣ Vestido de baño\n"
            "3️⃣ Amigurumi o peluche\n"
            "4️⃣ Llavero o flores"
        )
        user_states[wa_id] = "product_type"
        return

    if state == "product_type":
        product_type_options = {
            "1": "Prenda de vestir",
            "2": "Vestido de baño",
            "3": "Amigurumi o peluche",
            "4": "Llavero o flores",
        }

        selected_product_type = product_type_options.get((message_text or "").strip())
        if not selected_product_type:
            send_text(wa_id, "Opción no válida. Responde solo con: 1, 2, 3 o 4.")
            return

        orders_temp[wa_id]["product_type"] = selected_product_type
        send_text(wa_id, "¿como se llama lo que deseas pedir?")
        user_states[wa_id] = "product_name"
        return

    if state == "product_name":
        orders_temp[wa_id]["product_name"] = message_text
        send_text(wa_id, "Envía una foto del producto")
        user_states[wa_id] = "product_image"
        return

    if state == "product_image" and media_id:
        image_path = download_media(media_id, "img")
        orders_temp[wa_id]["product_image"] = image_path
        send_text(wa_id, "Indica los colores separados por coma.")
        user_states[wa_id] = "colors"
        return

    if state == "colors":
        orders_temp[wa_id]["colors"] = message_text
        send_text(wa_id, "Largo a proximado en centímetros (solo numeros):")
        user_states[wa_id] = "length"
        return

    if state == "length":
        orders_temp[wa_id]["length_cm"] = message_text
        send_text(wa_id, "Ancho aproximado en centímetros (solo numeros):")
        user_states[wa_id] = "width"
        return

    if state == "width":
        orders_temp[wa_id]["width_cm"] = message_text
        send_text(wa_id, "Describe todos los detalles adicionales, agrega mi nombre al tejido, tambien puedes escribir que te gustaria hablar con una persona para decirle los detalles:")
        user_states[wa_id] = "description"
        return

    if state == "description":
        orders_temp[wa_id]["description"] = message_text
        send_text(wa_id, "Ingresa tu nombre completo:")
        user_states[wa_id] = "full_name"
        return

    if state == "full_name":
        orders_temp[wa_id]["full_name"] = message_text
        send_text(wa_id, "Entrega (Dirección o Punto de recogida):")
        user_states[wa_id] = "delivery"
        return

    if state == "delivery":
        orders_temp[wa_id]["delivery"] = message_text
        orders_temp[wa_id]["date"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        orders_temp[wa_id]["wa_id"] = wa_id
        orders_temp[wa_id]["payment_proof"] = ""
        orders_temp[wa_id]["status"] = "cotizacion"

        cotizacion = calcular_precio(
            tipo=orders_temp[wa_id].get("product_type"),
            largo=orders_temp[wa_id].get("length_cm"),
            ancho=orders_temp[wa_id].get("width_cm"),
            archivo_historico=CSV_FILE,
        )
        orders_temp[wa_id]["quote_min"] = cotizacion["precio_min"]
        orders_temp[wa_id]["quote_max"] = cotizacion["precio_max"]
        orders_temp[wa_id]["advance_payment"] = cotizacion["pago_30"]

        save_order(orders_temp[wa_id])

        send_text(
            wa_id,
            "🧾 Tu orden podria costar entre "
            f"${cotizacion['precio_min']} y ${cotizacion['precio_max']}.\n"
            "Para confirmar la orden envia comprobante de pago a este chat\n"
            f"con el monto minimo de ${cotizacion['pago_30']} a Nequi o Daviplata 3206420121."
        )
        user_states[wa_id] = "waiting_payment"
        return

    if state == "waiting_payment" and media_id:
        proof_path = download_media(media_id, "comprobante")
        mark_order_as_paid(wa_id, proof_path)
        send_text(wa_id, "✅ Orden enlistada exitosamente. \n Una persona de nuestro equipo se comunicará contigo en menos de 48 horas para confirmar detalles y tiempos de entrega.")
        user_states[wa_id] = "menu"
        return

# --------------------------------------------------------------

def is_valid_whatsapp_message(body):
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
    )
