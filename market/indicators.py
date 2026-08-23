"""
المؤشرات الفنية — technical indicators in pure Python.

كل الدوال تعمل على قوائم من الأرقام (``list[float]``) وتُعيد قوائم بنفس
الطول، حيث تكون القيم غير المتاحة (فترة الإحماء) ``None``. هذا يبقي
التطبيق خفيفًا بلا numpy/pandas ويجعل ربط النتائج بالشموع مباشرًا.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

Num = Optional[float]
Series = List[Num]


# ─────────────────────────── أدوات مساعدة ───────────────────────────


def _clean(values: Sequence[Num]) -> List[float]:
    return [float(v) for v in values if v is not None]


def last_valid(series: Sequence[Num]) -> Num:
    """آخر قيمة غير فارغة في السلسلة."""
    for value in reversed(series):
        if value is not None:
            return value
    return None


def slope(series: Sequence[Num], lookback: int = 10) -> Num:
    """ميل خط الانحدار الخطي لآخر ``lookback`` قيمة (تغيّر لكل شمعة)."""
    points = [(i, v) for i, v in enumerate(series[-lookback:]) if v is not None]
    if len(points) < 3:
        return None
    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return None
    return (n * sum_xy - sum_x * sum_y) / denom


def pct_change(new: Num, old: Num) -> Num:
    if new is None or old in (None, 0):
        return None
    return (new - old) / abs(old) * 100.0


# ─────────────────────────── المتوسطات ───────────────────────────


def sma(values: Sequence[float], period: int) -> Series:
    """المتوسط المتحرك البسيط."""
    out: Series = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    running = sum(values[:period])
    out[period - 1] = running / period
    for i in range(period, len(values)):
        running += values[i] - values[i - period]
        out[i] = running / period
    return out


def ema(values: Sequence[float], period: int) -> Series:
    """المتوسط المتحرك الأسّي (يبدأ من SMA لأول فترة)."""
    out: Series = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = (values[i] - prev) * k + prev
        out[i] = prev
    return out


def wilder_smooth(values: Sequence[float], period: int) -> Series:
    """تنعيم وايلدر المستخدم في RSI و ATR و ADX."""
    out: Series = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = prev + (values[i] - prev) / period
        out[i] = prev
    return out


# ─────────────────────────── الزخم ───────────────────────────


def rsi(closes: Sequence[float], period: int = 14) -> Series:
    """مؤشر القوة النسبية بطريقة وايلدر."""
    out: Series = [None] * len(closes)
    if len(closes) <= period:
        return out

    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = _rsi(avg_gain, avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


def macd(
    closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, Series]:
    """الماكد: خط الماكد وخط الإشارة والهستوغرام."""
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_line: Series = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(fast_ema, slow_ema)
    ]

    valid = [v for v in macd_line if v is not None]
    signal_line: Series = [None] * len(closes)
    if len(valid) >= signal:
        offset = len(macd_line) - len(valid)
        sig = ema(valid, signal)
        for i, v in enumerate(sig):
            signal_line[offset + i] = v

    hist: Series = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    return {"macd": macd_line, "signal": signal_line, "hist": hist}


def stochastic(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    k_period: int = 14,
    d_period: int = 3,
) -> Dict[str, Series]:
    """مذبذب ستوكاستك %K و %D."""
    n = len(closes)
    k_line: Series = [None] * n
    for i in range(k_period - 1, n):
        window_high = max(highs[i - k_period + 1 : i + 1])
        window_low = min(lows[i - k_period + 1 : i + 1])
        rng = window_high - window_low
        k_line[i] = 50.0 if rng == 0 else (closes[i] - window_low) / rng * 100.0

    valid = [v for v in k_line if v is not None]
    d_line: Series = [None] * n
    if len(valid) >= d_period:
        offset = n - len(valid)
        smoothed = sma(valid, d_period)
        for i, v in enumerate(smoothed):
            d_line[offset + i] = v
    return {"k": k_line, "d": d_line}


def roc(closes: Sequence[float], period: int = 20) -> Series:
    """معدل التغيّر (%) خلال ``period`` شمعة."""
    out: Series = [None] * len(closes)
    for i in range(period, len(closes)):
        base = closes[i - period]
        if base:
            out[i] = (closes[i] - base) / abs(base) * 100.0
    return out


# ─────────────────────────── التذبذب ───────────────────────────


def true_range(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]
) -> List[float]:
    out = [highs[0] - lows[0]] if highs else []
    for i in range(1, len(highs)):
        out.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )
    return out


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> Series:
    """المدى الحقيقي المتوسط."""
    return wilder_smooth(true_range(highs, lows, closes), period)


def bollinger(
    closes: Sequence[float], period: int = 20, mult: float = 2.0
) -> Dict[str, Series]:
    """بولنجر باند: العلوي والأوسط والسفلي وعرض النطاق (%)."""
    mid = sma(closes, period)
    upper: Series = [None] * len(closes)
    lower: Series = [None] * len(closes)
    width: Series = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = mid[i]
        if mean is None:
            continue
        variance = sum((c - mean) ** 2 for c in window) / period
        sd = math.sqrt(variance)
        upper[i] = mean + mult * sd
        lower[i] = mean - mult * sd
        width[i] = (upper[i] - lower[i]) / mean * 100.0 if mean else None
    return {"upper": upper, "middle": mid, "lower": lower, "width": width}


def historical_volatility(closes: Sequence[float], period: int = 20) -> Num:
    """التذبذب السنوي التقريبي (%) من العوائد اللوغاريتمية اليومية."""
    if len(closes) < period + 1:
        return None
    rets = []
    for i in range(len(closes) - period, len(closes)):
        prev, cur = closes[i - 1], closes[i]
        if prev > 0 and cur > 0:
            rets.append(math.log(cur / prev))
    if len(rets) < 3:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100.0


# ─────────────────────────── الاتجاه ───────────────────────────


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> Dict[str, Series]:
    """مؤشر الاتجاه ADX مع +DI و -DI (قوة الاتجاه واتجاهه)."""
    n = len(closes)
    empty: Series = [None] * n
    if n < period * 2:
        return {"adx": empty, "plus_di": list(empty), "minus_di": list(empty)}

    plus_dm, minus_dm = [0.0], [0.0]
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)

    tr = true_range(highs, lows, closes)
    tr_s = wilder_smooth(tr, period)
    plus_s = wilder_smooth(plus_dm, period)
    minus_s = wilder_smooth(minus_dm, period)

    plus_di: Series = [None] * n
    minus_di: Series = [None] * n
    dx: List[float] = []
    dx_index: List[int] = []

    for i in range(n):
        if tr_s[i] in (None, 0) or plus_s[i] is None or minus_s[i] is None:
            continue
        pdi = plus_s[i] / tr_s[i] * 100.0
        mdi = minus_s[i] / tr_s[i] * 100.0
        plus_di[i] = pdi
        minus_di[i] = mdi
        total = pdi + mdi
        if total > 0:
            dx.append(abs(pdi - mdi) / total * 100.0)
            dx_index.append(i)

    adx_line: Series = [None] * n
    if len(dx) >= period:
        smoothed = wilder_smooth(dx, period)
        for pos, value in enumerate(smoothed):
            if value is not None:
                adx_line[dx_index[pos]] = value

    return {"adx": adx_line, "plus_di": plus_di, "minus_di": minus_di}


def obv(closes: Sequence[float], volumes: Sequence[float]) -> Series:
    """حجم التوازن — يتراكم الحجم حسب اتجاه الإغلاق."""
    out: Series = [None] * len(closes)
    if not closes:
        return out
    total = 0.0
    out[0] = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            total += volumes[i]
        elif closes[i] < closes[i - 1]:
            total -= volumes[i]
        out[i] = total
    return out


# ─────────────────────────── البنية السعرية ───────────────────────────


def swing_points(
    highs: Sequence[float], lows: Sequence[float], span: int = 3
) -> Dict[str, List[Tuple[int, float]]]:
    """قمم وقيعان محورية: نقطة أعلى/أدنى من ``span`` شمعة على كل جانب."""
    tops: List[Tuple[int, float]] = []
    bottoms: List[Tuple[int, float]] = []
    n = len(highs)
    for i in range(span, n - span):
        window_h = highs[i - span : i + span + 1]
        window_l = lows[i - span : i + span + 1]
        if highs[i] == max(window_h) and window_h.count(highs[i]) == 1:
            tops.append((i, highs[i]))
        if lows[i] == min(window_l) and window_l.count(lows[i]) == 1:
            bottoms.append((i, lows[i]))
    return {"tops": tops, "bottoms": bottoms}


def cluster_levels(
    points: Sequence[Tuple[int, float]], tolerance_pct: float = 1.5
) -> List[Dict[str, float]]:
    """يدمج النقاط المتقاربة سعريًا في مستويات دعم/مقاومة مع وزن التكرار."""
    if not points:
        return []
    ordered = sorted(points, key=lambda p: p[1])
    clusters: List[List[Tuple[int, float]]] = [[ordered[0]]]
    for point in ordered[1:]:
        ref = clusters[-1][-1][1]
        if ref and abs(point[1] - ref) / ref * 100.0 <= tolerance_pct:
            clusters[-1].append(point)
        else:
            clusters.append([point])

    levels = []
    for group in clusters:
        prices = [p[1] for p in group]
        levels.append(
            {
                "price": sum(prices) / len(prices),
                "touches": len(group),
                "last_index": max(p[0] for p in group),
            }
        )
    return levels


def support_resistance(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    span: int = 3,
    tolerance_pct: float = 1.5,
    max_levels: int = 4,
) -> Dict[str, List[Dict[str, float]]]:
    """أقرب مستويات الدعم (تحت السعر) والمقاومة (فوق السعر)."""
    if not closes:
        return {"supports": [], "resistances": []}

    swings = swing_points(highs, lows, span)
    price = closes[-1]
    levels = cluster_levels(swings["tops"] + swings["bottoms"], tolerance_pct)

    supports = sorted(
        [lv for lv in levels if lv["price"] < price * 0.999],
        key=lambda lv: price - lv["price"],
    )
    resistances = sorted(
        [lv for lv in levels if lv["price"] > price * 1.001],
        key=lambda lv: lv["price"] - price,
    )

    for lv in supports + resistances:
        lv["distance_pct"] = (lv["price"] - price) / price * 100.0

    return {
        "supports": supports[:max_levels],
        "resistances": resistances[:max_levels],
    }


def trendline(
    points: Sequence[Tuple[int, float]], last_index: int, min_points: int = 3
) -> Optional[Dict[str, float]]:
    """
    خط اتجاه بالانحدار الخطي على النقاط المحورية الأخيرة.

    يُعيد الميل والقيمة الحالية للخط، ونسبة الميل لكل شمعة حتى تُقارن
    بين الأسهم المختلفة الأسعار.
    """
    recent = list(points)[-6:]
    if len(recent) < min_points:
        return None

    n = len(recent)
    sum_x = sum(p[0] for p in recent)
    sum_y = sum(p[1] for p in recent)
    sum_xy = sum(p[0] * p[1] for p in recent)
    sum_xx = sum(p[0] * p[0] for p in recent)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return None

    m = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - m * sum_x) / n
    value_now = m * last_index + b
    if value_now == 0:
        return None

    return {
        "slope": m,
        "intercept": b,
        "value_now": value_now,
        "slope_pct": m / abs(value_now) * 100.0,
        "start_index": recent[0][0],
        "start_value": m * recent[0][0] + b,
        "points": len(recent),
    }


def range_position(closes: Sequence[float], lookback: int = 252) -> Dict[str, Num]:
    """موقع السعر داخل نطاق آخر سنة (0% عند القاع، 100% عند القمة)."""
    window = list(closes[-lookback:])
    if len(window) < 5:
        return {"high": None, "low": None, "position_pct": None}
    high, low = max(window), min(window)
    rng = high - low
    return {
        "high": high,
        "low": low,
        "position_pct": 50.0 if rng == 0 else (closes[-1] - low) / rng * 100.0,
    }


def rsi_divergence(
    closes: Sequence[float], rsi_series: Sequence[Num], lookback: int = 40, span: int = 3
) -> Optional[str]:
    """
    دايفرجنس بين السعر والـ RSI.

    ``bullish``  : قاع سعري أدنى مقابل قاع RSI أعلى (إشارة انعكاس صاعد).
    ``bearish``  : قمة سعرية أعلى مقابل قمة RSI أدنى (إشارة انعكاس هابط).
    """
    if len(closes) < lookback:
        return None

    start = len(closes) - lookback
    window_closes = list(closes[start:])
    swings = swing_points(window_closes, window_closes, span)

    def _pair(points: List[Tuple[int, float]]):
        if len(points) < 2:
            return None
        (i1, p1), (i2, p2) = points[-2], points[-1]
        r1, r2 = rsi_series[start + i1], rsi_series[start + i2]
        if r1 is None or r2 is None:
            return None
        return p1, p2, r1, r2

    bottoms = _pair(swings["bottoms"])
    if bottoms:
        p1, p2, r1, r2 = bottoms
        if p2 < p1 * 0.995 and r2 > r1 + 1.5:
            return "bullish"

    tops = _pair(swings["tops"])
    if tops:
        p1, p2, r1, r2 = tops
        if p2 > p1 * 1.005 and r2 < r1 - 1.5:
            return "bearish"

    return None
