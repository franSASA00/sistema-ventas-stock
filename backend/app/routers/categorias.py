from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Categoria, Producto, RolUsuario
from app.schemas import CategoriaCreate, CategoriaOut, CategoriaUpdate
from app.security import requiere_rol, usuario_actual

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.post("", response_model=CategoriaOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def crear_categoria(datos: CategoriaCreate, db: Session = Depends(get_db)):
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacio")
    if db.query(Categoria).filter(Categoria.nombre.ilike(nombre)).first():
        raise HTTPException(status_code=400, detail="Ya existe una categoria con ese nombre")
    categoria = Categoria(nombre=nombre, notas=datos.notas, stockeable=datos.stockeable, visible_pos=datos.visible_pos)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.put("/{categoria_id}", response_model=CategoriaOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def editar_categoria(categoria_id: int, datos: CategoriaUpdate, db: Session = Depends(get_db)):
    categoria = db.query(Categoria).get(categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.get("", response_model=List[CategoriaOut])
def listar_categorias(db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    return db.query(Categoria).order_by(Categoria.nombre).all()


@router.delete("/{categoria_id}", dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def eliminar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    categoria = db.query(Categoria).get(categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    db.query(Producto).filter(Producto.categoria_id == categoria_id).update({Producto.categoria_id: None})
    db.delete(categoria)
    db.commit()
    return {"ok": True}
