if (!Sesion.activa() || Sesion.rol() !== 'servidor') {
  window.location.href = 'login.html';
}

document.getElementById('nombre-usuario').textContent = Sesion.nombre() || '';
document.getElementById('btn-salir').addEventListener('click', () => {
  Sesion.cerrar();
  window.location.href = 'login.html';
});

const NOMBRES_METODO = { efectivo: 'Efectivo', debito: 'Debito', credito: 'Credito', transferencia: 'Transferencia', qr: 'QR' };
const DIAS_SEMANA = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo'];

// ---------- Navegacion ----------
document.querySelectorAll('nav button[data-seccion]').forEach((btn) => {
  btn.addEventListener('click', () => cambiarSeccion(btn.dataset.seccion));
});

function cambiarSeccion(id) {
  document.querySelectorAll('.seccion').forEach((s) => s.classList.remove('activa'));
  document.querySelectorAll('nav button').forEach((b) => b.classList.remove('activo'));
  document.getElementById(`seccion-${id}`).classList.add('activa');
  document.querySelector(`nav button[data-seccion="${id}"]`).classList.add('activo');
  cargarDatosSeccion(id);
}

function cargarDatosSeccion(id) {
  if (id === 'resumen') cargarResumen();
  if (id === 'productos') { cargarCategorias(); cargarProductos(); }
  if (id === 'categorias') cargarCategorias();
  if (id === 'compras') { cargarSucursalesParaCompra(); cargarProveedores(); cargarCompras(); }
  if (id === 'inventario') { cargarInventario(); }
  if (id === 'turnos') cargarTurnos();
  if (id === 'formas-pago') cargarFormasPago();
  if (id === 'informes') cargarSelectorTurnosInforme();
  if (id === 'sucursales') cargarSucursales();
  if (id === 'usuarios') cargarUsuarios();
  if (id === 'config') cargarConfigFiscal();
}

let productosCache = [];
let sucursalesCache = [];
let categoriasCache = [];
let proveedoresCache = [];

// ---------- Nombre del negocio en el sidebar ----------
async function cargarNombreNegocio() {
  try {
    const config = await apiFetch('/config-fiscal', { auth: false });
    if (config && config.razon_social) {
      document.getElementById('nombre-negocio-sidebar').textContent = config.razon_social;
    }
  } catch (err) { /* se queda con "Backoffice" */ }
}
cargarNombreNegocio();

// ---------- Resumen ----------
let chartDiaSemana = null;
let chartFormasPago = null;
let chartPorMes = null;
const COLORES_CHART = ['#0F5C4C', '#E8A33D', '#2F9E6E', '#6B7280', '#D6493F', '#14785F'];

async function cargarResumen() {
  try {
    const [resumen, stockBajo, masVendidos] = await Promise.all([
      apiFetch('/reportes/resumen-ventas'),
      apiFetch('/reportes/stock-bajo'),
      apiFetch('/reportes/productos-mas-vendidos?limite=8'),
    ]);
    document.getElementById('tarjetas-resumen').innerHTML = `
      <div class="tarjeta-metrica"><div class="etiqueta">Ventas</div><div class="valor">${resumen.cantidad_ventas}</div></div>
      <div class="tarjeta-metrica"><div class="etiqueta">Facturado</div><div class="valor">${formatoMoneda(resumen.total_facturado)}</div></div>
      <div class="tarjeta-metrica"><div class="etiqueta">Propinas</div><div class="valor">${formatoMoneda(resumen.total_propinas)}</div></div>
      <div class="tarjeta-metrica"><div class="etiqueta">IVA debito</div><div class="valor">${formatoMoneda(resumen.total_iva)}</div></div>
      <div class="tarjeta-metrica"><div class="etiqueta">Ganancia</div><div class="valor">${formatoMoneda(resumen.ganancia_total)}</div></div>
    `;

    const tablaDia = document.getElementById('tabla-dia-semana');
    const datosDia = DIAS_SEMANA.map((dia) => (resumen.por_dia_semana || {})[dia] || { cantidad: 0, total: 0 });
    tablaDia.innerHTML = DIAS_SEMANA.map((dia, i) =>
      `<tr><td>${dia}</td><td>${datosDia[i].cantidad}</td><td class="mono">${formatoMoneda(datosDia[i].total)}</td></tr>`
    ).join('');

    if (chartDiaSemana) chartDiaSemana.destroy();
    chartDiaSemana = new Chart(document.getElementById('chart-dia-semana'), {
      type: 'bar',
      data: {
        labels: DIAS_SEMANA.map((d) => d.slice(0, 3)),
        datasets: [{ label: 'Total vendido', data: datosDia.map((d) => d.total), backgroundColor: '#0F5C4C', borderRadius: 6 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => formatoMoneda(v) } } },
      },
    });

    const entradasPago = Object.entries(resumen.por_metodo_pago || {});
    if (chartFormasPago) chartFormasPago.destroy();
    chartFormasPago = new Chart(document.getElementById('chart-formas-pago'), {
      type: 'doughnut',
      data: {
        labels: entradasPago.map(([m]) => NOMBRES_METODO[m] || m),
        datasets: [{ data: entradasPago.map(([, d]) => d.total), backgroundColor: COLORES_CHART }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
      },
    });

    const tablaVendidos = document.getElementById('tabla-mas-vendidos');
    tablaVendidos.innerHTML = masVendidos.length
      ? masVendidos.map((p) => `<tr><td>${p.nombre}</td><td>${p.cantidad_vendida}</td><td class="mono">${formatoMoneda(p.ganancia)}</td></tr>`).join('')
      : '<tr><td colspan="3">Todavia no hay ventas registradas</td></tr>';

    const entradasMes = Object.entries(resumen.por_mes || {});
    if (chartPorMes) chartPorMes.destroy();
    chartPorMes = new Chart(document.getElementById('chart-por-mes'), {
      type: 'bar',
      data: {
        labels: entradasMes.map(([mes]) => mes),
        datasets: [{ label: 'Total vendido', data: entradasMes.map(([, d]) => d.total), backgroundColor: '#0F5C4C', borderRadius: 6 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => formatoMoneda(v) } } },
      },
    });

    const tbody = document.getElementById('tabla-stock-bajo');
    tbody.innerHTML = stockBajo.length
      ? stockBajo.map((p) => `<tr><td>${p.nombre}</td><td>${p.stock_total}</td><td>${p.stock_minimo}</td></tr>`).join('')
      : '<tr><td colspan="3">Sin alertas de stock por ahora</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Categorias ----------
async function cargarCategorias() {
  try {
    categoriasCache = await apiFetch('/categorias');
    const opciones = '<option value="">Sin categoria</option>' +
      categoriasCache.map((c) => `<option value="${c.id}">${c.nombre}</option>`).join('');
    document.getElementById('select-categoria-nuevo-producto').innerHTML = opciones;
    document.getElementById('select-categoria-editar').innerHTML = opciones;

    const tbody = document.getElementById('tabla-categorias');
    tbody.innerHTML = categoriasCache.map((c) => `
      <tr>
        <td>${c.nombre}</td>
        <td>${c.notas || '-'}</td>
        <td><button class="btn-accion-tabla btn-inactivar-fila" data-id="${c.id}">Eliminar</button></td>
      </tr>
    `).join('') || '<tr><td colspan="3">Todavia no hay categorias</td></tr>';

    tbody.querySelectorAll('button[data-id]').forEach((btn) => {
      btn.addEventListener('click', () => eliminarCategoria(Number(btn.dataset.id)));
    });
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

document.getElementById('form-categoria').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await apiFetch('/categorias', {
      method: 'POST',
      body: { nombre: form.nombre.value.trim(), notas: form.notas.value.trim() || null },
    });
    mostrarToast('Categoria agregada', 'success');
    form.reset();
    cargarCategorias();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

async function eliminarCategoria(id) {
  if (!confirm('¿Eliminar esta categoria? Los productos que la usan quedaran sin categoria.')) return;
  try {
    await apiFetch(`/categorias/${id}`, { method: 'DELETE' });
    mostrarToast('Categoria eliminada', 'success');
    cargarCategorias();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Productos ----------
async function cargarProductos() {
  try {
    const verInactivos = document.getElementById('check-ver-inactivos').checked;
    productosCache = await apiFetch(`/productos?incluir_inactivos=${verInactivos}`);
    const tbody = document.getElementById('tabla-productos');
    tbody.innerHTML = productosCache.map((p) => {
      const categoria = categoriasCache.find((c) => c.id === p.categoria_id);
      return `
      <tr style="${p.activo ? '' : 'opacity:0.55;'}">
        <td>${p.imagen_url
          ? `<img class="miniatura" src="${p.imagen_url}" onerror="this.outerHTML='<div class=&quot;miniatura-placeholder&quot;>📦</div>'">`
          : '<div class="miniatura-placeholder">📦</div>'}</td>
        <td class="mono">${p.codigo}</td>
        <td>${p.nombre}</td>
        <td>${categoria ? categoria.nombre : '-'}</td>
        <td class="mono">${formatoMoneda(p.precio_venta)}</td>
        <td class="mono">${formatoMoneda(p.costo_promedio)}</td>
        <td>${p.iva_porcentaje}%</td>
        <td>${p.activo ? '<span class="badge badge-verde">Activo</span>' : '<span class="badge badge-rojo">Inactivo</span>'}</td>
        <td class="celda-acciones">
          <button class="btn-accion-tabla btn-editar-fila" data-id="${p.id}" data-accion="editar">Editar</button>
          ${p.activo
            ? `<button class="btn-accion-tabla btn-inactivar-fila" data-id="${p.id}" data-accion="inactivar">Inactivar</button>`
            : `<button class="btn-accion-tabla btn-reactivar-fila" data-id="${p.id}" data-accion="reactivar">Reactivar</button>`}
        </td>
      </tr>
    `;
    }).join('') || '<tr><td colspan="9">Todavia no hay productos cargados</td></tr>';

    tbody.querySelectorAll('[data-accion="editar"]').forEach((btn) => {
      btn.addEventListener('click', () => abrirModalEditar(Number(btn.dataset.id)));
    });
    tbody.querySelectorAll('[data-accion="inactivar"]').forEach((btn) => {
      btn.addEventListener('click', () => cambiarEstadoProducto(Number(btn.dataset.id), false));
    });
    tbody.querySelectorAll('[data-accion="reactivar"]').forEach((btn) => {
      btn.addEventListener('click', () => cambiarEstadoProducto(Number(btn.dataset.id), true));
    });
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

document.getElementById('check-ver-inactivos').addEventListener('change', cargarProductos);

document.getElementById('form-producto').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const datos = {
    codigo: form.codigo.value.trim(),
    nombre: form.nombre.value.trim(),
    categoria_id: form.categoria_id.value ? Number(form.categoria_id.value) : null,
    imagen_url: form.imagen_url.value.trim() || null,
    iva_porcentaje: Number(form.iva_porcentaje.value),
    precio_venta: Number(form.precio_venta.value),
    stock_minimo: Number(form.stock_minimo.value) || 0,
  };
  try {
    await apiFetch('/productos', { method: 'POST', body: datos });
    mostrarToast('Producto agregado', 'success');
    form.reset();
    form.iva_porcentaje.value = 21;
    cargarProductos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

async function cambiarEstadoProducto(id, activo) {
  try {
    await apiFetch(`/productos/${id}/estado?activo=${activo}`, { method: 'PUT' });
    mostrarToast(activo ? 'Producto reactivado' : 'Producto inactivado', 'success');
    cargarProductos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function abrirModalEditar(id) {
  const producto = productosCache.find((p) => p.id === id);
  if (!producto) return;
  const form = document.getElementById('form-editar-producto');
  form.dataset.productoId = id;
  form.nombre.value = producto.nombre;
  form.categoria_id.value = producto.categoria_id || '';
  form.imagen_url.value = producto.imagen_url || '';
  form.precio_venta.value = producto.precio_venta;
  form.iva_porcentaje.value = producto.iva_porcentaje;
  form.stock_minimo.value = producto.stock_minimo;
  const preview = document.getElementById('preview-imagen-editar');
  preview.src = producto.imagen_url || '';
  preview.style.display = producto.imagen_url ? 'block' : 'none';
  document.getElementById('modal-editar-producto').classList.add('visible');
}

document.getElementById('btn-cancelar-editar').addEventListener('click', () => {
  document.getElementById('modal-editar-producto').classList.remove('visible');
});

document.getElementById('form-editar-producto').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const id = form.dataset.productoId;
  try {
    await apiFetch(`/productos/${id}`, {
      method: 'PUT',
      body: {
        nombre: form.nombre.value.trim(),
        categoria_id: form.categoria_id.value ? Number(form.categoria_id.value) : null,
        imagen_url: form.imagen_url.value.trim() || null,
        precio_venta: Number(form.precio_venta.value),
        iva_porcentaje: Number(form.iva_porcentaje.value),
        stock_minimo: Number(form.stock_minimo.value),
      },
    });
    mostrarToast('Producto actualizado', 'success');
    document.getElementById('modal-editar-producto').classList.remove('visible');
    cargarProductos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

document.getElementById('btn-subir-imagen').addEventListener('click', async () => {
  const form = document.getElementById('form-editar-producto');
  const id = form.dataset.productoId;
  const input = document.getElementById('input-archivo-imagen');
  if (!input.files || input.files.length === 0) {
    mostrarToast('Elegi un archivo primero', 'error');
    return;
  }
  const formData = new FormData();
  formData.append('archivo', input.files[0]);
  try {
    const resp = await fetch(`${API_BASE}/productos/${id}/imagen`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${Sesion.token()}` },
      body: formData,
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'No se pudo subir la imagen');
    document.getElementById('preview-imagen-editar').src = data.imagen_url;
    document.getElementById('preview-imagen-editar').style.display = 'block';
    form.imagen_url.value = data.imagen_url;
    mostrarToast('Imagen subida', 'success');
    cargarProductos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

// ---------- Sucursales ----------
async function cargarSucursales() {
  try {
    sucursalesCache = await apiFetch('/sucursales');
    const tbody = document.getElementById('tabla-sucursales');
    tbody.innerHTML = sucursalesCache.map((s) => `<tr><td>${s.nombre}</td><td>${s.direccion || '-'}</td><td>${s.telefono || '-'}</td></tr>`).join('')
      || '<tr><td colspan="3">Todavia no hay sucursales</td></tr>';

    const checksUsuario = document.getElementById('checks-sucursal-usuario');
    checksUsuario.innerHTML = sucursalesCache.map((s) => `
      <label><input type="checkbox" name="sucursal_ids" value="${s.id}"> ${s.nombre}</label>
    `).join('') || '<span>Crea una sucursal primero</span>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

document.getElementById('form-sucursal').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await apiFetch('/sucursales', {
      method: 'POST',
      body: {
        nombre: form.nombre.value.trim(),
        direccion: form.direccion.value.trim() || null,
        telefono: form.telefono.value.trim() || null,
      },
    });
    mostrarToast('Sucursal agregada', 'success');
    form.reset();
    cargarSucursales();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

// ---------- Usuarios ----------
async function cargarUsuarios() {
  await cargarSucursales();
  try {
    const usuarios = await apiFetch('/usuarios');
    const tbody = document.getElementById('tabla-usuarios');
    tbody.innerHTML = usuarios.map((u) => {
      const nombresSucursales = (u.sucursales || []).map((s) => s.nombre).join(', ');
      return `<tr>
        <td>${u.nombre}</td>
        <td class="mono">${u.username}</td>
        <td><span class="badge ${u.rol === 'servidor' ? 'badge-verde' : 'badge-ambar'}">${u.rol === 'servidor' ? 'Servidor' : 'Punto de venta'}</span></td>
        <td>${nombresSucursales || '-'}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="4">Todavia no hay usuarios</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

document.getElementById('form-usuario').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await apiFetch('/usuarios', {
      method: 'POST',
      body: {
        nombre: form.nombre.value.trim(),
        username: form.username.value.trim(),
        password: form.password.value,
        rol: form.rol.value,
        sucursal_ids: Array.from(form.querySelectorAll('input[name="sucursal_ids"]:checked')).map((el) => Number(el.value)),
      },
    });
    mostrarToast('Usuario creado', 'success');
    form.reset();
    cargarUsuarios();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

// ---------- Proveedores ----------
async function cargarProveedores() {
  try {
    proveedoresCache = await apiFetch('/proveedores');
    const opciones = '<option value="">Proveedor principal (opcional)</option>' +
      proveedoresCache.map((p) => `<option value="${p.id}">${p.nombre}</option>`).join('');
    document.getElementById('compra-proveedor').innerHTML = opciones;
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

document.getElementById('form-proveedor').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await apiFetch('/proveedores', {
      method: 'POST',
      body: { nombre: form.nombre.value.trim(), cuit: form.cuit.value.trim() || null },
    });
    mostrarToast('Proveedor agregado', 'success');
    form.reset();
    cargarProveedores();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

// ---------- Compras ----------
async function cargarSucursalesParaCompra() {
  await cargarSucursales();
  const select = document.getElementById('compra-sucursal');
  select.innerHTML = sucursalesCache.map((s) => `<option value="${s.id}">${s.nombre}</option>`).join('')
    || '<option value="">Crea una sucursal primero</option>';
  if (productosCache.length === 0) productosCache = await apiFetch('/productos?incluir_inactivos=true');
  reiniciarDetalleCompra();
}

function reiniciarDetalleCompra() {
  const cont = document.getElementById('lista-detalle-compra');
  cont.innerHTML = '';
  agregarItemCompra();
}

function agregarItemCompra() {
  const cont = document.getElementById('lista-detalle-compra');
  const fila = document.createElement('div');
  fila.className = 'item-detalle-compra';
  const opcionesProveedor = '<option value="">(usar el de la compra)</option>' +
    proveedoresCache.map((p) => `<option value="${p.id}">${p.nombre}</option>`).join('');
  fila.innerHTML = `
    <select class="item-producto" required>
      <option value="">Producto...</option>
      ${productosCache.map((p) => `<option value="${p.id}" data-iva="${p.iva_porcentaje}">${p.codigo} - ${p.nombre}</option>`).join('')}
    </select>
    <input class="item-cantidad" type="number" min="1" placeholder="Cantidad" required>
    <input class="item-costo" type="number" step="0.01" min="0" placeholder="Costo neto c/u" required>
    <input class="item-iva" type="number" step="0.1" min="0" placeholder="IVA %" value="21">
    <select class="item-proveedor">${opcionesProveedor}</select>
    <input class="item-bultos" type="number" min="0" placeholder="Bultos">
    <button type="button" class="btn-quitar-item">✕</button>
  `;
  fila.querySelector('.item-producto').addEventListener('change', (e) => {
    const iva = e.target.selectedOptions[0]?.dataset.iva;
    if (iva) fila.querySelector('.item-iva').value = iva;
  });
  fila.querySelector('.btn-quitar-item').addEventListener('click', () => fila.remove());
  cont.appendChild(fila);
}

document.getElementById('btn-agregar-item-compra').addEventListener('click', agregarItemCompra);

document.getElementById('form-compra').addEventListener('submit', async (e) => {
  e.preventDefault();
  const filas = Array.from(document.querySelectorAll('.item-detalle-compra'));
  const detalles = filas.map((fila) => ({
    producto_id: Number(fila.querySelector('.item-producto').value),
    cantidad: Number(fila.querySelector('.item-cantidad').value),
    costo_unitario_neto: Number(fila.querySelector('.item-costo').value),
    iva_compra_porcentaje: Number(fila.querySelector('.item-iva').value) || 0,
    proveedor_id: fila.querySelector('.item-proveedor').value ? Number(fila.querySelector('.item-proveedor').value) : null,
    bultos: fila.querySelector('.item-bultos').value ? Number(fila.querySelector('.item-bultos').value) : null,
  })).filter((d) => d.producto_id && d.cantidad > 0);

  if (detalles.length === 0) {
    mostrarToast('Agrega al menos un producto a la compra', 'error');
    return;
  }

  try {
    await apiFetch('/compras', {
      method: 'POST',
      body: {
        sucursal_id: Number(document.getElementById('compra-sucursal').value),
        proveedor_id: document.getElementById('compra-proveedor').value ? Number(document.getElementById('compra-proveedor').value) : null,
        numero_comprobante: document.getElementById('compra-comprobante').value.trim() || null,
        detalles,
      },
    });
    mostrarToast('Compra registrada, stock y costo actualizados', 'success');
    document.getElementById('compra-comprobante').value = '';
    reiniciarDetalleCompra();
    productosCache = await apiFetch('/productos?incluir_inactivos=true');
    cargarCompras();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

async function cargarCompras() {
  try {
    const compras = await apiFetch('/compras');
    const tbody = document.getElementById('tabla-compras');
    tbody.innerHTML = compras.map((c) => {
      const bultosTotal = c.detalles.reduce((acc, d) => acc + (d.bultos || 0), 0);
      return `
      <tr>
        <td>${new Date(c.fecha).toLocaleString('es-AR')}</td>
        <td>${c.numero_comprobante || '-'}</td>
        <td>${c.detalles.reduce((acc, d) => acc + d.cantidad, 0)} unidades</td>
        <td>${bultosTotal || '-'}</td>
      </tr>
    `;
    }).join('') || '<tr><td colspan="4">Todavia no hay compras</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Turnos de caja ----------
async function cargarTurnos() {
  try {
    const turnos = await apiFetch('/turnos');
    const tbody = document.getElementById('tabla-turnos');
    tbody.innerHTML = turnos.map((t) => {
      let claseDif = 'dif-exacta';
      let textoDif = '-';
      if (t.diferencia !== null && t.diferencia !== undefined) {
        claseDif = t.diferencia > 0 ? 'dif-positiva' : t.diferencia < 0 ? 'dif-negativa' : 'dif-exacta';
        textoDif = formatoMoneda(t.diferencia);
      }
      return `<tr>
        <td>Turno N°${t.numero}</td>
        <td>${new Date(t.fecha_apertura).toLocaleString('es-AR')}</td>
        <td>${t.fecha_cierre ? new Date(t.fecha_cierre).toLocaleString('es-AR') : '<span class="badge badge-verde">Abierto</span>'}</td>
        <td class="mono">${formatoMoneda(t.monto_apertura)}</td>
        <td class="mono">${t.monto_esperado_cierre !== null && t.monto_esperado_cierre !== undefined ? formatoMoneda(t.monto_esperado_cierre) : '-'}</td>
        <td class="mono">${t.monto_contado_cierre !== null && t.monto_contado_cierre !== undefined ? formatoMoneda(t.monto_contado_cierre) : '-'}</td>
        <td class="mono ${claseDif}">${textoDif}</td>
      </tr>`;
    }).join('') || '<tr><td colspan="7">Todavia no hay turnos registrados</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Informes ----------
document.getElementById('btn-filtrar-informe').addEventListener('click', cargarInformeVentas);

async function cargarSelectorTurnosInforme() {
  try {
    const turnos = await apiFetch('/turnos');
    const select = document.getElementById('informe-turno');
    select.innerHTML = '<option value="">Todos los turnos</option>' +
      turnos.map((t) => `<option value="${t.id}">Turno N°${t.numero} · ${new Date(t.fecha_apertura).toLocaleDateString('es-AR')}</option>`).join('');
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function construirQueryInforme() {
  const desde = document.getElementById('informe-desde').value;
  const hasta = document.getElementById('informe-hasta').value;
  const turnoId = document.getElementById('informe-turno').value;
  const query = new URLSearchParams();
  if (desde) query.set('desde', `${desde}T00:00:00`);
  if (hasta) query.set('hasta', `${hasta}T23:59:59`);
  if (turnoId) query.set('turno_id', turnoId);
  return query;
}

async function cargarInformeVentas() {
  const queryVentas = construirQueryInforme();
  queryVentas.set('incluir_anuladas', 'true');

  try {
    const ventas = await apiFetch(`/reportes/ventas-detalladas?${queryVentas.toString()}`);
    const tbody = document.getElementById('tabla-informe-ventas');
    tbody.innerHTML = ventas.map((v) => `
      <tr style="${v.estado === 'anulada' ? 'opacity:0.55;' : ''}">
        <td>${v.turno_numero ? `Turno N°${v.turno_numero}` : '-'}</td>
        <td>${new Date(v.fecha).toLocaleString('es-AR')}</td>
        <td class="mono">${v.numero_comprobante || '-'}</td>
        <td class="mono">${formatoMoneda(v.total)}</td>
        <td class="mono">${formatoMoneda(v.propina)}</td>
        <td class="mono">${formatoMoneda(v.ganancia_total)}</td>
        <td>${v.metodos_pago.map((m) => `${NOMBRES_METODO[m.metodo] || m.metodo}${m.banco ? ` (${m.banco})` : ''}: ${formatoMoneda(m.monto)}`).join(', ')}</td>
        <td>${v.estado === 'anulada' ? '<span class="badge-anulada-tabla">Anulada</span>' : '<span class="badge badge-verde">Activa</span>'}</td>
      </tr>
    `).join('') || '<tr><td colspan="8">No hay ventas en ese periodo</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }

  const queryMasVendidos = construirQueryInforme();
  queryMasVendidos.set('limite', '15');
  try {
    const masVendidos = await apiFetch(`/reportes/productos-mas-vendidos?${queryMasVendidos.toString()}`);
    const tbody = document.getElementById('tabla-informe-mas-vendidos');
    tbody.innerHTML = masVendidos.map((p) => `
      <tr>
        <td>${p.nombre}</td>
        <td>${p.cantidad_vendida}</td>
        <td class="mono">${formatoMoneda(p.total_facturado)}</td>
        <td class="mono">${formatoMoneda(p.ganancia)}</td>
      </tr>
    `).join('') || '<tr><td colspan="4">No hay ventas en ese periodo</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Configuracion del negocio ----------
async function cargarConfigFiscal() {
  try {
    const config = await apiFetch('/config-fiscal');
    pintarSeleccionRegimen(config.regimen);
    document.getElementById('input-razon-social').value = config.razon_social || '';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function pintarSeleccionRegimen(regimen) {
  document.getElementById('opcion-monotributo').classList.toggle('seleccionada', regimen === 'monotributo');
  document.getElementById('opcion-ri').classList.toggle('seleccionada', regimen === 'responsable_inscripto');
}

document.getElementById('opcion-monotributo').addEventListener('click', () => cambiarConfigNegocio({ regimen: 'monotributo' }));
document.getElementById('opcion-ri').addEventListener('click', () => cambiarConfigNegocio({ regimen: 'responsable_inscripto' }));

document.getElementById('form-razon-social').addEventListener('submit', async (e) => {
  e.preventDefault();
  await cambiarConfigNegocio({ razon_social: document.getElementById('input-razon-social').value.trim() || null });
  cargarNombreNegocio();
});

async function cambiarConfigNegocio(cambios) {
  try {
    const actual = await apiFetch('/config-fiscal');
    const config = await apiFetch('/config-fiscal', {
      method: 'PUT',
      body: {
        razon_social: cambios.razon_social !== undefined ? cambios.razon_social : actual.razon_social,
        regimen: cambios.regimen || actual.regimen,
      },
    });
    pintarSeleccionRegimen(config.regimen);
    mostrarToast('Configuracion actualizada', 'success');
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Inventario ----------
async function cargarInventario() {
  await cargarSucursales();
  if (productosCache.length === 0) productosCache = await apiFetch('/productos?incluir_inactivos=true');
  const select = document.getElementById('conteo-sucursal');
  select.innerHTML = '<option value="">Elegi una sucursal</option>' +
    sucursalesCache.map((s) => `<option value="${s.id}">${s.nombre}</option>`).join('');
  document.getElementById('tabla-conteo-form').innerHTML = '<tr><td colspan="3">Elegi una sucursal</td></tr>';
  cargarHistorialConteos();
}

document.getElementById('conteo-sucursal').addEventListener('change', async (e) => {
  const sucursalId = e.target.value;
  const tbody = document.getElementById('tabla-conteo-form');
  if (!sucursalId) {
    tbody.innerHTML = '<tr><td colspan="3">Elegi una sucursal</td></tr>';
    return;
  }
  tbody.innerHTML = '<tr><td colspan="3">Cargando productos...</td></tr>';
  try {
    const productos = await apiFetch(`/productos?sucursal_id=${sucursalId}`);
    tbody.innerHTML = productos.map((p) => `
      <tr data-producto-id="${p.id}">
        <td>${p.nombre}</td>
        <td class="mono">${p.stock_disponible}</td>
        <td><input type="number" min="0" class="input-cantidad-contada" value="${p.stock_disponible}" style="width:100px;"></td>
      </tr>
    `).join('') || '<tr><td colspan="3">No hay productos en esta sucursal</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

document.getElementById('btn-registrar-conteo').addEventListener('click', async () => {
  const sucursalId = document.getElementById('conteo-sucursal').value;
  if (!sucursalId) {
    mostrarToast('Elegi una sucursal primero', 'error');
    return;
  }
  const filas = Array.from(document.querySelectorAll('#tabla-conteo-form tr[data-producto-id]'));
  const detalles = filas.map((fila) => ({
    producto_id: Number(fila.dataset.productoId),
    cantidad_contada: Number(fila.querySelector('.input-cantidad-contada').value) || 0,
  }));

  try {
    const conteo = await apiFetch('/inventario/conteos', {
      method: 'POST',
      body: {
        sucursal_id: Number(sucursalId),
        notas: document.getElementById('conteo-notas').value.trim() || null,
        detalles,
      },
    });
    const conDesvio = conteo.detalles.filter((d) => d.diferencia !== 0).length;
    mostrarToast(
      conDesvio > 0 ? `Conteo registrado: ${conDesvio} producto(s) con desvio, stock corregido` : 'Conteo registrado: todo coincidia con el sistema',
      'success'
    );
    document.getElementById('conteo-notas').value = '';
    document.getElementById('conteo-sucursal').dispatchEvent(new Event('change'));
    cargarHistorialConteos();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

let conteosCache = [];

async function cargarHistorialConteos() {
  try {
    conteosCache = await apiFetch('/inventario/conteos');
    const tbody = document.getElementById('tabla-historial-conteos');
    tbody.innerHTML = conteosCache.map((c) => {
      const conDesvio = c.detalles.filter((d) => d.diferencia !== 0).length;
      return `
      <tr>
        <td>${new Date(c.fecha).toLocaleString('es-AR')}</td>
        <td>${c.notas || '-'}</td>
        <td>${conDesvio > 0 ? `<span class="badge badge-ambar">${conDesvio} producto(s)</span>` : '<span class="badge badge-verde">Sin desvios</span>'}</td>
        <td><button class="btn-accion-tabla btn-editar-fila" data-id="${c.id}">Ver detalle</button></td>
      </tr>
    `;
    }).join('') || '<tr><td colspan="4">Todavia no hay conteos registrados</td></tr>';

    tbody.querySelectorAll('button[data-id]').forEach((btn) => {
      btn.addEventListener('click', () => abrirDetalleConteo(Number(btn.dataset.id)));
    });
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

function abrirDetalleConteo(id) {
  const conteo = conteosCache.find((c) => c.id === id);
  if (!conteo) return;
  const tbody = document.getElementById('tabla-detalle-conteo');
  tbody.innerHTML = conteo.detalles.map((d) => {
    const producto = productosCache.find((p) => p.id === d.producto_id);
    const claseDif = d.diferencia > 0 ? 'dif-positiva' : d.diferencia < 0 ? 'dif-negativa' : 'dif-exacta';
    return `<tr>
      <td>${producto ? producto.nombre : `Producto #${d.producto_id}`}</td>
      <td class="mono">${d.stock_sistema}</td>
      <td class="mono">${d.cantidad_contada}</td>
      <td class="mono ${claseDif}">${d.diferencia > 0 ? '+' : ''}${d.diferencia}</td>
    </tr>`;
  }).join('');
  document.getElementById('modal-detalle-conteo').classList.add('visible');
}

document.getElementById('btn-cerrar-detalle-conteo').addEventListener('click', () => {
  document.getElementById('modal-detalle-conteo').classList.remove('visible');
});

// ---------- Kardex (libro de movimientos) ----------
document.getElementById('btn-filtrar-kardex').addEventListener('click', cargarKardex);

async function cargarKardex() {
  const desde = document.getElementById('kardex-desde').value;
  const hasta = document.getElementById('kardex-hasta').value;
  const query = new URLSearchParams();
  if (desde) query.set('desde', `${desde}T00:00:00`);
  if (hasta) query.set('hasta', `${hasta}T23:59:59`);

  try {
    const filas = await apiFetch(`/reportes/kardex?${query.toString()}`);
    const tbody = document.getElementById('tabla-kardex');
    tbody.innerHTML = filas.map((f) => `
      <tr>
        <td>${f.nombre}</td>
        <td class="mono">${f.ingresos}</td>
        <td class="mono">${f.compras}</td>
        <td class="mono">${f.salidas}</td>
        <td class="mono">${f.ventas}</td>
        <td class="mono">${f.stock_actual}</td>
      </tr>
    `).join('') || '<tr><td colspan="6">No hay movimientos en ese periodo</td></tr>';
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Formas de pago (bancos/proveedores) ----------
async function cargarFormasPago() {
  try {
    const formas = await apiFetch('/formas-pago?incluir_inactivas=true');
    const tbody = document.getElementById('tabla-formas-pago');
    tbody.innerHTML = formas.map((f) => `
      <tr>
        <td>${NOMBRES_METODO[f.tipo] || f.tipo}</td>
        <td>${f.nombre}</td>
        <td>${f.activo ? '<span class="badge badge-verde">Activa</span>' : '<span class="badge badge-rojo">Inactiva</span>'}</td>
        <td>
          ${f.activo
            ? `<button class="btn-accion-tabla btn-inactivar-fila" data-id="${f.id}" data-accion="inactivar">Inactivar</button>`
            : `<button class="btn-accion-tabla btn-reactivar-fila" data-id="${f.id}" data-accion="reactivar">Reactivar</button>`}
        </td>
      </tr>
    `).join('') || '<tr><td colspan="4">Todavia no hay bancos/proveedores cargados</td></tr>';

    tbody.querySelectorAll('[data-accion="inactivar"]').forEach((btn) => {
      btn.addEventListener('click', () => cambiarEstadoFormaPago(Number(btn.dataset.id), false));
    });
    tbody.querySelectorAll('[data-accion="reactivar"]').forEach((btn) => {
      btn.addEventListener('click', () => cambiarEstadoFormaPago(Number(btn.dataset.id), true));
    });
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

document.getElementById('form-forma-pago').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  try {
    await apiFetch('/formas-pago', {
      method: 'POST',
      body: { tipo: form.tipo.value, nombre: form.nombre.value.trim() },
    });
    mostrarToast('Agregado', 'success');
    form.nombre.value = '';
    cargarFormasPago();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
});

async function cambiarEstadoFormaPago(id, activo) {
  try {
    await apiFetch(`/formas-pago/${id}/estado?activo=${activo}`, { method: 'PUT' });
    mostrarToast(activo ? 'Reactivado' : 'Inactivado', 'success');
    cargarFormasPago();
  } catch (err) {
    mostrarToast(err.message, 'error');
  }
}

// ---------- Inicio ----------
cargarResumen();
