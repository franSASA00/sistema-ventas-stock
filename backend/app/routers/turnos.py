import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Turno, Venta, MovimientoCaja, EstadoTurno, EstadoVenta, MetodoPago, TipoMovimientoCaja, RolUsuario
from app.schemas import TurnoAbrir, TurnoCerrar, TurnoOut, TurnoResumen, MovimientoCajaCreate, MovimientoCajaOut
from app.security import requiere_rol, usuario_actual

router = APIRouter(prefix="/turnos", tags=["turnos"])


def turno_abierto_de(db: Session, usuario_id: int, sucursal_id: int) -> Optional[Turno]:
    return db.query(Turno).filter(
        Turno.usuario_id == usuario_id,
        Turno.sucursal_id == sucursal_id,
        Turno.estado == EstadoTurno.ABIERTO,
    ).first()


def calcular_resumen_turno(db: Session, turno: Turno) -> dict:
    ventas_efectivo = sum(
        pago.monto
        for venta in db.query(Venta).filter(Venta.turno_id == turno.id, Venta.estado == EstadoVenta.ACTIVA).all()
        for pago in venta.pagos
        if pago.metodo_pago == MetodoPago.EFECTIVO
    )
    movimientos = db.query(MovimientoCaja).filter(MovimientoCaja.turno_id == turno.id).all()
    total_ingresos = sum(m.monto for m in movimientos if m.tipo == TipoMovimientoCaja.INGRESO)
    total_egresos = sum(m.monto for m in movimientos if m.tipo == TipoMovimientoCaja.EGRESO)
    esperado = turno.monto_apertura + ventas_efectivo + total_ingresos - total_egresos
    return {
        "monto_apertura": turno.monto_apertura,
        "ventas_efectivo": round(ventas_efectivo, 2),
        "total_ingresos": round(total_ingresos, 2),
        "total_egresos": round(total_egresos, 2),
        "esperado": round(esperado, 2),
    }


@router.get("/actual", response_model=Optional[TurnoOut])
def obtener_turno_actual(sucursal_id: int, db: Session = Depends(get_db), usuario=Depends(usuario_actual)):
    """El POS consulta esto al arrancar para saber si hay que abrir turno o ya hay uno en curso."""
    return turno_abierto_de(db, usuario.id, sucursal_id)


@router.get("/{turno_id}/resumen", response_model=TurnoResumen)
def resumen_turno(turno_id: int, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    """Efectivo esperado en caja en este momento, para mostrar en vivo antes del cierre."""
    turno = db.query(Turno).get(turno_id)
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    return calcular_resumen_turno(db, turno)


@router.post("/abrir", response_model=TurnoOut)
def abrir_turno(
    datos: TurnoAbrir,
    db: Session = Depends(get_db),
    usuario=Depends(requiere_rol(RolUsuario.POS, RolUsuario.SERVIDOR)),
):
    if turno_abierto_de(db, usuario.id, datos.sucursal_id):
        raise HTTPException(status_code=400, detail="Ya tenes un turno abierto en esta sucursal")
    if datos.monto_apertura < 0:
        raise HTTPException(status_code=400, detail="El monto de apertura no puede ser negativo")

    cantidad_previa = db.query(Turno).filter(Turno.sucursal_id == datos.sucursal_id).count()

    turno = Turno(
        numero=cantidad_previa + 1,
        usuario_id=usuario.id,
        sucursal_id=datos.sucursal_id,
        monto_apertura=datos.monto_apertura,
    )
    db.add(turno)
    db.commit()
    db.refresh(turno)
    return turno


@router.post("/{turno_id}/cerrar", response_model=TurnoOut)
def cerrar_turno(
    turno_id: int,
    datos: TurnoCerrar,
    db: Session = Depends(get_db),
    usuario=Depends(requiere_rol(RolUsuario.POS, RolUsuario.SERVIDOR)),
):
    turno = db.query(Turno).get(turno_id)
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if turno.estado == EstadoTurno.CERRADO:
        raise HTTPException(status_code=400, detail="Este turno ya esta cerrado")
    if turno.usuario_id != usuario.id and usuario.rol != RolUsuario.SERVIDOR:
        raise HTTPException(status_code=403, detail="No podes cerrar el turno de otro usuario")

    resumen = calcular_resumen_turno(db, turno)
    monto_contado = sum(item.denominacion * item.cantidad for item in datos.conteo)

    turno.estado = EstadoTurno.CERRADO
    turno.fecha_cierre = datetime.utcnow()
    turno.monto_contado_cierre = round(monto_contado, 2)
    turno.monto_esperado_cierre = resumen["esperado"]
    turno.diferencia = round(monto_contado - resumen["esperado"], 2)
    turno.detalle_arqueo = json.dumps({str(item.denominacion): item.cantidad for item in datos.conteo})
    turno.notas_cierre = datos.notas_cierre

    db.commit()
    db.refresh(turno)
    return turno


@router.post("/{turno_id}/movimientos", response_model=MovimientoCajaOut)
def registrar_movimiento_caja(
    turno_id: int,
    datos: MovimientoCajaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(requiere_rol(RolUsuario.POS, RolUsuario.SERVIDOR)),
):
    turno = db.query(Turno).get(turno_id)
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")
    if turno.estado == EstadoTurno.CERRADO:
        raise HTTPException(status_code=400, detail="El turno ya esta cerrado")
    if datos.monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    movimiento = MovimientoCaja(
        turno_id=turno.id,
        usuario_id=usuario.id,
        tipo=datos.tipo,
        monto=datos.monto,
        motivo=datos.motivo,
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)
    return movimiento


@router.get("/{turno_id}/movimientos", response_model=List[MovimientoCajaOut])
def listar_movimientos_caja(turno_id: int, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    return db.query(MovimientoCaja).filter(MovimientoCaja.turno_id == turno_id).order_by(MovimientoCaja.fecha.desc()).all()


@router.get("", response_model=List[TurnoOut], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def listar_turnos(sucursal_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Turno).order_by(Turno.fecha_apertura.desc())
    if sucursal_id:
        query = query.filter(Turno.sucursal_id == sucursal_id)
    return query.all()
