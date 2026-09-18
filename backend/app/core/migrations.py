"""启动期轻量迁移：为既有数据库补建点位快照列并回填。

项目未使用 Alembic，这里用 inspector + 方言通用的原生 DDL 做幂等迁移，
SQLite 与 PostgreSQL 均适用。每段迁移在 ``schema_migrations`` 表登记版本号。

调用顺序约定：先 ``Base.metadata.create_all``（新库直接按新模型建全表），
再执行本迁移（老库补列、回填、建索引）。
"""

from datetime import datetime

from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import Connection

SNAPSHOT_COLUMNS = ("district", "address", "longitude", "latitude")

# 表 -> (快照列, 列类型 DDL)
_COLUMN_DDL: dict[str, dict[str, str]] = {
    "inspections": {
        "district": "VARCHAR(60) NOT NULL DEFAULT ''",
        "address": "VARCHAR(200) NOT NULL DEFAULT ''",
        "longitude": "FLOAT",
        "latitude": "FLOAT",
    },
    "issues": {
        "district": "VARCHAR(60) NOT NULL DEFAULT ''",
        "address": "VARCHAR(200) NOT NULL DEFAULT ''",
        "longitude": "FLOAT",
        "latitude": "FLOAT",
    },
}


def _applied(conn: Connection, version: str) -> bool:
    return (
        conn.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": version},
        ).first()
        is not None
    )


def _add_location_snapshot_columns(conn: Connection, inspector, table: str) -> None:
    existing = {column["name"] for column in inspector.get_columns(table)}
    for column in SNAPSHOT_COLUMNS:
        if column in existing:
            continue
        ddl = _COLUMN_DDL[table][column]
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _backfill_location_snapshots(conn: Connection, table: str) -> None:
    """按台账当前位置回填历史行；仅对空快照行生效，可安全重复执行。"""
    conn.execute(
        text(
            f"""
            UPDATE {table}
            SET district = COALESCE(
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
            WHERE district = '' OR district IS NULL
            """
        )
    )


def _create_district_indexes(conn: Connection) -> None:
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_inspections_district ON inspections (district)")
    )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_issues_district ON issues (district)"))


def _migrate_v1_location_snapshots(conn: Connection, inspector) -> None:
    version = "0001_location_snapshots"
    if _applied(conn, version):
        return
    for table in _COLUMN_DDL:
        _add_location_snapshot_columns(conn, inspector, table)
        _backfill_location_snapshots(conn, table)
    _create_district_indexes(conn)
    conn.execute(
        text("INSERT INTO schema_migrations (version, applied_at) VALUES (:version, :now)"),
        {"version": version, "now": datetime.now()},
    )


def run_startup_migrations(engine: Engine) -> None:
    """执行所有登记的启动迁移；每段在独立事务中提交。"""
    inspector = inspect(engine)
    with engine.begin() as conn:
        _migrate_v1_location_snapshots(conn, inspector)
