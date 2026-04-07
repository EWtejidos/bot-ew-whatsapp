from datetime import datetime

from app import db
from flask_login import UserMixin


# Modelo de usuarios del panel web (login de Flask-Login).
class User(db.Model, UserMixin):
    # Identificador interno autoincremental.
    id = db.Column(db.Integer, primary_key=True)
    # Nombre de usuario unico para iniciar sesion.
    username = db.Column(db.String(80), unique=True, nullable=False)
    # Contrasena hasheada (no texto plano).
    password = db.Column(db.String(200), nullable=False)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_username = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image_path = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "owner_username": self.owner_username,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "image_path": self.image_path,
            "is_active": self.is_active,
        }


# Cliente que escribe por WhatsApp.
class Customer(db.Model):
    # ID interno del cliente.
    id = db.Column(db.Integer, primary_key=True)
    # Numero de WhatsApp del cliente (wa_id), unico para no duplicar clientes.
    wa_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    # Nombre completo que el cliente reporta.
    full_name = db.Column(db.String(150), nullable=False)
    # Fecha de creacion del registro.
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Fecha de ultima actualizacion (SQLAlchemy la refresca en cada update).
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    # Relacion uno-a-muchos: un cliente puede tener muchas ordenes.
    orders = db.relationship("Order", back_populates="customer", lazy=True)

    # Estructura resumida para tablas/listados del frontend.
    def to_base_dict(self):
        # Busca la orden mas reciente del cliente por fecha de creacion.
        latest_order = (
            max(self.orders, key=lambda order: order.created_at)
            if self.orders
            else None
        )
        # Texto por defecto si todavia no hay ordenes.
        detail = "Sin ordenes registradas todavia"
        if latest_order:
            # Mensaje de detalle para mostrar ultima orden y estado actual.
            detail = (
                f"Ultima orden {latest_order.id_orden} en estado "
                f"{latest_order.status.replace('_', ' ')}"
            )

        # Diccionario final serializable para UI/API.
        return {
            "id": self.id,
            "wa_id": self.wa_id,
            "nombre": self.full_name,
            "estado": latest_order.status if latest_order else "sin-ordenes",
            "detalle": detail,
        }


class Order(db.Model):
    # ID interno autoincremental de la orden.
    id = db.Column(db.Integer, primary_key=True)
    # Identificador aleatorio unico de la orden (ID_orden de negocio).
    id_orden = db.Column(db.String(24), unique=True, nullable=False, index=True)
    # Clave foranea al cliente dueño de la orden.
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    # Fecha de creacion de la orden.
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    # Fecha de actualizacion de la orden.
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    # Fecha en que se recibio comprobante de pago.
    payment_received_at = db.Column(db.DateTime, nullable=True)
    # Fecha textual capturada en el flujo del bot (formato dd/mm/YYYY HH:MM).
    date = db.Column(db.String(20), nullable=True)
    # Numero de WhatsApp asociado a la orden.
    wa_id = db.Column(db.String(32), nullable=False, index=True)
    # Tipo de producto elegido por menu.
    product_type = db.Column(db.String(100), nullable=True)
    # Nombre puntual del producto solicitado.
    product_name = db.Column(db.String(150), nullable=True)
    # Colores reportados por el cliente.
    colors = db.Column(db.String(255), nullable=True)
    # Largo reportado (se maneja como texto en este modelo).
    length_cm = db.Column(db.String(32), nullable=True)
    # Ancho reportado (se maneja como texto en este modelo).
    width_cm = db.Column(db.String(32), nullable=True)
    # Detalles libres del cliente.
    description = db.Column(db.Text, nullable=True)
    # Copia del nombre (respaldo si no se logra relacionar cliente).
    full_name = db.Column(db.String(150), nullable=True)
    # Forma/lugar de entrega.
    delivery = db.Column(db.String(255), nullable=True)
    # Fecha limite objetivo de entrega (si se define en el flujo).
    deadline = db.Column(db.String(80), nullable=True)
    # Usuario tejedor/aliado que acepto el pedido desde el panel.
    assigned_to = db.Column(db.String(80), nullable=True)
    # Ruta local de la imagen del producto enviada por WhatsApp.
    product_image = db.Column(db.String(255), nullable=True)
    # Ruta local de la referencia cargada manualmente desde el panel admin.
    reference_image = db.Column(db.String(255), nullable=True)
    # Ruta local del comprobante de pago.
    payment_proof = db.Column(db.String(255), nullable=True)
    # Rango de cotizacion calculado.
    quote_min = db.Column(db.Integer, nullable=True)
    quote_max = db.Column(db.Integer, nullable=True)
    # Anticipo sugerido/calculado para confirmar la orden.
    advance_payment = db.Column(db.Integer, nullable=True)
    # Estado del flujo (cotizacion, comprado, etc.).
    status = db.Column(db.String(40), nullable=False, default="cotizacion", index=True)
    # Relacion inversa: cada orden pertenece a un cliente.
    customer = db.relationship("Customer", back_populates="orders")

    # Diccionario para tablero operativo.
    def to_dashboard_dict(self):
        # Usa nombre del cliente relacionado; si no existe, usa respaldo local.
        customer_name = self.customer.full_name if self.customer else (self.full_name or "Cliente sin nombre")
        return {
            "id": self.id,
            "id_orden": self.id_orden,
            "wa_id": self.wa_id,
            "cliente": customer_name,
            "producto": self.product_name or "Producto personalizado",
            "product_name": self.product_name,
            "fecha": self.date or (self.created_at.strftime("%d/%m/%Y %H:%M") if self.created_at else ""),
            "status": self.status,
            "cotizacion_min": self.quote_min,
            "cotizacion_max": self.quote_max,
            "anticipo": self.advance_payment,
            "delivery": self.delivery,
            "description": self.description,
            "deadline": self.deadline,
            "assigned_to": self.assigned_to,
            "length_cm": self.length_cm,
            "width_cm": self.width_cm,
            "product_image": self.product_image,
            # Se expone aparte para no mezclarla con la imagen original del pedido.
            "reference_image": self.reference_image,
        }

    # Diccionario para panel administrativo con campos extra.
    def to_admin_dict(self):
        # El panel admin necesita ambas imagenes: la del pedido y la referencia manual.
        customer_name = self.customer.full_name if self.customer else (self.full_name or "Cliente sin nombre")
        return {
            "id": self.id,
            "id_orden": self.id_orden,
            "wa_id": self.wa_id,
            "cliente": customer_name,
            "producto": " / ".join(
                value for value in [self.product_type, self.product_name] if value
            ) or "Producto personalizado",
            "product_type": self.product_type,
            "product_name": self.product_name,
            "colors": self.colors,
            "fecha": self.date or (self.created_at.strftime("%Y-%m-%d") if self.created_at else ""),
            "fecha_hora": self.created_at.strftime("%d/%m/%Y %H:%M") if self.created_at else "",
            "date": self.date,
            "status": self.status,
            "cotizacion_min": self.quote_min,
            "cotizacion_max": self.quote_max,
            "quote_min": self.quote_min,
            "quote_max": self.quote_max,
            "anticipo": self.advance_payment,
            "advance_payment": self.advance_payment,
            "delivery": self.delivery,
            "deadline": self.deadline,
            "assigned_to": self.assigned_to,
            "description": self.description,
            "length_cm": self.length_cm,
            "width_cm": self.width_cm,
            "full_name": self.full_name,
            "product_image": self.product_image,
            "reference_image": self.reference_image,
            "payment_proof": self.payment_proof,
            "weaver": self.assigned_to or "Sin asignar",
            "assigned": bool(self.assigned_to),
        }
