#!/usr/bin/env python3
"""
تحديث أسماء الشركات من مزوّد البيانات.

القائمة المدرجة في ``market/symbols.py`` قائمة انطلاق تعمل بلا اتصال،
وقد تتغيّر أسماء الشركات أو تُدرج/تُشطب شركات. هذه الأداة تسأل المزوّد
عن كل رمز وتكتب ما تجده في ``market/symbols_override.json`` الذي
يُطبَّق فوق القائمة المدرجة عند الإقلاع.

    python tools/refresh_symbols.py                # تحديث الكون كامل
    python tools/refresh_symbols.py 1211 2222      # رموز محددة
    python tools/refresh_symbols.py --check 4444   # فحص رمز غير مدرج

تحتاج اتصالًا بالإنترنت؛ في البيئات المغلقة تخرج بلا تعديل بدل كتابة
بيانات وهمية.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market import providers  # noqa: E402
from market import symbols as sym  # noqa: E402

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "market", "symbols_override.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="تحديث أسماء رموز تداول من المزوّد")
    parser.add_argument("codes", nargs="*", help="رموز محددة (الافتراضي: الكون كامل)")
    parser.add_argument("--check", action="store_true",
                        help="اطبع النتيجة فقط بلا كتابة الملف")
    args = parser.parse_args()

    if os.environ.get("MARKET_OFFLINE"):
        print("MARKET_OFFLINE مفعّل — لن تُجلب بيانات حقيقية. أزل المتغيّر وأعد المحاولة.")
        return 2

    codes = [c for c in (args.codes or sym.codes()) if sym.is_valid_code(c)]
    if not codes:
        print("لا توجد رموز صالحة.")
        return 2

    print(f"جلب {len(codes)} رمزًا من المزوّد…")
    payloads = providers.fetch_many(codes, "1mo")

    rows, demo, missing = [], 0, []
    for code in codes:
        payload = payloads.get(code)
        if not payload:
            missing.append(code)
            continue
        if payload["is_demo"]:
            demo += 1
            continue
        existing = sym.get(code) or {}
        rows.append({
            "code": code,
            # الاسم العربي لا يأتي من المزوّد، فنُبقي المدرج إن وُجد.
            "name_ar": existing.get("name_ar") or payload["name_en"] or code,
            "name_en": payload["name_en"] or existing.get("name_en") or code,
            "sector": existing.get("sector") or "غير مصنّف",
        })

    if demo:
        print(f"تعذّر الوصول للمزوّد ({demo} رمزًا رجع ببيانات تجريبية) — لن يُكتب الملف.")
        return 1

    print(f"نجح: {len(rows)} · مفقود لدى المزوّد: {len(missing)}")
    if missing:
        print("  رموز لم يعرفها المزوّد (قد تكون مشطوبة):", ", ".join(missing))

    if args.check:
        print(json.dumps(rows[:10], ensure_ascii=False, indent=2))
        return 0

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    print(f"كُتب {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
