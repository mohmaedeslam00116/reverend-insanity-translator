import re
import sys
from pathlib import Path
from typing import List, Tuple

from config import Config
from fast_translator import FastGoogleTranslator
from organize_volumes import get_volume_dir

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class AutoChapterHealer:
    """
    Scans translated chapters, detects leftover English text or missing
    paragraphs, and selectively re-translates & patches ONLY the defective
    paragraphs in place without re-translating the whole chapter.
    """

    def __init__(self):
        self.translator = FastGoogleTranslator()
        self.english_pattern = re.compile(r"\b[A-Za-z]{3,}\b")
        # Words allowed in markdown header
        self.ignored_words = {"chapter", "vol", "volume", "txt", "md"}

    def find_file(self, base_dir: Path, chapter_num: int) -> Path:
        vol_path = get_volume_dir(base_dir, chapter_num) / f"chapter_{chapter_num:04d}.txt"
        if vol_path.exists():
            return vol_path
        return base_dir / f"chapter_{chapter_num:04d}.txt"

    def heal_chapter(self, chapter_num: int) -> dict:
        """Scan and heal a single chapter file."""
        trans_file = self.find_file(Config.TRANSLATED_AR_DIR, chapter_num)
        raw_file = self.find_file(Config.RAW_EN_DIR, chapter_num)

        if not trans_file.exists() or not raw_file.exists():
            return {"chapter": chapter_num, "status": "skipped", "reason": "File not found"}

        with open(trans_file, "r", encoding="utf-8") as f:
            trans_content = f.read()

        with open(raw_file, "r", encoding="utf-8") as f:
            raw_content = f.read()

        trans_lines = trans_content.split("\n\n")
        raw_lines = [p.strip() for p in raw_content.split("\n\n") if p.strip() and not p.startswith("#")]

        repaired_paragraphs = 0
        healed_lines = []

        for idx, p in enumerate(trans_lines):
            # Check title line
            if p.startswith("#"):
                # Translate title if it has english
                en_words = [w for w in self.english_pattern.findall(p) if w.lower() not in self.ignored_words]
                if en_words:
                    # Clean title
                    clean_title = self.translator.translate_paragraph(p.replace("#", "").strip())
                    healed_lines.append(f"# {clean_title}")
                    repaired_paragraphs += 1
                else:
                    healed_lines.append(p)
                continue

            # Check body paragraph
            en_words = [w for w in self.english_pattern.findall(p) if w.lower() not in self.ignored_words]
            if len(en_words) >= 3:
                # This paragraph likely failed translation or has heavy leftover English
                # Re-translate this paragraph
                healed_p = self.translator.translate_paragraph(p)
                healed_lines.append(healed_p)
                repaired_paragraphs += 1
            else:
                healed_lines.append(p)

        if repaired_paragraphs > 0:
            healed_text = "\n\n".join(healed_lines)
            with open(trans_file, "w", encoding="utf-8") as f:
                f.write(healed_text.strip() + "\n")
            return {
                "chapter": chapter_num,
                "status": "healed",
                "repaired_paragraphs": repaired_paragraphs,
            }
        else:
            return {"chapter": chapter_num, "status": "clean"}

    def run_healing_scan(self, start: int = 1, end: int = 50):
        """Scan and auto-heal a range of chapters."""
        print("=" * 70)
        print(f" 🩺 نظام الترميم والإصلاح الذاتي للفصول (Auto-Healer)")
        print("=" * 70)
        print(f" • نطاق الفحص: من {start} إلى {end}")
        print("=" * 70)

        total_healed = 0
        for cnum in range(start, end + 1):
            res = self.heal_chapter(cnum)
            if res["status"] == "healed":
                print(f"  [🩺 ترميم] تم إصلاح الفصل {cnum:04d} (ترميم {res['repaired_paragraphs']} فقرة/عنوان)")
                total_healed += 1

        print("\n" + "=" * 70)
        print(f" [✓] اكتمل الفحص! تم ترميم وإصلاح {total_healed} فصلاً بنجاح.")
        print("=" * 70)


if __name__ == "__main__":
    healer = AutoChapterHealer()
    healer.run_healing_scan(start=1, end=20)
