"""مسارات الاستيراد + بيانات اصطناعية مشتركة للاختبارات."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MARKET_OFFLINE", "1")  # لا اتصال شبكة أثناء الاختبار

import pytest  # noqa: E402


def make_payload(candles, code="9001", name="سهم اختبار", is_demo=False):
    return {
        "code": code,
        "name_ar": name,
        "name_en": name,
        "sector": "اختبار",
        "currency": "SAR",
        "is_demo": is_demo,
        "timeframe": "6mo",
        "interval": "1d",
        "fetched_at": 0,
        "candles": candles,
        "previous_close": candles[-2]["c"] if len(candles) > 1 else candles[-1]["c"],
    }


def candle(t, o, h, l, c, v):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": float(v)}


@pytest.fixture
def rising_index():
    """مؤشر عام صاعد بثبات — يفتح البوابة ② (حالة سوق إيجابية)."""
    candles = []
    price = 8000.0
    for i in range(260):
        price *= 1.0016
        candles.append(candle(i * 86400, price * 0.999, price * 1.004,
                              price * 0.996, price, 1_000_000))
    return make_payload(candles, code="TASI", name="تاسي")


@pytest.fixture
def falling_index():
    """مؤشر عام هابط — يغلق البوابة ② ويمنع الشراء."""
    candles = []
    price = 12000.0
    for i in range(260):
        price *= 0.9984
        candles.append(candle(i * 86400, price * 1.001, price * 1.004,
                              price * 0.996, price, 1_000_000))
    return make_payload(candles, code="TASI", name="تاسي")


@pytest.fixture
def textbook_breakout():
    """
    سهم يمثّل النموذج (أ) بالضبط: هبوط متعرّج بقمم متناقصة، ثم قاع
    عرضي، ثم كسر لخط الهبوط بارتفاع مدعوم بحجم مضاعف.

    المعاملات مضبوطة لينتج وضعًا يجتاز البوابات الخمس كاملة، فهذا هو
    الاختبار الذي يثبت أن مسار «صفقة مقبولة» قابل للتحقّق فعلًا ولم
    تُغلقه القواعد على نفسها.
    """
    candles = []
    t = 0

    # ① هبوط متعرّج: قمة محورية كل ٨ شموع، وكل دورة أدنى من سابقتها بـ ٦ ريالات
    top = 100.0
    for _cycle in range(6):
        for phase in range(8):
            if phase <= 3:                       # صعود نحو القمة
                close = top - (3 - phase) * (4.0 / 3)
            else:                                # هبوط بعد القمة
                close = top - (phase - 3) * (4.0 / 4)
            candles.append(candle(t, close + 0.15, close + 0.45, close - 0.45,
                                  close, 220_000))
            t += 86400
        top -= 6.0

    # ② قاع عرضي قصير يمتصّ البيع
    base = candles[-1]["c"]
    for i in range(12):
        close = base + (0.5 if i % 2 else -0.5)
        candles.append(candle(t, close, close + 0.4, close - 0.4, close, 200_000))
        t += 86400

    # ③ ارتداد بقمم مرتفعة باطّراد وإغلاقات متذبذبة (تُبقي RSI دون التشبّع)،
    #    وآخر شمعة بحجم ٣× المتوسط = حجم يوم الكسر.
    high = candles[-1]["h"]
    for i in range(24):
        high += 0.7
        low = high - 1.1
        close = low + (0.95 if i % 3 else 0.25)
        volume = 240_000 if i < 23 else 700_000
        candles.append(candle(t, low + 0.4, high, low, close, volume))
        t += 86400

    return make_payload(candles, code="9002", name="سهم الكسر")


@pytest.fixture
def illiquid_stock():
    """سهم بسيولة ضعيفة — يجب أن تسقطه البوابة ① قبل أي تحليل."""
    candles = []
    price = 3.0
    for i in range(120):
        price *= 1.001
        candles.append(candle(i * 86400, price, price * 1.01,
                              price * 0.99, price, 900))
    return make_payload(candles, code="9003", name="سهم ضعيف السيولة")
