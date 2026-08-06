from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FormaPagoDetalle, RolUsuario
from app.schemas import FormaPagoDetalleCreate, FormaPagoDetalleOut
from app.security import requiere_rol, usuario_actual

router = APIRouter(prefix="/formas-pago", tags=["formas de pago"])


@router.post("", response_model=FormaPagoDetalleOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def crear_forma_pago(datos: FormaPagoDetalleCreate, db: Session = Depends(get_db)):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacio")
    forma = FormaPagoDetalle(tipo=datos.tipo, nombre=nombre)
    db.add(forma)
    db.commit()
    db.refresh(forma)
    return forma


@router.get("", response_model=List[FormaPagoDetalleOut])
def listar_formas_pago(
    tipo: Optional[str] = None,
    incluir_inactivas: bool = False,
    db: Session = Depends(get_db),
    _usuario=Depends(usuario_actual),
):
    query = db.query(FormaPagoDetalle)
    if tipo:
        query = query.filter(FormaPagoDetalle.tipo == tipo)
    if not incluir_inactivas:
        query = query.filter(FormaPagoDetalle.activo == True)  # noqa: E712
    return query.order_by(FormaPagoDetalle.nombre).all()


@router.put("/{forma_id}/estado", response_model=FormaPagoDetalleOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def cambiar_estado_forma_pago(forma_id: int, activo: bool, db: Session = Depends(get_db)):
    forma = db.query(FormaPagoDetalle).get(forma_id)
    if not forma:
        raise HTTPException(status_code=404, detail="No encontrada")
    forma.activo = activo
    db.commit()
    db.refresh(forma)
    return forma
