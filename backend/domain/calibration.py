"""换钟标定计算：同段新旧拍点拟合时钟比例与偏移，末段留作检验。

换算口径：旧钟时间 old = scale * 新钟时间 new + offset
"""
import numpy as np

# 检验段最大误差阈值（秒），超过则标定不启用
MAX_ERROR_LIMIT = 0.1
MIN_PAIRS = 6
MIN_FIT = 4
MIN_CHECK = 2


def split_pairs(pairs):
    """末段约 1/4 留作检验，且保证拟合段与检验段各有最少样本。"""
    need = len(pairs) >= MIN_PAIRS
    check_n = max(MIN_CHECK, len(pairs) // 4)
    fit_n = len(pairs) - check_n
    return need, fit_n


def fit_calibration(pairs):
    """返回拟合参数与检验结果。pairs 为 [{"old": float, "new": float}, ...]，按新钟时间升序。"""
    if not isinstance(pairs, list) or len(pairs) < MIN_PAIRS:
        raise ValueError(f'同段新旧拍点至少需要 {MIN_PAIRS} 对，末段还要留作检验')
    cleaned = []
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {'old', 'new'}:
            raise ValueError('每对拍点须为含 old、new 两个键的对象')
        old, new = pair['old'], pair['new']
        if type(old) not in (int, float) or type(new) not in (int, float):
            raise ValueError('新旧拍点须为有限数值')
        cleaned.append((float(old), float(new)))
    cleaned.sort(key=lambda item: item[1])
    if any(b[1] <= a[1] for a, b in zip(cleaned, cleaned[1:])):
        raise ValueError('新钟拍点须严格递增')
    if any(b[0] <= a[0] for a, b in zip(cleaned, cleaned[1:])):
        raise ValueError('旧钟拍点须严格递增')

    _, fit_n = split_pairs(cleaned)
    fit = cleaned[:fit_n]
    check = cleaned[fit_n:]
    if len(fit) < MIN_FIT or len(check) < MIN_CHECK:
        raise ValueError('拟合段或检验段样本不足')

    new_x = np.array([p[1] for p in fit])
    old_y = np.array([p[0] for p in fit])
    # 最小二乘拟合 old = scale * new + offset
    scale, offset = np.polyfit(new_x, old_y, 1)
    scale, offset = float(scale), float(offset)
    if not np.isfinite(scale) or not np.isfinite(offset) or scale <= 0:
        raise ValueError('拟合出的时钟比例非法（须为正数）')

    errors = [abs(old - (scale * new + offset)) for old, new in check]
    max_error = round(float(max(errors)), 6)
    return {
        'scale': round(scale, 9),
        'offset': round(offset, 9),
        'max_error': max_error,
        'fit_count': len(fit),
        'check_count': len(check),
        'passed': max_error <= MAX_ERROR_LIMIT,
    }


def apply_calibration(timings, scale, offset):
    """把换钟素材的原拍点换算到原时钟口径。"""
    return [round(scale * float(x) + offset, 6) for x in timings]
