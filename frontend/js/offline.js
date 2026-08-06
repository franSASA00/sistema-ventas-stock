// Pequeño wrapper sobre IndexedDB para operar el POS sin conexion:
// - guarda una copia del catalogo de productos (para poder seguir vendiendo)
// - encola las ventas hechas offline hasta poder enviarlas al servidor

const OfflineDB = (() => {
  const NOMBRE_DB = 'ventas_stock_offline';
  const VERSION_DB = 1;
  let dbPromise = null;

  function abrir() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(NOMBRE_DB, VERSION_DB);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains('productos_cache')) {
          db.createObjectStore('productos_cache', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('ventas_pendientes')) {
          db.createObjectStore('ventas_pendientes', { keyPath: 'idCliente' });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  async function conStore(nombreStore, modo, fn) {
    const db = await abrir();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(nombreStore, modo);
      const store = tx.objectStore(nombreStore);
      const resultado = fn(store);
      tx.oncomplete = () => resolve(resultado);
      tx.onerror = () => reject(tx.error);
    });
  }

  return {
    async guardarProductosCache(productos) {
      await conStore('productos_cache', 'readwrite', (store) => {
        store.clear();
        productos.forEach((p) => store.put(p));
      });
    },

    async obtenerProductosCache() {
      const db = await abrir();
      return new Promise((resolve, reject) => {
        const tx = db.transaction('productos_cache', 'readonly');
        const req = tx.objectStore('productos_cache').getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    },

    async encolarVentaPendiente(idCliente, payload) {
      await conStore('ventas_pendientes', 'readwrite', (store) => {
        store.put({ idCliente, payload, intentos: 0, creadoEn: new Date().toISOString() });
      });
    },

    async obtenerVentasPendientes() {
      const db = await abrir();
      return new Promise((resolve, reject) => {
        const tx = db.transaction('ventas_pendientes', 'readonly');
        const req = tx.objectStore('ventas_pendientes').getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
      });
    },

    async eliminarVentaPendiente(idCliente) {
      await conStore('ventas_pendientes', 'readwrite', (store) => {
        store.delete(idCliente);
      });
    },

    async contarVentasPendientes() {
      const pendientes = await this.obtenerVentasPendientes();
      return pendientes.length;
    },
  };
})();

function generarUuid() {
  if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
  // Fallback simple para navegadores viejos
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
