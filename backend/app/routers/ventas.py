from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculos import calcular_ganancia_unitaria
from app.database import get_db
from app.models import Venta, VentaDetalle, VentaPago, Producto, Stock, ConfiguracionFiscal, EstadoVenta, TipoMovimientoStock, RolUsuario
from app.movimientos import registrar_movimiento_stock
from app.routers.config_fiscal import _obtener_o_crear_config
from app.routers.turnos import turno_abierto_de
from app.schemas import VentaCreate, VentaOut
from app.security import requiere_rol, usuario_actual

router = APIRouter(prefix="/ventas", tags=["ventas"])


def _siguiente_numero_comprobante(db: Session, sucursal_id: int) -> str:
    cantidad = db.query(Venta).filter(Venta.sucursal_id == sucursal_id).count()
    return f"SUC{sucursal_id:03d}-{cantidad + 1:06d}"


@router.post("", response_model=VentaOut)
def registrar_venta(
    datos: VentaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(requiere_rol(RolUsuario.POS, RolUsuario.SERVIDOR)),
):
    if not datos.detalles:
        raise HTTPException(status_code=400, detail="La venta necesita al menos un producto")
    if not datos.pagos:
        raise HTTPException(status_code=400, detail="Elegi al menos una forma de pago")
    if datos.propina < 0:
        raise HTTPException(status_code=400, detail="La propina no puede ser negativa")

    # Idempotencia: si esta venta ya se proceso antes (ej: se reintento al reconectar
    # despues de vender offline), devolver la que ya existe en vez de duplicarla.
    if datos.id_cliente:
        existente = db.query(Venta).filter(Venta.id_cliente == datos.id_cliente).first()
        if existente:
            return existente

    # El usuario POS necesita un turno de caja abierto para poder vender.
    # El usuario servidor puede vender sin turno (uso ocasional desde el backoffice).
    turno = turno_abierto_de(db, usuario.id, datos.sucursal_id)
    if usuario.rol == RolUsuario.POS and not turno:
        raise HTTPException(
            status_code=409,
            detail="No tenes un turno de caja abierto. Abri turno antes de vender.",
        )

    config: ConfiguracionFiscal = _obtener_o_crear_config(db)

    # 1) Validar stock disponible de TODOS los items antes de tocar nada
    productos_y_stock = {}
    for item in datos.detalles:
        producto = db.query(Producto).get(item.producto_id)
        if not producto or not producto.activo:
            raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado")
        stock = db.query(Stock).filter(
            Stock.producto_id == producto.id, Stock.sucursal_id == datos.sucursal_id
        ).first()
        disponible = stock.cantidad if stock else 0
        if item.cantidad <= 0:
            raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
        if disponible < item.cantidad:
            raise HTTPException(
                status_code=409,
                detail=f"Stock insuficiente para '{producto.nombre}' (disponible: {disponible})",
            )
        productos_y_stock[item.producto_id] = (producto, stock)

    # 2) Crear la venta y sus detalles, descontando stock y calculando ganancia
    venta = Venta(
        sucursal_id=datos.sucursal_id,
        usuario_id=usuario.id,
        turno_id=turno.id if turno else None,
        propina=datos.propina,
        id_cliente=datos.id_cliente,
        numero_comprobante=_siguiente_numero_comprobante(db, datos.sucursal_id),
        fecha=datos.fecha_local or datetime.utcnow(),
    )
    db.add(venta)
    db.flush()

    total = total_neto = total_iva = ganancia_total = 0.0

    for item in datos.detalles:
        producto, stock = productos_y_stock[item.producto_id]

        calculo = calcular_ganancia_unitaria(
            config.regimen, producto.precio_venta, producto.iva_porcentaje, producto.costo_promedio
        )
        subtotal = round(producto.precio_venta * item.cantidad, 2)
        subtotal_neto = round(calculo["precio_neto"] * item.cantidad, 2)
        subtotal_iva = round(calculo["iva"] * item.cantidad, 2)
        subtotal_ganancia = round(calculo["ganancia"] * item.cantidad, 2)

        detalle = VentaDetalle(
            venta_id=venta.id,
            producto_id=producto.id,
            cantidad=item.cantidad,
            precio_unitario_venta=producto.precio_venta,
            precio_unitario_neto=calculo["precio_neto"],
            costo_unitario_momento=producto.costo_promedio,
            ganancia_unitaria=calculo["ganancia"],
        )
        db.add(detalle)

        registrar_movimiento_stock(
            db, producto.id, datos.sucursal_id, TipoMovimientoStock.VENTA, -item.cantidad, referencia_id=venta.id
        )

        total += subtotal
        total_neto += subtotal_neto
        total_iva += subtotal_iva
        ganancia_total += subtotal_ganancia

    venta.total = round(total, 2)
    venta.total_neto = round(total_neto, 2)
    venta.total_iva = round(total_iva, 2)
    venta.ganancia_total = round(ganancia_total, 2)

    # 3) Validar que los pagos cubran exactamente total + propina (con margen de centavos)
    total_a_cobrar = round(venta.total + venta.propina, 2)
    total_pagado = round(sum(p.monto for p in datos.pagos), 2)
    if abs(total_pagado - total_a_cobrar) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Los pagos suman {total_pagado} pero el total a cobrar es {total_a_cobrar}",
        )

    for pago in datos.pagos:
        if pago.monto <= 0:
            raise HTTPException(status_code=400, detail="Cada pago debe ser mayor a 0")
        db.add(VentaPago(
            venta_id=venta.id,
            metodo_pago=pago.metodo_pago,
            forma_pago_detalle_id=pago.forma_pago_detalle_id,
            monto=pago.monto,
        ))

    db.commit()
    db.refresh(venta)
    return venta


@router.post("/{venta_id}/anular", response_model=VentaOut)
def anular_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(requiere_rol(RolUsuario.POS, RolUsuario.SERVIDOR)),
):
    """Anula una venta y repone el stock vendido. Un usuario POS solo puede anular ventas
    de su turno abierto actual; el servidor puede anular cualquier venta activa."""
    venta = db.query(Venta).get(venta_id)
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if venta.estado == EstadoVenta.ANULADA:
        raise HTTPException(status_code=400, detail="Esta venta ya esta anulada")

    if usuario.rol == RolUsuario.POS:
        turno = turno_abierto_de(db, usuario.id, venta.sucursal_id)
        if not turno or venta.turno_id != turno.id:
            raise HTTPException(status_code=403, detail="Solo podes anular ventas de tu turno actual")

    for detalle in venta.detalles:
        registrar_movimiento_stock(
            db, detalle.producto_id, venta.sucursal_id, TipoMovimientoStock.ANULACION,
            detalle.cantidad, referencia_id=venta.id,
        )

    venta.estado = EstadoVenta.ANULADA
    venta.anulada_en = datetime.utcnow()
    db.commit()
    db.refresh(venta)
    return venta


@router.get("/turno/{turno_id}", response_model=List[VentaOut])
def ventas_del_turno(turno_id: int, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    """Listado de ventas de un turno, usado por el POS para poder anular alguna si hizo falta."""
    return db.query(Venta).filter(Venta.turno_id == turno_id).order_by(Venta.fecha.desc()).all()


@router.get("", response_model=List[VentaOut], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def listar_ventas(db: Session = Depends(get_db)):
    return db.query(Venta).order_by(Venta.fecha.desc()).all()


@router.get("/{venta_id}", response_model=VentaOut)
def obtener_venta(venta_id: int, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    venta = db.query(Venta).get(venta_id)
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return venta
