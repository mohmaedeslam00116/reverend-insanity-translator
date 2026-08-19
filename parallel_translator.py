import sys
import time
import json
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from config import Config
from prompt_templates import GLOSSARY
from fast_translator import FastGoogleTranslator
from translator import KiloTranslator

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class ParallelNovelTranslator:
    """
    High-performance concurrent translator using multi-threading.
    Translates multiple chapters simultaneously (e.g. 10-20 workers)
    with Xianxia glossary replacement and clean paragraph formatting.
    """

    def __init__(self, max_workers: int = 15):
        self.max_workers = max_workers
        self.lock = threading.Lock()
        self.completed_count = 0
        self.failed_count = 0

    def translate_single_chapter(self, chapter_num: int) -> dict:
        """Process and translate a single chapter from local raw_en file."""
        raw_file = Config.RAW_EN_DIR / f"chapter_{chapter_num:04d}.txt"
        trans_file = Config.TRANSLATED_AR_DIR / f"chapter_{chapter_num:04d}.txt"

        if not raw_file.exists():
            return {"chapter": chapter_num, "status": "error", "error": "Raw file not found"}

        try:
            with open(raw_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines and lines[0].startswith("#"):
                    chapter_title = lines[0].replace("#", "").strip()
                    paragraphs = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]
                else:
                    chapter_title = f"Chapter {chapter_num}"
                    paragraphs = [p.strip() for p in "".join(lines).split("\n\n") if p.strip()]

            # Translate using FastGoogleTranslator
            t_engine = FastGoogleTranslator()
            t_start = time.time()
            trans_res = t_engine.translate_chapter(chapter_title, paragraphs)
            elapsed = time.time() - t_start

            if trans_res.get("status") == "success":
                t_engine.save_translated_chapter(
                    chapter_num=chapter_num,
                    title=chapter_title,
                    translated_text=trans_res["translated_text"],
                    filepath=trans_file,
                )
                return {
                    "chapter": chapter_num,
                    "status": "success",
                    "title": chapter_title,
                    "elapsed": round(elapsed, 2),
                    "paragraphs": len(paragraphs),
                }
            else:
                return {
                    "chapter": chapter_num,
                    "status": "error",
                    "error": trans_res.get("error", "Translation failed"),
                }
        except Exception as e:
            return {"chapter": chapter_num, "status": "error", "error": str(e)}

    def run_parallel(self, start_chapter: int = 1, end_chapter: int = 2334):
        """Translate all chapters in range in parallel using ThreadPoolExecutor."""
        Config.init_directories()

        # Find which chapters are actually missing
        pending_chapters = []
        for cnum in range(start_chapter, end_chapter + 1):
            trans_file = Config.TRANSLATED_AR_DIR / f"chapter_{cnum:04d}.txt"
            if not trans_file.exists():
                pending_chapters.append(cnum)

        total_pending = len(pending_chapters)
        print("=" * 75)
        print(f" ⚡ محرك الترجمة المتوازية الفائقة (Parallel Multi-Threading)")
        print("=" * 75)
        print(f" • نطاق الفصول: من {start_chapter} إلى {end_chapter}")
        print(f" • الفصول المتبقية للترجمة: {total_pending} فصلاً")
        print(f" • عدد المسارات المتوازية (Threads): {self.max_workers} مساراً في نفس الوقت")
        print("=" * 75)

        if total_pending == 0:
            print("[✓] جميع الفصول في هذا النطاق مترجمة بالفعل!")
            return

        start_time = time.time()
        self.completed_count = 0
        self.failed_count = 0

        # Run with ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_chap = {
                executor.submit(self.translate_single_chapter, cnum): cnum
                for cnum in pending_chapters
            }

            for future in as_completed(future_to_chap):
                res = future.result()
                cnum = res["chapter"]
                with self.lock:
                    if res["status"] == "success":
                        self.completed_count += 1
                        pct = (self.completed_count / total_pending) * 100
                        print(
                            f"  [✓] ({self.completed_count:04d}/{total_pending:04d} - {pct:5.1f}%) تم إنجاز الفصل {cnum:04d} في {res['elapsed']:.1f}ث ({res['paragraphs']} فقرة)"
                        )
                    else:
                        self.failed_count += 1
                        print(f"  [X] فشل الفصل {cnum:04d}: {res.get('error')}")

        total_time = time.time() - start_time
        print("\n" + "=" * 75)
        print(" 🎉 اكتملت الترجمة المتوازية بالكامل!")
        print("=" * 75)
        print(f" • إجمالي الفصول المنجزة: {self.completed_count}")
        print(f" • الفصول المتعثرة: {self.failed_count}")
        print(f" • إجمالي الوقت المستغرق: {total_time / 60:.2f} دقيقة ({total_time / max(1, self.completed_count):.2f}ث / فصل)")
        print("=" * 75)

        # Update progress.json
        try:
            from main import ProgressTracker
            tracker = ProgressTracker(Config.PROGRESS_FILE)
            for cnum in range(start_chapter, end_chapter + 1):
                t_f = Config.TRANSLATED_AR_DIR / f"chapter_{cnum:04d}.txt"
                if t_f.exists():
                    tracker.mark_completed(cnum)
        except Exception:
            pass

        # Compile book
        try:
            from compile_novel import compile_translated_chapters
            compile_translated_chapters()
        except Exception as e:
            print(f"[Compiler] Error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parallel Novel Translator")
    parser.add_argument("-s", "--start", type=int, default=1100)
    parser.add_argument("-e", "--end", type=int, default=2334)
    parser.add_argument("-w", "--workers", type=int, default=15)
    args = parser.parse_args()

    translator = ParallelNovelTranslator(max_workers=args.workers)
    translator.run_parallel(start_chapter=args.start, end_chapter=args.end)
