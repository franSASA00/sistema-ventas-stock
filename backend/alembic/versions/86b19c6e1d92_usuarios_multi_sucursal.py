"""usuarios multi sucursal

Revision ID: 86b19c6e1d92
Revises: a0925c830039
Create Date: 2026-08-10 20:35:21.839454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86b19c6e1d92'
down_revision: Union[str, Sequence[str], None] = 'a0925c830039'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "usuario_sucursales",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("sucursal_id", sa.Integer(), sa.ForeignKey("sucursales.id"), primary_key=True),
    )

    bind = op.get_bind()
    bind.execute(sa.text(
        "INSERT INTO usuario_sucursales (usuario_id, sucursal_id) "
        "SELECT id, sucursal_id FROM usuarios WHERE sucursal_id IS NOT NULL"
    ))

    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("sucursal_id")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(sa.Column("sucursal_id", sa.Integer(), sa.ForeignKey("sucursales.id"), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE usuarios SET sucursal_id = ("
        "SELECT sucursal_id FROM usuario_sucursales WHERE usuario_sucursales.usuario_id = usuarios.id LIMIT 1"
        ")"
    ))

    op.drop_table("usuario_sucursales")
