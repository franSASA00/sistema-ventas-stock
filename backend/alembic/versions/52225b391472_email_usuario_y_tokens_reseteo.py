"""email usuario y tokens reseteo

Revision ID: 52225b391472
Revises: a4e5dbf95e50
Create Date: 2026-08-23 11:19:51.862033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '52225b391472'
down_revision: Union[str, Sequence[str], None] = 'a4e5dbf95e50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("token", sa.String(), nullable=False, unique=True),
        sa.Column("expira", sa.DateTime(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("creado", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("password_reset_tokens")
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("email")
