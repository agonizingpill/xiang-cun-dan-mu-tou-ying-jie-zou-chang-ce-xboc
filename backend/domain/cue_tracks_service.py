from sqlalchemy import select

from core.records import get, insert, need, scan, update
from domain.venues_model import venues
from domain.cue_tracks_model import cue_tracks
from domain.cue_clusters_model import cue_clusters
from domain.cue_routing_model import cue_routing
from domain.cue_tracks_schemas import CLOCK_ORIGINAL, CLOCK_REPLACED
from domain.clock_calibrations_service import effective_calibration
from domain.calibration import apply_calibration


def _bind_calibration(conn, row, lock=False):
    """换钟素材按计拍器与测量时间认标定，返回可直接落库的字段。"""
    cal = effective_calibration(conn, row['metronome'], row['measured_at'], lock=lock)
    if cal is None:
        return {'calibration': None, 'converted_timings': None}
    converted = apply_calibration(row['timings'], cal['scale'], cal['offset'])
    return {'calibration': cal['code'], 'converted_timings': converted}


def record_track(conn, user, data):
    v = get(conn, venues, data.venue)
    need(v['ready'], '场地未签验收单')
    t = data.timings
    need(isinstance(t, list) and 4 <= len(t) <= 30 and all(type(x) in (int, float) and 0 <= x <= 180 for x in t)
         and all(a < b for a, b in zip(t, t[1:])), '拍点需为递增有限时间序列')
    need(-5 <= data.shift <= 5, '拍点漂移超界')
    need(data.clock in (CLOCK_ORIGINAL, CLOCK_REPLACED), '时钟来源须为原时钟或换钟')

    payload = data.model_dump()
    if data.clock == CLOCK_REPLACED:
        need(data.metronome, '换钟素材须登记计拍器编号')
        need(data.measured_at is not None, '换钟素材须登记测量时间，以便按测量时段认标定')
        # 未标定的原件先收存：原拍点照录，换算留空，等标定到位再补认
        payload.update(_bind_calibration(conn, payload))
    else:
        # 原时钟素材照用，不挂计拍器与标定
        payload.update(metronome=None, measured_at=None,
                       calibration=None, converted_timings=None)
    return insert(conn, cue_tracks, **payload, locked=False)


def lock_track(conn, user, data):
    row = get(conn, cue_tracks, data.track, lock=True)
    # 换钟素材经标定和见证才可对场：未标定先不允许见证锁定
    if row['clock'] == CLOCK_REPLACED:
        need(row['calibration'] is not None, '换钟素材尚未取得生效标定，先收存原件并补认标定后再见证')
    return update(conn, cue_tracks, data.track, locked=True)


def resolve_track(conn, user, data):
    """标定晚到时，对已收存的换钟原件按测量时间补认标定并换算。"""
    row = get(conn, cue_tracks, data.track, lock=True)
    need(row['clock'] == CLOCK_REPLACED, '仅换钟素材需要补认标定')
    bound = _bind_calibration(conn, row, lock=True)
    need(bound['calibration'] is not None, '该计拍器在测量时段仍无生效标定')
    return update(conn, cue_tracks, data.track, **bound)
