from sqlalchemy import select

from core.queueing import submit, result
from core.records import get, insert, need, scan, update
from domain.venues_model import venues
from domain.cue_tracks_model import cue_tracks
from domain.cue_clusters_model import cue_clusters
from domain.cue_routing_model import cue_routing
from domain.cue_tracks_schemas import CLOCK_REPLACED


def _comparable(row):
    """可对场素材：原时钟照用；换钟素材须已见证且已标定，拍点取受理时的换算值。"""
    if row['clock'] != CLOCK_REPLACED:
        return True, row['timings'], ''
    if not row['locked'] or not row['calibration'] or not row['converted_timings']:
        return False, None, None
    return True, row['converted_timings'], row['calibration']


def compare_cues(conn, user, data):
    q = get(conn, cue_tracks, data.track)
    ok, q_timings, q_calibration = _comparable(q)
    need(q['locked'] and ok, '换钟素材须经标定和见证后才可对场')

    references = []
    for row in scan(conn, cue_tracks):
        if not row['locked'] or row['code'] == data.track:
            continue
        good, timings, _ = _comparable(row)
        if not good:
            continue  # 未标定的换钟原件不得进入可匹配集合
        references.append({**row, 'timings': timings})
    need(8 <= len(references) <= 200, '需要已确认素材及足够参考片段')

    track_snapshot = {**q, 'timings': q_timings}
    # 任务输入即受理时刻的换算快照，后续标定变化不影响本次比较
    return submit(user, {'track': track_snapshot, 'references': references,
                         'calibration': q_calibration})


def save_cluster(conn, user, data):
    run = result(user, data.token)
    stats = run['result']
    # 签簇沿用比较受理时的换算
    calibration = run['input'].get('calibration', '')
    return insert(conn, cue_clusters, code=data.code, track=run['input']['track']['code'],
                  representative=stats['representative'], distance=stats['distance'],
                  members=stats['members'], token=data.token, calibration=calibration)
