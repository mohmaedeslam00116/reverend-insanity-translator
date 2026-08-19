"""
📖 Shadow Slave (عبد الظل) - Full Glossary & Terminology Engine
==============================================================
Curated canonical dictionary and automated entity extraction for
Guiltythree's webnovel 'Shadow Slave'.
"""

import sys
import re
import json
from pathlib import Path
from typing import Dict, List
from collections import Counter

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Canonical Shadow Slave Glossary (قاموس مصطلحات عبد الظل المعتمد)
# ─────────────────────────────────────────────────────────────────────────────
SHADOW_SLAVE_CANON_GLOSSARY = {
    # ── Characters (الشخصيات) ──
    "Sunny": "صني",
    "Sunless": "سانلس",
    "Nephis": "نيفيس",
    "Changing Star": "نجم التغيير",
    "Cassie": "كاسي",
    "Song of the Fallen": "أغنية الساقطين",
    "Effie": "إيفي",
    "Athena": "أثينا",
    "Kai": "كاي",
    "Nightingale": "العندليب",
    "Jet": "جيت",
    "Master Jet": "المعلمة جيت",
    "Soul Reaper": "حاصدة الأرواح",
    "Mordret": "موردرت",
    "Prince of War": "أمير الحرب",
    "Weaver": "الحائك",
    "Daemon of Fate": "شيطان المصير",
    "Nether": "نيذر",
    "Daemon of Choice": "شيطان الاختيار",
    "Hope": "الأمل",
    "Daemon of Desire": "شيطانة الرغبة",
    "Gunlaug": "غونلوغ",
    "Bright Lord": "اللورد الساطع",
    "Caster": "كاستر",
    "Hero": "البطل",
    "Seishan": "سيشان",
    "Gemma": "غيما",
    "Kuro": "كورو",
    "Anvil of Valor": "سندان البسالة",
    "Ki Song": "كي سونغ",
    "Asterion": "أستريون",
    "Rain": "رين",

    # ── System, Spell & Ranks (نظام تعويذة الكابوس والمراتب) ──
    "Nightmare Spell": "تعويذة الكابوس",
    "First Nightmare": "الكابوس الأول",
    "Second Nightmare": "الكابوس الثاني",
    "Third Nightmare": "الكابوس الثالث",
    "Fourth Nightmare": "الكابوس الرابع",
    "True Name": "الاسم الحقيقي",
    "Lost from Light": "التائه عن النور",
    "Aspect": "الجانب",
    "Aspect Rank": "رتبة الجانب",
    "Shadow Slave": "عبد الظل",
    "Shadow God": "إله الظلال",
    "Sun God": "إله الشمس",
    "War God": "إله الحرب",
    "Storm God": "إله العواصف",
    "Beast God": "إله الوحوش",
    "Heart God": "إله القلب",
    "Flaw": "النقيصة / العيب",
    "Clear Conscience": "الضمير النقي",
    "Soul Core": "نواة الروح",
    "Shadow Core": "نواة الظل",
    "Soul Sea": "بحر الروح",
    "Soul Shards": "شظايا الروح",
    "Shadow Shards": "شظايا الظل",
    "Memories": "الذكريات",
    "Memory": "ذكرى",
    "Echoes": "الأصداء",
    "Echo": "صدى",
    "Soul Essence": "جوهر الروح",
    "Shadow Essence": "جوهر الظل",
    "Attributes": "السمات",
    "Attribute": "سمة",

    # ── Human Awakening Ranks (رتب المستيقظين) ──
    "Sleeper": "النائم",
    "Sleepers": "النائمون",
    "Awakened": "المستيقظ",
    "Ascended": "الصاعد / السيد",
    "Master": "السيد",
    "Masters": "الأسياد",
    "Transcendent": "المتسامي / القديس",
    "Saint": "القديس",
    "Saints": "القديسون",
    "Supreme": "الأسمى / السيادي",
    "Sovereign": "السيادي",
    "Sovereigns": "السياديون",
    "Sacred": "المقدس",
    "Divine": "الإلهي",

    # ── Nightmare Creature Ranks & Classes (تصنيف مخلوقات الكابوس) ──
    "Nightmare Creature": "مخلوق الكابوس",
    "Nightmare Creatures": "مخلوقات الكابوس",
    "Dormant": "خامل",
    "Fallen": "ساقط",
    "Corrupted": "فاسد",
    "Great": "عظيم",
    "Cursed": "ملعون",
    "Unholy": "دنس",
    # Classes:
    "Beast": "وحش",
    "Monster": "مسخ",
    "Demon": "شيطان",
    "Devil": "إبليس",
    "Tyrant": "طاغية",
    "Terror": "رعب",
    "Titan": "عملاق",

    # ── Key Locations & Geography (المواقع والعوالم) ──
    "Dream Realm": "عالم الأحلام",
    "Waking World": "عالم اليقظة",
    "Forgotten Shore": "الشاطئ المنسي",
    "Dark City": "المدينة المظلمة",
    "Crimson Spire": "البرج القرمزي",
    "Labyrinth": "المتاهة",
    "Ashen Barrow": "التل الرمادي",
    "Soul Devouring Tree": "شجرة التهام الأرواح",
    "Chained Isles": "الجزر المقيدة",
    "Ivory Tower": "البرج العاجي",
    "Nightmare Desert": "صحراء الكابوس",
    "Tomb of Ariel": "ضريح أرييل",
    "Citadel": "القلعة",
    "Citadels": "القلاع",
    "Gateway": "البوابة",
    "Gateways": "البوابات",
    "Black Sea": "البحر الأسود",

    # ── Clans & Legacy (العشائر الكبرى) ──
    "Great Clans": "العشائر العظمى",
    "Clan Valor": "عشيرة البسالة",
    "Clan Song": "عشيرة سونغ",
    "House of Night": "دار الليل",
    "Legacy Clan": "عشيرة موروثة",
    "Legacy": "الميراث",
}


class ShadowSlaveGlossary:
    """
    Extracts terms from raw chapters and maintains a complete Shadow Slave dictionary.
    """

    def __init__(self, novel_dir: Path = Path("novels/shadow-slave")):
        self.novel_dir = novel_dir
        self.raw_dir = novel_dir / "raw_en"
        self.glossary_file = novel_dir / "glossary.json"
        self.summary_md = novel_dir / "glossary_summary.md"
        self.glossary = dict(SHADOW_SLAVE_CANON_GLOSSARY)

    def scan_chapters(self, min_occurrences: int = 5) -> Dict[str, str]:
        """Scan all scraped chapters to detect names and entities."""
        files = list(self.raw_dir.glob("chapter_*.txt"))
        if not files:
            return self.glossary

        pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
        counter = Counter()

        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    text = file.read()
                for match in pattern.findall(text):
                    counter[match] += 1
            except Exception:
                continue

        # Add recurring capitalized terms
        for phrase, count in counter.most_common(200):
            if count >= min_occurrences and phrase not in self.glossary:
                # Basic phonetics
                self.glossary[phrase] = phrase

        return self.glossary

    def save(self):
        """Save glossary to json and markdown."""
        self.novel_dir.mkdir(parents=True, exist_ok=True)
        with open(self.glossary_file, "w", encoding="utf-8") as f:
            json.dump(self.glossary, f, ensure_ascii=False, indent=2)

        with open(self.summary_md, "w", encoding="utf-8") as f:
            f.write("# 📜 قاموس مصطلحات رواية عبد الظل (Shadow Slave Glossary)\n\n")
            f.write(f"- **إجمالي المصطلحات الموثقة:** **{len(self.glossary)}** مصطلحاً\n\n")
            f.write("| المصطلح الإنجليزي (English) | الترجمة العربية المعتمدة (Arabic) |\n")
            f.write("| :--- | :--- |\n")
            for k, v in sorted(self.glossary.items()):
                f.write(f"| `{k}` | **{v}** |\n")

        print(f"[ShadowSlave] تم حفظ القاموس في: {self.glossary_file.resolve()}")
        print(f"[ShadowSlave] تم حفظ التوثيق في: {self.summary_md.resolve()}")


if __name__ == "__main__":
    builder = ShadowSlaveGlossary()
    builder.scan_chapters()
    builder.save()
