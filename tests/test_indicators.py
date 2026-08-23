"""اختبارات المؤشرات الفنية — قيم معروفة مسبقًا لا تخمينات."""

import math

import pytest

from market import indicators as ta


def test_sma_matches_manual_average():
    values = [float(i) for i in range(1, 11)]
    result = ta.sma(values, 3)
    assert result[:2] == [None, None]      # فترة الإحماء
    assert result[2] == pytest.approx(2.0)  # (1+2+3)/3
    assert result[-1] == pytest.approx(9.0)  # (8+9+10)/3


def test_ema_seeds_from_sma_and_tracks_trend():
    values = [float(i) for i in range(1, 21)]
    result = ta.ema(values, 5)
    assert result[3] is None
    assert result[4] == pytest.approx(3.0)   # بذرة = متوسط أول ٥
    assert result[-1] < values[-1]           # المتوسط يتخلّف عن سعر صاعد
    assert result[-1] > result[-2]


def test_rsi_saturates_at_extremes():
    rising = [float(i) for i in range(1, 30)]
    falling = list(reversed(rising))
    assert ta.rsi(rising, 14)[-1] == pytest.approx(100.0)
    assert ta.rsi(falling, 14)[-1] == pytest.approx(0.0)


def test_rsi_sits_midrange_on_alternating_series():
    values = []
    price = 50.0
    for i in range(60):
        price += 1.0 if i % 2 == 0 else -1.0
        values.append(price)
    assert 40.0 < ta.rsi(values, 14)[-1] < 60.0


def test_atr_on_constant_range_equals_that_range():
    closes = [float(i) for i in range(1, 30)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    # مدى الشمعة ٢، والفجوة بين الإغلاقات ١ → المدى الحقيقي ٢
    assert ta.atr(highs, lows, closes, 14)[-1] == pytest.approx(2.0)


def test_macd_positive_in_uptrend_negative_in_downtrend():
    up = [float(i) for i in range(1, 80)]
    down = list(reversed(up))
    assert ta.macd(up)["macd"][-1] > 0
    assert ta.macd(down)["macd"][-1] < 0


def test_bollinger_bands_bracket_the_mean():
    values = [50.0 + (i % 5) for i in range(40)]
    bands = ta.bollinger(values, 20, 2.0)
    assert bands["lower"][-1] < bands["middle"][-1] < bands["upper"][-1]
    assert bands["width"][-1] > 0


def test_adx_detects_a_strong_trend():
    closes = [float(i) for i in range(1, 80)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    pack = ta.adx(highs, lows, closes, 14)
    assert pack["adx"][-1] > 40                       # اتجاه قوي جدًا
    assert pack["plus_di"][-1] > pack["minus_di"][-1]  # وصاعد


def test_obv_accumulates_with_direction():
    closes = [10.0, 11.0, 10.5, 12.0]
    volumes = [100.0, 200.0, 50.0, 300.0]
    assert ta.obv(closes, volumes)[-1] == pytest.approx(200.0 - 50.0 + 300.0)


def test_swing_points_finds_local_extremes():
    series = [1.0, 2, 3, 9, 3, 2, 1, 2, 3, 8, 3, 2, 1]
    swings = ta.swing_points(series, series, 3)
    assert [i for i, _ in swings["tops"]] == [3, 9]


def test_support_resistance_splits_around_price():
    highs, lows, closes = [], [], []
    for i in range(60):
        wave = 10 * math.sin(i / 3.0)
        closes.append(100 + wave)
        highs.append(100 + wave + 1)
        lows.append(100 + wave - 1)
    levels = ta.support_resistance(highs, lows, closes, 3)
    price = closes[-1]
    assert all(level["price"] < price for level in levels["supports"])
    assert all(level["price"] > price for level in levels["resistances"])


def test_trendline_slope_sign_follows_the_points():
    descending = [(0, 100.0), (10, 95.0), (20, 90.0), (30, 85.0)]
    line = ta.trendline(descending, 40)
    assert line["slope"] < 0
    assert line["value_now"] == pytest.approx(80.0, abs=0.01)


def test_trendline_needs_enough_points():
    assert ta.trendline([(0, 10.0), (5, 9.0)], 10) is None


def test_range_position_maps_to_percent():
    values = [float(i) for i in range(1, 101)]
    assert ta.range_position(values)["position_pct"] == pytest.approx(100.0)
    assert ta.range_position(list(reversed(values)))["position_pct"] == pytest.approx(0.0)


def test_indicators_return_none_when_series_too_short():
    short = [1.0, 2.0, 3.0]
    assert ta.ema(short, 20) == [None, None, None]
    assert ta.last_valid(ta.rsi(short, 14)) is None
    assert ta.slope(short, 10) == 1.0        # ٣ نقاط تكفي للانحدار
    assert ta.slope([1.0, 2.0], 10) is None  # نقطتان لا تكفيان
