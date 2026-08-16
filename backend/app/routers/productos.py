import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Producto, Categoria, Stock, RolUsuario
from app.schemas import ProductoCreate, ProductoUpdate, ProductoOut, ProductoConStock
from app.security import requiere_rol, usuario_actual

router = APIRouter(prefix="/productos", tags=["productos"])

DIRECTORIO_IMAGENES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "static", "uploads")
DIRECTORIO_IMAGENES = os.path.abspath(DIRECTORIO_IMAGENES)
EXTENSIONES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@router.post("", response_model=ProductoOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def crear_producto(datos: ProductoCreate, db: Session = Depends(get_db)):
    if db.query(Producto).filter(Producto.codigo == datos.codigo).first():
        raise HTTPException(status_code=400, detail="Ya existe un producto con ese codigo")
    producto = Producto(**datos.model_dump())
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.put("/{producto_id}", response_model=ProductoOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def editar_producto(producto_id: int, datos: ProductoUpdate, db: Session = Depends(get_db)):
    producto = db.query(Producto).get(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(producto, campo, valor)
    db.commit()
    db.refresh(producto)
    return producto


@router.put("/{producto_id}/estado", response_model=ProductoOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def cambiar_estado_producto(producto_id: int, activo: bool, db: Session = Depends(get_db)):
    """Inactiva o reactiva un producto sin borrar su historial de compras/ventas.
    Un producto inactivo no aparece en el catalogo del POS ni en el listado por defecto."""
    producto = db.query(Producto).get(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.activo = activo
    db.commit()
    db.refresh(producto)
    return producto


@router.post("/{producto_id}/imagen", response_model=ProductoOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def subir_imagen_producto(
    producto_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Sube un archivo de imagen para el producto (alternativa a pegar una URL externa)."""
    producto = db.query(Producto).get(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    extension = os.path.splitext(archivo.filename or "")[1].lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Formato de imagen no soportado (usa png, jpg, webp o gif)")

    os.makedirs(DIRECTORIO_IMAGENES, exist_ok=True)
    nombre_archivo = f"{uuid.uuid4().hex}{extension}"
    ruta_destino = os.path.join(DIRECTORIO_IMAGENES, nombre_archivo)
    with open(ruta_destino, "wb") as f:
        f.write(archivo.file.read())

    producto.imagen_url = f"{str(request.base_url).rstrip('/')}/static/uploads/{nombre_archivo}"
    db.commit()
    db.refresh(producto)
    return producto


@router.get("", response_model=List[ProductoConStock])
def listar_productos(
    sucursal_id: Optional[int] = None,
    buscar: Optional[str] = None,
    categoria_id: Optional[int] = None,
    incluir_inactivos: bool = False,
    solo_visibles_pos: bool = False,
    db: Session = Depends(get_db),
    _usuario=Depends(usuario_actual),
):
    """Lista productos. Si se pasa sucursal_id, incluye el stock disponible en esa sucursal (usado por el POS).
    Por defecto solo trae productos activos; incluir_inactivos=true los trae a todos (usado por el backoffice)."""
    query = db.query(Producto)
    if not incluir_inactivos:
        query = query.filter(Producto.activo == True)  # noqa: E712
    if categoria_id is not None:
        query = query.filter(Producto.categoria_id == categoria_id)
    if solo_visibles_pos:
        query = query.outerjoin(Categoria, Producto.categoria_id == Categoria.id).filter(
            (Producto.categoria_id.is_(None)) | (Categoria.visible_pos == True)  # noqa: E712
        )
    if buscar:
        like = f"%{buscar}%"
        query = query.filter((Producto.nombre.ilike(like)) | (Producto.codigo.ilike(like)))
    productos = query.all()

    resultado = []
    for p in productos:
        stock_disponible = 0
        if sucursal_id is not None:
            stock = db.query(Stock).filter(Stock.producto_id == p.id, Stock.sucursal_id == sucursal_id).first()
            stock_disponible = stock.cantidad if stock else 0
        item = ProductoConStock.model_validate(p)
        item.stock_disponible = stock_disponible
        item.stockeable = p.categoria_rel.stockeable if p.categoria_rel else True
        resultado.append(item)
    return resultado


@router.get("/{producto_id}", response_model=ProductoOut)
def obtener_producto(producto_id: int, db: Session = Depends(get_db), _usuario=Depends(usuario_actual)):
    producto = db.query(Producto).get(producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto
