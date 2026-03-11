from datetime import datetime, timedelta
import math

# ---------------- CONFIG ----------------

BUFFER_DIAS = 1

# Velocidad estimada por tipo (cm² por día)
VELOCIDAD = {
    "llavero": 20,      # 20 cm² por día
    "amigurumi": 15,    # 15 cm² por día
    "prenda": 10        # 10 cm² por día
}

# ---------------- TEJEDORES ----------------

def crear_tejedores(n):
    return [
        {
            "nombre": f"Tejedor_{i+1}",
            "dias_ocupados": 0
        }
        for i in range(n)
    ]

# ---------------- FUNCIONES ----------------

def calcular_dias_produccion(product_type, length_cm, width_cm):
    area = length_cm * width_cm

    velocidad = VELOCIDAD.get(product_type.lower(), 15)

    dias = math.ceil(area / velocidad)

    return max(dias, 1)  # mínimo 1 día


def proximo_sabado(fecha):
    dias_hasta_sabado = (5 - fecha.weekday()) % 7
    if dias_hasta_sabado == 0:
        dias_hasta_sabado = 7
    return fecha + timedelta(days=dias_hasta_sabado)


def asignar_pedido(pedido, tejedores):

    fecha_pedido = datetime.strptime(pedido["date"], "%d/%m/%Y %H:%M")

    dias_produccion = calcular_dias_produccion(
        pedido["product_type"],
        pedido["length_cm"],
        pedido["width_cm"]
    )

    while True:

        fecha_transporte = proximo_sabado(fecha_pedido)

        # Elegir tejedor con menor carga
        tejedor = min(tejedores, key=lambda t: t["dias_ocupados"])

        # Calcular cuándo realmente podría empezar
        fecha_inicio_real = fecha_pedido + timedelta(days=tejedor["dias_ocupados"])

        fecha_fin_real = fecha_inicio_real + timedelta(days=dias_produccion)

        fecha_limite = fecha_transporte - timedelta(days=BUFFER_DIAS)

        if fecha_fin_real <= fecha_limite:

            tejedor["dias_ocupados"] += dias_produccion

            print("-------------------------------------------------")
            print(f"Pedido para: {pedido['full_name']}")
            print(f"Producto: {pedido['product_name']}")
            print(f"Asignado a: {tejedor['nombre']}")
            print(f"Días estimados de producción: {dias_produccion}")
            print(f"El pedido debe estar listo más tardar el día {fecha_limite.date()}")
            print(f"Se recoge el sábado {fecha_transporte.date()}")
            print("-------------------------------------------------")

            return

        # Si no alcanza, mover a siguiente sábado
        fecha_pedido = fecha_transporte + timedelta(days=1)


# ---------------- EJEMPLO REAL ----------------

pedido_ejemplo = {
    "date": "26/02/2026 17:10",
    "wa_id": "573107298010",
    "product_type": "Llavero",
    "product_name": "Llavero gato",
    "colors": "Rojo, negro",
    "length_cm": 4,
    "width_cm": 3,
    "description": "Que sea lindo",
    "full_name": "Kelly Cervantes"
}

tejedores = crear_tejedores(3)

asignar_pedido(pedido_ejemplo, tejedores)