if (!Sesion.activa()) window.location.href = 'login.html';

document.getElementById('nombre-usuario').textContent = Sesion.nombre() || '';
document.getElementById('btn-salir').addEventListener('click', () => {
  Sesion.cerrar();
  window.location.href = 'login.html';
});

// Billetes vigentes en Argentina (2026). Si cambian las denominaciones, alcanza con editar esta lista.
const DENOMINACIONES = [20000, 10000, 2000, 1000, 500, 200, 100, 50, 20, 10];
const NOMBRES_METODO = { efectivo: 'Efectivo', debito: 'Debito', credito: 'Credito', transferencia: 'Transferencia', qr: 'QR' };
const TIPOS_CON_BANCO = ['debito', 'credito', 'transferencia', 'qr'];

let sucursalId = Number(Sesion.sucursalId()) || null;
let productos = [];         // catalogo completo (base, sin descontar pendientes offline)
let categorias = [];
let carrito = {};           // producto_id -> { producto, cantidad }
let turnoActual = null;
let pagosAgregados = [];    // { metodo, monto }
let enLinea = true;         // ultimo estado de conexion conocido (se actualiza con cada llamada real)

const TURNO_STORAGE_KEY = () => `vs_turno_actual_${sucursalId}`;

// ---------- Estado de conexion ----------
function marcarConexion(online) {
  if (enLinea === online) { actualizarBadgeConexion(); return; }
  enLinea = online;
  actualizarBadgeConexion();
  if (online) sincronizarPendientes();
}

async function actualizarBadgeConexion() {
  const badge = document.getElementById('conexion-badge');
  const texto = document.getElementById('conexion-badge-texto');
  const pendientes = await OfflineDB.contarVentasPendientes().catch(() => 0);
  if (enLinea) {
    badge.className = 'conexion-badge online';
    texto.textContent = pendientes > 0 ? `En linea · sincronizando ${pendientes}...` : 'En linea';
  } else {
    badge.className = 'conexion-badge offline';
    texto.textContent = pendientes > 0 ? `Sin conexion · ${pendientes} venta(s) pendiente(s)` : 'Sin conexion';
  }
}

window.addEventListener('online', () => sincronizarPendientes());
setInterval(() => sincronizarPendientes(), 20000);

// ---------- Inicio ----------
async function inicializar() {
  if (!sucursalId) {
    mostrarToast('Este usuario no tiene sucursal asignada. Contacta al administrador.', 'error');
    return;
  }
  try {
    const config = await apiFetch('/config-fiscal', { auth: false });
    marcarConexion(true);
    if (config && config.razon_social) {
      document.getElementById('nombre-negocio').textContent = config.razon_social;
    }
  } catch (err) {
    if (err.esErrorDeRed) marcarConexion(false);
  }

  try {
    categorias = await apiFetch('/categorias');
    marcarConexion(true);
    const select = document.getElementById('select-categoria');
    categorias.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.nombre;
      select.appendChild(opt);
    });
  } catch (err) {
    if (err.esErrorDeRed) marcarConexion(false);
  }

  try {
    turnoActual = await apiFetch(`/turnos/actual?sucursal_id=${sucursalId}`);
    marcarConexion(true);
    if (turnoActual) localStorage.setItem(TURNO_STORAGE_KEY(), JSON.stringify(turnoActual));
  } catch (err) {
    if (err.esErrorDeRed) {
      marcarConexion(false);
      // Sin conexion: si ya habiamos abierto turno antes en este dispositivo, seguimos con ese
      const guardado = localStorage.getItem(TURNO_STORAGE_KEY());
      if (guardado) turnoActual = JSON.parse(guardado);
    } else {
      mostrarToast(err.message, 'error');
    }
  }

  if (!turnoActual) {
    document.getElementById('modal-apertura').classList.add('visible');
  } else {
    actualizarBadgeTurno();
    await cargarProductos();
  }
  await sincronizarPendientes();
}

function actualizarBadgeTurno() {
  const badge = document.getElementById('turno-badge');
  const texto = document.getElementById('turno-badge-texto');
  if (turnoActual) {
    badge.style.display = 'flex';
    texto.textContent = `Turno N°${turnoActual.numero} · ${formatoMoneda(turnoActual.monto_apertura)}`;
    document.getElementById('acciones-caja').style.display = 'flex';
  } else {
    badge.style.display = 'none';
    document.getElementById('acciones-caja').style.display = 'none';
  }
}

// ---------- Apertura de turno (requiere conexion: el numero de turno lo asigna el servidor) ----------
document.getElementById('btn-confirmar-apertura').addEventListener('click', async () => {
  const input = document.getElementById('monto-apertura');
  const monto = Number(input.value) || 0;
  const btn = document.getElementById('btn-confirmar-apertura');
  btn.disabled = true;
  btn.textContent = 'Abriendo...';
  try {
    turnoActual = await apiFetch('/turnos/abrir', {
      method: 'POST',
      body: { sucursal_id: sucursalId, monto_apertura: monto },
    });
    marcarConexion(true);
    localStorage.setItem(TURNO_STORAGE_KEY(), JSON.stringify(turnoActual));
    document.getElementById('modal-apertura').classList.remove('visible');
    actualizarBadgeTurno();
    await cargarProductos();
  } catch (err) {
    if (err.esErrorDeRed) {
      marcarConexion(false);
      mostrarToast('Necesitas conexion a internet para abrir el turno (una sola vez, al empezar el dia)', 'error');
    } else {
      mostrarToast(err.message, 'error');
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Abrir turno';
  }
});

// ---------- Productos: se cachean localmente para poder seguir vendiendo sin conexion ----------
document.getElementById('select-categoria').addEventListener('change', () => {
  aplicarFiltrosYRenderizar();
});

async function cargarProductos() {
  try {
    const query = new URLSearchParams({ sucursal_id: sucursalId, solo_visibles_pos: 'true' });
    productos = await apiFetch(`/productos?${query.toString()}`);
    marcarConexion(true);
    await OfflineDB.guardarProductosCache(productos);
  } catch (err) {
    if (err.esErrorDeRed) {
      marcarConexion(false);
      productos = await OfflineDB.obtenerProductosCache();
      if (productos.length === 0) {
        mostrarToast('Sin conexion y sin catalogo guardado todavia. Conectate una vez para descargarlo.', 'error');
      }
    } else {
      mostrarToast(err.message, 'error');
    }
  }
  aplicarFiltrosYRenderizar();
}

function aplicarFiltrosYRenderizar() {
  const filtro = document.getElementById('buscar').value.trim().toLowerCase();
  const categoriaId = document.getElementById('select-categoria').value;

  let lista = productos;
  if (filtro) {
    lista = lista.filter((p) => p.nombre.toLowerCase().includes(filtro) || p.codigo.toLowerCase().includes(filtro));
  }
  if (categoriaId) {
    lista = lista.filter((p) => String(p.categoria_id || '') === categoriaId);
  }
  renderizarProductos(lista);
}

function renderizarProductos(lista) {
  const grid = document.getElementById('grid-productos');
  if (lista.length === 0) {
    grid.innerHTML = '<div class="estado-vacio">No se encontraron productos</div>';
    return;
  }
  grid.innerHTML = '';
  lista.forEach((p) => {
    const sinStock = p.stockeable && p.stock_disponible <= 0;
    const stockBajo = p.stockeable && p.stock_disponible > 0 && p.stock_disponible <= (p.stock_minimo || 0);
    const btn = document.createElement('button');
    btn.className = 'tarjeta-producto';
    btn.disabled = sinStock;

    const imagenHtml = p.imagen_url
      ? `<img src="${escaparHtml(p.imagen_url)}" alt="" onerror="this.parentElement.innerHTML='<span class=\\'tp-imagen-placeholder\\'>📦</span>'">`
      : `<span class="tp-imagen-placeholder">📦</span>`;

    btn.innerHTML = `
      <div class="tp-imagen">${imagenHtml}</div>
      <div class="tp-cuerpo">
        <div class="tp-nombre">${escaparHtml(p.nombre)}</div>
        <div class="tp-fila">
          <span class="tp-precio">${formatoMoneda(p.precio_venta)}</span>
        </div>
        <div class="tp-stock ${stockBajo ? 'bajo' : ''}">${p.stockeable ? (sinStock ? 'Sin stock' : `Stock: ${p.stock_disponible}`) : 'Disponible'}</div>
      </div>
    `;
    btn.addEventListener('click', () => agregarAlCarrito(p));
    grid.appendChild(btn);
  });
}

function agregarAlCarrito(producto) {
  const item = carrito[producto.id];
  const cantidadActual = item ? item.cantidad : 0;
  if (producto.stockeable && cantidadActual + 1 > producto.stock_disponible) {
    mostrarToast(`No hay mas stock disponible de "${producto.nombre}"`, 'error');
    return;
  }
  carrito[producto.id] = { producto, cantidad: cantidadActual + 1 };
  renderizarTicket();
}

function cambiarCantidad(productoId, delta) {
  const item = carrito[productoId];
  if (!item) return;
  const nueva = item.cantidad + delta;
  if (nueva <= 0) {
    delete carrito[productoId];
  } else if (nueva > item.producto.stock_disponible) {
    mostrarToast('No hay mas stock disponible', 'error');
    return;
  } else {
    item.cantidad = nueva;
  }
  renderizarTicket();
}

function quitarDelCarrito(productoId) {
  delete carrito[productoId];
  renderizarTicket();
}

function totalCarrito() {
  return Object.values(carrito).reduce((acc, i) => acc + i.producto.precio_venta * i.cantidad, 0);
}

function renderizarTicket() {
  const cont = document.getElementById('ticket-lineas');
  const items = Object.values(carrito);

  if (items.length === 0) {
    cont.innerHTML = '<div class="ticket-vacio">Toca un producto para agregarlo</div>';
  } else {
    cont.innerHTML = '';
    items.forEach(({ producto, cantidad }) => {
      const subtotal = producto.precio_venta * cantidad;
      const linea = document.createElement('div');
      linea.className = 'linea-ticket';
      linea.innerHTML = `
        <div class="linea-info">
          <div class="linea-nombre">${escaparHtml(producto.nombre)}</div>
          <div class="linea-precio-u">${formatoMoneda(producto.precio_venta)} c/u</div>
        </div>
        <div class="linea-cant">
          <button data-accion="restar">−</button>
          <span>${cantidad}</span>
          <button data-accion="sumar">+</button>
        </div>
        <div class="linea-subtotal">${formatoMoneda(subtotal)}</div>
        <button class="linea-quitar" title="Quitar">✕</button>
      `;
      linea.querySelector('[data-accion="restar"]').addEventListener('click', () => cambiarCantidad(producto.id, -1));
      linea.querySelector('[data-accion="sumar"]').addEventListener('click', () => cambiarCantidad(producto.id, 1));
      linea.querySelector('.linea-quitar').addEventListener('click', () => quitarDelCarrito(producto.id));
      cont.appendChild(linea);
    });
  }

  const totalItems = items.reduce((acc, i) => acc + i.cantidad, 0);
  document.getElementById('total-items').textContent = totalItems;
  document.getElementById('total-monto').textContent = formatoMoneda(totalCarrito());
  document.getElementById('btn-cobrar').disabled = items.length === 0;
}

document.getElementById('btn-vaciar').addEventListener('click', () => {
  carrito = {};
  renderizarTicket();
});

// ---------- Cobro: propina + pagos (uno o varios), funciona online y offline ----------
document.getElementById('btn-cobrar').addEventListener('click', () => {
  if (Object.keys(carrito).length === 0) return;
  pagosAgregados = [];
  document.getElementById('input-propina').value = 0;
  renderizarPagos();
  document.getElementById('modal-pago').classList.add('visible');
});

document.getElementById('btn-cerrar-modal-pago').addEventListener('click', () => {
  document.getElementById('modal-pago').classList.remove('visible');
});

document.getElementById('input-propina').addEventListener('input', renderizarPagos);

function totalACobrar() {
  const propina = Number(document.getElementById('input-propina').value) || 0;
  return totalCarrito() + propina;
}

function restantePorCobrar() {
  const pagado = pagosAgregados.reduce((acc, p) => acc + p.monto, 0);
  return Math.round((totalACobrar() - pagado) * 100) / 100;
}

document.querySelectorAll('#modal-pago .opcion-pago').forEach((btn) => {
  btn.addEventListener('click', () => {
    const restante = restantePorCobrar();
    if (restante <= 0) return;
    const metodo = btn.dataset.metodo;
    if (TIPOS_CON_BANCO.includes(metodo)) {
      abrirModalBanco(metodo, restante);
    } else {
      pagosAgregados.push({ metodo, monto: restante });
      renderizarPagos();
    }
  });
});

async function abrirModalBanco(metodo, monto) {
  document.getElementById('titulo-modal-banco').textContent = `${NOMBRES_METODO[metodo]} — elegi el banco/proveedor`;
  const lista = document.getElementById('lista-bancos');
  lista.innerHTML = '<div class="sin-bancos-config">Cargando...</div>';
  document.getElementById('modal-banco').classList.add('visible');

  try {
    const bancos = await apiFetch(`/formas-pago?tipo=${metodo}`);
    if (bancos.length === 0) {
      lista.innerHTML = `
        <div class="sin-bancos-config">
          Todavia no hay bancos/proveedores configurados para ${NOMBRES_METODO[metodo]}.<br>
          Pedile al administrador que los cargue en Backoffice → Formas de pago.
        </div>
        <button class="opcion-banco" data-sin-banco="1">Continuar sin especificar banco</button>
      `;
    } else {
      lista.innerHTML = bancos.map((b) => `<button class="opcion-banco" data-id="${b.id}">${escaparHtml(b.nombre)}</button>`).join('') +
        `<button class="opcion-banco" data-sin-banco="1">Otro / no especificar</button>`;
    }
    lista.querySelectorAll('.opcion-banco').forEach((btnBanco) => {
      btnBanco.addEventListener('click', () => {
        const formaPagoDetalleId = btnBanco.dataset.sinBanco ? null : Number(btnBanco.dataset.id);
        pagosAgregados.push({ metodo, monto, forma_pago_detalle_id: formaPagoDetalleId, nombreBanco: btnBanco.textContent });
        document.getElementById('modal-banco').classList.remove('visible');
        renderizarPagos();
      });
    });
  } catch (err) {
    lista.innerHTML = `<div class="sin-bancos-config">${err.message}</div>`;
  }
}

document.getElementById('btn-cerrar-modal-banco').addEventListener('click', () => {
  document.getElementById('modal-banco').classList.remove('visible');
});

function renderizarPagos() {
  const totalProductos = totalCarrito();
  const propina = Number(document.getElementById('input-propina').value) || 0;
  document.getElementById('pago-total-productos').textContent = formatoMoneda(totalProductos);
  document.getElementById('pago-total-propina').textContent = formatoMoneda(propina);
  document.getElementById('pago-total-cobrar').textContent = formatoMoneda(totalProductos + propina);

  const lista = document.getElementById('lista-pagos-agregados');
  lista.innerHTML = pagosAgregados.map((p, idx) => `
    <div class="fila-pago-agregado" data-idx="${idx}">
      <span class="metodo-nombre">${NOMBRES_METODO[p.metodo] || p.metodo}${p.nombreBanco && p.nombreBanco !== 'Otro / no especificar' ? ` · ${escaparHtml(p.nombreBanco)}` : ''}</span>
      <input type="number" min="0" step="1" value="${p.monto}" class="input-monto-pago">
      <button class="quitar-pago">✕</button>
    </div>
  `).join('');

  lista.querySelectorAll('.fila-pago-agregado').forEach((fila) => {
    const idx = Number(fila.dataset.idx);
    fila.querySelector('.input-monto-pago').addEventListener('input', (e) => {
      pagosAgregados[idx].monto = Number(e.target.value) || 0;
      actualizarRestante();
    });
    fila.querySelector('.quitar-pago').addEventListener('click', () => {
      pagosAgregados.splice(idx, 1);
      renderizarPagos();
    });
  });

  actualizarRestante();
}

function actualizarRestante() {
  const restante = restantePorCobrar();
  const el = document.getElementById('pago-restante');
  const fila = document.getElementById('fila-restante');
  el.textContent = formatoMoneda(Math.abs(restante));
  fila.classList.remove('saldado', 'pendiente');
  const btnConfirmar = document.getElementById('btn-confirmar-cobro');
  if (Math.abs(restante) < 0.01 && pagosAgregados.length > 0) {
    fila.classList.add('saldado');
    document.querySelector('#fila-restante span:first-child').textContent = 'Cobro completo';
    btnConfirmar.disabled = false;
  } else {
    fila.classList.add('pendiente');
    document.querySelector('#fila-restante span:first-child').textContent = restante > 0 ? 'Falta cobrar' : 'Sobra (ajustá el monto)';
    btnConfirmar.disabled = true;
  }
}

let clienteSeleccionadoId = null;
let timerBusquedaCliente = null;

document.getElementById('input-cliente-buscar').addEventListener('input', (e) => {
  clienteSeleccionadoId = null;
  document.getElementById('campos-cliente-nuevo').classList.toggle('visible', e.target.value.trim().length > 0);
  clearTimeout(timerBusquedaCliente);
  const texto = e.target.value.trim();
  const cont = document.getElementById('sugerencias-cliente');
  if (texto.length < 2) {
    cont.classList.remove('visible');
    return;
  }
  timerBusquedaCliente = setTimeout(async () => {
    try {
      const resultados = await apiFetch(`/clientes?buscar=${encodeURIComponent(texto)}`);
      if (resultados.length === 0) {
        cont.classList.remove('visible');
        return;
      }
      cont.innerHTML = resultados.map((c) => `
        <div class="sugerencia-cliente-item" data-id="${c.id}" data-nombre="${escaparHtml(c.nombre)}${c.apellido ? ' ' + escaparHtml(c.apellido) : ''}">
          ${escaparHtml(c.nombre)}${c.apellido ? ' ' + escaparHtml(c.apellido) : ''}${c.telefono ? ` — ${escaparHtml(c.telefono)}` : ''}
        </div>
      `).join('');
      cont.classList.add('visible');
      cont.querySelectorAll('.sugerencia-cliente-item').forEach((item) => {
        item.addEventListener('click', () => seleccionarClienteExistente(Number(item.dataset.id), item.dataset.nombre));
      });
    } catch (err) { /* sin conexion: se ignora la busqueda, se puede seguir cargando como nuevo */ }
  }, 300);
});

function seleccionarClienteExistente(id, nombre) {
  clienteSeleccionadoId = id;
  document.getElementById('input-cliente-buscar').value = '';
  document.getElementById('sugerencias-cliente').classList.remove('visible');
  document.getElementById('campos-cliente-nuevo').classList.remove('visible');
  document.getElementById('cliente-seleccionado-nombre').textContent = nombre;
  document.getElementById('cliente-seleccionado-chip').classList.add('visible');
}

document.getElementById('btn-quitar-cliente').addEventListener('click', () => {
  clienteSeleccionadoId = null;
  document.getElementById('cliente-seleccionado-chip').classList.remove('visible');
});

function reiniciarCampoCliente() {
  clienteSeleccionadoId = null;
  document.getElementById('input-cliente-buscar').value = '';
  document.getElementById('cliente-nuevo-apellido').value = '';
  document.getElementById('cliente-nuevo-telefono').value = '';
  document.getElementById('cliente-nuevo-direccion').value = '';
  document.getElementById('campos-cliente-nuevo').classList.remove('visible');
  document.getElementById('cliente-seleccionado-chip').classList.remove('visible');
  document.getElementById('sugerencias-cliente').classList.remove('visible');
}

document.getElementById('btn-confirmar-cobro').addEventListener('click', () => {
  const propina = Number(document.getElementById('input-propina').value) || 0;
  confirmarVenta(propina, pagosAgregados);
});

async function confirmarVenta(propina, pagos) {
  const items = Object.values(carrito);
  if (items.length === 0) return;

  const idCliente = generarUuid();
  const payload = {
    sucursal_id: sucursalId,
    propina,
    pagos: pagos.map((p) => ({ metodo_pago: p.metodo, monto: p.monto, forma_pago_detalle_id: p.forma_pago_detalle_id || null })),
    detalles: items.map((i) => ({ producto_id: i.producto.id, cantidad: i.cantidad })),
    id_cliente: idCliente,
  };

  if (clienteSeleccionadoId) {
    payload.cliente_id = clienteSeleccionadoId;
  } else if (document.getElementById('input-cliente-buscar').value.trim()) {
    payload.cliente_nombre_nuevo = document.getElementById('input-cliente-buscar').value.trim();
    payload.cliente_apellido_nuevo = document.getElementById('cliente-nuevo-apellido').value.trim() || null;
    payload.cliente_telefono_nuevo = document.getElementById('cliente-nuevo-telefono').value.trim() || null;
    payload.cliente_direccion_nueva = document.getElementById('cliente-nuevo-direccion').value.trim() || null;
  }

  try {
    const venta = await apiFetch('/ventas', { method: 'POST', body: payload });
    marcarConexion(true);
    document.getElementById('modal-pago').classList.remove('visible');
    mostrarComprobante(venta, false);
    if (venta.cliente_frecuente) {
      mostrarToast('Cliente frecuente: ya supero las 10 compras este mes.', 'success');
    }
    reiniciarCampoCliente();
    carrito = {};
    renderizarTicket();
    await cargarProductos();
  } catch (err) {
    if (err.esErrorDeRed) {
      // Sin conexion: se guarda localmente y se sincroniza sola cuando vuelva la señal
      marcarConexion(false);
      payload.fecha_local = new Date().toISOString();
      await OfflineDB.encolarVentaPendiente(idCliente, payload);
      descontarStockLocal(items);
      document.getElementById('modal-pago').classList.remove('visible');
      mostrarComprobante({
        id_cliente: idCliente,
        numero_comprobante: 'Pendiente de sincronizar',
        total: totalCarrito(),
        propina,
      }, true);
      carrito = {};
      renderizarTicket();
      aplicarFiltrosYRenderizar();
      actualizarBadgeConexion();
    } else {
      mostrarToast(err.message, 'error');
    }
  }
}

function descontarStockLocal(items) {
  // Ajuste optimista para que este mismo dispositivo no vuelva a vender lo que ya vendio offline.
  // El servidor vuelve a validar el stock real al sincronizar.
  items.forEach(({ producto, cantidad }) => {
    const enCache = productos.find((p) => p.id === producto.id);
    if (enCache) enCache.stock_disponible = Math.max(0, enCache.stock_disponible - cantidad);
  });
  OfflineDB.guardarProductosCache(productos);
}

function mostrarComprobante(venta, esOffline) {
  document.getElementById('comprobante-num').textContent = venta.numero_comprobante || `Venta #${venta.id}`;
  document.getElementById('comprobante-total').textContent = formatoMoneda(venta.total + (venta.propina || 0));
  const icono = document.querySelector('#modal-comprobante .icono-ok');
  const titulo = document.querySelector('#modal-comprobante h3');
  if (esOffline) {
    icono.textContent = '⏳';
    titulo.textContent = 'Venta guardada (sin conexion)';
  } else {
    icono.textContent = '✓';
    titulo.textContent = 'Venta registrada';
  }
  document.getElementById('modal-comprobante').classList.add('visible');
}
document.getElementById('btn-nueva-venta').addEventListener('click', () => {
  document.getElementById('modal-comprobante').classList.remove('visible');
  document.getElementById('buscar').focus();
});

let debounceBusqueda;
document.getElementById('buscar').addEventListener('input', () => {
  clearTimeout(debounceBusqueda);
  debounceBusqueda = setTimeout(() => aplicarFiltrosYRenderizar(), 200);
});

// ---------- Sincronizacion de ventas pendientes ----------
let sincronizando = false;

async function sincronizarPendientes() {
  if (sincronizando) return;
  sincronizando = true;
  try {
    const pendientes = await OfflineDB.obtenerVentasPendientes();
    if (pendientes.length === 0) {
      actualizarBadgeConexion();
      return;
    }

    let seSincronizoAlguna = false;
    for (const pendiente of pendientes) {
      try {
        await apiFetch('/ventas', { method: 'POST', body: pendiente.payload });
        marcarConexion(true);
        await OfflineDB.eliminarVentaPendiente(pendiente.idCliente);
        seSincronizoAlguna = true;
      } catch (err) {
        if (err.esErrorDeRed) {
          marcarConexion(false);
          break; // seguimos sin conexion, no tiene sentido seguir intentando ahora
        }
        // Error de la app (ej: stock insuficiente al momento de sincronizar): se avisa
        // y se deja en la cola para revisión manual, sin bloquear el resto.
        mostrarToast(`No se pudo sincronizar una venta pendiente: ${err.message}`, 'error');
      }
    }
    if (seSincronizoAlguna) {
      mostrarToast('Ventas pendientes sincronizadas', 'success');
      await cargarProductos();
    }
    await actualizarBadgeConexion();
  } finally {
    sincronizando = false;
  }
}

// ---------- Movimientos de caja (requiere conexion) ----------
let tipoMovimientoSeleccionado = 'ingreso';

document.getElementById('btn-movimiento-caja').addEventListener('click', () => {
  if (!enLinea) { mostrarToast('Necesitas conexion para registrar movimientos de caja', 'error'); return; }
  document.getElementById('monto-movimiento').value = '';
  document.getElementById('motivo-movimiento').value = '';
  seleccionarTipoMovimiento('ingreso');
  document.getElementById('modal-movimiento').classList.add('visible');
});
document.getElementById('btn-cerrar-modal-movimiento').addEventListener('click', () => {
  document.getElementById('modal-movimiento').classList.remove('visible');
});

function seleccionarTipoMovimiento(tipo) {
  tipoMovimientoSeleccionado = tipo;
  document.getElementById('opcion-mov-ingreso').classList.toggle('seleccionada', tipo === 'ingreso');
  document.getElementById('opcion-mov-ingreso').classList.toggle('ingreso', tipo === 'ingreso');
  document.getElementById('opcion-mov-egreso').classList.toggle('seleccionada', tipo === 'egreso');
  document.getElementById('opcion-mov-egreso').classList.toggle('egreso', tipo === 'egreso');
}
document.getElementById('opcion-mov-ingreso').addEventListener('click', () => seleccionarTipoMovimiento('ingreso'));
document.getElementById('opcion-mov-egreso').addEventListener('click', () => seleccionarTipoMovimiento('egreso'));

document.getElementById('btn-confirmar-movimiento').addEventListener('click', async () => {
  const monto = Number(document.getElementById('monto-movimiento').value) || 0;
  if (monto <= 0) {
    mostrarToast('Ingresa un monto valido', 'error');
    return;
  }
  try {
    await apiFetch(`/turnos/${turnoActual.id}/movimientos`, {
      method: 'POST',
      body: {
        tipo: tipoMovimientoSeleccionado,
        monto,
        motivo: document.getElementById('motivo-movimiento').value.trim() || null,
      },
    });
    marcarConexion(true);
    mostrarToast('Movimiento registrado', 'success');
    document.getElementById('modal-movimiento').classList.remove('visible');
  } catch (err) {
    if (err.esErrorDeRed) marcarConexion(false);
    mostrarToast(err.message, 'error');
  }
});

// ---------- Ventas del turno / anular (requiere conexion) ----------
document.getElementById('btn-ver-ventas-turno').addEventListener('click', abrirVentasTurno);
document.getElementById('btn-cerrar-modal-ventas').addEventListener('click', () => {
  document.getElementById('modal-ventas-turno').classList.remove('visible');
});

async function abrirVentasTurno() {
  if (!enLinea) { mostrarToast('Necesitas conexion para ver y anular ventas', 'error'); return; }
  const lista = document.getElementById('lista-ventas-turno');
  lista.innerHTML = '<div class="estado-vacio">Cargando...</div>';
  document.getElementById('modal-ventas-turno').classList.add('visible');
  try {
    const ventas = await apiFetch(`/ventas/turno/${turnoActual.id}`);
    marcarConexion(true);
    if (ventas.length === 0) {
      lista.innerHTML = '<div class="estado-vacio">Todavia no hay ventas en este turno</div>';
      return;
    }
    lista.innerHTML = '';
    ventas.forEach((v) => {
      const fila = document.createElement('div');
      fila.className = `fila-venta-turno ${v.estado === 'anulada' ? 'anulada' : ''}`;
      const hora = new Date(v.fecha).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
      fila.innerHTML = `
        <div class="info-venta">
          <div class="num-venta">${v.numero_comprobante || `Venta #${v.id}`}</div>
          <div class="hora-venta">${hora}</div>
        </div>
        <div class="total-venta">${formatoMoneda(v.total + v.propina)}</div>
        ${v.estado === 'anulada'
          ? '<span class="badge-anulada">Anulada</span>'
          : `<button class="btn-anular" data-id="${v.id}">Anular</button>`}
      `;
      lista.appendChild(fila);
    });
    lista.querySelectorAll('.btn-anular').forEach((btn) => {
      btn.addEventListener('click', () => anularVenta(Number(btn.dataset.id)));
    });
  } catch (err) {
    if (err.esErrorDeRed) marcarConexion(false);
    lista.innerHTML = `<div class="estado-vacio">${err.message}</div>`;
  }
}

async function anularVenta(ventaId) {
  if (!confirm('¿Anular esta venta? El stock se repone automaticamente.')) return;
  try {
    await apiFetch(`/ventas/${ventaId}/anular`, { method: 'POST' });
    mostrarToast('Venta anulada', 'success');
    await abrirVentasTurno();
    await cargarProductos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Cierre de turno / arqueo (requiere conexion) ----------
document.getElementById('btn-cerrar-turno').addEventListener('click', abrirModalArqueo);
document.getElementById('btn-cerrar-modal-arqueo').addEventListener('click', () => {
  document.getElementById('modal-arqueo').classList.remove('visible');
});

async function abrirModalArqueo() {
  if (!enLinea) { mostrarToast('Necesitas conexion para cerrar el turno', 'error'); return; }
  document.getElementById('arqueo-esperado').textContent = '...';
  document.getElementById('modal-arqueo').classList.add('visible');

  let esperado = turnoActual.monto_apertura || 0;
  try {
    const resumen = await apiFetch(`/turnos/${turnoActual.id}/resumen`);
    marcarConexion(true);
    esperado = resumen.esperado;
  } catch (err) {
    if (err.esErrorDeRed) marcarConexion(false);
    mostrarToast('No se pudo calcular el esperado en vivo, usando la apertura como base', 'error');
  }
  document.getElementById('arqueo-esperado').textContent = formatoMoneda(esperado);
  document.getElementById('arqueo-esperado').dataset.valor = esperado;

  const lista = document.getElementById('lista-denominaciones');
  lista.innerHTML = DENOMINACIONES.map((valor) => `
    <div class="fila-denominacion" data-valor="${valor}">
      <span class="etiqueta-billete">$${valor.toLocaleString('es-AR')}</span>
      <input type="number" min="0" step="1" value="0" class="input-cantidad-billete">
      <span class="subtotal-billete mono">$0</span>
    </div>
  `).join('');

  lista.querySelectorAll('.input-cantidad-billete').forEach((input) => {
    input.addEventListener('input', recalcularArqueo);
  });

  recalcularArqueo();
}

function recalcularArqueo() {
  const esperado = Number(document.getElementById('arqueo-esperado').dataset.valor) || 0;
  let contado = 0;
  document.querySelectorAll('#lista-denominaciones .fila-denominacion').forEach((fila) => {
    const valor = Number(fila.dataset.valor);
    const cantidad = Number(fila.querySelector('.input-cantidad-billete').value) || 0;
    const subtotal = valor * cantidad;
    fila.querySelector('.subtotal-billete').textContent = formatoMoneda(subtotal);
    contado += subtotal;
  });

  const diferencia = contado - esperado;
  document.getElementById('arqueo-contado').textContent = formatoMoneda(contado);
  const elDif = document.getElementById('arqueo-diferencia');
  const filaDif = document.getElementById('arqueo-diferencia-fila');
  elDif.textContent = formatoMoneda(diferencia);
  filaDif.classList.remove('positiva', 'negativa');
  if (diferencia > 0) filaDif.classList.add('positiva');
  if (diferencia < 0) filaDif.classList.add('negativa');
}

document.getElementById('btn-confirmar-cierre').addEventListener('click', async () => {
  const pendientes = await OfflineDB.contarVentasPendientes();
  if (pendientes > 0) {
    mostrarToast(`Todavia hay ${pendientes} venta(s) sin sincronizar. Esperá a que se sincronicen antes de cerrar el turno.`, 'error');
    return;
  }

  const conteo = Array.from(document.querySelectorAll('#lista-denominaciones .fila-denominacion'))
    .map((fila) => ({
      denominacion: Number(fila.dataset.valor),
      cantidad: Number(fila.querySelector('.input-cantidad-billete').value) || 0,
    }))
    .filter((c) => c.cantidad > 0);

  const notas = document.getElementById('arqueo-notas').value.trim();
  const btn = document.getElementById('btn-confirmar-cierre');
  btn.disabled = true;
  btn.textContent = 'Cerrando turno...';

  try {
    const turnoCerrado = await apiFetch(`/turnos/${turnoActual.id}/cerrar`, {
      method: 'POST',
      body: { conteo, notas_cierre: notas || null },
    });
    localStorage.removeItem(TURNO_STORAGE_KEY());
    document.getElementById('modal-arqueo').classList.remove('visible');
    mostrarResultadoCierre(turnoCerrado);
  } catch (err) {
    mostrarToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Cerrar turno';
  }
});

function mostrarResultadoCierre(turno) {
  const dif = turno.diferencia || 0;
  const icono = document.getElementById('resultado-cierre-icono');
  const titulo = document.getElementById('resultado-cierre-titulo');
  const detalle = document.getElementById('resultado-cierre-detalle');

  if (dif === 0) {
    icono.textContent = '✓';
    titulo.textContent = `Turno N°${turno.numero} cerrado — caja exacta`;
  } else if (dif > 0) {
    icono.textContent = '＋';
    titulo.textContent = `Turno N°${turno.numero} cerrado — sobrante de ${formatoMoneda(dif)}`;
  } else {
    icono.textContent = '！';
    titulo.textContent = `Turno N°${turno.numero} cerrado — faltante de ${formatoMoneda(Math.abs(dif))}`;
  }
  detalle.textContent = `Esperado ${formatoMoneda(turno.monto_esperado_cierre)} · Contado ${formatoMoneda(turno.monto_contado_cierre)}`;
  document.getElementById('modal-resultado-cierre').classList.add('visible');
}

document.getElementById('btn-cerrar-sesion-post-turno').addEventListener('click', () => {
  Sesion.cerrar();
  window.location.href = 'login.html';
});

function escaparHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto;
  return div.innerHTML;
}

inicializar();
