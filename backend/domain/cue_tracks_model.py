from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table

from core.db import metadata


cue_tracks = Table('cue_tracks', metadata,
    Column('code', String(64), primary_key=True),
    Column('venue', String(160), ForeignKey('venues.code'), nullable=False),
    Column('timings', JSON, nullable=False),
    Column('shift', Float, nullable=False),
    Column('locked', Boolean, nullable=False),
    # 时钟来源：原时钟 / 换钟。原时钟素材照用；换钟素材须经标定并见证后才可对场
    Column('clock', String(32), nullable=False, server_default='原时钟'),
    Column('metronome', String(160), nullable=True),
    Column('measured_at', DateTime, nullable=True),
    Column('calibration', String(64), ForeignKey('clock_calibrations.code'), nullable=True),
    # 原拍点留在 timings；换算到原时钟口径的拍点单独留存，未标定为 None
    Column('converted_timings', JSON, nullable=True),
)
