from sqlalchemy import select

from core.records import insert, need, scan, update
from domain.calibration import fit_calibration, MAX_ERROR_LIMIT
from domain.clock_calibrations_model import clock_calibrations


def list_enabled(conn, metronome=None):
    rows = scan(conn, clock_calibrations)
    out = [r for r in rows if r['enabled'] and (metronome is None or r['metronome'] == metronome)]
    return out


def effective_calibration(conn, metronome, measured_at, lock=False):
    """按计拍器和测量时间取生效标定；晚到的试投记录也按测量时间认这一份。

    时段为半开区间 [valid_from, valid_to)，边界时刻只归后一份，保证唯一命中。
    """
    query = select(clock_calibrations).where(
        clock_calibrations.c.metronome == metronome,
        clock_calibrations.c.enabled.is_(True),
        clock_calibrations.c.valid_from <= measured_at,
        clock_calibrations.c.valid_to > measured_at,
    )
    if lock:
        query = query.with_for_update()
    rows = [dict(r) for r in conn.execute(query).mappings()]
    return rows[0] if rows else None


def overlaps(a_from, a_to, b_from, b_to):
    # 半开区间：仅端点相接不算重叠
    return a_from < b_to and b_from < a_to


def submit_calibration(conn, user, data):
    need(data.valid_from < data.valid_to, '测量时段起须早于止')
    result = fit_calibration([p.model_dump() for p in data.pairs])

    # 同计拍器时段重叠的标定只允许启用一份：先锁表内该计拍器的全部行再判重叠
    existing = [dict(r) for r in conn.execute(
        select(clock_calibrations).where(
            clock_calibrations.c.metronome == data.metronome).with_for_update()).mappings()]
    clash = next((r for r in existing if r['enabled']
                  and overlaps(data.valid_from, data.valid_to, r['valid_from'], r['valid_to'])), None)
    enabled = result['passed'] and clash is None
    if not result['passed']:
        note = f'检验最大误差 {result["max_error"]}s 超过 {MAX_ERROR_LIMIT}s，收存但不启用'
    elif clash is not None:
        note = f'与已启用标定 {clash["code"]} 测量时段重叠，仅收存不启用'
    else:
        note = f'检验通过（最大误差 {result["max_error"]}s），已启用'

    return insert(conn, clock_calibrations,
                  code=data.code, metronome=data.metronome,
                  valid_from=data.valid_from, valid_to=data.valid_to,
                  pairs=[p.model_dump() for p in data.pairs],
                  scale=result['scale'], offset=result['offset'],
                  max_error=result['max_error'], fit_count=result['fit_count'],
                  check_count=result['check_count'], enabled=enabled, note=note)
