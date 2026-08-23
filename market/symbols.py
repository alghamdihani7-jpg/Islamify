"""
كون الأسهم — Saudi Exchange (Tadawul) main-market universe.

كل سهم يمثَّل برمز تداول المكوّن من أربعة أرقام، وهو نفس الرمز الذي
يُستخدم مع مزوّد البيانات بإضافة اللاحقة ``.SR`` (مثال: ``2222.SR``).

ملاحظة مهمّة
-----------
هذه القائمة قائمة انطلاق مُدرجة داخل التطبيق حتى يعمل بلا اتصال، وقد
تتغيّر أسماء الشركات أو تُدرج/تُشطب شركات مع الوقت. الاسم المعروض في
الواجهة يُؤخذ دائمًا من مزوّد البيانات عند توفّره، ولا يُستخدم الاسم
المدرج هنا إلا كبديل احتياطي. لتحديث القائمة من المزوّد:

    python tools/refresh_symbols.py

"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

# مؤشر السوق الرئيسي — مرشّحات الرمز لدى المزوّد (تُجرّب بالترتيب)
INDEX_SYMBOL_CANDIDATES = ["^TASI.SR", "^TASI", "TASI.SR"]
INDEX_NAME_AR = "المؤشر العام (تاسي)"
INDEX_NAME_EN = "Tadawul All Share Index (TASI)"

SECTORS = [
    "البنوك",
    "الطاقة",
    "المواد الأساسية",
    "الأسمنت",
    "المرافق العامة",
    "الاتصالات",
    "الرعاية الصحية",
    "التجزئة والأغذية",
    "الزراعة والأغذية",
    "العقار",
    "النقل والخدمات",
    "التأمين",
    "الاستثمار والتمويل",
    "التعليم",
]

# code, name_ar, name_en, sector
_RAW_UNIVERSE = [
    # ── البنوك ──
    ("1010", "بنك الرياض", "Riyad Bank", "البنوك"),
    ("1020", "بنك الجزيرة", "Bank Aljazira", "البنوك"),
    ("1030", "البنك السعودي للاستثمار", "Saudi Investment Bank", "البنوك"),
    ("1050", "البنك السعودي الفرنسي", "Banque Saudi Fransi", "البنوك"),
    ("1060", "البنك السعودي الأول", "Saudi Awwal Bank", "البنوك"),
    ("1080", "البنك العربي الوطني", "Arab National Bank", "البنوك"),
    ("1120", "مصرف الراجحي", "Al Rajhi Bank", "البنوك"),
    ("1140", "بنك البلاد", "Bank Albilad", "البنوك"),
    ("1150", "مصرف الإنماء", "Alinma Bank", "البنوك"),
    ("1180", "البنك الأهلي السعودي", "Saudi National Bank", "البنوك"),
    # ── الاستثمار والتمويل ──
    ("1111", "مجموعة تداول السعودية", "Saudi Tadawul Group", "الاستثمار والتمويل"),
    ("1182", "أملاك العالمية", "Amlak International", "الاستثمار والتمويل"),
    ("4130", "الباحة", "Al Baha Investment", "الاستثمار والتمويل"),
    ("4280", "المملكة القابضة", "Kingdom Holding", "الاستثمار والتمويل"),
    ("2120", "سيسكو القابضة", "SISCO Holding", "الاستثمار والتمويل"),
    # ── الطاقة ──
    ("2222", "أرامكو السعودية", "Saudi Aramco", "الطاقة"),
    ("2030", "المصافي العربية السعودية", "SARCO", "الطاقة"),
    ("2380", "رابغ للتكرير والبتروكيماويات", "Petro Rabigh", "الطاقة"),
    ("2381", "الحفر العربية", "Arabian Drilling", "الطاقة"),
    ("2382", "أديس القابضة", "ADES Holding", "الطاقة"),
    ("4030", "البحري", "Bahri", "الطاقة"),
    ("4200", "الدريس", "Aldrees Petroleum", "الطاقة"),
    # ── المواد الأساسية ──
    ("1201", "تكوين", "Takween Advanced Industries", "المواد الأساسية"),
    ("1202", "مبكو", "MEPCO", "المواد الأساسية"),
    ("1210", "بي سي آي", "Basic Chemical Industries", "المواد الأساسية"),
    ("1211", "معادن", "Ma'aden", "المواد الأساسية"),
    ("1301", "أسلاك", "Aslak", "المواد الأساسية"),
    ("1303", "صناعات كهربائية", "Electrical Industries", "المواد الأساسية"),
    ("1304", "اليمامة للحديد", "Al Yamamah Steel", "المواد الأساسية"),
    ("1320", "أنابيب السعودية", "Saudi Steel Pipe", "المواد الأساسية"),
    ("1321", "أنابيب الشرق", "East Pipes", "المواد الأساسية"),
    ("2001", "كيمانول", "Chemanol", "المواد الأساسية"),
    ("2002", "بتروكيم", "Petrochem", "المواد الأساسية"),
    ("2010", "سابك", "SABIC", "المواد الأساسية"),
    ("2020", "سابك للمغذيات الزراعية", "SABIC Agri-Nutrients", "المواد الأساسية"),
    ("2040", "الخزف السعودي", "Saudi Ceramic", "المواد الأساسية"),
    ("2060", "التصنيع", "Tasnee", "المواد الأساسية"),
    ("2090", "جبسكو", "Gypsum Co", "المواد الأساسية"),
    ("2170", "اللجين", "Alujain", "المواد الأساسية"),
    ("2180", "فيبكو", "FIPCO", "المواد الأساسية"),
    ("2200", "أنابيب", "Arabian Pipes", "المواد الأساسية"),
    ("2210", "نماء للكيماويات", "Nama Chemicals", "المواد الأساسية"),
    ("2220", "معدنية", "Maadaniyah", "المواد الأساسية"),
    ("2240", "الزامل للصناعة", "Zamil Industrial", "المواد الأساسية"),
    ("2250", "المجموعة السعودية", "SIIG", "المواد الأساسية"),
    ("2290", "ينساب", "Yansab", "المواد الأساسية"),
    ("2300", "صناعة الورق", "Saudi Paper Manufacturing", "المواد الأساسية"),
    ("2310", "سبكيم العالمية", "Sipchem", "المواد الأساسية"),
    ("2330", "المتقدمة", "Advanced Petrochemical", "المواد الأساسية"),
    ("2350", "كيان السعودية", "Saudi Kayan", "المواد الأساسية"),
    ("2360", "الفخارية", "Saudi Vitrified Clay Pipes", "المواد الأساسية"),
    # ── الأسمنت ──
    ("3001", "أسمنت حائل", "Hail Cement", "الأسمنت"),
    ("3002", "أسمنت نجران", "Najran Cement", "الأسمنت"),
    ("3003", "أسمنت المدينة", "City Cement", "الأسمنت"),
    ("3004", "أسمنت الشمالية", "Northern Region Cement", "الأسمنت"),
    ("3005", "أسمنت أم القرى", "Umm Al Qura Cement", "الأسمنت"),
    ("3010", "أسمنت العربية", "Arabian Cement", "الأسمنت"),
    ("3020", "أسمنت اليمامة", "Yamama Cement", "الأسمنت"),
    ("3030", "أسمنت السعودية", "Saudi Cement", "الأسمنت"),
    ("3040", "أسمنت القصيم", "Qassim Cement", "الأسمنت"),
    ("3050", "أسمنت الجنوبية", "Southern Province Cement", "الأسمنت"),
    ("3060", "أسمنت ينبع", "Yanbu Cement", "الأسمنت"),
    ("3080", "أسمنت الشرقية", "Eastern Province Cement", "الأسمنت"),
    ("3090", "أسمنت تبوك", "Tabuk Cement", "الأسمنت"),
    ("3091", "أسمنت الجوف", "Al Jouf Cement", "الأسمنت"),
    ("3092", "أسمنت الرياض", "Riyadh Cement", "الأسمنت"),
    # ── المرافق العامة ──
    ("5110", "كهرباء السعودية", "Saudi Electricity", "المرافق العامة"),
    ("2081", "الخريف لتقنية المياه والطاقة", "Alkhorayef Water & Power", "المرافق العامة"),
    ("2082", "أكوا باور", "ACWA Power", "المرافق العامة"),
    ("2083", "مرافق", "Marafiq", "المرافق العامة"),
    # ── الاتصالات وتقنية المعلومات ──
    ("7010", "اتصالات السعودية stc", "Saudi Telecom Company", "الاتصالات"),
    ("7020", "اتحاد اتصالات (موبايلي)", "Etihad Etisalat (Mobily)", "الاتصالات"),
    ("7030", "زين السعودية", "Zain KSA", "الاتصالات"),
    ("7040", "عذيب للاتصالات", "Etihad Atheeb (GO)", "الاتصالات"),
    ("7200", "المعمر لأنظمة المعلومات", "Al Moammar Information Systems", "الاتصالات"),
    ("7202", "سلوشنز", "Solutions by stc", "الاتصالات"),
    ("7203", "علم", "Elm", "الاتصالات"),
    # ── الرعاية الصحية ──
    ("4002", "المواساة للخدمات الطبية", "Mouwasat Medical Services", "الرعاية الصحية"),
    ("4004", "دله الصحية", "Dallah Healthcare", "الرعاية الصحية"),
    ("4005", "رعاية", "National Medical Care (Care)", "الرعاية الصحية"),
    ("4007", "الحمادي القابضة", "Al Hammadi Holding", "الرعاية الصحية"),
    ("4009", "السعودي الألماني الصحية", "Middle East Healthcare", "الرعاية الصحية"),
    ("4013", "د. سليمان الحبيب", "Dr. Sulaiman Al Habib", "الرعاية الصحية"),
    ("4015", "جمجوم فارما", "Jamjoom Pharma", "الرعاية الصحية"),
    ("4017", "فقيه للرعاية الطبية", "Fakeeh Care Group", "الرعاية الصحية"),
    # ── التجزئة والأغذية ──
    ("4001", "أسواق عبدالله العثيم", "Abdullah Al Othaim Markets", "التجزئة والأغذية"),
    ("4003", "إكسترا", "United Electronics (eXtra)", "التجزئة والأغذية"),
    ("4008", "ساكو", "SACO", "التجزئة والأغذية"),
    ("4050", "ساسكو", "SASCO", "التجزئة والأغذية"),
    ("4051", "باعظيم التجارية", "Baazeem Trading", "التجزئة والأغذية"),
    ("4061", "أنعام القابضة", "Anaam Holding", "التجزئة والأغذية"),
    ("4161", "بن داود القابضة", "BinDawood Holding", "التجزئة والأغذية"),
    ("4162", "المطاحن الأولى", "First Milling", "التجزئة والأغذية"),
    ("4163", "المطاحن الحديثة", "Modern Mills", "التجزئة والأغذية"),
    ("4164", "المطاحن العربية", "Arabian Mills", "التجزئة والأغذية"),
    ("4190", "جرير", "Jarir Marketing", "التجزئة والأغذية"),
    ("4240", "سينومي ريتيل", "Cenomi Retail", "التجزئة والأغذية"),
    ("6001", "حلواني إخوان", "Halwani Bros", "التجزئة والأغذية"),
    ("6002", "هرفي للأغذية", "Herfy Food Services", "التجزئة والأغذية"),
    ("2270", "سدافكو", "SADAFCO", "التجزئة والأغذية"),
    ("2280", "المراعي", "Almarai", "التجزئة والأغذية"),
    ("2050", "صافولا", "Savola Group", "التجزئة والأغذية"),
    # ── الزراعة والأغذية ──
    ("6010", "نادك", "NADEC", "الزراعة والأغذية"),
    ("6040", "تبوك الزراعية", "Tabuk Agricultural", "الزراعة والأغذية"),
    ("6050", "الأسماك", "Saudi Fisheries", "الزراعة والأغذية"),
    ("6060", "الشرقية للتنمية", "Ash-Sharqiyah Development", "الزراعة والأغذية"),
    ("6070", "الجوف الزراعية", "Al Jouf Agricultural", "الزراعة والأغذية"),
    ("6090", "جازادكو", "Jazadco", "الزراعة والأغذية"),
    # ── العقار ──
    ("4020", "العقارية", "Saudi Real Estate (Al Akaria)", "العقار"),
    ("4090", "طيبة للاستثمار", "Taiba Investments", "العقار"),
    ("4100", "مكة للإنشاء والتعمير", "Makkah Construction & Development", "العقار"),
    ("4150", "التعمير", "Arriyadh Development", "العقار"),
    ("4220", "إعمار المدينة الاقتصادية", "Emaar The Economic City", "العقار"),
    ("4230", "البحر الأحمر العالمية", "Red Sea International", "العقار"),
    ("4250", "جبل عمر", "Jabal Omar Development", "العقار"),
    ("4300", "دار الأركان", "Dar Al Arkan", "العقار"),
    ("4310", "مدينة المعرفة", "Knowledge Economic City", "العقار"),
    ("4320", "الأندلس العقارية", "Alandalus Property", "العقار"),
    ("4321", "سينومي سنترز", "Cenomi Centers", "العقار"),
    ("4322", "رتال", "Retal Urban Development", "العقار"),
    # ── النقل والخدمات ──
    ("4040", "سابتكو", "SAPTCO", "النقل والخدمات"),
    ("4110", "باتك", "Batic Investments", "النقل والخدمات"),
    ("4180", "فتيحي القابضة", "Fitaihi Holding", "النقل والخدمات"),
    ("4260", "بدجت السعودية", "United International Transportation", "النقل والخدمات"),
    ("4261", "ذيب لتأجير السيارات", "Theeb Rent a Car", "النقل والخدمات"),
    ("4262", "لومي", "Lumi Rental", "النقل والخدمات"),
    ("4270", "طباعة وتغليف", "Saudi Printing & Packaging", "النقل والخدمات"),
    ("4031", "الخدمات الأرضية", "Saudi Ground Services", "النقل والخدمات"),
    # ── التعليم ──
    ("4290", "الخليج للتدريب", "Al Khaleej Training & Education", "التعليم"),
    ("4291", "الوطنية للتعليم", "National Co. for Learning & Education", "التعليم"),
    ("4292", "عطاء التعليمية", "Ataa Educational", "التعليم"),
    # ── التأمين ──
    ("8010", "التعاونية", "Tawuniya", "التأمين"),
    ("8012", "جزيرة تكافل", "Jazira Takaful", "التأمين"),
    ("8020", "ملاذ للتأمين", "Malath Insurance", "التأمين"),
    ("8030", "ميدغلف", "MEDGULF", "التأمين"),
    ("8040", "أليانز إس إف", "Allianz Saudi Fransi", "التأمين"),
    ("8050", "سلامة", "Salama Cooperative Insurance", "التأمين"),
    ("8060", "ولاء للتأمين", "Walaa Cooperative Insurance", "التأمين"),
    ("8070", "الدرع العربي", "Arabian Shield", "التأمين"),
    ("8100", "سايكو", "SAICO", "التأمين"),
    ("8120", "الصقر للتأمين", "Al Sagr Insurance", "التأمين"),
    ("8150", "أسيج", "ACIG", "التأمين"),
    ("8160", "التأمين العربية", "AICC", "التأمين"),
    ("8170", "الاتحاد التجاري", "Alettihad Cooperative Insurance", "التأمين"),
    ("8200", "إعادة السعودية", "Saudi Re", "التأمين"),
    ("8210", "بوبا العربية", "Bupa Arabia", "التأمين"),
    ("8230", "تكافل الراجحي", "Al Rajhi Takaful", "التأمين"),
    ("8250", "جي أي جي", "GIG Saudi", "التأمين"),
    ("8260", "الخليجية العامة", "Gulf General Cooperative Insurance", "التأمين"),
    ("8270", "بروج للتأمين", "Buruj Cooperative Insurance", "التأمين"),
    ("8280", "العالمية", "Alalamiya for Cooperative Insurance", "التأمين"),
]

_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "symbols_override.json")


def _build() -> List[Dict[str, str]]:
    """يبني القائمة النهائية مع تطبيق ملف التحديث إن وُجد."""
    rows = [
        {"code": c, "name_ar": ar, "name_en": en, "sector": sec}
        for c, ar, en, sec in _RAW_UNIVERSE
    ]
    by_code = {r["code"]: r for r in rows}

    if os.path.exists(_OVERRIDES_PATH):
        try:
            with open(_OVERRIDES_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for item in data if isinstance(data, list) else []:
                code = str(item.get("code", "")).strip()
                if not is_valid_code(code):
                    continue
                row = by_code.get(code, {"code": code})
                row["name_ar"] = item.get("name_ar") or row.get("name_ar") or code
                row["name_en"] = item.get("name_en") or row.get("name_en") or code
                row["sector"] = item.get("sector") or row.get("sector") or "غير مصنّف"
                by_code[code] = row
        except (OSError, ValueError):
            # ملف تحديث تالف — نتجاهله ونكمل بالقائمة المدرجة.
            pass

    return sorted(by_code.values(), key=lambda r: r["code"])


UNIVERSE: List[Dict[str, str]] = _build()
BY_CODE: Dict[str, Dict[str, str]] = {r["code"]: r for r in UNIVERSE}

_CODE_RE = re.compile(r"^\d{4}$")


def is_valid_code(code: str) -> bool:
    """رمز تداول صالح = أربعة أرقام."""
    return bool(_CODE_RE.match(str(code or "").strip()))


def normalize_code(raw: str) -> Optional[str]:
    """يستخرج رمز تداول من نص المستخدم (يقبل ``2222`` أو ``2222.SR``)."""
    text = str(raw or "").strip().upper()
    text = text.split(".")[0]
    digits = re.sub(r"\D", "", text)
    return digits if is_valid_code(digits) else None


def get(code: str) -> Optional[Dict[str, str]]:
    return BY_CODE.get(str(code or "").strip())


def display_name(code: str, lang: str = "ar") -> str:
    row = get(code)
    if not row:
        return str(code)
    return row["name_ar"] if lang == "ar" else row["name_en"]


def codes() -> List[str]:
    return [r["code"] for r in UNIVERSE]


def by_sector(sector: str) -> List[Dict[str, str]]:
    return [r for r in UNIVERSE if r["sector"] == sector]


def search(query: str, limit: int = 15) -> List[Dict[str, str]]:
    """بحث بالرمز أو بالاسم العربي/الإنجليزي."""
    q = str(query or "").strip().lower()
    if not q:
        return []

    exact_code = normalize_code(q)
    hits: List[Dict[str, str]] = []
    seen = set()

    if exact_code and exact_code in BY_CODE:
        hits.append(BY_CODE[exact_code])
        seen.add(exact_code)

    for row in UNIVERSE:
        if row["code"] in seen:
            continue
        haystack = f"{row['code']} {row['name_ar']} {row['name_en']} {row['sector']}".lower()
        if q in haystack:
            hits.append(row)
            seen.add(row["code"])
        if len(hits) >= limit:
            break

    return hits[:limit]
