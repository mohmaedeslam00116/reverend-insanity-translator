import os
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

from config import Config
from scraper import NovelFireScraper
from translator import KiloTranslator


class ProgressTracker:
    """Manages persistent progress tracking across runs."""

    def __init__(self, progress_file: Path):
        self.file_path = progress_file
        self.data: Dict[str, Any] = {
            "completed_chapters": [],
            "failed_chapters": {},
            "last_chapter": 0,
            "started_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }
        self.load()

    def load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[Tracker] تحذير: تعذر قراءة ملف التقدم، سيتم إنشاء ملف جديد ({e})")

    def save(self):
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self.data["last_updated"] = datetime.now().isoformat()
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Tracker] خطأ في حفظ ملف التقدم: {e}")

    def is_completed(self, chapter_num: int) -> bool:
        return chapter_num in self.data.get("completed_chapters", [])

    def mark_completed(self, chapter_num: int):
        completed = set(self.data.get("completed_chapters", []))
        completed.add(chapter_num)
        self.data["completed_chapters"] = sorted(list(completed))
        self.data["last_chapter"] = max(self.data.get("last_chapter", 0), chapter_num)
        # Remove from failed if it was there
        if str(chapter_num) in self.data.get("failed_chapters", {}):
            del self.data["failed_chapters"][str(chapter_num)]
        self.save()

    def mark_failed(self, chapter_num: int, reason: str):
        if "failed_chapters" not in self.data:
            self.data["failed_chapters"] = {}
        self.data["failed_chapters"][str(chapter_num)] = reason
        self.save()


def parse_args():
    parser = argparse.ArgumentParser(
        description="أداة سحب وترجمة رواية Reverend Insanity (القس المجنون) إلى العربية الأدبية الفصحى."
    )
    parser.add_argument(
        "-s", "--start",
        type=int,
        default=None,
        help="رقم فصل البداية (إذا ترك فارغاً مع --auto، يبدأ تلقائياً من آخر فصل غير مكتمل)",
    )
    parser.add_argument(
        "-e", "--end",
        type=int,
        default=None,
        help="رقم فصل النهاية (الافتراضي: 2334 أو start + batch-size)",
    )
    parser.add_argument(
        "-b", "--batch-size",
        type=int,
        default=None,
        help="عدد الفصول المراد معالجتها في هذه الجلسة (مثال: 50 فصل)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="البدء تلقائياً من أول فصل لم يتم إكماله في سجل progress.json",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["fast", "ai"],
        default="fast",
        help="محرك الترجمة: 'fast' (ترجمة جوجل فائقة السرعة مع مصطلحات الرواية) أو 'ai' (ترجمة أدبية عبر نماذج الذكاء الاصطناعي)",
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=2.0,
        help="الفاصل الزمني بالثواني بين كل فصل والآخر (الافتراضي مع المحرك السريع: 2 ثانية)",
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=Config.KILO_MODEL,
        help=f"اسم نموذج الذكاء الاصطناعي على Kilo AI Gateway (الافتراضي: {Config.KILO_MODEL})",
    )
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="سحب الفصول الإنجليزية فقط دون ترجمتها",
    )
    parser.add_argument(
        "--translate-only",
        action="store_true",
        help="ترجمة الفصول المسحوبة مسبقاً من مجلد raw_en دون سحب جديد",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="إعادة معالجة الفصول المكتملة مسبقاً وتجاوز ملف التقدم",
    )
    return parser.parse_args()


def countdown_delay(seconds: float):
    """Visual countdown for delays between chapter requests."""
    if seconds <= 0:
        return
    print(f"  [⏳] استراحة لمدة {int(seconds)} ثانية لتفادي الحظر وتنظيم الطلبات...")
    step = 1
    remaining = int(seconds)
    while remaining > 0:
        sys.stdout.write(f"\r     -> المتبقي: {remaining} ثانية... ")
        sys.stdout.flush()
        time.sleep(step)
        remaining -= step
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def run_pipeline():
    args = parse_args()
    Config.init_directories()

    tracker = ProgressTracker(Config.PROGRESS_FILE)

    # Determine starting chapter
    start_chap = args.start
    if start_chap is None:
        if args.auto or True:
            # Find first uncompleted chapter
            last_done = tracker.data.get("last_chapter", 0)
            start_chap = last_done + 1
        else:
            start_chap = 1

    # Determine ending chapter
    if args.end is not None:
        end_chap = args.end
    elif args.batch_size is not None:
        end_chap = start_chap + args.batch_size - 1
    else:
        end_chap = 2334  # Total chapters of Reverend Insanity

    print("=" * 70)
    print(" 📖 أداة سحب وترجمة رواية Reverend Insanity (القس المجنون)")
    print("=" * 70)
    print(f" • نطاق الفصول: من {start_chap} إلى {end_chap}")
    print(f" • المحرك: {'Google Fast Engine (فائق السرعة مع قاموس الرواية)' if args.engine == 'fast' else f'AI Engine ({args.model})'}")
    print(f" • الفاصل الزمني: {args.delay} ثانية")
    print(f" • مجلد الإخراج: {Config.OUTPUT_DIR.resolve()}")
    print("=" * 70)

    scraper = NovelFireScraper()
    
    if args.engine == "fast":
        from fast_translator import FastGoogleTranslator
        translator = FastGoogleTranslator()
    else:
        translator = KiloTranslator(model=args.model)

    total_chapters = end_chap - start_chap + 1
    success_count = 0
    skipped_count = 0
    failed_count = 0
    start_time = time.time()

    for idx, chapter_num in enumerate(range(start_chap, end_chap + 1), 1):
        raw_file = Config.RAW_EN_DIR / f"chapter_{chapter_num:04d}.txt"
        trans_file = Config.TRANSLATED_AR_DIR / f"chapter_{chapter_num:04d}.txt"

        print(f"\n[{idx}/{total_chapters}] >>> معالجة الفصل {chapter_num} <<<")

        # Check if already completed
        if not args.force and tracker.is_completed(chapter_num) and trans_file.exists():
            print(f"  [✓] الفصل {chapter_num} مكتمل مسبقاً. تم التخطي.")
            skipped_count += 1
            continue

        chapter_title = f"Chapter {chapter_num}"
        paragraphs = []

        # -------------------------------------------------------------
        # STEP 1: SCRAPING / LOADING RAW CHAPTER
        # -------------------------------------------------------------
        if args.translate_only:
            # Read from existing raw file
            if not raw_file.exists():
                print(f"  [!] لم يتم العثور على الملف الإنجليزي للفصل {chapter_num} في {raw_file}")
                tracker.mark_failed(chapter_num, "Raw file not found in translate-only mode")
                failed_count += 1
                continue
            with open(raw_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines and lines[0].startswith("#"):
                    chapter_title = lines[0].replace("#", "").strip()
                    paragraphs = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]
                else:
                    paragraphs = [p.strip() for p in "".join(lines).split("\n\n") if p.strip()]
        else:
            # Scrape from novelfire.net
            print(f"  [1/2] سحب الفصل من novelfire.net...")
            scrape_res = scraper.fetch_chapter(chapter_num, max_retries=Config.MAX_RETRIES)

            if scrape_res.get("status") != "success":
                err_msg = scrape_res.get("error", "فشل السحب")
                print(f"  [X] خطأ أثناء سحب الفصل {chapter_num}: {err_msg}")
                tracker.mark_failed(chapter_num, f"Scrape error: {err_msg}")
                failed_count += 1
                continue

            chapter_title = scrape_res["title"]
            paragraphs = scrape_res["paragraphs"]
            print(f"  [✓] تم سحب العنوان بنجاح: \"{chapter_title}\" ({len(paragraphs)} فقرة)")

            # Save raw English text
            scraper.save_raw_chapter(scrape_res, raw_file)

        # If raw-only mode requested, finish here for this chapter
        if args.raw_only:
            print(f"  [✓] تم حفظ النص الخام للفصل {chapter_num} بنجاح.")
            success_count += 1
            if idx < total_chapters:
                countdown_delay(args.delay)
            continue

        # -------------------------------------------------------------
        # STEP 2: TRANSLATING WITH KILO AI GATEWAY
        # -------------------------------------------------------------
        print(f"  [2/2] إرسال الفصل إلى Kilo AI Gateway للترجمة الأدبية...")
        try:
            trans_res = translator.translate_chapter(chapter_title, paragraphs)
            if trans_res.get("status") == "success":
                translated_text = trans_res["translated_text"]
                translator.save_translated_chapter(
                    chapter_num=chapter_num,
                    title=chapter_title,
                    translated_text=translated_text,
                    filepath=trans_file,
                )
                tracker.mark_completed(chapter_num)
                print(f"  [✨] اكتملت ترجمة الفصل {chapter_num} وتم حفظه في: {trans_file.name}")
                success_count += 1
            else:
                err_msg = trans_res.get("error", "خطأ غير معروف في الترجمة")
                print(f"  [X] فشل في ترجمة الفصل {chapter_num}: {err_msg}")
                tracker.mark_failed(chapter_num, err_msg)
                failed_count += 1
        except Exception as e:
            print(f"  [X] استثناء أثناء ترجمة الفصل {chapter_num}: {e}")
            tracker.mark_failed(chapter_num, str(e))
            failed_count += 1

        # Delay before next chapter
        if idx < total_chapters:
            countdown_delay(args.delay)

    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(" 🎉 اكتملت عملية المعالجة!")
    print("=" * 70)
    print(f" • إجمالي الفصول المحددة: {total_chapters}")
    print(f" • المكتمل بنجاح: {success_count}")
    print(f" • المتخطى (مكتمل مسبقاً): {skipped_count}")
    print(f" • المتعثر/فشل: {failed_count}")
    print(f" • إجمالي الوقت المستغرق: {total_time/60:.2f} دقيقة")
    print(f" • ملفات الترجمة موجودة في: {Config.TRANSLATED_AR_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()
