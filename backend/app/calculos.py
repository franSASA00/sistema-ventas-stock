"""
Toda la matematica de costos / IVA / ganancia vive aca, en un solo lugar,
para que cambiar de regimen fiscal (Monotributo <-> Responsable Inscripto)
actualice el comportamiento de TODO el sistema de forma consistente.

Regla de negocio:

- RESPONSABLE INSCRIPTO:
    * El IVA de las compras es credito fiscal -> NO forma parte del costo del producto.
      costo = precio_compra_neto
    * El precio de venta se discrimina en neto + IVA debito fiscal.
      precio_venta_neto = precio_venta / (1 + iva/100)
    * Ganancia = precio_venta_neto - costo

- MONOTRIBUTO:
    * No hay credito ni debito fiscal: el IVA que se paga al comprar es un costo real.
      costo = precio_compra_neto * (1 + iva_compra/100)
    * El precio de venta NO se discrimina (es el total, no se factura IVA aparte).
      precio_venta_neto = precio_venta
    * Ganancia = precio_venta - costo
"""

from app.models import RegimenFiscal


def costo_unitario_compra(regimen: RegimenFiscal, costo_neto: float, iva_compra_porcentaje: float) -> float:
    """Costo real que impacta en el costo promedio del producto, segun el regimen vigente."""
    if regimen == RegimenFiscal.RESPONSABLE_INSCRIPTO:
        return costo_neto
    return costo_neto * (1 + iva_compra_porcentaje / 100)


def actualizar_costo_promedio(stock_actual: int, costo_promedio_actual: float,
                               cantidad_comprada: int, costo_unitario_nuevo: float) -> float:
    """Costo Promedio Ponderado (CPP)."""
    if cantidad_comprada <= 0:
        return costo_promedio_actual
    stock_valorizado = stock_actual * costo_promedio_actual
    compra_valorizada = cantidad_comprada * costo_unitario_nuevo
    nuevo_stock = stock_actual + cantidad_comprada
    if nuevo_stock <= 0:
        return costo_unitario_nuevo
    return (stock_valorizado + compra_valorizada) / nuevo_stock


def descomponer_venta(regimen: RegimenFiscal, precio_venta: float, iva_porcentaje: float) -> dict:
    """Devuelve el neto y el IVA discriminado de un precio de venta, segun regimen."""
    if regimen == RegimenFiscal.RESPONSABLE_INSCRIPTO:
        neto = precio_venta / (1 + iva_porcentaje / 100)
        iva = precio_venta - neto
    else:
        neto = precio_venta
        iva = 0.0
    return {"neto": round(neto, 2), "iva": round(iva, 2)}


def calcular_ganancia_unitaria(regimen: RegimenFiscal, precio_venta: float,
                                iva_porcentaje: float, costo_unitario: float) -> dict:
    descomposicion = descomponer_venta(regimen, precio_venta, iva_porcentaje)
    ganancia = descomposicion["neto"] - costo_unitario
    return {
        "precio_neto": descomposicion["neto"],
        "iva": descomposicion["iva"],
        "ganancia": round(ganancia, 2),
    }
