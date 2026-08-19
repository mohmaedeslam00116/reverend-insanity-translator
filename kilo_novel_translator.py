"""
🌟 Kilo AI Literary Novel Translator (مترجم الروايات الأدبي عبر كيلو)
=====================================================================
High-quality literary Arabic novel translator powered by Kilo AI Gateway.
Features:
  - Xianxia & Fantasy literary prompt engineering
  - 500+ Canonical Glossary injection per novel
  - Automatic Raw chapter discovery and scraping
  - ThreadPool concurrency with robust exponential backoff retry
  - Master book compilation & progress checkpointing
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional
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
sys.path.insert(0, str(Path(__file__).parent))
from config import Config


class KiloTranslator:
    """Handles communication with Kilo AI Gateway with retry and literary prompting."""

    def __init__(
        self,
        model: str = "stepfun/step-3.7-flash:free",
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key or Config.KILO_API_KEY
        self.api_url = api_url or Config.KILO_API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://novelfire.net",
            "X-Title": "Literary Novel Arabic Translator",
        }

    def translate_chapter_content(
        self,
        chapter_num: int,
        title_en: str,
        paragraphs: List[str],
        glossary: Dict[str, str],
        novel_title: str = "Reverend Insanity",
        chunk_size: int = 25,
    ) -> Dict[str, Any]:
        """Translate chapter in manageable chunks for ultra-fast response and zero timeouts."""
        # Relevant glossary
        full_text = "\n\n".join(paragraphs)
        relevant_terms = {}
        for en, ar in glossary.items():
            if re.search(rf"\b{re.escape(en)}\b", full_text, re.IGNORECASE):
                relevant_terms[en] = ar

        glossary_prompt = ""
        if relevant_terms:
            glossary_prompt = "\n[قاموس المصطلحات المعتمد - التزم به بدقة]:\n" + "\n".join(
                [f"- {k}: {v}" for k, v in list(relevant_terms.items())[:50]]
            )

        system_instruction = (
            "أنت مترجم ومحرر أدبي عبقري متخصص في ترجمة روايات الفانتازيا والـ Xianxia إلى العربية الفصحى الراقية.\n"
            "مهمتك: ترجمة النص التالي ترجمة روائية أدبية بليغة.\n"
            "قواعد صارمة:\n"
            "1. السرد الروائي الفخم وتفادي الترجمة الحرفية الجافة.\n"
            "2. الالتزام بالقاموس المرفق للأسماء والمصطلحات.\n"
            "3. أعد النص المترجم فقط دون أي مقدمات أو تعليقات."
        )

        translated_chunks = []
        for i in range(0, len(paragraphs), chunk_size):
            chunk = paragraphs[i : i + chunk_size]
            chunk_text = "\n\n".join(chunk)

            user_content = (
                f"رواية: {novel_title} | الفصل: {chapter_num}\n"
                f"{glossary_prompt}\n\n"
                f"[النص الأصلي]:\n{chunk_text}"
            )

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.3,
            }

            for attempt in range(1, 4):
                try:
                    resp = requests.post(
                        self.api_url, headers=self.headers, json=payload, timeout=40
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        c_text = data["choices"][0]["message"]["content"].strip()
                        c_text = re.sub(r"^```(?:markdown)?\s*", "", c_text)
                        c_text = re.sub(r"\s*```$", "", c_text)
                        translated_chunks.append(c_text)
                        break
                    else:
                        time.sleep(2.0 * attempt)
                except Exception:
                    time.sleep(2.0 * attempt)

        if not translated_chunks:
            return {"status": "error", "error": "All chunks failed"}

        final_body = "\n\n".join(translated_chunks)
        return {"status": "success", "text": final_body}


class KiloNovelPipeline:
    """End-to-end pipeline for scraping, translating, and organizing novel chapters."""

    def __init__(
        self,
        novel_slug: str = "reverend-insanity",
        model: str = "stepfun/step-3.7-flash:free",
        overwrite: bool = False,
    ):
        self.novel_slug = novel_slug.strip().lower()
        self.novel_dir = Path("novels") / self.novel_slug
        self.raw_dir = self.novel_dir / "raw_en"
        self.trans_dir = self.novel_dir / "translated_ar"
        self.glossary_file = self.novel_dir / "glossary.json"
        self.overwrite = overwrite

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.trans_dir.mkdir(parents=True, exist_ok=True)

        self.translator = KiloTranslator(model=model)
        self.glossary = self._load_glossary()

    def _load_glossary(self) -> Dict[str, str]:
        # Novel specific glossary
        if self.glossary_file.exists():
            try:
                with open(self.glossary_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Root glossary for reverend-insanity
        if self.novel_slug == "reverend-insanity" and Path("glossary.json").exists():
            try:
                with open("glossary.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _find_raw_chapter(self, chapter_num: int) -> Optional[Dict[str, Any]]:
        """Look for local raw file or scrape from web."""
        # 1. Search locally in novel_dir and output/raw_en
        search_paths = [
            self.raw_dir / f"chapter_{chapter_num:04d}.txt",
            Path("output/raw_en"),
            self.raw_dir,
        ]

        for p in search_paths:
            if p.is_file() and p.stat().st_size > 50:
                with open(p, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                title = lines[0].replace("#", "").strip() if lines else f"Chapter {chapter_num}"
                paras = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]
                return {"title": title, "paragraphs": paras}
            elif p.is_dir():
                matches = list(p.rglob(f"chapter_{chapter_num:04d}.txt"))
                if matches and matches[0].stat().st_size > 50:
                    with open(matches[0], "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    title = lines[0].replace("#", "").strip() if lines else f"Chapter {chapter_num}"
                    paras = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]
                    return {"title": title, "paragraphs": paras}

        # 2. Scrape from NovelFire
        url = f"https://novelfire.net/book/{self.novel_slug}/chapter-{chapter_num}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
            "Referer": f"https://novelfire.net/book/{self.novel_slug}",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                soup = BeautifulSoup(resp.read().decode("utf-8", errors="ignore"), "html.parser")
            title_tag = soup.find("span", class_="chapter-title") or soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_num}"
            content_div = soup.find("div", id="chapter-container") or soup.find("div", class_="chapter-content")
            paras = [p.get_text(strip=True) for p in content_div.find_all("p")] if content_div else []

            # Save locally
            raw_path = self.raw_dir / f"chapter_{chapter_num:04d}.txt"
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n" + "\n\n".join(paras) + "\n")
            return {"title": title, "paragraphs": paras}
        except Exception:
            return None

    def process_chapter(self, chapter_num: int) -> Dict[str, Any]:
        trans_file = self.trans_dir / f"chapter_{chapter_num:04d}.txt"
        if trans_file.exists() and trans_file.stat().st_size > 100 and not self.overwrite:
            return {"chapter": chapter_num, "status": "already_done"}

        raw_data = self._find_raw_chapter(chapter_num)
        if not raw_data or not raw_data["paragraphs"]:
            return {"chapter": chapter_num, "status": "error", "error": "Raw text not found"}

        t0 = time.time()
        res = self.translator.translate_chapter_content(
            chapter_num=chapter_num,
            title_en=raw_data["title"],
            paragraphs=raw_data["paragraphs"],
            glossary=self.glossary,
            novel_title=self.novel_slug.replace("-", " ").title(),
        )

        if res["status"] == "success":
            text = res["text"]
            # Ensure title header exists
            if not text.startswith("#"):
                text = f"# الفصل {chapter_num}: {raw_data['title']}\n\n" + text
            with open(trans_file, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            elapsed = time.time() - t0
            return {"chapter": chapter_num, "status": "success", "elapsed": elapsed}
        else:
            return {"chapter": chapter_num, "status": "error", "error": res.get("error")}

    def run_parallel(self, start: int, end: int, workers: int = 3):
        print("=" * 80, flush=True)
        print(f" 🌟 خط الترجمة الأدبية الاحترافية عبر Kilo AI: [{self.novel_slug.upper()}]", flush=True)
        print("=" * 80, flush=True)
        print(f" • النموذج: {self.translator.model}", flush=True)
        print(f" • النطاق: من الفصل {start} إلى الفصل {end} ({end - start + 1} فصل)", flush=True)
        print(f" • المسارات المتزامنة: {workers}", flush=True)
        print(f" • المجلد: {self.novel_dir.resolve()}", flush=True)
        print("=" * 80, flush=True)

        t_start = time.time()
        chapters = list(range(start, end + 1))
        success_count = 0
        skipped_count = 0
        error_count = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(self.process_chapter, c): c for c in chapters}
            for future in as_completed(future_map):
                res = future.result()
                cnum = res.get("chapter")
                status = res.get("status")

                if status == "success":
                    success_count += 1
                    print(f"  [✨ ترجمة أدبية مكتملة] الفصل {cnum:>4} (استغرق {res.get('elapsed', 0):.1f}ث)", flush=True)
                elif status == "already_done":
                    skipped_count += 1
                else:
                    error_count += 1
                    print(f"  [❌ فشل] الفصل {cnum:>4}: {res.get('error')}", flush=True)

        elapsed_total = time.time() - t_start
        print("\n" + "=" * 80, flush=True)
        print(f" 🏆 ملخص الترجمة الأدبية: {success_count} فصل جديد تم صقله في {elapsed_total:.1f} ثانية ({elapsed_total/60:.1f} دقيقة)", flush=True)
        print("=" * 80, flush=True)

    def compile_master(self) -> Path:
        master_file = self.novel_dir / f"{self.novel_slug}_Literary_Arabic_Complete.md"
        files = sorted(
            list(self.trans_dir.glob("chapter_*.txt")),
            key=lambda x: int(re.search(r"chapter_(\d+)", x.name).group(1))
            if re.search(r"chapter_(\d+)", x.name)
            else 0,
        )
        if not files:
            return master_file

        with open(master_file, "w", encoding="utf-8") as out:
            out.write(f"# 🌟 رواية {self.novel_slug.replace('-', ' ').title()} - الترجمة الأدبية الفاخرة\n\n")
            out.write(f"- **إجمالي الفصول المصقولة أدبياً:** {len(files)} فصلاً\n\n---\n\n")
            for f in files:
                with open(f, "r", encoding="utf-8") as cf:
                    out.write(cf.read().strip() + "\n\n---\n\n")

        print(f"[Master] تم تجميع الكتاب الأدبي الكامل: {master_file.resolve()} ({len(files)} فصل)", flush=True)
        return master_file


def main():
    parser = argparse.ArgumentParser(description="Kilo AI Literary Novel Translator")
    parser.add_argument("--novel", type=str, default="reverend-insanity", help="Novel identifier slug")
    parser.add_argument("--model", type=str, default="stepfun/step-3.7-flash:free", help="Kilo model name")
    parser.add_argument("--start", type=int, default=1, help="Start chapter")
    parser.add_argument("--end", type=int, default=10, help="End chapter")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent worker threads")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing chapters")
    parser.add_argument("--compile", action="store_true", help="Compile master book only")

    args = parser.parse_args()
    pipeline = KiloNovelPipeline(novel_slug=args.novel, model=args.model, overwrite=args.overwrite)

    if args.compile:
        pipeline.compile_master()
    else:
        pipeline.run_parallel(start=args.start, end=args.end, workers=args.workers)
        pipeline.compile_master()


if __name__ == "__main__":
    main()
