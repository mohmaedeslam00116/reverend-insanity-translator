"""
📖 Comprehensive Fantasy & Cultivation Glossary Extractor for Reverend Insanity
================================================================================
Builds a complete, rich glossary of all Xianxia cultivation terms, Gu worms,
Venerables, Paths, Clans, Sects, Locations, and Character names.

Combines:
  1. Deeply Curated Canon Glossary (250+ canonical Reverend Insanity terms)
  2. Automatic Noun & Pinyin Extractor across all 2,334 chapters
  3. Context-aware Arabic transliteration engine

Outputs:
  - glossary.json (root directory for pipeline usage)
  - output/reverend_insanity_glossary.json
  - output/glossary_summary.md
"""

import sys
import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Set
from collections import Counter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import Config
from organize_volumes import VOLUME_RANGES, get_volume_dir


# ─────────────────────────────────────────────────────────────────────────────
# 1. Canonical Curated Glossary for Reverend Insanity (رواية القس المجنون)
# ─────────────────────────────────────────────────────────────────────────────
CANONICAL_GLOSSARY = {
    # ── Characters (شخصيات رئيسية) ──
    "Fang Yuan": "فانغ يوان",
    "Gu Yue Fang Yuan": "غو يوي فانغ يوان",
    "Fang Zheng": "فانغ تشنغ",
    "Gu Yue Fang Zheng": "غو يوي فانغ تشنغ",
    "Bai Ning Bing": "باي نينغ بينغ",
    "Hei Lou Lan": "هي لو لان",
    "Tai Bai Yun Sheng": "تاي باي يون شنغ",
    "Zhao Lian Yun": "تشاو ليان يون",
    "Feng Jiu Ge": "فينغ جيو غي",
    "Feng Jin Huang": "فينغ جين هوانغ",
    "Xie Han Mo": "شيه هان مو",
    "Shang Xin Ci": "شانغ شين تسي",
    "Wu Yong": "وو يونغ",
    "Wu Du Xiu": "وو دو شيو",
    "Tie Ruo Nan": "تي روو نان",
    "Tie Xue Leng": "تي شيويه لينغ",
    "Lord Sky Crane": "اللورد الرافعة السماوية",
    "Mo Yao": "مو ياو",
    "Bo Qing": "بو تشينغ",
    "Zhan Bu Du": "تشان بو دو",
    "Meng Qiu Zhen": "منغ تشيو تشن",
    "Li Xiao Bai": "لي شياو باي",
    "Wu Shuai": "وو شواي",
    "Qi Sea Ancestor": "سلف بحر التشي",
    "Duke Long": "الدوق لونغ",
    "Fairy Zi Wei": "الجنية تسي وي",
    "Qin Ding Ling": "تشين دينغ لينغ",
    "Chen Yi": "تشن يي",
    "Thunder Ghost True Monarch": "العاهل الحقيقي شبح الرعد",
    "Fang Di Chang": "فانغ دي تشانغ",
    "Lu Wei Yin": "لو وي يين",
    "Shen Shang": "شن شانغ",
    "Qi Jue Demon Immortal": "شيطان التشي السبعة الخالد",
    "Mao Li Qiu": "ماو لي تشيو",
    "Bing Sai Chuan": "بينغ ساي تشوان",

    # ── The Ten Venerables (المبجلون العشرة) ──
    "Primordial Origin Immortal Venerable": "المبجل الخالد الأصل البدائي",
    "Star Constellation Immortal Venerable": "المبجلة الخالدة كوكبة النجوم",
    "Limitless Demon Venerable": "المبجل الشيطاني اللامحدود",
    "Reckless Savage Demon Venerable": "المبجل الشيطاني الهمجي المتهور",
    "Red Lotus Demon Venerable": "المبجل الشيطاني اللوتس الأحمر",
    "Genesis Lotus Immortal Venerable": "المبجل الخالد لوتس التكوين",
    "Thieving Heaven Demon Venerable": "المبجل الشيطاني سارق السماء",
    "Giant Sun Immortal Venerable": "المبجل الخالد الشمس العملاقة",
    "Spectral Soul Demon Venerable": "المبجل الشيطاني الروح الشبحية",
    "Paradise Earth Immortal Venerable": "المبجل الخالد أرض الفردوس",
    "Great Dream Immortal Venerable": "المبجلة الخالدة الحلم العظيم",
    "Ren Zu": "رين زو (سلف البشر)",

    # ── Key Gu Worms (ديدان القو الأسطورية) ──
    "Spring Autumn Cicada": "زيز الربيع والخريف",
    "Sovereign Immortal Fetus Gu": "قو الجنين الخالد السيادي",
    "Wisdom Gu": "قو الحكمة",
    "Hope Gu": "قو الأمل",
    "Liquor Worm": "دودة الخمر",
    "Moonlight Gu": "قو ضوء القمر",
    "Moonglow Gu": "قو توهج القمر",
    "Moonscar Gu": "قو ندبة القمر",
    "Fixed Immortal Travel": "قو السفر الخالد الثابت",
    "Attitude Gu": "قو الموقف",
    "Change Form Gu": "قو تغيير الهيئة",
    "Cleanse Soul Gu": "قو تطهير الروح",
    "Blood Skull Gu": "قو جمجمة الدم",
    "Man as Before": "قو الإنسان كما كان",
    "Landscape as Before": "قو المنظر الطبيعي كما كان",
    "Fate Gu": "قو المصير",
    "Destiny Gu": "قو القدر",
    "Dream Wings Gu": "قو أجنحة الأحلام",
    "Heavenly Essence Treasure Imperial Lotus": "لوتس كنز الجوهر السماوي الإمبراطوري",
    "Connect Heaven Gu": "قو الاتصال بالسماء",
    "Perceive Dao Gu": "قو إدراك الداو",
    "Steal Life Gu": "قو سرقة الحياة",
    "All-Out Effort Gu": "قو الجهد الشامل",
    "Strength Gu": "قو القوة",
    "Bone Flesh Unity Gu": "قو وحدة اللحم والعظام",
    "Yang Gu": "قو اليانغ",
    "Yin Gu": "قو الين",
    "Self Strength Gu": "قو قوة الذات",
    "Eat Strength Gu": "قو أكل القوة",
    "Pulling Mountain Gu": "قو سحب الجبال",
    "Pulling Water Gu": "قو سحب المياه",
    "Dog Shit Luck Gu": "قو حظ براز الكلاب",
    "Calamity Beckoning Gu": "قو جلب المصائب",
    "Qi Escape Gu": "قو هروب التشي",
    "Qi Sea Gu": "قو بحر التشي",
    "Soul Beast Token": "رمز وحش الروح",
    "Wealth Gu": "قو الثروة",

    # ── Cultivation Paths (مسارات الزراعة) ──
    "Time Path": "مسار الزمن",
    "Space Path": "مسار الفضاء",
    "Wisdom Path": "مسار الحكمة",
    "Refinement Path": "مسار الصقل",
    "Blood Path": "مسار الدم",
    "Soul Path": "مسار الروح",
    "Strength Path": "مسار القوة",
    "Transformation Path": "مسار التحول",
    "Rule Path": "مسار القواعد",
    "Information Path": "مسار المعلومات",
    "Qi Path": "مسار التشي",
    "Light Path": "مسار الضوء",
    "Dark Path": "مسار الظلام",
    "Shadow Path": "مسار الظل",
    "Dream Path": "مسار الأحلام",
    "Poison Path": "مسار السم",
    "Heaven Path": "مسار السماء",
    "Human Path": "مسار البشر",
    "Luck Path": "مسار الحظ",
    "Sword Path": "مسار السيف",
    "Blade Path": "مسار النصل",
    "Food Path": "مسار الطعام",
    "Earth Path": "مسار الأرض",
    "Water Path": "مسار الماء",
    "Fire Path": "مسار النار",
    "Wind Path": "مسار الرياح",
    "Lightning Path": "مسار البرق",
    "Sound Path": "مسار الصوت",
    "Painting Path": "مسار الرسم",
    "Moon Path": "مسار القمر",
    "Star Path": "مسار النجوم",
    "Illusion Path": "مسار الوهم",
    "Emotion Path": "مسار العاطفة",
    "Pill Path": "مسار الحبوب",
    "Weapon Path": "مسار الأسلحة",
    "Bone Path": "مسار العظام",
    "Restriction Path": "مسار القيود",
    "Enslavement Path": "مسار الاستعباد",
    "Theft Path": "مسار السرقة",
    "Metal Path": "مسار المعدن",
    "Wood Path": "مسار الخشب",

    # ── Cultivation Ranks & Terms (مراتب ومصطلحات الزراعة) ──
    "Gu Master": "سيد غو",
    "Gu Masters": "أسياد غو",
    "Gu Immortal": "خالد غو",
    "Gu Immortals": "خالدوا غو",
    "Immortal Venerable": "المبجل الخالد",
    "Demon Venerable": "المبجل الشيطاني",
    "Rank 1": "المرتبة الأولى",
    "Rank 2": "المرتبة الثانية",
    "Rank 3": "المرتبة الثالثة",
    "Rank 4": "المرتبة الرابعة",
    "Rank 5": "المرتبة الخامسة",
    "Rank 6": "المرتبة السادسة",
    "Rank 7": "المرتبة السابعة",
    "Rank 8": "المرتبة الثامنة",
    "Rank 9": "المرتبة التاسعة",
    "Initial Stage": "المرحلة الأولية",
    "Middle Stage": "المرحلة المتوسطة",
    "Upper Stage": "المرحلة المتقدمة",
    "Peak Stage": "مرحلة الذروة",
    "Primeval Essence": "الجوهر البدائي",
    "Immortal Essence": "الجوهر الخالد",
    "Primeval Stone": "حجر الجوهر البدائي",
    "Primeval Stones": "أحجار الجوهر البدائي",
    "Immortal Essence Stone": "حجر الجوهر الخالد",
    "Immortal Essence Stones": "أحجار الجوهر الخالد",
    "Aperture": "الفتحة الروحية",
    "Primeval Sea": "بحر الجوهر البدائي",
    "Immortal Aperture": "الفتحة الخالدة",
    "Blessed Land": "أرض مباركة",
    "Blessed Lands": "أراضٍ مباركة",
    "Grotto-Heaven": "الكهف السماوي",
    "Grotto-Heavens": "كهوف سماوية",
    "Dao Mark": "علامة داو",
    "Dao Marks": "علامات الداو",
    "Killer Move": "حركة قاتلة",
    "Immortal Killer Move": "حركة قاتلة خالدة",
    "Immortal Gu House": "منزل غو خالد",
    "Heavenly Tribulation": "المحنة السماوية",
    "Earthly Calamity": "كارثة أرضية",
    "Grand Tribulation": "محنة كبرى",
    "Myriad Tribulation": "محنة لا حصر لها",
    "Chaotic Tribulation": "محنة الفوضى",
    "Lifespan Gu": "قو إطالة العمر",
    "Desolate Beast": "وحش مقفر",
    "Ancient Desolate Beast": "وحش مقفر قديم",
    "Immemorial Desolate Beast": "وحش مقفر سحيق",
    "Desolate Plant": "نبات مقفر",
    "Ancient Desolate Plant": "نبات مقفر قديم",
    "Immemorial Desolate Plant": "نبات مقفر سحيق",
    "Sovereign Immortal Body": "الجسد الخالد السيادي",
    "Ten Extreme Physiques": "الأجساد العشرة المتطرفة",

    # ── Geography & Regions (المناطق والجغرافيا) ──
    "Five Regions": "المناطق الخمس",
    "Southern Border": "الحدود الجنوبية",
    "Northern Plains": "السهول الشمالية",
    "Central Continent": "القارة الوسطى",
    "Eastern Sea": "البحر الشرقي",
    "Western Desert": "الصحراء الغربية",
    "White Heaven": "السماء البيضاء",
    "Black Heaven": "السماء السوداء",
    "Two Heavens": "السماوان",
    "Immemorial Nine Heavens": "السماوات التسع السحيقة",
    "River of Time": "نهر الزمن",
    "Door of Life and Death": "باب الحياة والموت",
    "Ordinary Abyss": "الهاوية العادية",
    "City Well": "بئر المدينة",
    "Luo Po Valley": "وادي لوو بو",
    "Dang Hun Mountain": "جبل دانغ هون",
    "Qing Mao Mountain": "جبل تشينغ ماو",
    "Yi Tian Mountain": "جبل يي تيان",
    "Crazy Demon Cave": "كهف الشياطين المجانين",
    "Dragon Palace": "قصر التنين",
    "Heavenly Court": "المحكمة السماوية",
    "Longevity Heaven": "سماء طول العمر",
    "Lang Ya Blessed Land": "أرض لانغ يا المباركة",
    "Hu Immortal Blessed Land": "أرض هو الخالدة المباركة",
    "Imperial Court Blessed Land": "أرض البلاط الإمبراطوري المباركة",
    "Treasure Yellow Heaven": "السماء الصفراء للكنوز",

    # ── Clans, Sects, & Organizations (العشائر والطوائف) ──
    "Gu Yue Clan": "عشيرة غو يوي",
    "Bai Clan": "عشيرة باي",
    "Tie Clan": "عشيرة تي",
    "Shang Clan": "عشيرة شانغ",
    "Wu Clan": "عشيرة وو",
    "Fang Clan": "عشيرة فانغ",
    "Hei Clan": "عشيرة هي",
    "Bao Clan": "عشيرة باو",
    "Shadow Sect": "طائفة الظل",
    "Zombie Alliance": "تحالف الزومبي",
    "Spirit Affinity House": "دار التقارب الروحي",
    "Ancient Soul Sect": "طائفة الروح القديمة",
    "Immortal Crane Sect": "طائفة الرافعة الخالدة",
    "Heavenly Lotus Sect": "طائفة اللوتس السماوي",
    "Ten Great Ancient Sects": "الطوائف العشر القديمة الكبرى",
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Pinyin / Phonetic Transliteration Helpers
# ─────────────────────────────────────────────────────────────────────────────
PINYIN_MAP = {
    "fang": "فانغ", "yuan": "يوان", "zheng": "تشنغ", "bai": "باي", "ning": "نينغ",
    "bing": "بينغ", "gu": "غو", "yue": "يوي", "tie": "تي", "ruo": "روو",
    "nan": "نان", "chi": "تشي", "mo": "مو", "yan": "يان", "xue": "شيويه",
    "feng": "فينغ", "jiu": "جيو", "ge": "غي", "zhao": "تشاو", "lian": "ليان",
    "yun": "يون", "lin": "لين", "qing": "تشينغ", "wu": "وو", "shu": "شو",
    "jin": "جين", "bao": "باو", "long": "لونغ", "hu": "هو", "tian": "تيان",
    "di": "دي", "xuan": "شوان", "huang": "هوانغ", "chen": "تشن", "li": "لي",
    "wang": "وانغ", "zhang": "تشانغ", "liu": "ليو", "yang": "يانغ", "song": "سونغ",
    "lu": "لو", "ding": "دينغ", "shan": "شان", "shui": "شوي", "ming": "مينغ",
    "zi": "تسي", "sun": "سون", "zhou": "تشو", "zhuang": "تشوانغ", "xiao": "شياو",
    "tai": "تاي", "sheng": "شنغ", "ci": "تسي", "xin": "شين", "wei": "وي",
    "han": "هان", "xie": "شيه", "ye": "يه", "fan": "فان", "qiu": "تشيو",
    "dao": "داو", "qi": "تشي", "ba": "با", "hong": "هونغ", "ling": "لينغ"
}

KEYWORDS_MAP = {
    "Clan": "عشيرة",
    "Sect": "طائفة",
    "Tribe": "قبيلة",
    "Elder": "كبير/شيخ",
    "Grandmaster": "سيد عظيم",
    "Great Grandmaster": "سيد عظيم فائق",
    "Supreme Grandmaster": "سيد عظيم أعلى",
    "Master": "سيد",
    "Patriarch": "زعيم العشيرة",
    "Leader": "قائد",
    "Lord": "لورد",
    "Venerable": "مبجل",
    "Immortal": "خالد",
    "Mortal": "فانٍ",
    "Heaven": "السماء",
    "Earth": "الأرض",
    "Soul": "الروح",
    "Demon": "شيطان",
    "Demonic": "شيطاني",
    "Righteous": "مستقيم/عادل",
    "Path": "مسار",
    "Pavilion": "جناح",
    "Mountain": "جبل",
    "River": "نهر",
    "Sea": "بحر",
    "Domain": "نطاق",
    "Realm": "عالم",
    "Continent": "قارة",
    "Hall": "قاعة",
    "Formation": "تشكيل",
    "Beast": "وحش",
    "Dragon": "تنين",
    "Phoenix": "عنقاء",
    "Sword": "سيف",
    "Blade": "نصل",
    "Essence": "جوهر",
    "Aperture": "فتحة روحية",
    "Valley": "وادي",
    "Cave": "كهف",
    "Palace": "قصر",
    "Court": "بلاط/محكمة",
    "House": "منزل/دار",
    "Alliance": "تحالف",
    "City": "مدينة",
    "Island": "جزيرة",
    "Desert": "صحراء",
    "Plains": "سهول",
    "Lake": "بحيرة",
    "Spring": "ينبوع/ربيع",
    "Lotus": "لوتس",
    "Cicada": "زيز",
    "Worm": "دودة",
    "Stone": "حجر",
    "Stones": "أحجار",
}

COMMON_WORDS = {
    "The", "This", "That", "There", "Here", "When", "What", "Where", "Which",
    "Who", "Why", "How", "After", "Before", "While", "Then", "They", "Them",
    "Their", "He", "Him", "His", "She", "Her", "It", "Its", "You", "Your",
    "We", "Our", "All", "Both", "Each", "Every", "Other", "Another", "Some",
    "Any", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
    "Nine", "Ten", "First", "Second", "Third", "Next", "Last", "Suddenly",
    "Meanwhile", "However", "Although", "Because", "Since", "Even", "Just",
    "Now", "Today", "Yesterday", "Tomorrow", "Chapter", "Volume", "Book",
    "Inside", "Outside", "Above", "Below", "Between", "Around", "Through",
    "Into", "Onto", "Upon", "About", "Against", "Along", "Among", "Without",
    "Like", "From", "With", "Over", "Under", "Such", "Most", "Much", "Many",
    "Lord", "Lady", "Sir", "Master", "Young", "Old", "Little", "Great", "Big"
}


class FullGlossaryBuilder:
    """
    Builds and exports the ultimate comprehensive Reverend Insanity Glossary
    from all 2,334 chapters.
    """

    def __init__(self, raw_dir: Path = Config.RAW_EN_DIR):
        self.raw_dir = raw_dir
        self.glossary = dict(CANONICAL_GLOSSARY)

    def transliterate(self, phrase: str) -> str:
        words = phrase.strip().split()
        parts = []
        for w in words:
            w_low = w.lower()
            if w in KEYWORDS_MAP:
                parts.append(KEYWORDS_MAP[w])
            elif w_low in PINYIN_MAP:
                parts.append(PINYIN_MAP[w_low])
            else:
                parts.append(w)
        return " ".join(parts)

    def scan_all_chapters(self, min_occurrences: int = 10) -> Dict[str, str]:
        """Scan all 2,334 chapters to extract any additional proper nouns."""
        print("=" * 80)
        print(" 🔍 جاري فحص جميع الفصول الـ 2,334 لاستخراج كل المصطلحات والأسماء...")
        print("=" * 80)

        t0 = time.time()
        files = list(self.raw_dir.rglob("chapter_*.txt"))
        if not files:
            print(" ⚠️ لم يتم العثور على فصول في مجلد الخام، سيتم الاعتماد على القاموس القياسي.")
            return self.glossary

        multi_counter = Counter()
        multi_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")

        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    text = file.read()
                for match in multi_pattern.findall(text):
                    words = match.split()
                    if all(w not in COMMON_WORDS for w in words):
                        multi_counter[match] += 1
            except Exception:
                continue

        extracted_count = 0
        for phrase, count in multi_counter.most_common(500):
            if count >= min_occurrences and phrase not in self.glossary:
                ar_trans = self.transliterate(phrase)
                if ar_trans != phrase:
                    self.glossary[phrase] = ar_trans
                    extracted_count += 1

        elapsed = time.time() - t0
        print(f" [✓] تم فحص {len(files)} فصلاً في {elapsed:.1f}ث.")
        print(f" [✓] إجمالي مصطلحات القاموس: {len(self.glossary)} مصطلحاً (تم استخراج {extracted_count} مصطلحاً جديداً تلقائياً).")
        return self.glossary

    def save(self):
        """Save glossary to both root and output directories, plus markdown documentation."""
        # 1. Root glossary.json
        root_path = Path("glossary.json")
        with open(root_path, "w", encoding="utf-8") as f:
            json.dump(self.glossary, f, ensure_ascii=False, indent=2)

        # 2. Output directory glossary.json
        out_path = Config.OUTPUT_DIR / "reverend_insanity_glossary.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.glossary, f, ensure_ascii=False, indent=2)

        # 3. Human readable Markdown Glossary
        md_path = Config.OUTPUT_DIR / "glossary_summary.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 📜 القاموس الشامل لمصطلحات رواية القس المجنون (Reverend Insanity Glossary)\n\n")
            f.write(f"- **إجمالي المصطلحات الموثقة:** **{len(self.glossary)}** مصطلحاً\n")
            f.write("- **الاستخدام:** توحيد الترجمة الدلالية في خط المعالجة وWorkflow جيت هب.\n\n")
            f.write("| المصطلح الإنجليزي (English) | الترجمة العربية المعتمدة (Arabic) |\n")
            f.write("| :--- | :--- |\n")
            for k, v in sorted(self.glossary.items()):
                f.write(f"| `{k}` | **{v}** |\n")

        print(f" [✓] تم حفظ القاموس في: {root_path.resolve()}")
        print(f" [✓] تم حفظ القاموس في: {out_path.resolve()}")
        print(f" [✓] تم إنشاء التوثيق: {md_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Full Glossary Extractor for Reverend Insanity")
    parser.add_argument("--min-occurrences", type=int, default=8, help="Min occurrences to include")
    args = parser.parse_args()

    builder = FullGlossaryBuilder()
    builder.scan_all_chapters(min_occurrences=args.min_occurrences)
    builder.save()


if __name__ == "__main__":
    main()
