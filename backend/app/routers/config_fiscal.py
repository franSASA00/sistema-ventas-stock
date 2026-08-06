from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ConfiguracionFiscal, RolUsuario
from app.schemas import ConfiguracionFiscalOut, ConfiguracionFiscalUpdate
from app.security import requiere_rol

router = APIRouter(prefix="/config-fiscal", tags=["configuracion fiscal"])


def _obtener_o_crear_config(db: Session) -> ConfiguracionFiscal:
    config = db.query(ConfiguracionFiscal).first()
    if not config:
        config = ConfiguracionFiscal()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("", response_model=ConfiguracionFiscalOut)
def obtener_config(db: Session = Depends(get_db)):
    return _obtener_o_crear_config(db)


@router.put("", response_model=ConfiguracionFiscalOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def actualizar_config(datos: ConfiguracionFiscalUpdate, db: Session = Depends(get_db)):
    """Solo el usuario servidor puede cambiar el regimen fiscal del negocio."""
    config = _obtener_o_crear_config(db)
    config.regimen = datos.regimen
    config.razon_social = datos.razon_social
    db.commit()
    db.refresh(config)
    return config
