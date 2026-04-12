// Obtiene el contenedor principal del módulo donde se renderiza todo
const anticiposContainer = document.getElementById("moduleContent");

// Elemento donde se muestran mensajes de estado al usuario
const anticiposStatus = document.getElementById("statusBadge");

// Crea el contenedor para modales (ventanas emergentes)
const modalHost = createModalHost();

// Array principal donde se almacenan los anticipos
let anticipos = [];

// Controla si se muestra ayuda para carga masiva
let showBulkUploadHelp = false;

// Guarda IDs de referencias que se están subiendo (evita duplicaciones)
const uploadingReferenceIds = new Set();

// Plantilla de mensaje para rechazar anticipos
const ANTICIPO_REJECT_TEMPLATE = "Estimado cliente el anticipo no concuerda con lo recibido. Si desea subirlo nuevamente escriba anticipo+{orderId}.";

// Guarda la imagen actualmente en vista previa
let activePreview = null;

// Guarda el ID de la orden en el modal de rechazo
let rejectModalOrderId = null;

// Guarda la orden que se está editando
let editModalOrder = null;

// Renderiza la interfaz inicial
renderAnticipos();

// Carga los datos de anticipos (probablemente desde backend)
loadAnticipos();


// Evento cuando cambia algo dentro del contenedor (ej: input file)
anticiposContainer.addEventListener("change", (event) => {

  // Busca si el evento ocurrió en un input de referencia
  const input = event.target.closest("[data-reference-input]");

  // Si no es el input correcto o no hay archivos, no hace nada
  if (!input || !input.files || !input.files.length) {
    return;
  }

  // Llama función para subir una referencia (imagen)
  handleSingleReferenceUpload(input.dataset.id, input.files[0]);

  // Limpia el input para permitir volver a subir el mismo archivo
  input.value = "";
});


// Evento de click dentro del contenedor principal
anticiposContainer.addEventListener("click", (event) => {

  // Detecta botones con acciones
  const button = event.target.closest("[data-action]");

  // Detecta si se hizo click en una imagen de preview
  const previewImage = event.target.closest("[data-preview-image]");

  // Si se hizo click en imagen, abre la vista previa
  if (previewImage) {
    openImagePreview(previewImage.dataset.previewImage, previewImage.alt || "Vista previa");
    return;
  }

  // Si no hay botón, no hace nada
  if (!button) {
    return;
  }

  // Obtiene el ID del botón
  const id = button.dataset.id;

  // Busca el anticipo correspondiente
  const item = anticipos.find((anticipo) => String(anticipo.id) === id);

  // Si no lo encuentra, muestra error
  if (!item) {
    adminCommon.setStatus(anticiposStatus, "No se encontro la orden seleccionada.");
    return;
  }

  // Acción: subir referencia
  if (button.dataset.action === "upload-reference") {
    const input = document.getElementById(`reference-input-${item.id}`);
    if (input) {
      input.click(); // Abre selector de archivo
    }
    return;
  }

  // Acción: aprobar
  if (button.dataset.action === "approve") {
    handleApprove(item);
  }

  // Acción: editar
  if (button.dataset.action === "edit") {
    openEditModal(item);
  }

  // Acción: rechazar
  if (button.dataset.action === "reject") {
    openRejectModal(item);
  }

  // Acción: eliminar referencia
  if (button.dataset.action === "delete-reference") {
    handleDeleteReference(item);
  }
});


// Evento global del documento (manejo de modales y acciones generales)
document.addEventListener("click", (event) => {

  // Detecta acciones de cierre o copiar en modales
  const previewClose = event.target.closest("[data-preview-close]");
  const rejectClose = event.target.closest("[data-reject-close]");
  const rejectCopy = event.target.closest("[data-reject-copy]");

  // Cierra vista previa de imagen
  if (previewClose || event.target.classList.contains("image-preview-overlay")) {
    closeImagePreview();
    return;
  }

  // Cierra modal de rechazo
  if (rejectClose || event.target.classList.contains("reject-modal-overlay")) {
    closeRejectModal();
    return;
  }

  // Copia el mensaje de rechazo
  if (rejectCopy) {
    handleRejectCopy();
    return;
  }

  // Detecta cierre o envío del modal de edición
  const editClose = event.target.closest("[data-edit-close]");
  const editForm = event.target.closest("#editOrderForm");

  // Cierra modal de edición
  if (editClose || event.target.classList.contains("edit-modal-overlay")) {
    closeEditModal();
    return;
  }

  // Maneja el submit del formulario de edición
  if (editForm && event.type === "submit") {
    event.preventDefault(); // Evita recargar la página
    handleEditSave(); // Guarda cambios
    return;
  }

  // Detecta botones del header
  const button = event.target.closest("[data-header-action]");
  if (!button) {
    return;
  }

  // Acción: verificación automática (placeholder futuro)
  if (button.dataset.headerAction === "auto-check") {
    adminCommon.setStatus(anticiposStatus, "Verificacion automatica lista para conectarse con tu flujo bancario.");
  }

  // Acción: mostrar ayuda para subir comprobantes
  if (button.dataset.headerAction === "upload-proof") {
    showBulkUploadHelp = true; // Activa ayuda
    renderAnticipos(); // Re-renderiza la UI
    adminCommon.setStatus(anticiposStatus, "Usa el boton Subir de cada fila en la columna Referencia para escoger una imagen desde tu PC.");
  }
})
// Detecta si se hizo click en un botón con acción global (como eliminar o exportar)
const globalButton = event.target.closest("[data-global-action]");

// Si existe ese botón
if (globalButton) {

  // Si la acción es eliminar seleccionados
  if (globalButton.dataset.globalAction === "delete-selected") {
    handleDeleteSelected(); // Llama función que elimina múltiples elementos
  }

  // Si la acción es exportar a CSV
  if (globalButton.dataset.globalAction === "export-csv") {
    handleExportCSV(); // Llama función que exporta los datos
  }
}

// Detecta si se hizo click en el checkbox "seleccionar todo"
const selectAll = event.target.closest("#select-all");

if (selectAll) {

  // Busca todos los checkboxes de filas (similar a recorrer una lista en Python)
  const checkboxes = document.querySelectorAll(".row-select");

  // Recorre cada checkbox (como un for en Python)
  checkboxes.forEach(cb => 
    cb.checked = selectAll.checked // Marca o desmarca todos según el principal
  );
}
});


// ================= FUNCIÓN ASÍNCRONA (como async en Python) =================
async function loadAnticipos() {

  // Muestra mensaje de estado (feedback al usuario)
  adminCommon.setStatus(anticiposStatus, "Cargando anticipos reales...");

  try {

    // Hace una petición HTTP (similar a requests.get en Python)
    const response = await fetch("/api/admin/orders", {
      headers: {
        Accept: "application/json" // Indica que espera JSON
      }
    });

    // Si la respuesta no es exitosa, lanza error
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    // Convierte la respuesta a JSON (como response.json() en Python)
    const orders = await response.json();

    // Procesa los datos:
    anticipos = orders

      // Filtra solo los que cumplen condiciones (como filter en Python)
      .filter((order) => 
        Boolean(order.payment_proof) || 
        ["comprado", "anticipo_pendiente", "rechazado"].includes(order.status)
      )

      // Transforma cada elemento (como map en Python)
      .map(mapAnticipoForView);

    // Renderiza los datos en pantalla
    renderAnticipos();

    // Muestra mensaje con cantidad cargada
    adminCommon.setStatus(
      anticiposStatus, 
      `${anticipos.length} anticipos cargados desde la base de datos.`
    );

  } catch (error) {

    // Si ocurre un error lo muestra en consola
    console.error("No fue posible cargar los anticipos", error);

    // Limpia los datos
    anticipos = [];

    // Renderiza vacío
    renderAnticipos();

    // Muestra error al usuario
    adminCommon.setStatus(
      anticiposStatus, 
      "No fue posible cargar los anticipos desde el backend."
    );
  }
}


// ================= TRANSFORMA DATOS PARA LA VISTA =================
function mapAnticipoForView(order) {

  // Normaliza la ruta de la imagen de referencia
  const referenceImage = normalizeImagePath(order.reference_image, "");

  // Determina si está aprobado
  const isApproved = order.status === "comprado";

  // Determina si está rechazado
  const isRejected = order.status === "rechazado";

  // Similaridad (si está aprobado = 100, si no = 0)
  const similarity = isApproved ? 100 : 0;

  // Estado final simplificado
  const status = isApproved 
    ? "aprobado" 
    : (isRejected ? "rechazado" : "pendiente");

  // Retorna un objeto nuevo (como crear un dict en Python)
  return {
    id: order.id,

    // Usa id_orden si existe, si no crea uno con #
    businessOrderId: order.id_orden || `#${order.id}`,

    orderCode: order.id_orden || `#${order.id}`,

    waId: order.wa_id || "",

    cliente: order.cliente || "Cliente sin nombre",

    // Imagen del comprobante de pago
    whatsappProof: normalizeImagePath(order.payment_proof),

    referenceImage,

    similarity,

    status,

    // Formatea el dinero (como usar format en Python)
    total: formatCurrency(order.anticipo),

    referencia: order.producto || "Pedido personalizado",

    // Datos adicionales del pedido
    id_orden: order.id_orden,
    product_type: order.product_type,
    product_name: order.product_name,
    colors: order.colors,
    length_cm: order.length_cm,
    width_cm: order.width_cm,
    description: order.description,
    full_name: order.full_name,
    delivery: order.delivery,
    date: order.date,
    deadline: order.deadline,
    quote_min: order.quote_min,
    quote_max: order.quote_max
  };
}


// ================= NORMALIZA RUTAS DE IMÁGENES =================
function normalizeImagePath(path, fallback = "images/products/top.jpg") {

  // Si no hay ruta, devuelve una por defecto
  if (!path) {
    return fallback;
  }

  // Reemplaza "\" por "/" (compatibilidad de rutas)
  // Elimina "./" del inicio
  return path
    .replace(/\\/g, "/")
    .replace(/^\.\//, "");
}


// ================= FORMATEA VALORES MONETARIOS =================
function formatCurrency(value) {

  // Si el valor no es válido
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "Sin valor";
  }

  // Formatea como moneda colombiana (COP)
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0
  }).format(Number(value));
}

// Función que se encarga de construir y mostrar la tabla de anticipos en pantalla
function renderAnticipos() {

  // Construye las filas de la tabla recorriendo el array "anticipos"
  // (esto es equivalente a hacer un "for" o un "list comprehension" en Python)
  const rowsMarkup = anticipos
    .map(
      (anticipo) => `
        <tr>
          <!-- Checkbox para seleccionar la fila -->
          <td><input type="checkbox" class="row-select" data-id="${anticipo.id}"></td>

          <!-- ID de la orden -->
          <td class="verification-order-id">${anticipo.orderCode}</td>

          <!-- Nombre del cliente -->
          <td>${anticipo.cliente}</td>

          <!-- Imagen del comprobante del cliente -->
          <td>
            <img class="verification-proof is-clickable" 
                 src="${anticipo.whatsappProof}" 
                 alt="Comprobante cliente ${anticipo.orderCode}" 
                 data-preview-image="${anticipo.whatsappProof}">
          </td>

          <!-- Celda de referencia (otra función la construye) -->
          <td>
            ${renderReferenceCell(anticipo)}
          </td>

          <!-- Porcentaje de similitud -->
          <td class="verification-similarity">${anticipo.similarity}%</td>

          <!-- Estado (aprobado, pendiente, rechazado) -->
          <td>
            <span class="status-badge ${adminCommon.normalizeStatusClass(anticipo.status)}">
              ${adminCommon.formatStatus(anticipo.status)}
            </span>
          </td>

          <!-- Botones de acciones -->
          <td>
            <div class="verification-actions">

              <!-- Botón para aprobar -->
              <button class="button primary" type="button" data-action="approve" data-id="${anticipo.id}">
                Aprobar
              </button>

              <!-- Botón para rechazar -->
              <button class="button danger" type="button" data-action="reject" data-id="${anticipo.id}">
                Rechazar
              </button>

            </div>
          </td>
        </tr>
      `
    )
    // Une todas las filas en un solo string (como "".join() en Python)
    .join("");

  // Inserta todo el HTML dentro del contenedor principal
  anticiposContainer.innerHTML = `
    <article class="verification-card">

      <!-- Encabezado del bloque -->
      <div class="block-header">
        <div>
          <h4>Tabla de verificacion visual</h4>
          <span class="block-copy">
            Comprobantes del bot y datos de la orden reunidos en una sola vista.
          </span>
        </div>

        <!-- Cuenta cuántos están pendientes (como len(filter(...)) en Python) -->
        <span class="section-badge">
          Pendientes: ${anticipos.filter((item) => item.status === "pendiente").length}
        </span>
      </div>

      <!-- Muestra ayuda si está activada -->
      ${showBulkUploadHelp ? `
        <div class="reference-upload-banner">
          <strong>Subida de referencias desde PC</strong>
          <p>
            Cada fila tiene su propio boton Subir. Haz clic en ese boton dentro de la columna Referencia,
            elige una imagen desde tu PC y la vista previa aparecera en esa misma celda.
          </p>
        </div>
      ` : ""}

      <!-- Contenedor de la tabla -->
      <div class="verification-table-wrap">

        <!-- Acciones globales -->
        <div class="global-actions">
          <button class="button danger" type="button" data-global-action="delete-selected">
            🗑 Eliminar
          </button>

          <button class="button secondary" type="button" data-global-action="export-csv">
            📄 Imprimir CSV
          </button>
        </div>

        <!-- Tabla -->
        <table class="verification-table">
          <thead>
            <tr>

              <!-- Checkbox para seleccionar todo -->
              <th><input type="checkbox" id="select-all"></th>

              <th>ID orden</th>
              <th>Cliente</th>
              <th>Comprobante cliente</th>
              <th>Referencia</th>
              <th>Similitud</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>

          <tbody>

            <!-- Si hay datos, muestra las filas -->
            ${rowsMarkup || `

              <!-- Si no hay datos, muestra mensaje -->
              <tr>
                <td colspan="7">
                  No hay anticipos registrados todavia.
                </td>
              </tr>

            `}
          </tbody>
        </table>
      </div>
    </article>
  `;

  // Renderiza modales flotantes (ventanas emergentes)
  renderFloatingModals();
}

// Función asíncrona que maneja la subida de una imagen de referencia para una orden
// (equivalente a una función async en Python usando await)
async function handleSingleReferenceUpload(orderId, file) {

  // Busca el anticipo correspondiente al orderId (como usar next(...) en Python)
  const anticipo = anticipos.find((item) => String(item.id) === String(orderId));

  // Si no encuentra el anticipo, muestra error y termina la función
  if (!anticipo) {
    adminCommon.setStatus(anticiposStatus, "No se encontro la fila para cargar la referencia.");
    return;
  }

  // Marca este orderId como "subiendo" (para control interno)
  uploadingReferenceIds.add(String(orderId));

  // Re-renderiza la UI para reflejar que está en proceso
  renderAnticipos();

  try {

    // Crea un objeto tipo formulario (como enviar archivos en requests en Python)
    const formData = new FormData();

    // Agrega el archivo con la clave "foto"
    formData.append("foto", file);

    // Hace una petición POST al backend para subir la imagen
    const response = await fetch(`/api/upload-reference/${orderId}`, {
      method: "POST",
      body: formData
    });

    // Si la respuesta no es exitosa
    if (!response.ok) {

      // Mensaje inicial con código HTTP
      let message = `HTTP ${response.status}`;

      try {

        // Intenta leer el error que venga del backend (JSON)
        const payload = await response.json();

        // Si el backend envía un error específico, lo usa
        if (payload.error) {
          message = payload.error;
        }

      } catch (parseError) {

        // Si no puede leer el JSON, muestra error en consola
        console.error("No fue posible leer el error de subida", parseError);
      }

      // Lanza error con el mensaje final
      throw new Error(message);
    }

    // Si todo salió bien, muestra mensaje de éxito
    adminCommon.setStatus(
      anticiposStatus, 
      `Referencia cargada para la orden ${anticipo.orderCode}. Recargando datos...`
    );

    // Vuelve a cargar los datos desde el backend (como volver a hacer un GET en Python)
    await loadAnticipos();

  } catch (error) {

    // Si ocurre un error, lo muestra en consola
    console.error("No fue posible subir la referencia", error);

    // Muestra error al usuario
    adminCommon.setStatus(
      anticiposStatus, 
      `No fue posible subir la referencia para la orden ${anticipo.orderCode}: ${error.message}`
    );

  } finally {

    // Este bloque siempre se ejecuta (como finally en Python)

    // Quita el ID del set de "subiendo"
    uploadingReferenceIds.delete(String(orderId));

    // Re-renderiza la UI para reflejar el estado final
    renderAnticipos();
  }
}


// ================= MODAL DE VISTA PREVIA DE IMAGEN =================
function renderImagePreviewModal() {

  // Si no hay imagen activa para mostrar, no renderiza nada
  if (!activePreview) {
    return "";
  }

  // Retorna el HTML del modal (ventana emergente)
  return `
    <div class="image-preview-overlay">

      <!-- Contenedor del modal -->
      <div class="image-preview-dialog" 
           role="dialog" 
           aria-modal="true" 
           aria-label="Vista ampliada de imagen">

        <!-- Botón para cerrar -->
        <button class="preview-close-button" 
                type="button" 
                data-preview-close 
                aria-label="Cerrar vista previa">
          ×
        </button>

        <!-- Imagen en tamaño completo -->
        <img class="image-preview-full" 
             src="${activePreview.src}" 
             alt="${activePreview.alt}">
      </div>
    </div>
  `;
}

// Función que renderiza todos los modales flotantes en pantalla
function renderFloatingModals() {

  // Inserta en el contenedor de modales (modalHost) la suma de:
  // - modal de vista previa de imagen
  // - modal de rechazo
  // - modal de edición
  // (esto es como concatenar strings en Python)
  modalHost.innerHTML = 
    renderImagePreviewModal() + 
    renderRejectModal() + 
    renderEditModal();
}


// ================= MODAL DE RECHAZO =================
function renderRejectModal() {

  // Si no hay un ID de orden seleccionado para rechazo, no muestra nada
  if (!rejectModalOrderId) {
    return "";
  }

  // Busca el anticipo correspondiente a ese ID
  // (equivalente a buscar en una lista en Python)
  const anticipo = anticipos.find(
    (item) => String(item.id) === String(rejectModalOrderId)
  );

  // Si no encuentra el anticipo, no renderiza nada
  if (!anticipo) {
    return "";
  }

  // Construye el mensaje de rechazo reemplazando {orderId}
  // (similar a usar .format() o f-string en Python)
  const message = ANTICIPO_REJECT_TEMPLATE.replace(
    "{orderId}", 
    anticipo.businessOrderId
  );

  // Retorna el HTML del modal
  return `
    <div class="reject-modal-overlay">

      <!-- Contenedor del modal -->
      <div class="reject-modal-card" 
           role="dialog" 
           aria-modal="true" 
           aria-label="Mensaje de rechazo de anticipo">

        <!-- Botón para cerrar el modal -->
        <button class="preview-close-button" 
                type="button" 
                data-reject-close 
                aria-label="Cerrar mensaje">
          ×
        </button>

        <!-- Título -->
        <h4>Rechazo de anticipo</h4>

        <!-- Información del cliente -->
        <p><strong>Cliente:</strong> ${anticipo.cliente}</p>

        <!-- Número de WhatsApp (si no existe muestra texto por defecto) -->
        <p><strong>Numero:</strong> ${anticipo.waId || "Sin numero registrado"}</p>

        <!-- Mensaje generado dinámicamente -->
        <p>${message}</p>

        <!-- Acciones del modal -->
        <div class="reject-modal-actions">

          <!-- Botón para copiar el mensaje -->
          <button class="button primary" 
                  type="button" 
                  data-reject-copy>
            Copiar
          </button>

        </div>
      </div>
    </div>
  `;
}
// ================= MODAL DE RECHAZO =================
function renderRejectModal() {

  // Si no hay un ID seleccionado para rechazar, no muestra nada
  if (!rejectModalOrderId) {
    return "";
  }

  // Busca el anticipo correspondiente al ID
  // (equivalente a buscar en una lista en Python)
  const anticipo = anticipos.find((item) => String(item.id) === String(rejectModalOrderId));

  // Si no encuentra el anticipo, no renderiza nada
  if (!anticipo) {
    return "";
  }

  // Construye el mensaje reemplazando {orderId} en el template
  // (similar a usar f-strings o .format() en Python)
  const message = ANTICIPO_REJECT_TEMPLATE.replace("{orderId}", anticipo.businessOrderId);

  // Retorna el HTML del modal de rechazo
  return `
    <div class="reject-modal-overlay">

      <!-- Contenedor del modal -->
      <div class="reject-modal-card" role="dialog" aria-modal="true" aria-label="Mensaje de rechazo de anticipo">

        <!-- Botón para cerrar el modal -->
        <button class="preview-close-button" type="button" data-reject-close aria-label="Cerrar mensaje">×</button>

        <!-- Título -->
        <h4>Rechazo de anticipo</h4>

        <!-- Información del cliente -->
        <p><strong>Cliente:</strong> ${anticipo.cliente}</p>

        <!-- Número de WhatsApp (si no existe muestra un texto por defecto) -->
        <p><strong>Numero:</strong> ${anticipo.waId || "Sin numero registrado"}</p>

        <!-- Mensaje dinámico generado -->
        <p>${message}</p>

        <!-- Acciones del modal -->
        <div class="reject-modal-actions">

          <!-- Botón para copiar el mensaje -->
          <button class="button primary" type="button" data-reject-copy>Copiar</button>

        </div>
      </div>
    </div>
  `;
}


// ================= MODAL DE EDICIÓN =================
function renderEditModal() {

  // Si no hay una orden seleccionada para editar, no muestra nada
  if (!editModalOrder) {
    return "";
  }

  // Retorna el HTML del modal de edición
  return `
    <div class="edit-modal-overlay">

      <!-- Contenedor del modal -->
      <div class="edit-modal-card" role="dialog" aria-modal="true" aria-label="Editar orden">

        <!-- Botón para cerrar -->
        <button class="preview-close-button" type="button" data-edit-close aria-label="Cerrar">×</button>

        <!-- Título con el código de la orden -->
        <h4>Editar Orden ${editModalOrder.orderCode}</h4>

        <!-- Formulario de edición -->
        <form id="editOrderForm">

          <!-- Campo: ID de la orden -->
          <div class="form-group">
            <label for="edit_id_orden">ID Orden</label>
            <input type="text" id="edit_id_orden" name="id_orden" value="${editModalOrder.id_orden || ''}" required>
          </div>

          <!-- Campo: Tipo de producto -->
          <div class="form-group">
            <label for="edit_product_type">Tipo de Producto</label>
            <input type="text" id="edit_product_type" name="product_type" value="${editModalOrder.product_type || ''}">
          </div>

          <!-- Campo: Nombre del producto -->
          <div class="form-group">
            <label for="edit_product_name">Nombre del Producto</label>
            <input type="text" id="edit_product_name" name="product_name" value="${editModalOrder.product_name || ''}">
          </div>

          <!-- Campo: Colores -->
          <div class="form-group">
            <label for="edit_colors">Colores</label>
            <input type="text" id="edit_colors" name="colors" value="${editModalOrder.colors || ''}">
          </div>

          <!-- Campo: Largo -->
          <div class="form-group">
            <label for="edit_length_cm">Largo (cm)</label>
            <input type="text" id="edit_length_cm" name="length_cm" value="${editModalOrder.length_cm || ''}">
          </div>

          <!-- Campo: Ancho -->
          <div class="form-group">
            <label for="edit_width_cm">Ancho (cm)</label>
            <input type="text" id="edit_width_cm" name="width_cm" value="${editModalOrder.width_cm || ''}">
          </div>

          <!-- Campo: Descripción -->
          <div class="form-group">
            <label for="edit_description">Descripción</label>
            <textarea id="edit_description" name="description">${editModalOrder.description || ''}</textarea>
          </div>

          <!-- Campo: Nombre completo -->
          <div class="form-group">
            <label for="edit_full_name">Nombre Completo</label>
            <input type="text" id="edit_full_name" name="full_name" value="${editModalOrder.full_name || ''}">
          </div>

          <!-- Campo: Entrega -->
          <div class="form-group">
            <label for="edit_delivery">Entrega</label>
            <input type="text" id="edit_delivery" name="delivery" value="${editModalOrder.delivery || ''}">
          </div>

          <!-- Campo: Fecha -->
          <div class="form-group">
            <label for="edit_date">Fecha</label>
            <input type="text" id="edit_date" name="date" value="${editModalOrder.date || ''}">
          </div>

          <!-- Campo: Fecha límite -->
          <div class="form-group">
            <label for="edit_deadline">Fecha Límite</label>
            <input type="text" id="edit_deadline" name="deadline" value="${editModalOrder.deadline || ''}">
          </div>

          <!-- Campo: Cotización mínima -->
          <div class="form-group">
            <label for="edit_quote_min">Cotización Mínima</label>
            <input type="number" id="edit_quote_min" name="quote_min" value="${editModalOrder.quote_min || ''}">
          </div>

          <!-- Campo: Cotización máxima -->
          <div class="form-group">
            <label for="edit_quote_max">Cotización Máxima</label>
            <input type="number" id="edit_quote_max" name="quote_max" value="${editModalOrder.quote_max || ''}">
          </div>

          <!-- Botones del formulario -->
          <div class="edit-modal-actions">

            <!-- Cancelar (cierra el modal) -->
            <button type="button" class="button secondary" data-edit-close>Cancelar</button>

            <!-- Guardar cambios -->
            <button type="submit" class="button primary">Guardar</button>

          </div>
        </form>
      </div>
    </div>
  `;
}

// ================= ABRIR PREVIEW DE IMAGEN =================
function openImagePreview(src, alt) {

  // Guarda la imagen activa que se quiere mostrar en el modal
  // (es como guardar un estado en una variable global)
  activePreview = { src, alt };

  // Vuelve a renderizar los modales para mostrar el preview
  renderFloatingModals();
}


// ================= CERRAR PREVIEW DE IMAGEN =================
function closeImagePreview() {

  // Si no hay imagen activa, no hace nada
  if (!activePreview) {
    return;
  }

  // Limpia la imagen activa (cierra el modal)
  activePreview = null;

  // Re-renderiza para actualizar la UI
  renderFloatingModals();
}


// ================= ABRIR MODAL DE RECHAZO =================
function openRejectModal(anticipo) {

  // Guarda el ID del anticipo que se quiere rechazar
  rejectModalOrderId = anticipo.id;

  // Renderiza los modales para mostrar el de rechazo
  renderFloatingModals();
}


// ================= CERRAR MODAL DE RECHAZO =================
function closeRejectModal() {

  // Si no hay ningún modal abierto, no hace nada
  if (!rejectModalOrderId) {
    return;
  }

  // Limpia el ID (cierra el modal)
  rejectModalOrderId = null;

  // Re-renderiza para actualizar la interfaz
  renderFloatingModals();
}


// ================= (REPETIDO) ABRIR MODAL DE RECHAZO =================
function openRejectModal(anticipo) {

  // Guarda el ID del anticipo que se quiere rechazar
  rejectModalOrderId = anticipo.id;

  // Renderiza los modales para mostrar el de rechazo
  renderFloatingModals();
}


// ================= (REPETIDO) CERRAR MODAL DE RECHAZO =================
function closeRejectModal() {

  // Si no hay ningún modal abierto, no hace nada
  if (!rejectModalOrderId) {
    return;
  }

  // Limpia el ID (cierra el modal)
  rejectModalOrderId = null;

  // Re-renderiza para actualizar la interfaz
  renderFloatingModals();
}


// ================= ABRIR MODAL DE EDICIÓN =================
function openEditModal(anticipo) {

  // Guarda toda la información del anticipo que se quiere editar
  editModalOrder = anticipo;

  // Renderiza los modales para mostrar el formulario de edición
  renderFloatingModals();
}


// ================= CERRAR MODAL DE EDICIÓN =================
function closeEditModal() {

  // Si no hay un modal abierto, no hace nada
  if (!editModalOrder) {
    return;
  }

  // Limpia la orden (cierra el modal)
  editModalOrder = null;

  // Re-renderiza la UI
  renderFloatingModals();
}

// ================= APROBAR ANTICIPO =================
async function handleApprove(anticipo) {

  try {

    // Hace una petición al backend para aprobar el anticipo
    // (equivalente a requests.post en Python)
    const response = await fetch(`/api/admin/orders/${anticipo.id}/approve-anticipo`, {
      method: "POST",
      headers: {
        Accept: "application/json" // Indica que espera respuesta en JSON
      }
    });

    // Si la respuesta no es exitosa, lanza un error construido desde la respuesta
    if (!response.ok) {
      throw await buildRequestError(response);
    }

    // Si todo sale bien, muestra mensaje de éxito
    adminCommon.setStatus(
      anticiposStatus, 
      `Anticipo de la orden ${anticipo.orderCode} aprobado con 100% de validacion.`
    );

    // Recarga los datos para reflejar cambios en la UI
    await loadAnticipos();

  } catch (error) {

    // Si ocurre un error, lo muestra en consola
    console.error("No fue posible aprobar el anticipo", error);

    // Muestra mensaje de error al usuario
    adminCommon.setStatus(
      anticiposStatus, 
      `No fue posible aprobar la orden ${anticipo.orderCode}: ${error.message}`
    );
  }
}


// ================= ELIMINAR REFERENCIA =================
async function handleDeleteReference(anticipo) {

  try {

    // Hace una petición DELETE al backend para eliminar la imagen de referencia
    const response = await fetch(`/api/admin/orders/${anticipo.id}/reference-image`, {
      method: "DELETE",
      headers: {
        Accept: "application/json"
      }
    });

    // Si falla la petición, lanza error
    if (!response.ok) {
      throw await buildRequestError(response);
    }

    // Mensaje de éxito
    adminCommon.setStatus(
      anticiposStatus, 
      `Referencia eliminada para la orden ${anticipo.orderCode}.`
    );

    // Recarga los datos actualizados
    await loadAnticipos();

  } catch (error) {

    // Muestra error en consola
    console.error("No fue posible eliminar la referencia", error);

    // Muestra error en la UI
    adminCommon.setStatus(
      anticiposStatus, 
      `No fue posible eliminar la referencia de la orden ${anticipo.orderCode}: ${error.message}`
    );
  }
}


// ================= COPIAR MENSAJE Y RECHAZAR ANTICIPO =================
async function handleRejectCopy() {

  // Busca el anticipo usando el ID guardado del modal de rechazo
  const anticipo = anticipos.find(
    (item) => String(item.id) === String(rejectModalOrderId)
  );

  // Si no lo encuentra, cierra el modal y termina
  if (!anticipo) {
    closeRejectModal();
    return;
  }

  // Genera el mensaje reemplazando el ID en el template
  const message = ANTICIPO_REJECT_TEMPLATE.replace(
    "{orderId}", 
    anticipo.businessOrderId
  );

  try {

    // Copia el mensaje al portapapeles
    // (similar a guardar en clipboard en otros lenguajes)
    await copyToClipboard(message);

    // Hace petición al backend para marcar el anticipo como rechazado
    const response = await fetch(`/api/admin/orders/${anticipo.id}/reject-anticipo`, {
      method: "POST",
      headers: {
        Accept: "application/json"
      }
    });

    // Si falla, lanza error
    if (!response.ok) {
      throw await buildRequestError(response);
    }

    // Cierra el modal de rechazo
    closeRejectModal();

    // Muestra mensaje de éxito (copiado + rechazo)
    adminCommon.setStatus(
      anticiposStatus, 
      `Mensaje copiado y anticipo rechazado para la orden ${anticipo.orderCode}.`
    );

    // Recarga los datos
    await loadAnticipos();

  } catch (error) {

    // Muestra error en consola
    console.error("No fue posible rechazar el anticipo", error);

    // Muestra error en UI
    adminCommon.setStatus(
      anticiposStatus, 
      `No fue posible copiar o rechazar la orden ${anticipo.orderCode}: ${error.message}`
    );
  }
}

// ================= EXPORTAR DATOS A CSV =================
function handleExportCSV() {

  // Si no hay datos en el array de anticipos, muestra alerta y termina
  if (anticipos.length === 0) {
    alert('No hay anticipos para exportar');
    return;
  }

  // Define los encabezados del archivo CSV (primera fila)
  const headers = ['ID Orden', 'Cliente', 'Numero', 'ID Producto'];

  // Construye las filas del CSV recorriendo los anticipos
  // (equivalente a un for o list comprehension en Python)
  const rows = anticipos.map(anticipo => [
    anticipo.orderCode, // ID de la orden
    anticipo.cliente,   // Nombre del cliente
    anticipo.waId || 'Sin numero', // Número o valor por defecto
    anticipo.product_name || anticipo.referencia || 'Sin producto' // Producto o fallback
  ]);

  // Construye el contenido final del CSV
  const csvContent = [

    // Une los headers con coma (como "join" en Python)
    headers.join(','),

    // Convierte cada fila en string CSV
    ...rows.map(row => 
      row.map(cell => `"${cell}"`).join(',') // Encierra cada valor en comillas
    )

  ].join('\n'); // Une todo con saltos de línea

  // ================= CREAR ARCHIVO =================

  // Crea un objeto Blob (archivo en memoria)
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });

  // Crea un elemento <a> para descargar el archivo
  const link = document.createElement('a');

  // Genera una URL temporal para el archivo
  const url = URL.createObjectURL(blob);

  // Asigna la URL al link
  link.setAttribute('href', url);

  // Define el nombre del archivo con fecha actual
  link.setAttribute(
    'download', 
    `anticipos_export_${new Date().toISOString().split('T')[0]}.csv`
  );

  // Oculta el link (no visible para el usuario)
  link.style.visibility = 'hidden';

  // Agrega el link al DOM
  document.body.appendChild(link);

  // Simula click para descargar el archivo
  link.click();

  // Elimina el link del DOM
  document.body.removeChild(link);

  // Muestra mensaje de éxito
  adminCommon.setStatus(
    anticiposStatus, 
    `${anticipos.length} anticipos exportados a CSV`
  );
}


// ================= ELIMINAR ELEMENTOS SELECCIONADOS =================
function handleDeleteSelected() {

  // Obtiene los IDs de los checkboxes seleccionados
  const selectedIds = Array
    .from(document.querySelectorAll('.row-select:checked')) // selecciona los marcados
    .map(cb => cb.dataset.id); // extrae sus IDs

  // Si no hay seleccionados, muestra alerta
  if (selectedIds.length === 0) {
    alert('Selecciona al menos un anticipo para eliminar');
    return;
  }

  // Pide confirmación al usuario antes de eliminar
  if (!confirm(`¿Eliminar ${selectedIds.length} anticipo(s) seleccionado(s)?`)) {
    return;
  }

  // Aquí debería ir la lógica real de eliminación (no está implementada aún)
  // (ej: enviar petición DELETE al backend)

  adminCommon.setStatus(
    anticiposStatus, 
    'Eliminación múltiple no implementada aún'
  );
}
// ================= ELIMINAR ÓRDENES SELECCIONADAS =================
async function handleDeleteSelected() {

  // Selecciona todos los checkboxes marcados
  const selected = document.querySelectorAll(".row-select:checked");

  // Si no hay ninguno seleccionado, muestra mensaje y termina
  if (!selected.length) {
    adminCommon.setStatus(anticiposStatus, "Selecciona al menos una orden para eliminar.");
    return;
  }

  // Convierte los elementos seleccionados en un array de IDs
  // (similar a extraer valores de una lista en Python)
  const ids = Array.from(selected).map(cb => cb.dataset.id);

  // Pide confirmación al usuario antes de eliminar
  if (!confirm(`¿Estás seguro de eliminar ${ids.length} orden(es)?`)) {
    return;
  }

  try {

    // Recorre cada ID y envía petición DELETE al backend
    // (equivalente a un for en Python con requests)
    for (const id of ids) {

      const response = await fetch(`/api/admin/orders/${id}`, {
        method: "DELETE",
        headers: {
          Accept: "application/json"
        }
      });

      // Si alguna petición falla, lanza error
      if (!response.ok) {
        throw new Error(`Error eliminando orden ${id}`);
      }
    }

    // Si todo sale bien, muestra mensaje de éxito
    adminCommon.setStatus(
      anticiposStatus, 
      `${ids.length} orden(es) eliminada(s).`
    );

    // Recarga los datos para actualizar la UI
    await loadAnticipos();

  } catch (error) {

    // Muestra error en consola
    console.error("Error eliminando órdenes", error);

    // Muestra error al usuario
    adminCommon.setStatus(
      anticiposStatus, 
      `Error eliminando órdenes: ${error.message}`
    );
  }
}


// ================= EXPORTAR CSV COMPLETO =================
function handleExportCSV() {

  // Construye el contenido CSV como un array de arrays
  const csvContent = [

    // Primera fila: headers (nombres de columnas)
    ["full_name", "product_type", "product_name", "product_image", "colors", "length_cm", "width_cm", "description", "delivery", "date", "deadline", "wa_id", "payment_proof", "status", "quote_min", "quote_max", "advance_payment", "id_orden"],

    // Agrega todas las filas de datos recorriendo anticipos
    ...anticipos.map(a => [
      a.full_name || "",
      a.product_type || "",
      a.product_name || "",
      a.product_image || "",
      a.colors || "",
      a.length_cm || "",
      a.width_cm || "",
      a.description || "",
      a.delivery || "",
      a.date || "",
      a.deadline || "",
      a.waId || "",
      a.whatsappProof || "",
      a.status || "",
      a.quote_min || "",
      a.quote_max || "",
      a.advance_payment || "",
      a.id_orden || ""
    ])

  ]

  // Convierte cada fila en string CSV (valores separados por coma)
  .map(row => 
    row.map(cell => `"${cell}"`).join(",") // Encierra cada valor en comillas
  )

  // Une todas las filas con salto de línea
  .join("\n");

  // ================= CREAR ARCHIVO =================

  // Crea un archivo en memoria (Blob)
  const blob = new Blob([csvContent], { type: "text/csv" });

  // Genera una URL temporal para el archivo
  const url = URL.createObjectURL(blob);

  // Crea un elemento <a> para descargar
  const a = document.createElement("a");

  // Asigna la URL al link
  a.href = url;

  // Define el nombre del archivo
  a.download = "anticipos.csv";

  // Simula click para iniciar descarga
  a.click();

  // Libera la URL de memoria
  URL.revokeObjectURL(url);
}


// ================= CREAR CONTENEDOR DE MODALES =================
function createModalHost() {

  // Busca si ya existe un contenedor de modales en el DOM
  const existingHost = document.getElementById("anticiposModalHost");

  // Si existe, lo reutiliza (evita duplicados)
  if (existingHost) {
    return existingHost;
  }

  // Si no existe, crea un nuevo div
  const host = document.createElement("div");

  // Le asigna un ID único
  host.id = "anticiposModalHost";

  // Lo agrega al body de la página
  document.body.appendChild(host);

  // Retorna el contenedor creado
  return host;
}