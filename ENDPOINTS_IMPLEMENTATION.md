# 🚀 Implementación de Endpoints Backend

## ✅ Cambios Realizados

### 1. **Modelo de Datos (models.py)**
- ✅ Eliminado field `order_code` del modelo `Order`
- ✅ Actualizado método `to_admin_dict()` para:
  - Remover referencias a `order_code`
  - Incluir todos los campos editables: product_type, product_name, colors, length_cm, width_cm, description, full_name, delivery, date, deadline, quote_min, quote_max, advance_payment
  - Exponer aliases para compatibilidad: cotizacion_min → quote_min, etc.

- ✅ Actualizado método `to_dashboard_dict()` para remover `order_code`

### 2. **Endpoints (views.py)**

#### ✅ NUEVO: PUT `/api/admin/orders/{id}`
**Propósito**: Actualizar una orden existente
**Método**: PUT
**Autenticación**: Requerida (login_required)
**Parámetros**: ID numérico de la orden en la URL

**Body JSON**:
```json
{
  "product_type": "Prenda de vestir",
  "product_name": "Camiseta",
  "colors": "Rojo, Azul",
  "length_cm": "50",
  "width_cm": "40",
  "description": "Detalle personalizado",
  "full_name": "Juan Pérez",
  "delivery": "Punto de recogida",
  "date": "06/04/2026",
  "deadline": "10/04/2026",
  "quote_min": 40000,
  "quote_max": 50000,
  "advance_payment": 15000
}
```

**Respuesta exitosa (200)**:
```json
{
  "status": "success",
  "order": {
    "id": 123,
    "id_orden": "ID-A1B2C3D4",
    "product_name": "Camiseta",
    ...
  }
}
```

---

#### ✅ NUEVO: DELETE `/api/admin/orders/{id}`
**Propósito**: Eliminar una orden de la base de datos
**Método**: DELETE
**Autenticación**: Requerida (login_required)
**Parámetros**: ID numérico de la orden en la URL

**Respuesta exitosa (200)**:
```json
{
  "status": "success",
  "message": "Orden eliminada correctamente."
}
```

---

#### ✅ MODIFICADO: POST `/api/admin/orders/{id}/approve-anticipo`
**Cambio**: Ahora NO valida que exista referencia. El anticipo se aprueba directamente.
- Antes: Requería `payment_proof` Y `reference_image`
- Ahora: Solo cambia estado a "comprado"

---

#### ✅ GET `/api/admin/orders`
**Cambio**: Ahora retorna los campos completos sin `order_code`
- Todos los campos editables están disponibles
- Compatible con productosadmin.js
- Compatible con anticiposadmin.js

---

## 🧪 Validación de Endpoints

### Opción 1: Script de Prueba Automático
```bash
cd whatsapp-bot-python
python test_endpoints.py
```

**Requisitos**:
- Aplicación corriendo en localhost:5000
- Usuario admin con credenciales configuradas en test_endpoints.py
- Al menos una orden en la base de datos

**Qué prueba**:
1. ✅ Autenticación
2. ✅ GET /api/admin/orders
3. ✅ PUT /api/admin/orders/{id} (actualización)
4. ✅ POST /api/admin/orders/{id}/approve-anticipo (aprobación)
5. (DELETE comentado para preservar datos)

---

### Opción 2: Prueba Manual con cURL

**1. Obtener órdenes**:
```bash
curl -X GET http://localhost:5000/api/admin/orders \
  -H "Cookie: session=TU_COOKIE_DE_SESION"
```

**2. Actualizar orden**:
```bash
curl -X PUT http://localhost:5000/api/admin/orders/123 \
  -H "Content-Type: application/json" \
  -H "Cookie: session=TU_COOKIE_DE_SESION" \
  -d '{
    "product_name": "Nuevo Nombre",
    "colors": "Verde, Amarillo",
    "quote_max": 60000
  }'
```

**3. Eliminar orden**:
```bash
curl -X DELETE http://localhost:5000/api/admin/orders/123 \
  -H "Cookie: session=TU_COOKIE_DE_SESION"
```

---

### Opción 3: Prueba Manual con Postman
1. Importar colección o crear requests manualmente
2. Usar GET /api/admin/orders para obtener ID de orden
3. Crear PUT request a /api/admin/orders/{id}
4. Enviar JSON con campos a actualizar
5. Verificar respuesta 200 con orden actualizada

---

## 📱 Integración con Frontend

### Panel de Anticipos (anticiposadmin.js)
- Usa: `PUT /api/admin/orders/{id}` para editar
- Usa: `DELETE /api/admin/orders/{id}` para eliminar
- Usa: `GET /api/admin/orders` para cargar datos
- ✅ **Estado**: Listo para funcionar

### Vista General (tableroadmin.js)
- Usa: `POST /api/admin/orders/{id}/approve-anticipo` para aprobar
- ✅ **Estado**: Funcionando (sin validación de referencia)

### Panel Órdenes (ordenesadmin.js)
- Usa: `GET /api/admin/orders` para cargar
- ✅ **Estado**: Listo para funcionar

### Productos Admin (productosadmin.js)
- Usa: `GET /api/admin/orders` para listar órdenes como productos
- ✅ **Estado**: Listo para funcionar (ahora con id_orden correctamente)

---

## 🌐 Funcionamiento en PythonAnywhere

Los endpoints funcionarán automáticamente una vez que hagas push a GitHub:

1. PythonAnywhere detectará los cambios
2. Recargarérá la aplicación
3. Los nuevos endpoints estarán disponibles en: `https://tuusuario.pythonanywhere.com/api/admin/orders/...`

**Cambios en URLs**:
- Local: `http://localhost:5000/api/admin/orders`
- PythonAnywhere: `https://tuusuario.pythonanywhere.com/api/admin/orders`

---

## ⚠️ Notas Importantes

### Identidad de Órdenes
- **Frontend usa**: ID numérico (`order.id`)
- **Backend almacena**: `id_orden` (ID-XXXXXX)
- **Ambos están disponibles en respuestas JSON**

### Campos Editables
Desde el frontend puedes actualizar:
- `product_type` - Tipo de producto
- `product_name` - Nombre específico
- `colors` - Colores solicitados
- `length_cm` - Largo en centímetros
- `width_cm` - Ancho en centímetros
- `description` - Detalles adicionales
- `full_name` - Nombre del cliente
- `delivery` - Lugar de entrega
- `date` - Fecha de solicitud
- `deadline` - Fecha límite de entrega
- `quote_min` - Cotización mínima
- `quote_max` - Cotización máxima
- `advance_payment` - Anticipo requerido

### Campos NO editables (de lectura)
- `id` - ID interno
- `id_orden` - ID único de negocio
- `wa_id` - Número de WhatsApp
- `status` - Estado (se cambia con endpoints específicos)
- `created_at` - Fecha de creación
- `payment_proof` - Comprobante de pago (se sube por endpoint específico)

---

## 🔍 Verificación de Funcionamiento

### Checklist Post-Deploy
- [ ] GET /api/admin/orders retorna órdenes sin `order_code`
- [ ] PUT /api/admin/orders/{id} actualiza datos correctamente
- [ ] DELETE /api/admin/orders/{id} elimina la orden
- [ ] Cambios se reflejan al recargar (persistencia en BD)
- [ ] Frontend anticipo edita sin errores
- [ ] Frontend puede eliminar órdenes
- [ ] Vista general carga correctamente

---

## 🐛 Troubleshooting

### Error: "No se encontro la orden solicitada"
- Verificar que el ID_orden existe
- Usar GET /api/admin/orders para obtener IDs válidos

### Error: "AttributeError: 'Order' object has no attribute 'order_code'"
- ✅ **RESUELTO**: Removido de modelos.py
- Si persiste en PythonAnywhere: Hacer hard refresh (Ctrl+Shift+R)

### Error: "Nada se actualiza"
- Verificar que el JSON está bien formado
- Content-Type debe ser "application/json"
- Usuario debe estar logueado (@login_required)

---

## 📝 Historial de Cambios

| Fecha | Cambio | Archivo |
|-------|--------|---------|
| 06/04/2026 | Eliminado order_code | models.py |
| 06/04/2026 | Agregado PUT endpoint | views.py |
| 06/04/2026 | Agregado DELETE endpoint | views.py |
| 06/04/2026 | Removida validación rigurosa en approve | views.py |
| 06/04/2026 | Creado script de test | test_endpoints.py |

