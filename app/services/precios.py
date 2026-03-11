import csv
import os

# ---- PRECIOS MINIMOS POR TIPO ----
PRECIOS_MINIMOS = {
    "Prenda de vestir": 45000,
    "Vestido de baño": 40000,
    "Amigurumi o peluche": 20000,
    "Llavero o flores": 6000,
}

# Multiplicadores por tipo
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


def _buscar_similar(rows, tipo, largo, ancho):
    candidatos = [row for row in rows if row.get("product_type") == tipo]
    if not candidatos:
        return None

    def distancia(row):
        return abs(_to_float(row.get("length_cm")) - largo) + abs(
            _to_float(row.get("width_cm")) - ancho
        )

    return min(candidatos, key=distancia)


def _cargar_historico_csv(archivo_historico):
    if not archivo_historico or not os.path.isfile(archivo_historico):
        return []

    with open(archivo_historico, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


def calcular_precio(tipo, largo, ancho, archivo_historico=None):
    if tipo not in PRECIOS_MINIMOS:
        raise ValueError("Tipo no valido")

    largo = _to_float(largo)
    ancho = _to_float(ancho)

    precio_minimo_tipo = PRECIOS_MINIMOS[tipo]
    multiplicador = MULTIPLICADORES[tipo]
    incremento = largo * ancho * multiplicador

    historico = _cargar_historico_csv(archivo_historico)
    producto_similar = _buscar_similar(historico, tipo, largo, ancho)

    precio_base = precio_minimo_tipo
    fuente = "Solo minimo por tipo (sin historico)"

    if producto_similar:
        precio_historico = _to_float(producto_similar.get("precio_final"))
        precio_base = max(precio_minimo_tipo, precio_historico)
        fuente = "Historico + minimo por tipo"

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
