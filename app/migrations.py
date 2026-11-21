# app/migrations.py
from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations() -> None:
    """Применяет все неприменённые миграции Alembic (upgrade head)."""
    project_root = Path(__file__).resolve().parent.parent
    alembic_cfg_path = project_root / "alembic.ini"

    if not alembic_cfg_path.exists():
        raise FileNotFoundError(
            f"alembic.ini не найден: {alembic_cfg_path}. "
            "Убедитесь, что Alembic инициализирован (alembic init -t async migrations)."
        )

    alembic_cfg = Config(str(alembic_cfg_path))
    command.upgrade(alembic_cfg, "head")