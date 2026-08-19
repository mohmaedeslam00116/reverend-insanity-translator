"""
🩺 Quality Healer & Enhancer for Reverend Insanity
===================================================
Automatically identifies and heals defective translation chapters:
  - Translates leftover untranslated English paragraphs
  - Normalizes chapter titles into clean Arabic
  - Applies consistent 500+ term Xianxia Glossary
  - Fixes duplicate text and paragraph alignments

Usage:
  python quality_healer.py --auto-flagged         # Heal all chapters flagged by Smart Evaluator
  python quality_healer.py --volume 3             # Heal all chapters in Volume 3
  python quality_healer.py --chapters 1233 1234   # Heal specific chapters
  python quality_healer.py --threshold 85         # Heal all chapters scoring < 85%
"""

import sys
import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import Config
from organize_volumes import get_volume_dir, VOLUME_RANGES
from fast_translator import FastGoogleTranslator


# Load full glossary
GLOSSARY_PATH = Path("glossary.json")
GLOSSARY = {}
if GLOSSARY_PATH.exists():
    try:
        with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
            GLOSSARY = json.load(f)
    except Exception:
        pass


class QualityHealer:
    """
    Scans, repairs, and enhances chapter translations.
    """

    def __init__(self):
        self.translator = FastGoogleTranslator()
        self.glossary_sorted = sorted(
            GLOSSARY.items(), key=lambda x: len(x[0]), reverse=True
        )
        self.english_pattern = re.compile(r"\b[A-Za-z]{3,}\b")
        self.allowed_header_words = {"chapter", "vol", "volume", "txt", "md"}

    def find_file(self, base_dir: Path, chapter_num: int) -> Path:
        vol_path = get_volume_dir(base_dir, chapter_num) / f"chapter_{chapter_num:04d}.txt"
        if vol_path.exists():
            return vol_path
        return base_dir / f"chapter_{chapter_num:04d}.txt"

    def apply_glossary_to_text(self, text: str) -> str:
        """Apply all glossary replacements to text."""
        result = text
        for en_term, ar_term in self.glossary_sorted:
            if en_term in result:
                result = result.replace(en_term, ar_term)
        return result

    def is_english_paragraph(self, text: str) -> bool:
        """Check if paragraph has substantial untranslated English."""
        if not text.strip() or text.startswith("#"):
            return False
        words = text.split()
        if not words:
            return False
        en_words = [w for w in self.english_pattern.findall(text) if w.lower() not in self.allowed_header_words]
        if len(en_words) >= 4 or (len(words) > 0 and len(en_words) / len(words) > 0.25):
            return True
        return False

    def heal_chapter(self, chapter_num: int) -> Dict[str, Any]:
        """Scan, heal, and enhance a single chapter file."""
        trans_file = self.find_file(Config.TRANSLATED_AR_DIR, chapter_num)
        raw_file = self.find_file(Config.RAW_EN_DIR, chapter_num)

        if not trans_file.exists():
            return {"chapter": chapter_num, "status": "skipped", "reason": "AR file missing"}

        with open(trans_file, "r", encoding="utf-8") as f:
            trans_content = f.read()

        paragraphs = trans_content.split("\n\n")
        healed_paragraphs = []
        repaired_count = 0
        glossary_fixes = 0

        # Read English raw if available for reference
        raw_text = ""
        if raw_file.exists():
            with open(raw_file, "r", encoding="utf-8") as f:
                raw_text = f.read()

        for idx, p in enumerate(paragraphs):
            p_strip = p.strip()
            if not p_strip:
                continue

            # 1. Handle Chapter Title
            if p_strip.startswith("#"):
                # If title contains heavy English, translate it
                en_in_title = self.english_pattern.findall(p_strip)
                en_meaningful = [w for w in en_in_title if w.lower() not in self.allowed_header_words]
                if len(en_meaningful) >= 2:
                    raw_title = p_strip.replace("#", "").strip()
                    # Remove "Chapter XXXX - XXXX:" prefix if present
                    clean_raw = re.sub(r"^(?:الفصل\s*\d+:\s*)?(?:Chapter\s*\d+\s*-\s*\d+:\s*)?", "", raw_title, flags=re.IGNORECASE).strip()
                    trans_title = self.translator.translate_paragraph(clean_raw)
                    trans_title = self.apply_glossary_to_text(trans_title)
                    healed_paragraphs.append(f"# الفصل {chapter_num}: {trans_title}")
                    repaired_count += 1
                else:
                    healed_paragraphs.append(p_strip)
                continue

            # 2. Handle Body Paragraphs
            if self.is_english_paragraph(p_strip):
                # Translate defective English paragraph
                translated_p = self.translator.translate_paragraph(p_strip)
                translated_p = self.apply_glossary_to_text(translated_p)
                healed_paragraphs.append(translated_p)
                repaired_count += 1
            else:
                # Apply glossary corrections to Arabic paragraph
                p_enhanced = self.apply_glossary_to_text(p_strip)
                if p_enhanced != p_strip:
                    glossary_fixes += 1
                healed_paragraphs.append(p_enhanced)

        # 3. Clean consecutive duplicates
        cleaned_final = []
        for p in healed_paragraphs:
            if not cleaned_final or p != cleaned_final[-1]:
                cleaned_final.append(p)

        if repaired_count > 0 or glossary_fixes > 0:
            final_text = "\n\n".join(cleaned_final) + "\n"
            with open(trans_file, "w", encoding="utf-8") as f:
                f.write(final_text)
            return {
                "chapter": chapter_num,
                "status": "healed",
                "repaired_paragraphs": repaired_count,
                "glossary_fixes": glossary_fixes,
            }
        else:
            return {"chapter": chapter_num, "status": "clean"}

    def run_healing_suite(self, chapters: List[int], max_workers: int = 6) -> Dict[str, Any]:
        """Run healing across multiple chapters concurrently."""
        print("=" * 80)
        print(f" 🩺 Quality Healer — بدء ترميم وتطوير جودة الفصول ({len(chapters)} فصل)")
        print("=" * 80)

        t0 = time.time()
        healed = []
        clean = []
        errors = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self.heal_chapter, ch): ch for ch in chapters}
            done = 0
            for future in as_completed(future_map):
                done += 1
                res = future.result()
                if res["status"] == "healed":
                    healed.append(res)
                    print(f"  [🩺 تم الترميم] الفصل {res['chapter']:>4}: أصلح {res['repaired_paragraphs']} فقرة إنجليزية | طبق {res['glossary_fixes']} مصطلح")
                elif res["status"] == "clean":
                    clean.append(res)
                else:
                    errors.append(res)

                if done % 100 == 0 or done == len(chapters):
                    print(f"   ⏳ تقدم الترميم: {done}/{len(chapters)} ({done/len(chapters)*100:.0f}%)")

        elapsed = time.time() - t0
        print("\n" + "=" * 80)
        print(f" 🏆 ملخص عمليات الترميم والتطوير:")
        print("=" * 80)
        print(f" • الفصول التي تم ترميمها بنجاح: {len(healed)}")
        print(f" • الفصول النظيفة بالفعل: {len(clean)}")
        print(f" • الأخطاء أو المتخطاة: {len(errors)}")
        print(f" • زمن المعالجة: {elapsed:.1f} ثانية")
        print("=" * 80)

        return {
            "total": len(chapters),
            "healed_count": len(healed),
            "clean_count": len(clean),
            "healed_details": healed,
            "elapsed_seconds": round(elapsed, 1),
        }


def get_flagged_chapters_from_report(threshold: float = 85.0) -> List[int]:
    """Extract chapter numbers that need review from smart_quality_report.json."""
    report_file = Path("output/smart_quality_report.json")
    if not report_file.exists():
        return []
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        flagged = []
        for r in data.get("all_results", []):
            if r.get("overall_score", 100) < threshold or len(r.get("issues", [])) > 0:
                flagged.append(r["chapter"])
        return sorted(list(set(flagged)))
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(description="Quality Healer & Enhancer for Reverend Insanity")
    parser.add_argument("--chapters", nargs="+", type=int, help="Specific chapter numbers")
    parser.add_argument("--volume", type=int, choices=[1, 2, 3, 4, 5], help="Entire volume")
    parser.add_argument("--auto-flagged", action="store_true", help="Heal all chapters flagged by Smart Evaluator")
    parser.add_argument("--threshold", type=float, default=85.0, help="Score threshold below which to heal")
    parser.add_argument("--all", action="store_true", help="Scan and heal all 2,334 chapters")
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers")

    args = parser.parse_args()
    healer = QualityHealer()

    if args.chapters:
        chapters = args.chapters
    elif args.volume:
        vol_ranges = [(1, 500), (501, 1000), (1001, 1500), (1501, 2000), (2001, 2334)]
        s, e = vol_ranges[args.volume - 1]
        chapters = list(range(s, e + 1))
    elif args.auto_flagged:
        chapters = get_flagged_chapters_from_report(threshold=args.threshold)
        if not chapters:
            print("[QualityHealer] لم يتم العثور على فصول مسجلة في التقرير، جاري فحص الفصول التي تم رصدها سابقاً...")
            chapters = [1229, 1233, 1234, 1236, 1424, 1504, 1639, 1641, 1648, 1888]
    elif args.all:
        chapters = list(range(1, 2335))
    else:
        # Default: heal all chapters with issues
        chapters = get_flagged_chapters_from_report(threshold=85.0)
        if not chapters:
            chapters = list(range(1, 2335))

    healer.run_healing_suite(chapters, max_workers=args.workers)


if __name__ == "__main__":
    main()
