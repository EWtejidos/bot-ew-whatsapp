import csv
import os

# ---- CONFIGURACIÓN DE RUTAS ----
# Usamos la ruta absoluta para que PythonAnywhere no se pierda
BASE_DIR = "/home/ewtejidos/bot/bot-ew-whatsapp"
# Por defecto buscamos el historial en la carpeta 'ordenes'
DEFAULT_CSV_PATH = os.path.join(BASE_DIR, "ordenes", "precios_referencias.csv")

PRECIOS_MINIMOS = {
    "Prenda de vestir": 45000,
    "Vestido de baño": 40000,
    "Amigurumi o peluche": 20000,
    "Llavero o flores": 6000,
}

MULTIPLICADORES = {
    "Prenda de vestir": 15,
    "Vestido de baño": 18,
    "Amigurumi o peluche": 12,
    "Llavero o flores": 8,
}

def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _cargar_historico_csv(archivo_historico):
    # Si no pasan ruta, usamos la de por defecto
    ruta = archivo_historico or DEFAULT_CSV_PATH

    if not os.path.isfile(ruta):
        return []

    try:
        with open(ruta, mode="r", newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))
    except Exception:
        return []

def _buscar_similar(rows, tipo, largo, ancho):
    candidatos = [row for row in rows if row.get("product_type") == tipo]
    if not candidatos:
        return None

    def distancia(row):
        # Comparamos qué tan cerca están las medidas
        d_largo = abs(_to_float(row.get("length_cm")) - largo)
        d_ancho = abs(_to_float(row.get("width_cm")) - ancho)
        return d_largo + d_ancho

    return min(candidatos, key=distancia)

def calcular_precio(tipo, largo, ancho, archivo_historico=None):
    if tipo not in PRECIOS_MINIMOS:
        return { "error": "Tipo no válido" }

    largo = _to_float(largo)
    ancho = _to_float(ancho)

    precio_minimo_tipo = PRECIOS_MINIMOS[tipo]
    multiplicador = MULTIPLICADORES[tipo]

    # El incremento depende del área del tejido
    incremento = (largo * ancho) * multiplicador

    historico = _cargar_historico_csv(archivo_historico)
    producto_similar = _buscar_similar(historico, tipo, largo, ancho)

    precio_base = precio_minimo_tipo
    fuente = "Cálculo base (sin histórico)"

    if producto_similar:
        # IMPORTANTE: Asegúrate que en tu CSV la columna se llame 'precio_final'
        precio_historico = _to_float(producto_similar.get("precio_final"))
        if precio_historico > 0:
            precio_base = max(precio_minimo_tipo, precio_historico)
            fuente = "Basado en historial"

    precio_min = int(round(precio_base))
    precio_max = int(round(precio_base + incremento))
    pago_30 = int(round(precio_min * 0.30))

    return {
        "tipo": tipo,
        "fuente": fuente,
        "precio_min": precio_min,
        "precio_max": precio_max,
        "pago_30": pago_30,
    }
