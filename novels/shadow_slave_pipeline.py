"""
🛡️ Shadow Slave (عبد الظل) - Full Translation & Automation Pipeline
====================================================================
End-to-end scraper, terminology builder, and parallel translator for
Shadow Slave by Guiltythree.

Usage:
  python novels/shadow_slave_pipeline.py --start 1 --end 50 --workers 10
  python novels/shadow_slave_pipeline.py --extract-glossary
  python novels/shadow_slave_pipeline.py --compile
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from novels.shadow_slave_glossary import ShadowSlaveGlossary, SHADOW_SLAVE_CANON_GLOSSARY


VOLUME_RANGES = [
    (1, 350, "Volume_1 (Forgotten Shore - Chapters 0001 - 0350)"),
    (351, 600, "Volume_2 (Chained Isles - Chapters 0351 - 0600)"),
    (601, 750, "Volume_3 (Second Nightmare - Chapters 0601 - 0750)"),
    (751, 1200, "Volume_4 (Antarctica - Chapters 0751 - 1200)"),
    (1201, 1600, "Volume_5 (Third Nightmare - Chapters 1201 - 1600)"),
    (1601, 2500, "Volume_6 (War of the Domains - Chapters 1601+)"),
]


def get_volume_dir(base_dir: Path, chapter_num: int) -> Path:
    for s, e, name in VOLUME_RANGES:
        if s <= chapter_num <= e:
            target = base_dir / name
            target.mkdir(parents=True, exist_ok=True)
            return target
    target = base_dir / "Volume_Other"
    target.mkdir(parents=True, exist_ok=True)
    return target


class ShadowSlavePipeline:
    """
    Dedicated parallel pipeline for Shadow Slave.
    """

    NOVEL_URL = "https://novelfire.net/book/shadow-slave"

    def __init__(self, output_dir: Path = Path("novels/shadow-slave")):
        self.novel_dir = output_dir
        self.raw_dir = output_dir / "raw_en"
        self.trans_dir = output_dir / "translated_ar"
        self.glossary_file = output_dir / "glossary.json"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.trans_dir.mkdir(parents=True, exist_ok=True)

        # Load glossary
        self.glossary_builder = ShadowSlaveGlossary(output_dir)
        self.glossary = self.glossary_builder.scan_chapters()
        self.glossary_sorted = sorted(
            self.glossary.items(), key=lambda x: len(x[0]), reverse=True
        )

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_chapter(self, chapter_num: int, max_retries: int = 4) -> Dict[str, Any]:
        """Fetch raw chapter from NovelFire."""
        url = f"{self.NOVEL_URL}/chapter-{chapter_num}"

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(url, headers=self.headers, timeout=20)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    title_tag = (
                        soup.find("span", class_="chapter-title")
                        or soup.find("h1")
                        or soup.find("h2")
                    )
                    title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_num}"

                    content_div = (
                        soup.find("div", id="chapter-container")
                        or soup.find("div", class_="chapter-content")
                        or soup.find("div", class_="content")
                    )
                    if not content_div:
                        return {"status": "error", "error": "Content container missing"}

                    paragraphs = []
                    for p in content_div.find_all("p"):
                        txt = p.get_text(strip=True)
                        if txt and not any(
                            ad in txt.lower()
                            for ad in ["novelfire", "patreon", "discord", "lightnovelpub"]
                        ):
                            paragraphs.append(txt)

                    return {
                        "status": "success",
                        "chapter": chapter_num,
                        "title": title,
                        "paragraphs": paragraphs,
                    }
                elif resp.status_code == 404:
                    return {"status": "not_found", "chapter": chapter_num}
                else:
                    time.sleep(1.5 * attempt)
            except Exception as e:
                time.sleep(2.0 * attempt)

        return {"status": "error", "chapter": chapter_num, "error": "Max retries exceeded"}

    def translate_text_block(self, text: str) -> str:
        """Translate a single block using Google Translate GTX endpoint."""
        if not text.strip():
            return ""
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ar&dt=t&q="
                + urllib.parse.quote(text)
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"
                },
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                translated = "".join([s[0] for s in res_json[0] if s and s[0]])
                return translated
        except Exception:
            return text

    def apply_glossary(self, text: str) -> str:
        """Apply Shadow Slave glossary terms."""
        out = text
        for en_term, ar_term in self.glossary_sorted:
            if en_term in out:
                out = out.replace(en_term, ar_term)
        return out

    def process_chapter(self, chapter_num: int) -> Dict[str, Any]:
        """Scrape raw if missing, translate, and save in volume directory."""
        vol_raw_dir = get_volume_dir(self.raw_dir, chapter_num)
        vol_trans_dir = get_volume_dir(self.trans_dir, chapter_num)

        raw_file = vol_raw_dir / f"chapter_{chapter_num:04d}.txt"
        trans_file = vol_trans_dir / f"chapter_{chapter_num:04d}.txt"

        # Check if already translated
        if trans_file.exists() and trans_file.stat().st_size > 100:
            return {"chapter": chapter_num, "status": "already_translated"}

        # 1. Scrape raw if missing
        paragraphs = []
        title = f"Chapter {chapter_num}"
        if raw_file.exists():
            with open(raw_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if lines:
                title = lines[0].replace("#", "").strip()
                paragraphs = [
                    p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()
                ]
        else:
            res = self.fetch_chapter(chapter_num)
            if res["status"] != "success":
                return res
            title = res["title"]
            paragraphs = res["paragraphs"]
            # Save raw
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n" + "\n\n".join(paragraphs) + "\n")

        if not paragraphs:
            return {"chapter": chapter_num, "status": "error", "error": "Empty paragraphs"}

        # 2. Translate in chunks of 5 paragraphs
        translated_paragraphs = []
        batch_size = 5
        for i in range(0, len(paragraphs), batch_size):
            chunk = paragraphs[i : i + batch_size]
            combined = "\n\n".join(chunk)
            t_chunk = self.translate_text_block(combined)
            for p in t_chunk.split("\n\n"):
                p_clean = p.strip()
                if p_clean:
                    p_clean = self.apply_glossary(p_clean)
                    translated_paragraphs.append(p_clean)

        # Translate Title
        clean_title_en = re.sub(
            r"^(?:Chapter\s*\d+\s*-\s*\d+:\s*)?", "", title, flags=re.IGNORECASE
        ).strip()
        trans_title = self.translate_text_block(clean_title_en)
        trans_title = self.apply_glossary(trans_title)

        final_text = (
            f"# الفصل {chapter_num}: {trans_title}\n\n"
            + "\n\n".join(translated_paragraphs)
            + "\n"
        )
        with open(trans_file, "w", encoding="utf-8") as f:
            f.write(final_text)

        return {
            "chapter": chapter_num,
            "status": "success",
            "paragraphs": len(translated_paragraphs),
        }

    def run_parallel_pipeline(self, start: int, end: int, max_workers: int = 10):
        """Run scraping and translation across multiple chapters in parallel."""
        print("=" * 80)
        print(" 🛡️ خط إنتاج وترجمة رواية عبد الظل (Shadow Slave) فائق السرعة")
        print("=" * 80)
        print(f" • نطاق الفصول: من الفصل {start} إلى الفصل {end} ({end - start + 1} فصل)")
        print(f" • المسارات المتوازية (Threads): {max_workers}")
        print(f" • المجلد المخصص: {self.novel_dir.resolve()}")
        print("=" * 80)

        t0 = time.time()
        chapters = list(range(start, end + 1))
        success_count = 0
        skipped_count = 0
        error_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self.process_chapter, c): c for c in chapters
            }
            done = 0
            for future in as_completed(future_map):
                done += 1
                res = future.result()
                cnum = res.get("chapter")
                status = res.get("status")

                if status == "success":
                    success_count += 1
                    print(f"  [✓ تم الترجمة] الفصل {cnum:>4} ({res.get('paragraphs')} فقرة)")
                elif status == "already_translated":
                    skipped_count += 1
                else:
                    error_count += 1
                    print(f"  [❌ فشل] الفصل {cnum:>4}: {res.get('error')}")

                if done % 20 == 0 or done == len(chapters):
                    elapsed = time.time() - t0
                    print(f"   ⏳ تقدم: {done}/{len(chapters)} ({done/len(chapters)*100:.0f}%) | {elapsed:.1f}ث")

        elapsed_total = time.time() - t0

        # Update glossary with new terms
        self.glossary_builder.scan_chapters()
        self.glossary_builder.save()

        print("\n" + "=" * 80)
        print(" 🏆 ملخص تشغيل خط عبد الظل (Shadow Slave):")
        print("=" * 80)
        print(f" • الفصول المترجمة حديثاً: {success_count}")
        print(f" • الفصول المترجمة مسبقاً (مكتملة): {skipped_count}")
        print(f" • الأخطاء: {error_count}")
        print(f" • الزمن الكلي: {elapsed_total:.1f} ثانية")
        print("=" * 80)

    def compile_master(self) -> Path:
        """Compile all translated chapters into a single master markdown book."""
        master_file = self.novel_dir / "Shadow_Slave_Arabic_Complete.md"
        print(f"[Compiler] جاري تجميع كافة فصول رواية عبد الظل...")

        files = sorted(
            list(self.trans_dir.rglob("chapter_*.txt")),
            key=lambda x: int(re.search(r"chapter_(\d+)", x.name).group(1))
            if re.search(r"chapter_(\d+)", x.name)
            else 0,
        )

        with open(master_file, "w", encoding="utf-8") as out:
            out.write("# 🛡️ رواية عبد الظل (Shadow Slave) - الترجمة العربية الكاملة\n\n")
            out.write(f"- **المؤلف:** Guiltythree\n")
            out.write(f"- **إجمالي الفصول المترجمة المجمعة:** {len(files)} فصلاً\n\n")
            out.write("---\n\n")

            for f in files:
                with open(f, "r", encoding="utf-8") as cfile:
                    text = cfile.read().strip()
                out.write(text + "\n\n---\n\n")

        print(f"[✓] تم إنشاء الكتاب الموحد بنجاح: {master_file.resolve()} ({len(files)} فصل)")
        return master_file


def main():
    parser = argparse.ArgumentParser(description="Shadow Slave Translation Pipeline")
    parser.add_argument("--start", type=int, default=1, help="Start chapter number")
    parser.add_argument("--end", type=int, default=10, help="End chapter number")
    parser.add_argument("--workers", type=int, default=10, help="Parallel workers count")
    parser.add_argument("--extract-glossary", action="store_true", help="Extract glossary only")
    parser.add_argument("--compile", action="store_true", help="Compile master book only")

    args = parser.parse_args()
    pipeline = ShadowSlavePipeline()

    if args.extract_glossary:
        pipeline.glossary_builder.scan_chapters()
        pipeline.glossary_builder.save()
    elif args.compile:
        pipeline.compile_master()
    else:
        pipeline.run_parallel_pipeline(start=args.start, end=args.end, max_workers=args.workers)
        pipeline.compile_master()


if __name__ == "__main__":
    main()
