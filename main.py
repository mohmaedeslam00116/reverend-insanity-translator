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
        "--scrape-all-first",
        action="store_true",
        default=True,
        help="سحب جميع الفصول الإنجليزية أولاً مع فاصل زمني آمن ثم بدء ترجمتها بالكامل دفعة واحدة",
    )
    parser.add_argument(
        "--scrape-delay",
        type=float,
        default=1.5,
        help="الفاصل الزمني بالثواني بين سحب كل فصل لتفادي حظر الموقع (الافتراضي: 1.5 ثانية)",
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


def run_pipeline():
    args = parse_args()
    Config.init_directories()

    tracker = ProgressTracker(Config.PROGRESS_FILE)

    # Determine starting chapter
    start_chap = args.start if args.start is not None else 1

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
    print(f" • تأخير السحب: {args.scrape_delay} ثانية")
    print(f" • تأخير الترجمة: {args.delay} ثانية")
    print(f" • مجلد الإخراج: {Config.OUTPUT_DIR.resolve()}")
    print("=" * 70)

    scraper = NovelFireScraper()

    if args.engine == "fast":
        from fast_translator import FastGoogleTranslator
        translator = FastGoogleTranslator()
    else:
        translator = KiloTranslator(model=args.model)

    # =========================================================================
    # PHASE 1: SCRAPING ALL CHAPTERS FIRST (سحب جميع الفصول الإنجليزية أولاً)
    # =========================================================================
    if not args.translate_only:
        print("\n" + "=" * 70)
        print(" 📥 [المرحلة الأولى] سحب الفصول الإنجليزية من novelfire.net")
        print("=" * 70)

        for chapter_num in range(start_chap, end_chap + 1):
            raw_file = Config.RAW_EN_DIR / f"chapter_{chapter_num:04d}.txt"
            if raw_file.exists() and not args.force:
                continue

            print(f"  [سحب] جاري سحب الفصل {chapter_num}/{end_chap}...", end="", flush=True)
            scrape_res = scraper.fetch_chapter(chapter_num, max_retries=Config.MAX_RETRIES)

            if scrape_res.get("status") == "success":
                scraper.save_raw_chapter(scrape_res, raw_file)
                p_cnt = scrape_res.get("paragraph_count", 0)
                print(f" ✓ ({p_cnt} فقرة)")
            else:
                err = scrape_res.get("error", "خطأ")
                print(f" ❌ ({err})")

            # Polite delay between scrapes
            time.sleep(args.scrape_delay)

        print("\n[✓] اكتملت مرحلة سحب الفصول الإنجليزية بالكامل!\n")

    if args.raw_only:
        print("تم الانتهاء من وضع السحب فقط (--raw-only).")
        return

    # =========================================================================
    # PHASE 2: TRANSLATING ALL SCRAPED CHAPTERS (ترجمة الفصول المسحوبة بالكامل)
    # =========================================================================
    print("=" * 70)
    print(" 🌐 [المرحلة الثانية] ترجمة الفصول وحفظها بالعربية الفصحى")
    print("=" * 70)

    total_chapters = end_chap - start_chap + 1
    success_count = 0
    skipped_count = 0
    failed_count = 0
    start_time = time.time()

    for idx, chapter_num in enumerate(range(start_chap, end_chap + 1), 1):
        raw_file = Config.RAW_EN_DIR / f"chapter_{chapter_num:04d}.txt"
        trans_file = Config.TRANSLATED_AR_DIR / f"chapter_{chapter_num:04d}.txt"

        if not args.force and tracker.is_completed(chapter_num) and trans_file.exists():
            skipped_count += 1
            continue

        if not raw_file.exists():
            print(f"[{idx}/{total_chapters}] [!] تخطي الفصل {chapter_num} (الملف الإنجليزي غير موجود)")
            failed_count += 1
            continue

        # Load raw file
        with open(raw_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines and lines[0].startswith("#"):
                chapter_title = lines[0].replace("#", "").strip()
                paragraphs = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]
            else:
                chapter_title = f"Chapter {chapter_num}"
                paragraphs = [p.strip() for p in "".join(lines).split("\n\n") if p.strip()]

        print(f"[{idx}/{total_chapters}] ✍️ ترجمة الفصل {chapter_num} (\"{chapter_title}\" - {len(paragraphs)} فقرة)...", end="", flush=True)

        try:
            t_start = time.time()
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
                t_dur = time.time() - t_start
                print(f" ✨ تم في {t_dur:.1f}ث")
                success_count += 1
            else:
                err = trans_res.get("error", "فشل")
                print(f" ❌ ({err})")
                failed_count += 1
        except Exception as e:
            print(f" ❌ (استثناء: {e})")
            failed_count += 1

        if args.delay > 0:
            time.sleep(args.delay)

    # Compile the book
    try:
        from compile_novel import compile_translated_chapters
        compile_translated_chapters()
    except Exception as e:
        print(f"[Compiler] تحذير أثناء تجميع الكتاب: {e}")

    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(" 🎉 اكتملت العملية بالكامل!")
    print("=" * 70)
    print(f" • إجمالي الفصول المحددة: {total_chapters}")
    print(f" • المكتمل بنجاح: {success_count}")
    print(f" • المتخطى (مكتمل مسبقاً): {skipped_count}")
    print(f" • المتعثر/فشل: {failed_count}")
    print(f" • إجمالي الوقت المستغرق: {total_time/60:.2f} دقيقة")
    print(f" • المخرجات في: {Config.TRANSLATED_AR_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()

