import re
import time
import argparse
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

from auto_glossary import AutoGlossaryExtractor
from fast_translator import FastGoogleTranslator
from parallel_translator import ParallelNovelTranslator


class UniversalNovelPipeline:
    """
    Universal pipeline to scrape, auto-generate glossary, and translate
    any webnovel from supported sites into Arabic.
    """

    def __init__(self, novel_identifier: str, base_output_dir: Path = Path("novels")):
        # Clean slug (e.g. 'reverend-insanity' or 'shadow-slave' or full URL)
        if novel_identifier.startswith("http"):
            path = urlparse(novel_identifier).path.strip("/")
            parts = path.split("/")
            self.novel_slug = parts[-1] if parts else "novel"
            self.base_url = novel_identifier.rstrip("/")
        else:
            self.novel_slug = novel_identifier.strip().lower().replace(" ", "-")
            self.base_url = f"https://novelfire.net/book/{self.novel_slug}"

        self.novel_dir = base_output_dir / self.novel_slug
        self.raw_dir = self.novel_dir / "raw_en"
        self.trans_dir = self.novel_dir / "translated_ar"
        self.glossary_file = self.novel_dir / "glossary.json"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.trans_dir.mkdir(parents=True, exist_ok=True)

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_chapter(self, chapter_num: int) -> dict:
        """Fetch a single chapter from the novel URL."""
        url = f"{self.base_url}/chapter-{chapter_num}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                return {"status": "error", "error": f"HTTP {resp.status_code}"}

            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Extract title
            title = f"Chapter {chapter_num}"
            title_tag = soup.find("span", class_="chapter-title") or soup.find("h1") or soup.find("h2")
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Extract content
            content_div = soup.find("div", id="chapter-container") or soup.find("div", class_="chapter-content") or soup.find("div", class_="content")
            if not content_div:
                return {"status": "error", "error": "Content container not found"}

            paragraphs = []
            for p in content_div.find_all("p"):
                txt = p.get_text(strip=True)
                if txt and not any(ad in txt.lower() for ad in ["novelfire", "lightnovel", "patreon", "discord"]):
                    paragraphs.append(txt)

            return {
                "status": "success",
                "chapter_num": chapter_num,
                "title": title,
                "paragraphs": paragraphs,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def run_sample_test(self, start: int = 1, end: int = 3):
        """Quick sample run to demonstrate universal scraping and translation."""
        print("=" * 70)
        print(f" 🌐 Universal Novel Pipeline: {self.novel_slug.upper()}")
        print("=" * 70)
        print(f" • المجلد المخصص: {self.novel_dir.resolve()}")
        print(f" • نطاق الفصول: {start} إلى {end}")
        print("=" * 70)

        # 1. Scrape
        for cnum in range(start, end + 1):
            raw_path = self.raw_dir / f"chapter_{cnum:04d}.txt"
            if not raw_path.exists():
                print(f"  [سحب] جاري سحب الفصل {cnum} من {self.novel_slug}...", end="", flush=True)
                res = self.fetch_chapter(cnum)
                if res["status"] == "success":
                    with open(raw_path, "w", encoding="utf-8") as f:
                        f.write(f"# {res['title']}\n\n" + "\n\n".join(res["paragraphs"]))
                    print(f" ✓ ({len(res['paragraphs'])} فقرة)")
                else:
                    print(f" ❌ ({res.get('error')})")
                time.sleep(1.0)

        # 2. Extract Glossary
        extractor = AutoGlossaryExtractor(self.raw_dir)
        glossary = extractor.extract_from_chapters(max_chapters=5, min_occurrences=2)
        extractor.save_glossary(glossary, self.glossary_file)

        # 3. Translate
        translator = FastGoogleTranslator()
        for cnum in range(start, end + 1):
            raw_path = self.raw_dir / f"chapter_{cnum:04d}.txt"
            trans_path = self.trans_dir / f"chapter_{cnum:04d}.txt"
            if raw_path.exists() and not trans_path.exists():
                with open(raw_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                title = lines[0].replace("#", "").strip() if lines else f"Chapter {cnum}"
                paras = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]

                print(f"  [ترجمة] ترجمة الفصل {cnum}...", end="", flush=True)
                t_res = translator.translate_chapter(title, paras)
                if t_res["status"] == "success":
                    translator.save_translated_chapter(cnum, title, t_res["translated_text"], trans_path)
                    print(f" ✨ تم بنجاح!")

        print("\n[✓] اكتمل الاختبار المصغر للرواية العامة بنجاح!")


if __name__ == "__main__":
    # Test on a popular novel e.g. 'shadow-slave'
    pipeline = UniversalNovelPipeline(novel_identifier="shadow-slave")
    pipeline.run_sample_test(start=1, end=2)
