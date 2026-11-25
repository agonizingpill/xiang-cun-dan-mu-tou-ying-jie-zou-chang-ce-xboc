from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


# 换过计拍器后的时钟标定：同段新旧拍点拟合 scale/offset，按计拍器和测量时段生效
clock_calibrations = Table('clock_calibrations', metadata,
    Column('code', String(64), primary_key=True),
    Column('metronome', String(160), nullable=False),
    Column('valid_from', DateTime, nullable=False),
    Column('valid_to', DateTime, nullable=False),
    Column('pairs', JSON, nullable=False),
    Column('scale', Float, nullable=False),
    Column('offset', Float, nullable=False),
    Column('max_error', Float, nullable=False),
    Column('fit_count', Integer, nullable=False),
    Column('check_count', Integer, nullable=False),
    Column('enabled', Boolean, nullable=False),
    Column('note', String(320), nullable=False),
)
