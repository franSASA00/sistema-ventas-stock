"""agregar valor QR al enum metodopago (Postgres)

Revision ID: b1c2d3e4f5a6
Revises: 1885e0211ab4
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '1885e0211ab4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # En SQLite los enums son solo un CHECK constraint (ya se recreo con el valor nuevo
    # al aplicar la migracion anterior en modo batch), pero en Postgres 'metodopago' es un
    # tipo de dato real: hay que agregarle el valor 'QR' explicitamente antes de poder
    # usarlo. No se puede combinar con otra sentencia que USE ese valor en la misma
    # transaccion, por eso esto va en su propia migracion, separada de la que actualiza
    # los datos viejos.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE metodopago ADD VALUE IF NOT EXISTS 'QR'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres no permite quitar un valor de un enum de forma simple; no se revierte.
    pass
