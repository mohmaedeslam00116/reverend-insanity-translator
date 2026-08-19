import re
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


class AutoGlossaryExtractor:
    """
    Analyzes raw English chapters of any webnovel, extracts key proper nouns,
    character names, sects, ranks, and Xianxia terms, and builds a consistent
    Arabic glossary automatically.
    """

    COMMON_ENGLISH_WORDS = {
        "The", "This", "That", "There", "Here", "When", "What", "Where", "Which",
        "Who", "Why", "How", "After", "Before", "While", "Then", "They", "Them",
        "Their", "He", "Him", "His", "She", "Her", "It", "Its", "You", "Your",
        "We", "Our", "All", "Both", "Each", "Every", "Other", "Another", "Some",
        "Any", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
        "Nine", "Ten", "First", "Second", "Third", "Next", "Last", "Suddenly",
        "Meanwhile", "However", "Although", "Because", "Since", "Even", "Just",
        "Now", "Today", "Yesterday", "Tomorrow", "Chapter", "Volume", "Book",
        "Inside", "Outside", "Above", "Below", "Between", "Around", "Through",
        "Into", "Onto", "Upon", "About", "Against", "Along", "Among", "Without"
    }

    # Standard English -> Arabic fantasy keyword translations
    TERM_TRANSLATIONS = {
        "Clan": "عشيرة",
        "Sect": "طائفة",
        "Tribe": "قبيلة",
        "Elder": "كبير/شيخ",
        "Grandmaster": "سيد عظيم",
        "Master": "سيد",
        "Patriarch": "زعيم العشيرة",
        "Leader": "قائد",
        "Lord": "لورد/سيد",
        "Venerable": "موقر",
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
    }

    # Pinyin / Chinese name transliteration mapping to Arabic
    PINYIN_TO_ARABIC = {
        "fang": "فانغ", "yuan": "يوان", "zheng": "تشنغ", "bai": "باي", "ning": "نينغ",
        "bing": "بينغ", "gu": "غو", "yue": "يوي", "tie": "تي", "ruo": "روو",
        "nan": "نان", "chi": "تشي", "mo": "مو", "yan": "يان", "xue": "شيويه",
        "feng": "فينغ", "jiu": "جيو", "ge": "غه", "zhao": "تشاو", "lian": "ليان",
        "yun": "يون", "lin": "لين", "qing": "تشينغ", "wu": "وو", "shu": "شو",
        "jin": "جين", "bao": "باو", "long": "لونغ", "hu": "هو", "tian": "تيان",
        "di": "دي", "xuan": "شوان", "huang": "هوانغ", "chen": "تشن", "li": "لي",
        "wang": "وانغ", "zhang": "تشانغ", "liu": "ليو", "yang": "يانغ", "song": "سونغ",
        "lu": "لو", "ding": "دينغ", "shan": "شان", "shui": "شوي", "ming": "مينغ",
        "zi": "تسي", "sun": "سون", "zhou": "تشو", "zhuang": "تشوانغ", "xiao": "شياو"
    }

    def __init__(self, raw_chapters_dir: Path):
        self.raw_dir = Path(raw_chapters_dir)

    def transliterate_name(self, english_name: str) -> str:
        """Attempt phonetic transliteration for Chinese Pinyin or compound names."""
        words = english_name.strip().split()
        translated_parts = []

        for word in words:
            w_lower = word.lower()
            if word in self.TERM_TRANSLATIONS:
                translated_parts.append(self.TERM_TRANSLATIONS[word])
            elif w_lower in self.PINYIN_TO_ARABIC:
                translated_parts.append(self.PINYIN_TO_ARABIC[w_lower])
            else:
                translated_parts.append(word)

        return " ".join(translated_parts)

    def extract_from_chapters(self, max_chapters: int = 50, min_occurrences: int = 4) -> Dict[str, str]:
        """Extract multi-word proper nouns and high-frequency terms from chapters."""
        files = list(self.raw_dir.rglob("chapter_*.txt"))[:max_chapters]
        if not files:
            print(f"[AutoGlossary] لا توجد فصول في {self.raw_dir}")
            return {}

        print(f"[AutoGlossary] جاري تحليل {len(files)} فصلاً لاستخراج المصطلحات والأسماء...")

        multi_word_counter = Counter()
        single_word_counter = Counter()

        # Regex for multi-word Capitalized phrases (e.g. "Fang Yuan", "Gu Yue Clan", "Spring Autumn Cicada")
        multi_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")
        single_pattern = re.compile(r"\b([A-Z][a-z]{2,})\b")

        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as file:
                    text = file.read()

                # Multi-word proper nouns
                for match in multi_pattern.findall(text):
                    words = match.split()
                    if all(w not in self.COMMON_ENGLISH_WORDS for w in words):
                        multi_word_counter[match] += 1

                # Single capitalized words
                for match in single_pattern.findall(text):
                    if match not in self.COMMON_ENGLISH_WORDS:
                        single_word_counter[match] += 1
            except Exception:
                continue

        glossary = {}

        # 1. Process multi-word phrases (High Priority)
        for phrase, count in multi_word_counter.most_common(150):
            if count >= min_occurrences:
                ar_trans = self.transliterate_name(phrase)
                glossary[phrase] = ar_trans

        # 2. Process single words
        for word, count in single_word_counter.most_common(100):
            if count >= min_occurrences * 2 and word not in glossary:
                ar_trans = self.transliterate_name(word)
                if ar_trans != word:
                    glossary[word] = ar_trans

        print(f"[AutoGlossary] تم استخراج وتوليد {len(glossary)} مصطلحاً واسماً بنجاح!")
        return glossary

    def save_glossary(self, glossary: Dict[str, str], output_path: Path):
        """Save extracted glossary to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        print(f"[✓] تم حفظ القاموس التلقائي في: {output_path.resolve()}")


if __name__ == "__main__":
    from config import Config
    extractor = AutoGlossaryExtractor(Config.RAW_EN_DIR)
    gloss = extractor.extract_from_chapters(max_chapters=30, min_occurrences=5)
    
    out_file = Path("output/auto_extracted_glossary.json")
    extractor.save_glossary(gloss, out_file)
    
    print("\n--- عينة من المصطلحات المستخرجة تلقائياً ---")
    for k, v in list(gloss.items())[:15]:
        print(f" • {k:<30} ➔ {v}")
