from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Venta, VentaDetalle, VentaPago, Producto, Stock, Turno, MovimientoStock, TipoMovimientoStock, EstadoVenta, RolUsuario
from app.security import requiere_rol

router = APIRouter(prefix="/reportes", tags=["reportes"], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])

DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
NOMBRES_MES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _query_ventas_activas(db: Session, desde, hasta, sucursal_id, turno_id=None):
    query = db.query(Venta).filter(Venta.estado == EstadoVenta.ACTIVA)
    if desde:
        query = query.filter(Venta.fecha >= desde)
    if hasta:
        query = query.filter(Venta.fecha <= hasta)
    if sucursal_id:
        query = query.filter(Venta.sucursal_id == sucursal_id)
    if turno_id:
        query = query.filter(Venta.turno_id == turno_id)
    return query


@router.get("/resumen-ventas")
def resumen_ventas(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    sucursal_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    ventas = _query_ventas_activas(db, desde, hasta, sucursal_id).all()

    por_metodo = {}
    for v in ventas:
        for pago in v.pagos:
            metodo = pago.metodo_pago.value
            por_metodo.setdefault(metodo, {"cantidad": 0, "total": 0.0})
            por_metodo[metodo]["cantidad"] += 1
            por_metodo[metodo]["total"] += pago.monto
    for metodo in por_metodo:
        por_metodo[metodo]["total"] = round(por_metodo[metodo]["total"], 2)

    por_dia = {}
    for v in ventas:
        nombre_dia = DIAS_SEMANA[v.fecha.weekday()]
        por_dia.setdefault(nombre_dia, {"cantidad": 0, "total": 0.0})
        por_dia[nombre_dia]["cantidad"] += 1
        por_dia[nombre_dia]["total"] += v.total
    for dia in por_dia:
        por_dia[dia]["total"] = round(por_dia[dia]["total"], 2)
    # se devuelve tambien en orden fijo lunes a domingo, aunque el dict no lo garantice
    por_dia_ordenado = {dia: por_dia.get(dia, {"cantidad": 0, "total": 0.0}) for dia in DIAS_SEMANA}

    por_mes_bruto = {}
    for v in ventas:
        clave = (v.fecha.year, v.fecha.month)
        por_mes_bruto.setdefault(clave, {"cantidad": 0, "total": 0.0})
        por_mes_bruto[clave]["cantidad"] += 1
        por_mes_bruto[clave]["total"] += v.total
    por_mes_ordenado = {}
    for (anio, mes) in sorted(por_mes_bruto.keys()):
        etiqueta = f"{NOMBRES_MES[mes]} {anio}"
        datos = por_mes_bruto[(anio, mes)]
        por_mes_ordenado[etiqueta] = {"cantidad": datos["cantidad"], "total": round(datos["total"], 2)}

    return {
        "cantidad_ventas": len(ventas),
        "total_facturado": round(sum(v.total for v in ventas), 2),
        "total_neto": round(sum(v.total_neto for v in ventas), 2),
        "total_iva": round(sum(v.total_iva for v in ventas), 2),
        "total_propinas": round(sum(v.propina for v in ventas), 2),
        "ganancia_total": round(sum(v.ganancia_total for v in ventas), 2),
        "por_metodo_pago": por_metodo,
        "por_dia_semana": por_dia_ordenado,
        "por_mes": por_mes_ordenado,
    }


@router.get("/productos-mas-vendidos")
def productos_mas_vendidos(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    sucursal_id: Optional[int] = None,
    turno_id: Optional[int] = None,
    limite: int = 10,
    db: Session = Depends(get_db),
):
    ventas_ids = [v.id for v in _query_ventas_activas(db, desde, hasta, sucursal_id, turno_id).all()]
    if not ventas_ids:
        return []

    filas = (
        db.query(
            VentaDetalle.producto_id,
            func.sum(VentaDetalle.cantidad).label("cantidad_vendida"),
            func.sum(VentaDetalle.cantidad * VentaDetalle.precio_unitario_venta).label("total_facturado"),
            func.sum(VentaDetalle.cantidad * VentaDetalle.ganancia_unitaria).label("ganancia"),
        )
        .filter(VentaDetalle.venta_id.in_(ventas_ids))
        .group_by(VentaDetalle.producto_id)
        .order_by(func.sum(VentaDetalle.cantidad).desc())
        .limit(limite)
        .all()
    )

    resultado = []
    for producto_id, cantidad, facturado, ganancia in filas:
        producto = db.query(Producto).get(producto_id)
        resultado.append({
            "producto_id": producto_id,
            "nombre": producto.nombre if producto else "(producto eliminado)",
            "cantidad_vendida": int(cantidad or 0),
            "total_facturado": round(facturado or 0, 2),
            "ganancia": round(ganancia or 0, 2),
        })
    return resultado


@router.get("/ventas-detalladas")
def ventas_detalladas(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    sucursal_id: Optional[int] = None,
    turno_id: Optional[int] = None,
    incluir_anuladas: bool = False,
    db: Session = Depends(get_db),
):
    """Listado linea por linea de ventas, para el informe de ventas del backoffice."""
    query = db.query(Venta)
    if not incluir_anuladas:
        query = query.filter(Venta.estado == EstadoVenta.ACTIVA)
    if desde:
        query = query.filter(Venta.fecha >= desde)
    if hasta:
        query = query.filter(Venta.fecha <= hasta)
    if sucursal_id:
        query = query.filter(Venta.sucursal_id == sucursal_id)
    if turno_id:
        query = query.filter(Venta.turno_id == turno_id)

    ventas = query.order_by(Venta.fecha.desc()).all()
    numeros_turno = {t.id: t.numero for t in db.query(Turno.id, Turno.numero).all()}

    return [{
        "id": v.id,
        "numero_comprobante": v.numero_comprobante,
        "fecha": v.fecha,
        "sucursal_id": v.sucursal_id,
        "turno_id": v.turno_id,
        "turno_numero": numeros_turno.get(v.turno_id),
        "estado": v.estado.value,
        "total": v.total,
        "propina": v.propina,
        "ganancia_total": v.ganancia_total,
        "metodos_pago": [{"metodo": p.metodo_pago.value, "monto": p.monto, "banco": p.forma_pago_nombre} for p in v.pagos],
    } for v in ventas]


@router.get("/stock-bajo")
def productos_stock_bajo(sucursal_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Producto, func.coalesce(func.sum(Stock.cantidad), 0).label("stock_total")).outerjoin(
        Stock, Stock.producto_id == Producto.id
    )
    if sucursal_id:
        query = query.filter(Stock.sucursal_id == sucursal_id)
    query = query.filter(Producto.activo == True).group_by(Producto.id)  # noqa: E712

    resultado = []
    for producto, stock_total in query.all():
        if stock_total <= producto.stock_minimo:
            resultado.append({
                "producto_id": producto.id,
                "nombre": producto.nombre,
                "stock_total": stock_total,
                "stock_minimo": producto.stock_minimo,
            })
    return resultado


@router.get("/kardex")
def kardex_stock(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    sucursal_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Libro de movimientos por producto: ingresos, compras, salidas, ventas y stock actual,
    en el periodo filtrado. Ingresos = anulaciones + ajustes/conteos positivos.
    Salidas = ajustes/conteos negativos (mermas). Compras y Ventas van aparte porque son
    los movimientos mas frecuentes y los que mas interesa distinguir."""
    query = db.query(MovimientoStock)
    if desde:
        query = query.filter(MovimientoStock.fecha >= desde)
    if hasta:
        query = query.filter(MovimientoStock.fecha <= hasta)
    if sucursal_id:
        query = query.filter(MovimientoStock.sucursal_id == sucursal_id)
    movimientos = query.all()

    acumulado = {}  # producto_id -> {compras, ventas, ingresos, salidas}
    for m in movimientos:
        fila = acumulado.setdefault(m.producto_id, {"compras": 0, "ventas": 0, "ingresos": 0, "salidas": 0})
        if m.tipo == TipoMovimientoStock.COMPRA:
            fila["compras"] += m.cantidad
        elif m.tipo == TipoMovimientoStock.VENTA:
            fila["ventas"] += abs(m.cantidad)
        elif m.tipo == TipoMovimientoStock.ANULACION:
            fila["ingresos"] += m.cantidad
        elif m.tipo in (TipoMovimientoStock.AJUSTE_MANUAL, TipoMovimientoStock.CONTEO):
            if m.cantidad > 0:
                fila["ingresos"] += m.cantidad
            else:
                fila["salidas"] += abs(m.cantidad)

    resultado = []
    for producto_id, datos in acumulado.items():
        producto = db.query(Producto).get(producto_id)
        if not producto:
            continue
        stock_query = db.query(func.coalesce(func.sum(Stock.cantidad), 0)).filter(Stock.producto_id == producto_id)
        if sucursal_id:
            stock_query = stock_query.filter(Stock.sucursal_id == sucursal_id)
        stock_actual = stock_query.scalar() or 0

        resultado.append({
            "producto_id": producto_id,
            "nombre": producto.nombre,
            "ingresos": datos["ingresos"],
            "compras": datos["compras"],
            "salidas": datos["salidas"],
            "ventas": datos["ventas"],
            "stock_actual": stock_actual,
        })

    resultado.sort(key=lambda r: r["nombre"])
    return resultado
