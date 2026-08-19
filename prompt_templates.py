"""
قوالب البرومبتات وقاموس المصطلحات الموحد لترجمة رواية Reverend Insanity (القس المجنون)
إلى العربية الأدبية الفصحى البليغة.
"""

# القاموس المرجعي للمصطلحات والشخصيات والمفاهيم
GLOSSARY = {
    # الشخصيات الرئيسية
    "Fang Yuan": "فانغ يوان",
    "Fang Zheng": "فانغ تشنغ",
    "Gu Yue Bo": "غو يوي بو",
    "Bai Ning Bing": "باي نينغ بينغ",
    "Tie Ruo Nan": "تي رو نان",
    "Hei Lou Lan": "هي لو لان",
    "Feng Jiu Ge": "فنغ جيو غي",
    "Red Lotus Demon Venerable": "المبجل الشيطاني اللوتس الأحمر",
    "Spectral Soul Demon Venerable": "المبجل الشيطاني الروح الطيفية",
    "Paradise Earth Immortal Venerable": "المبجل الخالد أرض الفردوس",
    "Limitless Demon Venerable": "المبجل الشيطاني اللامحدود",
    "Giant Sun Immortal Venerable": "المبجل الخالد الشمس العملاقة",
    "Primordial Origin Immortal Venerable": "المبجل الخالد الأصل البدائي",
    "Star Constellation Immortal Venerable": "المبجل الخالد كوكبة النجوم",
    "Genesis Lotus Immortal Venerable": "المبجل الخالد لوتس التكوين",
    "Thieving Heaven Demon Venerable": "المبجل الشيطاني سارق السماء",
    "Reckless Savage Demon Venerable": "المبجل الشيطاني الهمجي الطائش",

    # الأماكن والعشائر
    "Gu Yue Village": "قرية غو يوي",
    "Gu Yue Clan": "عشيرة غو يوي",
    "Qing Mao Mountain": "جبل تشينغ ماو",
    "Southern Border": "الحدود الجنوبية",
    "Central Continent": "القارة الوسطى",
    "Northern Plains": "السهول الشمالية",
    "Western Desert": "الصحراء الغربية",
    "Eastern Sea": "البحر الشرقي",
    "Heavenly Court": "البلاط السماوي",
    "River of Time": "نهر الزمن",
    "Door of Life and Death": "باب الحياة والموت",

    # مفاهيم الزراعة والغو
    "Gu": "غو",
    "Gu Master": "سيد غو",
    "Gu Masters": "أسياد الغو",
    "Gu Immortal": "خالد غو",
    "Gu Immortals": "خالدو الغو",
    "Immortal Venerable": "مبجل خالد",
    "Demon Venerable": "مبجل شيطاني",
    "Spring Autumn Cicada": "زيز الربيع والخريف",
    "Moonlight Gu": "غو ضوء القمر",
    "Liquor Worm": "دودة الخمر",
    "Hope Gu": "غو الأمل",
    "Fate Gu": "غو القدر",
    "Aperture": "الفتحة الروحية",
    "Primeval Essence": "الجوهر البدائي",
    "Immortal Essence": "الجوهر الخالد",
    "Primeval Stones": "الأحجار البدائية",
    "Primeval Sea": "بحر الجوهر البدائي",
    "Dao Marks": "علامات الداو",
    "Great Dao": "الداو العظيم",
    "Cultivation": "الزراعة (أو تنمية القوة)",
    "Cultivator": "مزارع",
    "Rank 1": "المرتبة الأولى",
    "Rank 2": "المرتبة الثانية",
    "Rank 3": "المرتبة الثالثة",
    "Rank 4": "المرتبة الرابعة",
    "Rank 5": "المرتبة الخامسة",
    "Rank 6": "المرتبة السادسة",
    "Rank 7": "المرتبة السابعة",
    "Rank 8": "المرتبة الثامنة",
    "Rank 9": "المرتبة التاسعة",
    "Initial stage": "المرحلة الأولية",
    "Middle stage": "المرحلة المتوسطة",
    "Upper stage": "المرحلة المتقدمة",
    "Peak stage": "مرحلة الذروة",
    "Tribulation": "المحنة",
    "Heavenly Tribulation": "المحنة السماوية",
    "Grand Tribulation": "المحنة الكبرى",
    "Myriad Tribulation": "محنة الآلاف",
    "Refining Gu": "صقل الغو",
    "Refinement Path": "مسار الصقل",
    "Time Path": "مسار الزمن",
    "Wisdom Path": "مسار الحكمة",
    "Strength Path": "مسار القوة",
    "Blood Path": "مسار الدم",
    "Soul Path": "مسار الروح",
}

# البرومبت الأساسي لمترجم الرواية
LITERARY_SYSTEM_PROMPT = """أنت مترجم أدبي عبقري وخبير بروايات الفانتازيا والزراعة الصينية (Xianxia / Xuanhuan)، وخاصة الرواية الملحمية الشهيرة "Reverend Insanity" (القس المجنون / Gu Zhen Ren).

مهمتك:
ترجمة النص الإنجليزي المقدم إلى اللغة العربية الفصحى الأدبية الرفيعة والبليغة (Literary High Arabic)، مع الالتزام الصارم بالقواعد التالية:

1. الأسلوب الأدبي والفصاحة:
- الصياغة بلغة عربية أدبية ثرية، قوية السبك، بليغة الألفاظ، تجمع بين الرصانة اللغوية والتشويق السردي.
- الحفاظ على الطابع الفلسفي، المظلم، والملحمي لشخصية البطل (فانغ يوان) وتأملاته في الطبيعة البشرية وقسوة طريق الخلود.
- صياغة الحوارات والقصائد والأبيات الشعرية بديباجة عربية فخمة وموزونة تليق بأجواء الأدب الملحمي.

2. الأمانة والدقة الكاملة:
- ترجمة كل سطر وفقرة بالكامل دون أي اختصار أو حذف أو تلخيص للأحداث أو الأوصاف.
- الحفاظ على التسلسل المنطقي لفقرات السرد.

3. الالتزام بمصطلحات الرواية الموحدة:
- Fang Yuan -> فانغ يوان
- Fang Zheng -> فانغ تشنغ
- Gu / Gu Master / Gu Immortal / Venerable -> غو / سيد غو / خالد غو / مبجل
- Spring Autumn Cicada -> زيز الربيع والخريف
- Moonlight Gu -> غو ضوء القمر
- Liquor Worm -> دودة الخمر
- Hope Gu -> غو الأمل
- Aperture -> الفتحة الروحية
- Primeval Essence -> الجوهر البدائي
- Primeval Stones -> الأحجار البدائية
- Qing Mao Mountain -> جبل تشينغ ماو
- Gu Yue Clan / Village -> عشيرة / قرية غو يوي
- Heavenly Court -> البلاط السماوي
- Cultivation -> الزراعة
- Refine / Refining -> صقل

4. قواعد التنسيق والمسافات:
- اترك سطرًا فارغًا تامًا (Double Line Break / \n\n) بين كل فقرة وأخرى وبين كل حوار وآخر لضمان راحة القراءة وتنسيق الرواية بشكل ممتاز.
- ضع كل حوار أو عبارة منطوقة في سطر مستقل داخل أقواس تنصيص عربية «...».
- لا تكرر عنوان الفصل داخل النص المترجم، ولا تضع ترويسات أجزاء مثل (الجزء 1) أو (ترجمة الفصل).
- أخرج النص المترجم فقط، بدون أي مقدمات، ملاحظات شخصية، شروحات إضافية، أو تعليقات من المترجم.
"""


def build_translation_prompt(chapter_title: str, text: str, is_chunk: bool = False, chunk_num: int = 1, total_chunks: int = 1) -> list:
    """
    بناء مصفوفة الرسائل (Messages) الجاهزة للإرسال إلى الـ API
    """
    if is_chunk and total_chunks > 1:
        user_msg = (
            f"ترجم الفقرات التالية من الرواية إلى العربية الأدبية الفصحى البليغة، مع ترك سطر فارغ بين كل فقرة وأخرى:\n\n"
            f"{text}"
        )
    else:
        user_msg = (
            f"ترجم الفصل التالي كاملاً إلى العربية الأدبية الفصحى البليغة، مع ترك سطر فارغ بين كل فقرة وأخرى:\n\n"
            f"{text}"
        )

    return [
        {"role": "system", "content": LITERARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ]

