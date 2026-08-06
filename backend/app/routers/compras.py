from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.calculos import costo_unitario_compra, actualizar_costo_promedio
from app.database import get_db
from app.models import Compra, CompraDetalle, Producto, Stock, ConfiguracionFiscal, TipoMovimientoStock, RolUsuario
from app.movimientos import registrar_movimiento_stock
from app.routers.config_fiscal import _obtener_o_crear_config
from app.schemas import CompraCreate, CompraOut, ProveedorCreate, ProveedorOut
from app.models import Proveedor
from app.security import requiere_rol

router = APIRouter(tags=["compras"])


@router.post("/proveedores", response_model=ProveedorOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def crear_proveedor(datos: ProveedorCreate, db: Session = Depends(get_db)):
    proveedor = Proveedor(**datos.model_dump())
    db.add(proveedor)
    db.commit()
    db.refresh(proveedor)
    return proveedor


@router.get("/proveedores", response_model=List[ProveedorOut])
def listar_proveedores(db: Session = Depends(get_db), _usuario=Depends(requiere_rol(RolUsuario.SERVIDOR))):
    return db.query(Proveedor).all()


@router.post("/compras", response_model=CompraOut, dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def registrar_compra(datos: CompraCreate, db: Session = Depends(get_db)):
    if not datos.detalles:
        raise HTTPException(status_code=400, detail="La compra necesita al menos un producto")

    config: ConfiguracionFiscal = _obtener_o_crear_config(db)
    compra = Compra(
        proveedor_id=datos.proveedor_id,
        sucursal_id=datos.sucursal_id,
        numero_comprobante=datos.numero_comprobante,
    )
    db.add(compra)
    db.flush()  # para tener compra.id sin cerrar la transaccion

    for item in datos.detalles:
        producto = db.query(Producto).get(item.producto_id)
        if not producto:
            raise HTTPException(status_code=404, detail=f"Producto {item.producto_id} no encontrado")
        if item.cantidad <= 0:
            raise HTTPException(status_code=400, detail="La cantidad comprada debe ser mayor a 0")

        costo_final = costo_unitario_compra(config.regimen, item.costo_unitario_neto, item.iva_compra_porcentaje)

        detalle = CompraDetalle(
            compra_id=compra.id,
            producto_id=producto.id,
            cantidad=item.cantidad,
            costo_unitario_neto=item.costo_unitario_neto,
            iva_compra_porcentaje=item.iva_compra_porcentaje,
            costo_unitario_final=costo_final,
            proveedor_id=item.proveedor_id or datos.proveedor_id,
            bultos=item.bultos,
        )
        db.add(detalle)

        # Stock global del producto (suma de todas las sucursales) se usa como base del costo promedio
        stock_total_actual = sum(s.cantidad for s in producto.stocks)
        producto.costo_promedio = actualizar_costo_promedio(
            stock_total_actual, producto.costo_promedio, item.cantidad, costo_final
        )

        # Sumar stock en la sucursal donde entro la mercaderia, dejando registro del movimiento
        registrar_movimiento_stock(
            db, producto.id, datos.sucursal_id, TipoMovimientoStock.COMPRA, item.cantidad, referencia_id=compra.id
        )

    db.commit()
    db.refresh(compra)
    return compra


@router.get("/compras", response_model=List[CompraOut], dependencies=[Depends(requiere_rol(RolUsuario.SERVIDOR))])
def listar_compras(db: Session = Depends(get_db)):
    return db.query(Compra).order_by(Compra.fecha.desc()).all()
