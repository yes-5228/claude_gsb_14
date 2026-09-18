"""数据库引擎、会话与初始化。"""

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _prepare_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    path = url.replace("sqlite:///", "", 1)
    if path.startswith(":memory:"):
        return
    directory = Path(path).parent
    if str(directory) not in ("", "."):
        os.makedirs(directory, exist_ok=True)


_prepare_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.database_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  确保模型完成注册

    Base.metadata.create_all(bind=engine)
    _ensure_location_snapshot_columns()


# 事件表（巡查/问题）上的「发生时位置」快照列：列名 -> DDL 列定义
_LOCATION_COLUMNS: dict[str, str] = {
    "district": "VARCHAR(60) DEFAULT '' NOT NULL",
    "address": "VARCHAR(200) DEFAULT '' NOT NULL",
    "longitude": "FLOAT",
    "latitude": "FLOAT",
}


def _ensure_location_snapshot_columns() -> None:
    """老库平滑升级：为巡查/问题表补齐位置快照列并按当前公厕位置回填。

    新库的列由 create_all 直接建出；仅当检测到列缺失（既有库）时才执行
    ALTER TABLE 与回填，保证幂等，且 SQLite / PostgreSQL 通用。
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    backfill_targets: list[str] = []

    with engine.begin() as conn:
        for table in ("inspections", "issues"):
            if table not in existing_tables:
                continue
            present = {column["name"] for column in inspector.get_columns(table)}
            added = False
            for column, ddl in _LOCATION_COLUMNS.items():
                if column not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                    added = True
            if added:
                backfill_targets.append(table)

        # 仅对刚补过列的表回填：用公厕当前位置填充仍为空的历史行
        for table in backfill_targets:
            conn.execute(
                text(
                    f"""
                    UPDATE {table} SET
                        district = COALESCE(
                            (SELECT r.district FROM restrooms r WHERE r.id = {table}.restroom_id), ''
                        ),
                        address = COALESCE(
                            (SELECT r.address FROM restrooms r WHERE r.id = {table}.restroom_id), ''
                        ),
                        longitude = (
                            SELECT r.longitude FROM restrooms r WHERE r.id = {table}.restroom_id
                        ),
                        latitude = (
                            SELECT r.latitude FROM restrooms r WHERE r.id = {table}.restroom_id
                        )
                    WHERE COALESCE({table}.district, '') = ''
                      AND EXISTS (
                          SELECT 1 FROM restrooms r WHERE r.id = {table}.restroom_id
                      )
                    """
                )
            )
