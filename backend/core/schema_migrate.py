"""轻量幂等迁移：metadata.create_all 只建新表，已存在的表靠这里补齐新增列。

项目没有迁移框架，演示库与命名卷可能保留旧表结构，启动时按列名检查后 ALTER ADD。
"""
from sqlalchemy import inspect, text

from core.db import engine

# 表 -> (列名, 列级 DDL 片段)。新库由 metadata.create_all 直接建出完整结构与外键。
COLUMN_PATCHES = {
    'cue_tracks': [
        ("clock", "VARCHAR(32) NOT NULL DEFAULT '原时钟'"),
        ("metronome", "VARCHAR(160) NULL"),
        ("measured_at", "DATETIME NULL"),
        ("calibration", "VARCHAR(64) NULL"),
        ("converted_timings", "JSON NULL"),
    ],
    'cue_clusters': [
        ("calibration", "VARCHAR(64) NOT NULL DEFAULT ''"),
    ],
}


def migrate():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, patches in COLUMN_PATCHES.items():
            if table not in existing_tables:
                continue
            present = {col['name'] for col in inspector.get_columns(table)}
            for name, ddl in patches:
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
