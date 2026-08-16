import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Usuario, RolUsuario, ConfiguracionFiscal
from app.security import hash_password
from app.routers import (
    auth, productos, compras, ventas, stock, administracion, reportes,
    config_fiscal, turnos, categorias, inventario, formas_pago, clientes,
)

# El esquema de la base de datos lo maneja Alembic (ver alembic/ y el comando
# `alembic upgrade head`), NO este arranque. Asi las actualizaciones de tablas
# no requieren borrar la base de datos.

app = FastAPI(title="Sistema de Ventas y Stock")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en produccion, restringir al dominio del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Imagenes de producto subidas como archivo (alternativa a pegar una URL externa)
DIRECTORIO_STATIC = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(os.path.join(DIRECTORIO_STATIC, "uploads"), exist_ok=True)
app.mount("/static", StaticFiles(directory=DIRECTORIO_STATIC), name="static")

app.include_router(auth.router)
app.include_router(config_fiscal.router)
app.include_router(administracion.router)
app.include_router(categorias.router)
app.include_router(productos.router)
app.include_router(compras.router)
app.include_router(stock.router)
app.include_router(inventario.router)
app.include_router(formas_pago.router)
app.include_router(ventas.router)
app.include_router(turnos.router)
app.include_router(reportes.router)
app.include_router(clientes.router)


def _seed_inicial():
    db: Session = SessionLocal()
    try:
        if not db.query(Usuario).filter(Usuario.username == settings.admin_username).first():
            admin = Usuario(
                nombre="Administrador",
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                rol=RolUsuario.SERVIDOR,
            )
            db.add(admin)
        if not db.query(ConfiguracionFiscal).first():
            db.add(ConfiguracionFiscal())
        db.commit()
    finally:
        db.close()


_seed_inicial()


@app.get("/")
def estado():
    return {"status": "ok", "servicio": "sistema-ventas-stock"}
