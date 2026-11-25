"""HTTP 层冒烟测试（SQLite 文件库 + Redis 桩）：python tests/test_api.py"""
import os
import sys
import tempfile

_db = os.path.join(tempfile.mkdtemp(), 'api_smoke.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_db}'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['JWT_SECRET'] = 'test-secret'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import core.queueing as queueing
import domain.cue_clusters_service as clusters_service
from core.app import app


def fake_submit(user, payload):
    fake_submit.last = payload
    return {'token': 'TOK-API', 'status': 'queued'}


def fake_result(user, token):
    return {'status': 'ready', 'input': fake_submit.last,
            'result': {'representative': 'CUE-R0', 'distance': 0.2,
                       'members': ['CUE-R0'], 'reference_count': 8}}


# 服务用 `from core.queueing import ...` 绑定，须桩到服务模块命名空间
clusters_service.submit = fake_submit
clusters_service.result = fake_result
queueing.view = fake_result
# 不触发 lifespan（避免真 Redis 连接），手动建表
from core.db import metadata, engine
metadata.create_all(engine)

client = TestClient(app)

# 直接建一条已验收场地（sign-venue 仅更新既有场地）
from domain.venues_model import venues
with engine.begin() as conn:
    conn.execute(venues.insert().values(code='HALL-A', protocol='PULSE4',
                                        channels=3, ready=True))


def login(role):
    resp = client.post('/auth/login', json={'email': f'{role}@demo.test',
                                            'password': 'DemoC0de!2026'})
    assert resp.status_code == 200
    return {'Authorization': 'Bearer ' + resp.json()['token']}


def main():
    op = login('operator')
    rv = login('reviewer')

    # 未登录拒绝
    assert client.get('/clock_calibrations').status_code == 401

    pairs = [{'old': round(1.002 * n + 0.01, 4), 'new': n} for n in
             (10.02, 10.66, 11.3, 11.94, 12.58, 13.22, 13.86, 14.5)]
    cal = client.post('/clock_calibrations/submit-calibration', headers=op, json={
        'code': 'CAL-A', 'metronome': 'MET-1',
        'valid_from': '2026-11-25T16:00:00', 'valid_to': '2026-11-25T20:00:00',
        'pairs': pairs}).json()
    assert cal['enabled'] is True

    # 超差标定收存但不启用
    bad = [dict(p) for p in pairs]
    bad[-1]['old'] += 0.5
    bad[-2]['old'] += 0.4
    cal_bad = client.post('/clock_calibrations/submit-calibration', headers=op, json={
        'code': 'CAL-BAD', 'metronome': 'MET-2',
        'valid_from': '2026-11-25T16:00:00', 'valid_to': '2026-11-25T20:00:00',
        'pairs': bad}).json()
    assert cal_bad['enabled'] is False

    # 登记换钟素材：自动按测量时间认标定并换算
    track = client.post('/cue_tracks/record-track', headers=op, json={
        'code': 'CUE-NEW', 'venue': 'HALL-A', 'timings': [1, 2, 3, 4, 5, 6],
        'shift': 0.0, 'clock': '换钟', 'metronome': 'MET-1',
        'measured_at': '2026-11-25T17:30:00'}).json()
    assert track['calibration'] == 'CAL-A' and track['converted_timings']

    # 未标定换钟原件先收存
    pending = client.post('/cue_tracks/record-track', headers=op, json={
        'code': 'CUE-PEND', 'venue': 'HALL-A', 'timings': [1, 2, 3, 4, 5, 6],
        'shift': 0.0, 'clock': '换钟', 'metronome': 'MET-9',
        'measured_at': '2026-11-25T17:30:00'}).json()
    assert pending['calibration'] is None and pending['converted_timings'] is None

    # 作业员无权见证
    assert client.post('/cue_tracks/lock-track', headers=op,
                       json={'track': 'CUE-NEW'}).status_code == 403
    # 未标定原件见证被业务拒绝
    assert client.post('/cue_tracks/lock-track', headers=rv,
                       json={'track': 'CUE-PEND'}).status_code == 409
    # 已标定换钟素材复核员可见证
    assert client.post('/cue_tracks/lock-track', headers=rv,
                       json={'track': 'CUE-NEW'}).json()['locked'] is True

    # 凑 8 条已锁定原时钟参考
    for i in range(8):
        code = f'CUE-R{i}'
        client.post('/cue_tracks/record-track', headers=op, json={
            'code': code, 'venue': 'HALL-A',
            'timings': [0.5 + i, 1.5 + i, 2.5 + i, 3.5 + i], 'shift': 0.0})
        client.post('/cue_tracks/lock-track', headers=rv, json={'track': code})

    # 对场比较 + 签簇沿用受理换算
    assert client.post('/cue_clusters/compare-cues', headers=op,
                       json={'track': 'CUE-NEW'}).json()['status'] == 'queued'
    saved = client.post('/cue_clusters/save-cluster', headers=rv,
                        json={'code': 'BEAT-API', 'token': 'TOK-API'}).json()
    assert saved['calibration'] == 'CAL-A'

    # 台账可查标定与原件
    rows = client.get('/cue_tracks', headers=op).json()
    assert any(r['code'] == 'CUE-NEW' and r['converted_timings'] for r in rows)
    cals = client.get('/clock_calibrations', headers=op).json()
    assert {c['code'] for c in cals} == {'CAL-A', 'CAL-BAD'}

    print('API smoke test passed')


if __name__ == '__main__':
    main()
