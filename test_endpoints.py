"""
Script de prueba para validar los endpoints del backend.
Ejecutar con: python test_endpoints.py

Nota: Requiere que la app esté corriendo localmente o en PythonAnywhere.
"""

import requests
import json
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:5000"  # Cambiar a URL de PythonAnywhere si es necesario
# BASE_URL = "https://usuario.pythonanywhere.com"  # Para PythonAnywhere

# Credenciales de prueba (asegúrate de que exista un usuario con estos datos)
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"

# Sesión con autenticación
session = requests.Session()

def login():
    """Autentica el usuario de prueba"""
    print("\n🔐 Autenticando...")
    
    # Nota: Ajusta la ruta de login según tu aplicación
    # Si usas Flask-Login, probablemente sea POST /login
    response = session.post(
        f"{BASE_URL}/login",
        data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        allow_redirects=True
    )
    
    if response.status_code in [200, 302]:
        print("✅ Autenticación exitosa")
        return True
    else:
        print(f"❌ Error de autenticación: {response.status_code}")
        print(response.text[:500])
        return False

def test_get_orders():
    """Prueba GET /api/admin/orders"""
    print("\n📋 Probando GET /api/admin/orders...")
    
    response = session.get(f"{BASE_URL}/api/admin/orders")
    
    if response.status_code == 200:
        orders = response.json()
        print(f"✅ Órdenes obtenidas: {len(orders)} órdenes")
        
        if orders:
            first_order = orders[0]
            print(f"   - Primera orden: ID={first_order.get('id')}, id_orden={first_order.get('id_orden')}")
            print(f"   - Campos disponibles: {list(first_order.keys())}")
            
            # Verificar que no haya order_code
            if "order_code" in first_order:
                print("   ⚠️ ADVERTENCIA: Aún contiene 'order_code' (debería estar eliminado)")
            
            return orders
        else:
            print("⚠️ No hay órdenes disponibles")
            return []
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text[:500])
        return None

def test_update_order(order_id):
    """Prueba PUT /api/admin/orders/{id}"""
    print(f"\n✏️ Probando PUT /api/admin/orders/{order_id}...")
    
    update_data = {
        "product_name": "Producto Actualizado Test",
        "colors": "Rojo, Azul",
        "description": "Descripción actualizada por test",
        "quote_max": 50000
    }
    
    response = session.put(
        f"{BASE_URL}/api/admin/orders/{order_id}",
        json=update_data,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Orden actualizada: {result.get('status')}")
        order = result.get("order", {})
        print(f"   - product_name: {order.get('product_name')}")
        print(f"   - colors: {order.get('colors')}")
        print(f"   - quote_max: {order.get('quote_max')}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text[:500])
        return False

def test_approve_anticipo(order_id):
    """Prueba POST /api/admin/orders/{id}/approve-anticipo"""
    print(f"\n✅ Probando POST /api/admin/orders/{order_id}/approve-anticipo...")
    
    response = session.post(
        f"{BASE_URL}/api/admin/orders/{order_id}/approve-anticipo",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        order = result.get("order", {})
        print(f"✅ Anticipo aprobado")
        print(f"   - Estado: {order.get('status')}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text[:500])
        return False

def test_delete_order(order_id):
    """Prueba DELETE /api/admin/orders/{id}"""
    print(f"\n🗑️ Probando DELETE /api/admin/orders/{order_id}...")
    
    response = session.delete(
        f"{BASE_URL}/api/admin/orders/{order_id}",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Orden eliminada: {result.get('status')}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text[:500])
        return False

def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 60)
    print("🧪 PRUEBA DE ENDPOINTS DEL BACKEND")
    print("=" * 60)
    
    # Autenticarse
    if not login():
        print("\n❌ No fue posible autenticarse. Abortando pruebas.")
        return
    
    # Obtener órdenes
    orders = test_get_orders()
    if not orders:
        print("\n❌ No hay órdenes para probar. Abortando.")
        return
    
    # Usar la primera orden para las pruebas
    test_order_id = orders[0]["id"]
    print(f"\n📌 Usando orden ID={test_order_id} para pruebas subsecuentes")
    
    # Probar actualización
    test_update_order(test_order_id)
    
    # Probar aprobación de anticipo
    test_approve_anticipo(test_order_id)
    
    # Probar eliminación (comentado para no perder datos en test)
    # test_delete_order(test_order_id)
    # print("\n⚠️ DELETE NO FUE EJECUTADO (comentado para preservar datos de test)")
    
    print("\n" + "=" * 60)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 60)

if __name__ == "__main__":
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print(f"\n❌ No se pudo conectar a {BASE_URL}")
        print("Asegúrate de que:")
        print("1. La app está corriendo localmente (python run.py)")
        print("2. O cambiar BASE_URL a tu instancia de PythonAnywhere")
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
