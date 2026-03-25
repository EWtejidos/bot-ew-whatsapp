from datetime import datetime

from app import db
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    wa_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    orders = db.relationship("Order", back_populates="customer", lazy=True)

    def to_base_dict(self):
        latest_order = (
            max(self.orders, key=lambda order: order.created_at)
            if self.orders
            else None
        )
        detail = "Sin ordenes registradas todavia"
        if latest_order:
            detail = (
                f"Ultima orden {latest_order.order_code} en estado "
                f"{latest_order.status.replace('_', ' ')}"
            )

        return {
            "id": self.id,
            "wa_id": self.wa_id,
            "nombre": self.full_name,
            "estado": latest_order.status if latest_order else "sin-ordenes",
            "detalle": detail,
        }


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    payment_received_at = db.Column(db.DateTime, nullable=True)
    wa_id = db.Column(db.String(32), nullable=False, index=True)
    product_type = db.Column(db.String(100), nullable=True)
    product_name = db.Column(db.String(150), nullable=True)
    colors = db.Column(db.String(255), nullable=True)
    length_cm = db.Column(db.String(32), nullable=True)
    width_cm = db.Column(db.String(32), nullable=True)
    description = db.Column(db.Text, nullable=True)
    full_name = db.Column(db.String(150), nullable=True)
    delivery = db.Column(db.String(255), nullable=True)
    product_image = db.Column(db.String(255), nullable=True)
    payment_proof = db.Column(db.String(255), nullable=True)
    quote_min = db.Column(db.Integer, nullable=True)
    quote_max = db.Column(db.Integer, nullable=True)
    advance_payment = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="cotizacion", index=True)
    customer = db.relationship("Customer", back_populates="orders")

    def to_dashboard_dict(self):
        customer_name = self.customer.full_name if self.customer else (self.full_name or "Cliente sin nombre")
        return {
            "id": self.id,
            "order_code": self.order_code,
            "wa_id": self.wa_id,
            "cliente": customer_name,
            "producto": " / ".join(
                value for value in [self.product_type, self.product_name] if value
            ),
            "fecha": self.created_at.strftime("%d/%m/%Y %H:%M") if self.created_at else "",
            "status": self.status,
            "cotizacion_min": self.quote_min,
            "cotizacion_max": self.quote_max,
            "anticipo": self.advance_payment,
            "delivery": self.delivery,
            "description": self.description,
        }

    def to_admin_dict(self):
        customer_name = self.customer.full_name if self.customer else (self.full_name or "Cliente sin nombre")
        return {
            "id": self.id,
            "order_code": self.order_code,
            "wa_id": self.wa_id,
            "cliente": customer_name,
            "producto": " / ".join(
                value for value in [self.product_type, self.product_name] if value
            ) or "Producto personalizado",
            "fecha": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
            "fecha_hora": self.created_at.strftime("%d/%m/%Y %H:%M") if self.created_at else "",
            "status": self.status,
            "cotizacion_min": self.quote_min,
            "cotizacion_max": self.quote_max,
            "anticipo": self.advance_payment,
            "delivery": self.delivery,
            "description": self.description,
            "product_image": self.product_image,
            "payment_proof": self.payment_proof,
            "weaver": "Sin asignar",
            "assigned": False,
        }
