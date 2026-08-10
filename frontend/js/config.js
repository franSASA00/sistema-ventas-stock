// Si la pagina se abre desde localhost/127.0.0.1 (modo local), usa el backend local.
// En produccion (Render u otro dominio) no hace nada, y api.js usa la URL de produccion.
if (['localhost', '127.0.0.1'].includes(window.location.hostname)) {
  window.API_BASE_URL = 'http://127.0.0.1:8000';
}
