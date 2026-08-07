"""corregir dato viejo mercadopago a qr en ventas_pago

Revision ID: a0925c830039
Revises: 1885e0211ab4
Create Date: 2026-08-06 02:44:38.714707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0925c830039'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Corrige ventas ya guardadas con el valor viejo 'mercadopago', que dejo de existir
    # cuando ese metodo de pago se renombro a la categoria general 'qr'.
    op.execute("UPDATE ventas_pago SET metodo_pago = 'QR' WHERE metodo_pago = 'MERCADOPAGO'")


def downgrade() -> None:
    """Downgrade schema."""
    # No hay forma de saber cuales 'qr' eran originalmente 'mercadopago', asi que
    # esta migracion no se puede revertir con precision.
    pass
