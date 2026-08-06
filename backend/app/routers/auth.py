from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, Token
from app.security import verify_password, crear_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.username == datos.username, Usuario.activo == True).first()  # noqa: E712
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contrasena incorrectos")

    token = crear_token({"sub": usuario.username, "rol": usuario.rol.value})
    return Token(access_token=token, rol=usuario.rol, nombre=usuario.nombre, sucursal_id=usuario.sucursal_id)
