from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cliente, Venta, RolUsuario
from app.schemas import ClienteCreate, ClienteOut, ClienteConEstadisticas
from app.security import requiere_rol, usuario_actual

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.post("", response_model=ClienteOut)
def crear_cliente(datos: ClienteCreate, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    """Cualquier usuario autenticado (POS o servidor) puede crear un cliente nuevo,
    ya que se carga sobre la marcha durante una venta."""
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacio")
    cliente = Cliente(
        nombre=nombre,
        apellido=(datos.apellido or "").strip() or None,
        telefono=(datos.telefono or "").strip() or None,
        direccion=(datos.direccion or "").strip() or None,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.get("", response_model=List[ClienteOut])
def buscar_clientes(buscar: Optional[str] = None, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    """Lista/busca clientes por nombre o apellido (usado por el autocompletado del POS)."""
    query = db.query(Cliente)
    if buscar:
        like = f"%{buscar}%"
        query = query.filter((Cliente.nombre.ilike(like)) | (Cliente.apellido.ilike(like)))
    return query.order_by(Cliente.nombre).limit(20).all()


@router.get("/{cliente_id}", response_model=ClienteConEstadisticas, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def obtener_cliente(cliente_id: int, db: Session = Depends(get_db)):
    """Detalle de un cliente con estadisticas de compra (usado en el backoffice)."""
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    stats = db.query(
        func.count(Venta.id), func.coalesce(func.sum(Venta.total + Venta.propina), 0), func.max(Venta.fecha)
    ).filter(Venta.cliente_id == cliente_id).first()

    item = ClienteConEstadisticas.model_validate(cliente)
    item.total_compras = stats[0] or 0
    item.total_gastado = round(stats[1] or 0, 2)
    item.ultima_compra = stats[2]
    return item
