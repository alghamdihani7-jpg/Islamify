"""
تحليل السوق السعودي (تاسي) — Saudi Stock Market (TASI) analysis package.

Modules
-------
symbols     : كون الأسهم المتداولة في السوق الرئيسية (رموز تداول).
indicators  : المؤشرات الفنية (بايثون خالص، بدون numpy/pandas).
providers   : جلب بيانات السوق الحقيقية + طبقة تخزين مؤقت + وضع تجريبي بلا إنترنت.
analysis    : محرك الإشارات (شراء/بيع/حياد) والمستويات والأهداف.
scanner     : ماسح السوق لترتيب الأسهم المرشحة للصعود/الهبوط.
routes      : Blueprint الخاص بواجهة وواجهات برمجة التطبيقات.
"""

__all__ = ["symbols", "indicators", "providers", "analysis", "scanner", "routes"]
