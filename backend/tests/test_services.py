"""服务层集成测试（SQLite 内存库 + 假队列）：python tests/test_services.py"""
import os
import sys
from datetime import datetime

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET', 'test-secret')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import domain.cue_clusters_service as clusters_service
from core.db import metadata
from core.records import get, scan
from domain.calibration import MAX_ERROR_LIMIT
from domain.clock_calibrations_model import clock_calibrations
from domain.clock_calibrations_schemas import SubmitCalibration, BeatPair
from domain.clock_calibrations_service import submit_calibration
from domain.cue_tracks_model import cue_tracks
from domain.cue_tracks_schemas import RecordTrack
from domain.cue_tracks_service import record_track, lock_track, resolve_track
from domain.venues_model import venues
from domain.cue_clusters_schemas import SaveCluster

USER = {'sub': 'operator@demo.test', 'role': 'operator'}
REVIEWER = {'sub': 'reviewer@demo.test', 'role': 'reviewer'}

engine = create_engine('sqlite://', poolclass=StaticPool,
                       connect_args={'check_same_thread': False})
metadata.create_all(engine)


def Pair(old, new):
    return BeatPair(old=old, new=new)


def calibration_payload(code, metronome, frm, to, pairs):
    return SubmitCalibration(code=code, metronome=metronome,
                             valid_from=frm, valid_to=to, pairs=pairs)


def good_pairs(scale=1.002, offset=0.01):
    return [Pair(round(scale * n + offset, 4), n) for n in
            (10.02, 10.66, 11.3, 11.94, 12.58, 13.22, 13.86, 14.5)]


def bad_pairs():
    pairs = good_pairs()
    pairs[-1].old += 0.5
    pairs[-2].old += 0.4
    return pairs


def main():
    with engine.begin() as conn:
        conn.execute(venues.insert().values(code='HALL-A', protocol='PULSE4',
                                             channels=3, ready=True))

    # 1) 合格标定启用
    with engine.begin() as conn:
        cal1 = submit_calibration(conn, USER, calibration_payload(
            'CAL-1', 'MET-NEW-01', datetime(2026, 11, 25, 16), datetime(2026, 11, 25, 20),
            good_pairs()))
    assert cal1['enabled'] is True and cal1['max_error'] <= MAX_ERROR_LIMIT

    # 2) 同计拍器时段重叠的第二份只收存不启用
    with engine.begin() as conn:
        cal2 = submit_calibration(conn, USER, calibration_payload(
            'CAL-2', 'MET-NEW-01', datetime(2026, 11, 25, 18), datetime(2026, 11, 25, 22),
            good_pairs()))
    assert cal2['enabled'] is False and '重叠' in cal2['note']

    # 3) 检验超差的标定也只收存不启用（独立计拍器，无重叠因素）
    with engine.begin() as conn:
        cal3 = submit_calibration(conn, USER, calibration_payload(
            'CAL-3', 'MET-NEW-02', datetime(2026, 11, 25, 16), datetime(2026, 11, 25, 20),
            bad_pairs()))
    assert cal3['enabled'] is False and cal3['max_error'] > MAX_ERROR_LIMIT

    # 4) 不重叠时段的标定可同时启用
    with engine.begin() as conn:
        cal4 = submit_calibration(conn, USER, calibration_payload(
            'CAL-4', 'MET-NEW-01', datetime(2026, 11, 25, 20), datetime(2026, 11, 26, 2),
            good_pairs()))
    assert cal4['enabled'] is True

    # 5) 换钟原件先收存：MET-NEW-02 无生效标定，换算留空
    with engine.begin() as conn:
        record_track(conn, USER, RecordTrack(
            code='CUE-X1', venue='HALL-A', timings=[1, 2, 3, 4, 5, 6], shift=0.0,
            clock='换钟', metronome='MET-NEW-02', measured_at=datetime(2026, 11, 25, 18)))
        x1 = get(conn, cue_tracks, 'CUE-X1')
    assert x1['calibration'] is None and x1['converted_timings'] is None and x1['locked'] is False

    # 6) 未标定换钟素材禁止见证
    try:
        with engine.begin() as conn:
            lock_track(conn, REVIEWER, type('D', (), {'track': 'CUE-X1'})())
    except Exception as exc:
        assert '标定' in str(exc.detail if hasattr(exc, 'detail') else exc)
    else:
        raise AssertionError('未标定换钟素材不应允许见证')

    # 7) 晚到的试投记录按测量时间认标定：落在 CAL-1 时段自动认用
    with engine.begin() as conn:
        record_track(conn, USER, RecordTrack(
            code='CUE-X2', venue='HALL-A', timings=[1, 2, 3, 4, 5, 6], shift=0.0,
            clock='换钟', metronome='MET-NEW-01', measured_at=datetime(2026, 11, 25, 17, 30)))
        x2 = get(conn, cue_tracks, 'CUE-X2')
    assert x2['calibration'] == 'CAL-1'
    expected = [round(cal1['scale'] * t + cal1['offset'], 6) for t in (1, 2, 3, 4, 5, 6)]
    assert x2['converted_timings'] == expected
    # 落在 CAL-4 时段（20:00 边界含端点）认另一份
    with engine.begin() as conn:
        record_track(conn, USER, RecordTrack(
            code='CUE-X3', venue='HALL-A', timings=[1, 2, 3, 4, 5, 6], shift=0.0,
            clock='换钟', metronome='MET-NEW-01', measured_at=datetime(2026, 11, 25, 21)))
        x3 = get(conn, cue_tracks, 'CUE-X3')
    assert x3['calibration'] == 'CAL-4'

    # 8) 标定晚到后补认 X1：先确认无生效标定时补认被拒，再登记合格且不重叠的启用标定
    try:
        with engine.begin() as conn:
            resolve_track(conn, USER, type('D', (), {'track': 'CUE-X1'})())
    except Exception as exc:
        assert '无生效标定' in str(getattr(exc, 'detail', exc))
    else:
        raise AssertionError('无生效标定时补认应被拒')
    with engine.begin() as conn:
        submit_calibration(conn, USER, calibration_payload(
            'CAL-5', 'MET-NEW-02', datetime(2026, 11, 25, 16), datetime(2026, 11, 25, 20),
            good_pairs()))
        resolve_track(conn, USER, type('D', (), {'track': 'CUE-X1'})())
        x1 = get(conn, cue_tracks, 'CUE-X1')
    assert x1['calibration'] == 'CAL-5' and x1['converted_timings'] is not None

    # 9) 补认后复核员可见证
    with engine.begin() as conn:
        lock_track(conn, REVIEWER, type('D', (), {'track': 'CUE-X1'})())
        lock_track(conn, REVIEWER, type('D', (), {'track': 'CUE-X2'})())
        assert get(conn, cue_tracks, 'CUE-X1')['locked'] is True

    # 10) 原时钟素材照用，且无需计拍器字段
    with engine.begin() as conn:
        record_track(conn, USER, RecordTrack(
            code='CUE-O1', venue='HALL-A', timings=[1, 2, 3, 4], shift=0.0))
        o1 = get(conn, cue_tracks, 'CUE-O1')
    assert o1['clock'] == '原时钟' and o1['metronome'] is None
    with engine.begin() as conn:
        lock_track(conn, REVIEWER, type('D', (), {'track': 'CUE-O1'})())

    # 11) 对场比较：假队列捕获受理快照，换钟素材使用换算拍点并携带标定
    captured = {}

    def fake_submit(user, payload):
        captured.update(payload)
        return {'token': 'TOK-1', 'status': 'queued'}

    def fake_result(user, token):
        return {'status': 'ready',
                'input': captured,
                'result': {'representative': 'CUE-O1', 'distance': 0.12,
                           'members': ['CUE-O1', 'CUE-X2'], 'reference_count': 1}}

    clusters_service.submit = fake_submit
    clusters_service.result = fake_result

    # 先凑够 8 条已锁定参考（原时钟）
    with engine.begin() as conn:
        for i in range(8):
            code = f'CUE-R{i}'
            record_track(conn, USER, RecordTrack(
                code=code, venue='HALL-A', timings=[0.5 + i, 1.5 + i, 2.5 + i, 3.5 + i],
                shift=0.0))
            lock_track(conn, REVIEWER, type('D', (), {'track': code})())

    with engine.begin() as conn:
        clusters_service.compare_cues(conn, USER, type('D', (), {'track': 'CUE-X2'})())
    assert captured['calibration'] == 'CAL-1'
    assert captured['track']['timings'] == x2['converted_timings']
    assert all(r.get('calibration') in (None, 'CAL-1', 'CAL-4', 'CAL-5') for r in captured['references'])

    # 12) 未见证的换钟素材不得对场
    try:
        with engine.begin() as conn:
            clusters_service.compare_cues(conn, USER, type('D', (), {'track': 'CUE-X3'})())
    except Exception as exc:
        assert '对场' in str(getattr(exc, 'detail', exc))
    else:
        raise AssertionError('未见证换钟素材不应进入对场比较')

    # 13) 签簇沿用受理时换算，并把标定号落到簇上
    with engine.begin() as conn:
        clusters_service.save_cluster(conn, REVIEWER, SaveCluster(code='BEAT-9', token='TOK-1'))
        from domain.cue_clusters_model import cue_clusters
        cluster = get(conn, cue_clusters, 'BEAT-9')
    assert cluster['calibration'] == 'CAL-1' and cluster['token'] == 'TOK-1'

    print('13 service scenarios passed')


if __name__ == '__main__':
    main()
