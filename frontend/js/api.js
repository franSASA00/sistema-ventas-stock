// Cambiar por la URL del backend cuando este desplegado (ej: https://mi-app.onrender.com)
const API_BASE = window.API_BASE_URL || 'http://127.0.0.1:8000';

const Sesion = {
  guardar(token, rol, nombre, sucursalId) {
    localStorage.setItem('vs_token', token);
    localStorage.setItem('vs_rol', rol);
    localStorage.setItem('vs_nombre', nombre);
    if (sucursalId !== undefined && sucursalId !== null) {
      localStorage.setItem('vs_sucursal_id', sucursalId);
    }
  },
  token() { return localStorage.getItem('vs_token'); },
  rol() { return localStorage.getItem('vs_rol'); },
  nombre() { return localStorage.getItem('vs_nombre'); },
  sucursalId() { return localStorage.getItem('vs_sucursal_id'); },
  cerrar() {
    localStorage.removeItem('vs_token');
    localStorage.removeItem('vs_rol');
    localStorage.removeItem('vs_nombre');
    localStorage.removeItem('vs_sucursal_id');
  },
  activa() { return !!this.token(); },
};

async function apiFetch(path, { method = 'GET', body = null, auth = true, timeoutMs = 6000 } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && Sesion.token()) {
    headers['Authorization'] = `Bearer ${Sesion.token()}`;
  }

  let resp;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    resp = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    clearTimeout(timer);
  } catch (err) {
    // fetch nunca llego a responder: no hay conexion con el servidor (no es un error de la app)
    const errorDeRed = new Error('Sin conexion con el servidor');
    errorDeRed.esErrorDeRed = true;
    throw errorDeRed;
  }

  if (resp.status === 401) {
    Sesion.cerrar();
    window.location.href = 'login.html';
    throw new Error('Sesion expirada');
  }

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detalle = data.detail || 'Ocurrio un error inesperado';
    throw new Error(typeof detalle === 'string' ? detalle : JSON.stringify(detalle));
  }
  return data;
}

async function login(username, password) {
  return apiFetch('/auth/login', { method: 'POST', body: { username, password }, auth: false });
}

function formatoMoneda(valor) {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(valor || 0);
}

function mostrarToast(mensaje, tipo = '') {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = mensaje;
  toast.className = `toast show ${tipo}`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 3200);
}
