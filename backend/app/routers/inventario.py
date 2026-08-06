from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ConteoInventario, ConteoInventarioDetalle, Stock, Producto, TipoMovimientoStock, RolUsuario
from app.movimientos import registrar_movimiento_stock
from app.schemas import ConteoCreate, ConteoOut
from app.security import requiere_rol

router = APIRouter(prefix="/inventario", tags=["inventario"], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])


@router.post("/conteos", response_model=ConteoOut)
def registrar_conteo(datos: ConteoCreate, db: Session = Depends(get_db), usuario=Depends(requiere_rol(RolUsuario.SERVIDOR))):
    """Registra un conteo fisico de stock. Por cada producto contado, compara contra el
    stock del sistema en este momento y, si hay diferencia, corrige el stock automaticamente
    dejando registrado el desvio (merma o sobrante) en el libro de movimientos."""
    if not datos.detalles:
        raise HTTPException(status_code=400, detail="El conteo necesita al menos un producto")

    conteo = ConteoInventario(sucursal_id=datos.sucursal_id, usuario_id=usuario.id, notas=datos.notas)
    db.add(conteo)
    db.flush()

    for item in datos.detalles:
        producto = db.query(Producto).get(item.producto_id)
        if not producto:
            raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado")
        if item.cantidad_contada < 0:
            raise HTTPException(status_code=400, detail="La cantidad contada no puede ser negativa")

        stock_row = db.query(Stock).filter(
            Stock.producto_id == item.producto_id, Stock.sucursal_id == datos.sucursal_id
        ).first()
        stock_sistema = stock_row.cantidad if stock_row else 0
        diferencia = item.cantidad_contada - stock_sistema

        db.add(ConteoInventarioDetalle(
            conteo_id=conteo.id,
            producto_id=item.producto_id,
            stock_sistema=stock_sistema,
            cantidad_contada=item.cantidad_contada,
            diferencia=diferencia,
        ))

        if diferencia != 0:
            registrar_movimiento_stock(
                db, item.producto_id, datos.sucursal_id, TipoMovimientoStock.CONTEO,
                diferencia, referencia_id=conteo.id,
                notas=f"Ajuste por conteo fisico ({'sobrante' if diferencia > 0 else 'faltante'})",
            )

    db.commit()
    db.refresh(conteo)
    return conteo


@router.get("/conteos", response_model=List[ConteoOut])
def listar_conteos(sucursal_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(ConteoInventario).order_by(ConteoInventario.fecha.desc())
    if sucursal_id:
        query = query.filter(ConteoInventario.sucursal_id == sucursal_id)
    return query.all()


@router.get("/conteos/{conteo_id}", response_model=ConteoOut)
def obtener_conteo(conteo_id: int, db: Session = Depends(get_db)):
    conteo = db.query(ConteoInventario).get(conteo_id)
    if not conteo:
        raise HTTPException(status_code=404, detail="Conteo no encontrado")
    return conteo
