import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, UniqueConstraint, Table
)
from sqlalchemy.orm import relationship

from app.database import Base


class RolUsuario(str, enum.Enum):
    SERVIDOR = "servidor"   # backoffice: productos, compras, config, reportes
    POS = "pos"              # punto de venta: solo vender y consultar stock


class RegimenFiscal(str, enum.Enum):
    MONOTRIBUTO = "monotributo"
    RESPONSABLE_INSCRIPTO = "responsable_inscripto"


class MetodoPago(str, enum.Enum):
    EFECTIVO = "efectivo"
    DEBITO = "debito"
    CREDITO = "credito"
    TRANSFERENCIA = "transferencia"
    QR = "qr"


class EstadoTurno(str, enum.Enum):
    ABIERTO = "abierto"
    CERRADO = "cerrado"


class EstadoVenta(str, enum.Enum):
    ACTIVA = "activa"
    ANULADA = "anulada"


class TipoMovimientoCaja(str, enum.Enum):
    INGRESO = "ingreso"
    EGRESO = "egreso"


class TipoMovimientoStock(str, enum.Enum):
    COMPRA = "compra"
    VENTA = "venta"
    ANULACION = "anulacion"       # repone stock de una venta anulada
    AJUSTE_MANUAL = "ajuste_manual"
    CONTEO = "conteo"              # correccion generada por un conteo fisico de inventario


usuario_sucursales = Table(
    "usuario_sucursales",
    Base.metadata,
    Column("usuario_id", Integer, ForeignKey("usuarios.id"), primary_key=True),
    Column("sucursal_id", Integer, ForeignKey("sucursales.id"), primary_key=True),
)


class Sucursal(Base):
    __tablename__ = "sucursales"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    direccion = Column(String, nullable=True)
    telefono = Column(String, nullable=True)

    usuarios = relationship("Usuario", secondary=usuario_sucursales, back_populates="sucursales")
    stocks = relationship("Stock", back_populates="sucursal")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    rol = Column(Enum(RolUsuario), nullable=False, default=RolUsuario.POS)
    activo = Column(Boolean, default=True)

    sucursales = relationship("Sucursal", secondary=usuario_sucursales, back_populates="usuarios")


class Categoria(Base):
    """Grupo/rubro de productos (ej: Hamburguesas, Bebidas) para organizar el catalogo."""
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, nullable=False)
    notas = Column(String, nullable=True)
    stockeable = Column(Boolean, nullable=False, default=True)
    visible_pos = Column(Boolean, nullable=False, default=True)

    productos = relationship("Producto", back_populates="categoria_rel")


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=False)
    nombre = Column(String, nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    imagen_url = Column(String, nullable=True)
    iva_porcentaje = Column(Float, nullable=False, default=21.0)
    precio_venta = Column(Float, nullable=False, default=0.0)
    costo_promedio = Column(Float, nullable=False, default=0.0)
    stock_minimo = Column(Integer, nullable=False, default=0)
    activo = Column(Boolean, default=True)
    insumo_id = Column(Integer, ForeignKey("productos.id"), nullable=True)
    insumo_cantidad = Column(Integer, nullable=True, default=1)

    stocks = relationship("Stock", back_populates="producto")
    categoria_rel = relationship("Categoria", back_populates="productos")
    insumo = relationship("Producto", remote_side="Producto.id")

    @property
    def insumo_nombre(self):
        return self.insumo.nombre if self.insumo else None


class Stock(Base):
    __tablename__ = "stock"
    __table_args__ = (UniqueConstraint("producto_id", "sucursal_id", name="uq_stock_producto_sucursal"),)

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=0)

    producto = relationship("Producto", back_populates="stocks")
    sucursal = relationship("Sucursal", back_populates="stocks")


class MovimientoStock(Base):
    """Libro historico de TODOS los cambios de stock: compras, ventas, anulaciones,
    ajustes manuales y correcciones por conteo fisico. Es lo que permite armar el
    reporte de ingresos/compras/salidas/ventas/stock por producto y periodo."""
    __tablename__ = "movimientos_stock"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    tipo = Column(Enum(TipoMovimientoStock), nullable=False)
    cantidad = Column(Integer, nullable=False)          # positivo = entrada, negativo = salida
    saldo_posterior = Column(Integer, nullable=False)    # stock resultante despues de este movimiento
    referencia_id = Column(Integer, nullable=True)       # id de la compra/venta/conteo que lo origino
    notas = Column(String, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

    producto = relationship("Producto")
    sucursal = relationship("Sucursal")


class ConteoInventario(Base):
    """Conteo fisico de stock en una sucursal, en una fecha. Comparado contra el stock
    del sistema en ese momento, revela el desvio (merma o sobrante) por producto."""
    __tablename__ = "conteos_inventario"

    id = Column(Integer, primary_key=True, index=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)
    notas = Column(String, nullable=True)

    sucursal = relationship("Sucursal")
    detalles = relationship("ConteoInventarioDetalle", back_populates="conteo", cascade="all, delete-orphan")


class ConteoInventarioDetalle(Base):
    __tablename__ = "conteos_inventario_detalle"

    id = Column(Integer, primary_key=True, index=True)
    conteo_id = Column(Integer, ForeignKey("conteos_inventario.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    stock_sistema = Column(Integer, nullable=False)   # lo que el sistema decia antes de corregir
    cantidad_contada = Column(Integer, nullable=False)  # lo que se conto fisicamente
    diferencia = Column(Integer, nullable=False)        # contada - sistema (+ sobrante / - faltante)

    conteo = relationship("ConteoInventario", back_populates="detalles")
    producto = relationship("Producto")


class Proveedor(Base):
    __tablename__ = "proveedores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    cuit = Column(String, nullable=True)


class Compra(Base):
    __tablename__ = "compras"

    id = Column(Integer, primary_key=True, index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)
    numero_comprobante = Column(String, nullable=True)

    detalles = relationship("CompraDetalle", back_populates="compra", cascade="all, delete-orphan")


class CompraDetalle(Base):
    __tablename__ = "compras_detalle"

    id = Column(Integer, primary_key=True, index=True)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"), nullable=True)  # override puntual del proveedor de la compra
    bultos = Column(Integer, nullable=True)
    cantidad = Column(Integer, nullable=False)
    costo_unitario_neto = Column(Float, nullable=False)  # precio de compra SIN IVA
    iva_compra_porcentaje = Column(Float, nullable=False, default=21.0)
    costo_unitario_final = Column(Float, nullable=False)  # neto o neto+IVA segun regimen vigente al momento

    compra = relationship("Compra", back_populates="detalles")
    producto = relationship("Producto")
    proveedor = relationship("Proveedor")


class Turno(Base):
    """Turno de caja: se abre con un monto inicial en efectivo y se cierra con un arqueo
    (conteo de billetes/monedas) que se compara contra lo esperado segun las ventas en efectivo
    y los movimientos de caja (ingresos/egresos) registrados durante el turno."""
    __tablename__ = "turnos"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False)  # correlativo por sucursal: Turno N°1, N°2...
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    estado = Column(Enum(EstadoTurno), nullable=False, default=EstadoTurno.ABIERTO)

    fecha_apertura = Column(DateTime, default=datetime.utcnow)
    monto_apertura = Column(Float, nullable=False, default=0.0)

    fecha_cierre = Column(DateTime, nullable=True)
    monto_contado_cierre = Column(Float, nullable=True)       # total contado en el arqueo
    detalle_arqueo = Column(String, nullable=True)            # JSON: {"20000": 3, "10000": 1, ...}
    monto_esperado_cierre = Column(Float, nullable=True)      # apertura + ventas efectivo + ingresos - egresos
    diferencia = Column(Float, nullable=True)                 # contado - esperado (+ sobrante / - faltante)
    notas_cierre = Column(String, nullable=True)

    usuario = relationship("Usuario")
    sucursal = relationship("Sucursal")
    ventas = relationship("Venta", back_populates="turno")
    movimientos = relationship("MovimientoCaja", back_populates="turno")


class MovimientoCaja(Base):
    """Ingreso o egreso de efectivo que no es una venta (ej: pago a proveedor, retiro, aporte)."""
    __tablename__ = "movimientos_caja"

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(Enum(TipoMovimientoCaja), nullable=False)
    monto = Column(Float, nullable=False)
    motivo = Column(String, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

    turno = relationship("Turno", back_populates="movimientos")


class Cliente(Base):
    """Cliente registrado opcionalmente en una venta (nombre, apellido, telefono, direccion).
    Permite buscar/reutilizar clientes ya cargados y analizar su historial de compras."""
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    direccion = Column(String, nullable=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip() if self.apellido else self.nombre


class Venta(Base):
    __tablename__ = "ventas"

    id = Column(Integer, primary_key=True, index=True)
    id_cliente = Column(String, unique=True, nullable=True, index=True)  # UUID generado en el POS; evita duplicar al reintentar
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)  # cliente registrado (opcional), distinto del UUID de arriba
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=True)
    estado = Column(Enum(EstadoVenta), nullable=False, default=EstadoVenta.ACTIVA)
    anulada_en = Column(DateTime, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)
    numero_comprobante = Column(String, nullable=True)
    total = Column(Float, nullable=False, default=0.0)       # total de productos (sin propina)
    propina = Column(Float, nullable=False, default=0.0)
    total_neto = Column(Float, nullable=False, default=0.0)
    total_iva = Column(Float, nullable=False, default=0.0)
    ganancia_total = Column(Float, nullable=False, default=0.0)

    detalles = relationship("VentaDetalle", back_populates="venta", cascade="all, delete-orphan")
    pagos = relationship("VentaPago", back_populates="venta", cascade="all, delete-orphan")
    turno = relationship("Turno", back_populates="ventas")
    cliente = relationship("Cliente")


class FormaPagoDetalle(Base):
    """Catalogo de bancos/proveedores por tipo de pago (ej: bajo Debito -> 'Banco Galicia',
    bajo QR -> 'Mercado Pago', 'MODO'). Se gestiona desde el backoffice y se elige en el POS
    cuando la venta se cobra con debito, credito, QR o transferencia."""
    __tablename__ = "formas_pago_detalle"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(Enum(MetodoPago), nullable=False)
    nombre = Column(String, nullable=False)
    activo = Column(Boolean, default=True)


class VentaPago(Base):
    """Un pago dentro de una venta. La mayoria de las ventas tienen un solo pago,
    pero se admite dividir el cobro entre varias formas de pago."""
    __tablename__ = "ventas_pago"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    metodo_pago = Column(Enum(MetodoPago), nullable=False)
    forma_pago_detalle_id = Column(Integer, ForeignKey("formas_pago_detalle.id"), nullable=True)
    monto = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="pagos")
    forma_pago_detalle = relationship("FormaPagoDetalle")

    @property
    def forma_pago_nombre(self):
        return self.forma_pago_detalle.nombre if self.forma_pago_detalle else None


class VentaDetalle(Base):
    __tablename__ = "ventas_detalle"

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario_venta = Column(Float, nullable=False)  # precio final que paga el cliente
    precio_unitario_neto = Column(Float, nullable=False)   # sin IVA (o igual al de venta si es monotributo)
    costo_unitario_momento = Column(Float, nullable=False)
    ganancia_unitaria = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="detalles")
    producto = relationship("Producto")


class ConfiguracionFiscal(Base):
    """Fila unica que define el nombre del negocio y el regimen fiscal vigente."""
    __tablename__ = "configuracion_fiscal"

    id = Column(Integer, primary_key=True, index=True)
    razon_social = Column(String, nullable=True)
    regimen = Column(Enum(RegimenFiscal), nullable=False, default=RegimenFiscal.MONOTRIBUTO)
