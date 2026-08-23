import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario, PasswordResetToken
from app.schemas import LoginRequest, Token, OlvidePasswordRequest, ResetearPasswordConTokenRequest
from app.security import verify_password, crear_token, hash_password
from app.config import settings
from app.email_service import enviar_email_reseteo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(datos: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.username == datos.username, Usuario.activo == True).first()  # noqa: E712
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o contrasena incorrectos")
    token = crear_token({"sub": usuario.username, "rol": usuario.rol.value})
    return Token(access_token=token, rol=usuario.rol, nombre=usuario.nombre, sucursales=usuario.sucursales)


@router.post("/olvide-password")
def olvide_password(datos: OlvidePasswordRequest, db: Session = Depends(get_db)):
    """Pide un email de recuperacion. Siempre responde lo mismo, exista o no ese email,
    para no revelar si un correo esta registrado en el sistema (buena practica de seguridad)."""
    usuario = db.query(Usuario).filter(Usuario.email == datos.email, Usuario.activo == True).first()  # noqa: E712
    if usuario:
        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            usuario_id=usuario.id,
            token=token,
            expira=datetime.utcnow() + timedelta(minutes=30),
        )
        db.add(reset)
        db.commit()
        link = f"{settings.frontend_url}/resetear-password.html?token={token}"
        enviar_email_reseteo(usuario.email, usuario.nombre, link)
    return {"mensaje": "Si el email esta registrado, te llegara un correo con instrucciones."}


@router.post("/resetear-password")
def resetear_password_con_token(datos: ResetearPasswordConTokenRequest, db: Session = Depends(get_db)):
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token == datos.token).first()
    if not reset or reset.usado or reset.expira < datetime.utcnow():
        raise HTTPException(status_code=400, detail="El link de recuperacion es invalido o ya vencio")
    if len(datos.nueva_password) < 4:
        raise HTTPException(status_code=400, detail="La contrasena debe tener al menos 4 caracteres")

    usuario = db.query(Usuario).get(reset.usuario_id)
    usuario.password_hash = hash_password(datos.nueva_password)
    reset.usado = True
    db.commit()
    return {"mensaje": "Contrasena actualizada correctamente"}
