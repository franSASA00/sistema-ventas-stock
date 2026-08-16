from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from app.models import RolUsuario, RegimenFiscal, MetodoPago, EstadoTurno, EstadoVenta, TipoMovimientoCaja, TipoMovimientoStock


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: RolUsuario
    nombre: str
    sucursales: List["SucursalOut"] = []


# ---------- Sucursal ----------
class SucursalBase(BaseModel):
    nombre: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None


class SucursalCreate(SucursalBase):
    pass


class SucursalOut(SucursalBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Usuario ----------
class UsuarioCreate(BaseModel):
    nombre: str
    username: str
    password: str
    rol: RolUsuario
    sucursal_ids: List[int] = []


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    username: str
    rol: RolUsuario
    sucursales: List["SucursalOut"] = []
    activo: bool


# ---------- Categorias ----------
class CategoriaCreate(BaseModel):
    nombre: str
    notas: Optional[str] = None
    stockeable: bool = True
    visible_pos: bool = True


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    notas: Optional[str] = None
    stockeable: Optional[bool] = None
    visible_pos: Optional[bool] = None


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    notas: Optional[str] = None
    stockeable: bool = True
    visible_pos: bool = True


# ---------- Producto ----------
class ProductoCreate(BaseModel):
    codigo: str
    nombre: str
    categoria_id: Optional[int] = None
    imagen_url: Optional[str] = None
    iva_porcentaje: float = 21.0
    precio_venta: float = 0.0
    stock_minimo: int = 0
    insumo_id: Optional[int] = None
    insumo_cantidad: Optional[int] = 1


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria_id: Optional[int] = None
    imagen_url: Optional[str] = None
    iva_porcentaje: Optional[float] = None
    precio_venta: Optional[float] = None
    stock_minimo: Optional[int] = None
    activo: Optional[bool] = None
    insumo_id: Optional[int] = None
    insumo_cantidad: Optional[int] = None


class ProductoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    categoria_id: Optional[int] = None
    imagen_url: Optional[str] = None
    iva_porcentaje: float
    precio_venta: float
    costo_promedio: float
    stock_minimo: int
    activo: bool
    insumo_id: Optional[int] = None
    insumo_cantidad: Optional[int] = None
    insumo_nombre: Optional[str] = None


class ProductoConStock(ProductoOut):
    stock_disponible: int = 0
    stockeable: bool = True


# ---------- Stock ----------
class StockAjuste(BaseModel):
    producto_id: int
    sucursal_id: int
    cantidad: int  # puede ser positivo o negativo (ajuste manual / merma)
    motivo: Optional[str] = None


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    producto_id: int
    sucursal_id: int
    cantidad: int


# ---------- Compras ----------
class CompraDetalleIn(BaseModel):
    producto_id: int
    cantidad: int
    costo_unitario_neto: float
    iva_compra_porcentaje: float = 21.0
    proveedor_id: Optional[int] = None
    bultos: Optional[int] = None


class CompraCreate(BaseModel):
    proveedor_id: Optional[int] = None
    sucursal_id: int
    numero_comprobante: Optional[str] = None
    detalles: List[CompraDetalleIn]


class CompraDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    producto_id: int
    cantidad: int
    costo_unitario_neto: float
    iva_compra_porcentaje: float
    costo_unitario_final: float
    proveedor_id: Optional[int] = None
    bultos: Optional[int] = None


class CompraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    proveedor_id: Optional[int]
    sucursal_id: int
    fecha: datetime
    numero_comprobante: Optional[str]
    detalles: List[CompraDetalleOut]


# ---------- Proveedor ----------
class ProveedorCreate(BaseModel):
    nombre: str
    cuit: Optional[str] = None


class ProveedorOut(ProveedorCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- Clientes ----------
class ClienteCreate(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None


class ClienteConEstadisticas(ClienteOut):
    total_compras: int = 0
    total_gastado: float = 0.0
    ultima_compra: Optional[datetime] = None


# ---------- Ventas ----------
class VentaDetalleIn(BaseModel):
    producto_id: int
    cantidad: int


class PagoIn(BaseModel):
    metodo_pago: MetodoPago
    monto: float
    forma_pago_detalle_id: Optional[int] = None


class VentaCreate(BaseModel):
    sucursal_id: int
    propina: float = 0.0
    pagos: List[PagoIn]
    detalles: List[VentaDetalleIn]
    id_cliente: Optional[str] = None       # UUID generado en el POS (idempotencia al reintentar)
    fecha_local: Optional[datetime] = None  # hora real de la venta si se hizo offline y se sincroniza despues
    cliente_id: Optional[int] = None       # cliente registrado (opcional)
    cliente_nombre_nuevo: Optional[str] = None    # si se carga un cliente nuevo desde el POS
    cliente_apellido_nuevo: Optional[str] = None
    cliente_telefono_nuevo: Optional[str] = None
    cliente_direccion_nueva: Optional[str] = None


class VentaDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    producto_id: int
    cantidad: int
    precio_unitario_venta: float
    precio_unitario_neto: float
    costo_unitario_momento: float
    ganancia_unitaria: float


class PagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metodo_pago: MetodoPago
    monto: float
    forma_pago_detalle_id: Optional[int] = None
    forma_pago_nombre: Optional[str] = None


class VentaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_cliente: Optional[str] = None
    cliente_id: Optional[int] = None
    cliente_nombre: Optional[str] = None
    cliente_frecuente: bool = False
    sucursal_id: int
    usuario_id: int
    turno_id: Optional[int]
    estado: EstadoVenta
    fecha: datetime
    numero_comprobante: Optional[str]
    total: float
    propina: float
    total_neto: float
    total_iva: float
    ganancia_total: float
    detalles: List[VentaDetalleOut]
    pagos: List[PagoOut]


# ---------- Turnos y caja ----------
class TurnoAbrir(BaseModel):
    sucursal_id: int
    monto_apertura: float = 0.0


class ConteoDenominacion(BaseModel):
    denominacion: float
    cantidad: int


class TurnoCerrar(BaseModel):
    conteo: List[ConteoDenominacion]
    notas_cierre: Optional[str] = None


class TurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    usuario_id: int
    sucursal_id: int
    estado: EstadoTurno
    fecha_apertura: datetime
    monto_apertura: float
    fecha_cierre: Optional[datetime]
    monto_contado_cierre: Optional[float]
    monto_esperado_cierre: Optional[float]
    diferencia: Optional[float]
    notas_cierre: Optional[str]


class TurnoResumen(BaseModel):
    monto_apertura: float
    ventas_efectivo: float
    total_ingresos: float
    total_egresos: float
    esperado: float


class MovimientoCajaCreate(BaseModel):
    tipo: TipoMovimientoCaja
    monto: float
    motivo: Optional[str] = None


class MovimientoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    turno_id: int
    usuario_id: int
    tipo: TipoMovimientoCaja
    monto: float
    motivo: Optional[str]
    fecha: datetime


# ---------- Configuracion fiscal / negocio ----------
class ConfiguracionFiscalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    razon_social: Optional[str] = None
    regimen: RegimenFiscal


class ConfiguracionFiscalUpdate(BaseModel):
    razon_social: Optional[str] = None
    regimen: RegimenFiscal


# ---------- Inventario: conteo fisico de stock ----------
class ConteoDetalleIn(BaseModel):
    producto_id: int
    cantidad_contada: int


class ConteoCreate(BaseModel):
    sucursal_id: int
    notas: Optional[str] = None
    detalles: List[ConteoDetalleIn]


class ConteoDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    producto_id: int
    stock_sistema: int
    cantidad_contada: int
    diferencia: int


class ConteoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sucursal_id: int
    usuario_id: int
    fecha: datetime
    notas: Optional[str]
    detalles: List[ConteoDetalleOut]


# ---------- Movimientos de stock (libro historico) ----------
class MovimientoStockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    producto_id: int
    sucursal_id: int
    tipo: TipoMovimientoStock
    cantidad: int
    saldo_posterior: int
    referencia_id: Optional[int]
    notas: Optional[str]
    fecha: datetime


class KardexProducto(BaseModel):
    producto_id: int
    nombre: str
    ingresos: int
    compras: int
    salidas: int
    ventas: int
    stock_actual: int


# ---------- Catalogo de bancos/proveedores por forma de pago ----------
class FormaPagoDetalleCreate(BaseModel):
    tipo: MetodoPago
    nombre: str


class FormaPagoDetalleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: MetodoPago
    nombre: str
    activo: bool

Token.model_rebuild()
UsuarioOut.model_rebuild()
