from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Stock, Producto, TipoMovimientoStock, RolUsuario
from app.movimientos import registrar_movimiento_stock
from app.schemas import StockAjuste, StockOut
from app.security import requiere_rol

router = APIRouter(prefix="/stock", tags=["stock"])


@router.post("/ajuste", response_model=StockOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def ajustar_stock(datos: StockAjuste, db: Session = Depends(get_db)):
    """Ajuste manual de stock (ej: merma, rotura). Queda registrado en el libro de movimientos."""
    producto = db.query(Producto).get(datos.producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    stock_actual = db.query(Stock).filter(
        Stock.producto_id == datos.producto_id, Stock.sucursal_id == datos.sucursal_id
    ).first()
    cantidad_actual = stock_actual.cantidad if stock_actual else 0
    if cantidad_actual + datos.cantidad < 0:
        raise HTTPException(status_code=400, detail="El ajuste dejaria el stock en negativo")

    movimiento = registrar_movimiento_stock(
        db, datos.producto_id, datos.sucursal_id, TipoMovimientoStock.AJUSTE_MANUAL,
        datos.cantidad, notas=datos.motivo,
    )
    db.commit()
    stock = db.query(Stock).filter(
        Stock.producto_id == datos.producto_id, Stock.sucursal_id == datos.sucursal_id
    ).first()
    return stock


@router.get("", response_model=List[StockOut], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def listar_stock(sucursal_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Stock)
    if sucursal_id is not None:
        query = query.filter(Stock.sucursal_id == sucursal_id)
    return query.all()
