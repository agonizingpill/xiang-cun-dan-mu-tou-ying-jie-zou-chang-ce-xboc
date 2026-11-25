"""标定拟合纯逻辑测试：python -I tests/test_calibration.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.calibration import fit_calibration, apply_calibration, MAX_ERROR_LIMIT, MIN_PAIRS


def make_pairs(scale, offset, n=8, noise=0.0, jitter=0.0):
    pairs = []
    for k in range(n):
        new = 10.0 + k * 0.65 + jitter
        old = round(scale * new + offset + noise * ((-1) ** k), 6)
        pairs.append({'old': old, 'new': round(new, 4)})
    return pairs


def test_pass_tight_clock():
    pairs = make_pairs(1.002, 0.01, noise=0.005)
    out = fit_calibration(pairs)
    assert out['passed'] is True
    assert abs(out['scale'] - 1.002) < 0.002
    assert abs(out['offset'] - 0.01) < 0.05
    assert out['max_error'] <= MAX_ERROR_LIMIT
    assert out['fit_count'] + out['check_count'] == len(pairs)
    assert out['check_count'] >= 2 and out['fit_count'] >= 4
    converted = apply_calibration([10.0, 20.0], out['scale'], out['offset'])
    assert converted == sorted(converted)


def test_fail_large_error():
    # 检验段（最后 2 对）故意加入远超 0.1s 的偏差
    pairs = make_pairs(1.0, 0.0, n=8)
    pairs[-1]['old'] += 0.5
    pairs[-2]['old'] += 0.4
    out = fit_calibration(pairs)
    assert out['passed'] is False
    assert out['max_error'] > MAX_ERROR_LIMIT


def test_too_few_pairs():
    try:
        fit_calibration(make_pairs(1.0, 0.0, n=MIN_PAIRS - 1))
    except ValueError:
        pass
    else:
        raise AssertionError('样本不足应拒绝')


def test_bad_shape_and_order():
    bad = [{'old': 1, 'new': 1}, {'old': 2}]
    try:
        fit_calibration(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('结构非法应拒绝')
    pairs = make_pairs(1.0, 0.0)
    pairs[2]['new'] = pairs[3]['new']
    try:
        fit_calibration(pairs)
    except ValueError:
        pass
    else:
        raise AssertionError('新钟拍点非递增应拒绝')


def test_nonpositive_scale_rejected():
    pairs = make_pairs(1.0, 0.0)
    for p in pairs:
        p['old'] = -p['new']
    try:
        fit_calibration(pairs)
    except ValueError:
        pass
    else:
        raise AssertionError('非正比例应拒绝')


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for test in tests:
        test()
        print('PASS', test.__name__)
    print(f'{len(tests)} calibration tests passed')
