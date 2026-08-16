"""clientes

Revision ID: a4e5dbf95e50
Revises: 8e9bfe7d70cc
Create Date: 2026-08-13 23:37:47.986870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4e5dbf95e50'
down_revision: Union[str, Sequence[str], None] = '8e9bfe7d70cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("apellido", sa.String(), nullable=True),
        sa.Column("telefono", sa.String(), nullable=True),
        sa.Column("direccion", sa.String(), nullable=True),
    )
    with op.batch_alter_table("ventas") as batch_op:
        batch_op.add_column(sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("ventas") as batch_op:
        batch_op.drop_column("cliente_id")
    op.drop_table("clientes")
