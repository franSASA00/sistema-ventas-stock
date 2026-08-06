from sqlalchemy.orm import Session

from app.models import Stock, MovimientoStock, TipoMovimientoStock


def registrar_movimiento_stock(
    db: Session,
    producto_id: int,
    sucursal_id: int,
    tipo: TipoMovimientoStock,
    cantidad: int,
    referencia_id: int = None,
    notas: str = None,
) -> MovimientoStock:
    """Aplica un cambio de stock (positivo=entrada, negativo=salida) y deja registrado
    el movimiento en el libro historico, con el saldo resultante."""
    stock = db.query(Stock).filter(Stock.producto_id == producto_id, Stock.sucursal_id == sucursal_id).first()
    if not stock:
        stock = Stock(producto_id=producto_id, sucursal_id=sucursal_id, cantidad=0)
        db.add(stock)
        db.flush()

    stock.cantidad += cantidad

    movimiento = MovimientoStock(
        producto_id=producto_id,
        sucursal_id=sucursal_id,
        tipo=tipo,
        cantidad=cantidad,
        saldo_posterior=stock.cantidad,
        referencia_id=referencia_id,
        notas=notas,
    )
    db.add(movimiento)
    return movimiento
