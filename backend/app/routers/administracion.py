from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Sucursal, Usuario, RolUsuario
from app.schemas import SucursalCreate, SucursalOut, UsuarioCreate, UsuarioOut, ResetearPasswordRequest
from app.security import requiere_rol, hash_password

router = APIRouter(tags=["administracion"], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])


@router.post("/sucursales", response_model=SucursalOut)
def crear_sucursal(datos: SucursalCreate, db: Session = Depends(get_db)):
    sucursal = Sucursal(**datos.model_dump())
    db.add(sucursal)
    db.commit()
    db.refresh(sucursal)
    return sucursal


@router.get("/sucursales", response_model=List[SucursalOut])
def listar_sucursales(db: Session = Depends(get_db)):
    return db.query(Sucursal).all()


@router.post("/usuarios", response_model=UsuarioOut)
def crear_usuario(datos: UsuarioCreate, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.username == datos.username).first():
        raise HTTPException(status_code=400, detail="Ese nombre de usuario ya existe")
    usuario = Usuario(
        nombre=datos.nombre,
        username=datos.username,
        password_hash=hash_password(datos.password),
        rol=datos.rol,
        email=datos.email,
    )
    if datos.sucursal_ids:
        usuario.sucursales = db.query(Sucursal).filter(Sucursal.id.in_(datos.sucursal_ids)).all()
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/usuarios", response_model=List[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).all()


@router.put("/usuarios/{usuario_id}/resetear-password", response_model=UsuarioOut)
def resetear_password(usuario_id: int, datos: ResetearPasswordRequest, db: Session = Depends(get_db)):
    """Un usuario servidor (admin) puede resetear la contrasena de cualquier usuario,
    sin necesidad de conocer la contrasena anterior. Util cuando alguien se olvida la suya."""
    usuario = db.query(Usuario).get(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if len(datos.nueva_password) < 4:
        raise HTTPException(status_code=400, detail="La contrasena debe tener al menos 4 caracteres")
    usuario.password_hash = hash_password(datos.nueva_password)
    db.commit()
    db.refresh(usuario)
    return usuario
