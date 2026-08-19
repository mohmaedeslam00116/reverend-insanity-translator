"""
💎 Gemini Flash Lite Multi-Key Novel Translator (مترجم جيميني الروائي متعدد المفاتيح)
=================================================================================
Ultra-high quality literary novel translator powered by Google Gemini Flash Lite
with Multi-Key Round-Robin Rotation and automatic rate-limit failover.
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


class GeminiKeyPool:
    """
    Manages a pool of Gemini API keys with automatic round-robin rotation
    and cooldown tracking for rate-limited keys.
    """

    def __init__(self, api_keys: List[str]):
        # Filter empty keys
        self.keys = [k.strip() for k in api_keys if k and k.strip()]
        if not self.keys:
            # Fallback to env var or config
            env_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEYS", "")
            if env_key:
                self.keys = [k.strip() for k in env_key.replace(",", " ").split() if k.strip()]

        self.current_idx = 0
        self.cooldowns: Dict[str, float] = {}

    def get_key(self) -> str:
        """Get next available key that is not in cooldown."""
        if not self.keys:
            raise ValueError("No Gemini API keys provided! Please provide at least one key.")

        now = time.time()
        for _ in range(len(self.keys)):
            key = self.keys[self.current_idx]
            self.current_idx = (self.current_idx + 1) % len(self.keys)
            cooldown_until = self.cooldowns.get(key, 0)
            if now >= cooldown_until:
                return key

        # If all in cooldown, wait for the one with shortest remaining time
        min_key = min(self.cooldowns, key=self.cooldowns.get)
        wait_time = max(1.0, self.cooldowns[min_key] - now)
        print(f"[GeminiPool] ⏳ جميع المفاتيح في فترة التهدئة، انتظر {wait_time:.1f}ث...", flush=True)
        time.sleep(wait_time)
        return min_key

    def mark_rate_limited(self, key: str, cooldown_seconds: float = 60.0):
        """Mark key as rate-limited for specified duration."""
        self.cooldowns[key] = time.time() + cooldown_seconds
        print(f"[GeminiPool] ⚠️ تم تحويل المفتاح (...{key[-6:]}) لفترة راحة لمدة {cooldown_seconds}ث.", flush=True)


class GeminiTranslator:
    """
    Communicates directly with Google Gemini REST API.
    """

    SUPPORTED_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    def __init__(self, key_pool: GeminiKeyPool, model: str = "gemini-2.5-flash"):
        self.key_pool = key_pool
        self.model = model

    def translate_chapter(
        self,
        chapter_num: int,
        title_en: str,
        paragraphs: List[str],
        glossary: Dict[str, str],
        novel_title: str = "Reverend Insanity",
        max_retries: int = 5,
    ) -> Dict[str, Any]:
        """Translate a single chapter using Gemini with literary prompting."""
        full_text = "\n\n".join(paragraphs)

        # Match relevant glossary terms
        relevant_terms = {}
        for en, ar in glossary.items():
            if re.search(rf"\b{re.escape(en)}\b", full_text, re.IGNORECASE):
                relevant_terms[en] = ar

        glossary_prompt = ""
        if relevant_terms:
            glossary_prompt = (
                "\n\n[قاموس المصطلحات والشخصيات المعتمد - التزم به بدقة]:\n"
                + "\n".join([f"- {k}: {v}" for k, v in list(relevant_terms.items())[:60]])
            )

        system_instruction = (
            "أنت مترجم ومحرر أدبي عبقري متخصص في ترجمة روايات الفانتازيا والـ Xianxia العالمية إلى اللغة العربية الفصحى الراقية والجزلة.\n"
            "مهمتك: ترجمة الفصل المرفق ترجمة روائية أدبية بليغة.\n"
            "القواعد الصارمة:\n"
            "1. السرد الروائي الفخم وتفادي الترجمة الحرفية الجافة.\n"
            "2. الحفاظ على نبرة الشخصيات وهيبة المشاهد الحماسية والحوارات والأشعار.\n"
            "3. الالتزام التام بالقاموس المرفق للأسماء والمصطلحات دون أي تغيير.\n"
            "4. أعد النص المترجم كاملاً مع عنوان الفصل في البداية (# الفصل X: العنوان) دون أي مقدمات أو تعليقات أو شروحات إضافية."
        )

        user_content = (
            f"رواية: {novel_title}\n"
            f"الفصل: {chapter_num}\n"
            f"العنوان الأصلي: {title_en}\n"
            f"{glossary_prompt}\n\n"
            f"[نص الفصل الأصلي]:\n{full_text}"
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_content}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 8192,
            },
        }

        for attempt in range(1, max_retries + 1):
            key = self.key_pool.get_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={key}"

            try:
                resp = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=60,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0]["content"]["parts"][0]["text"].strip()
                        content = re.sub(r"^```(?:markdown)?\s*", "", content)
                        content = re.sub(r"\s*```$", "", content)
                        return {"status": "success", "text": content}
                elif resp.status_code == 429:
                    self.key_pool.mark_rate_limited(key, cooldown_seconds=45.0)
                    time.sleep(1.0)
                elif resp.status_code == 404:
                    # Model not found on v1beta, try fallback model
                    if self.model != "gemini-2.0-flash":
                        self.model = "gemini-2.0-flash"
                    elif self.model != "gemini-1.5-flash":
                        self.model = "gemini-1.5-flash"
                else:
                    time.sleep(2.0 * attempt)
            except Exception as e:
                time.sleep(2.0 * attempt)

        return {"status": "error", "error": f"Failed after {max_retries} attempts"}


class GeminiNovelPipeline:
    """Universal pipeline linking scraper, glossary, multi-key pool, and book compiler."""

    def __init__(
        self,
        novel_slug: str,
        api_keys: List[str],
        model: str = "gemini-2.0-flash-lite-preview-02-05",
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

        self.key_pool = GeminiKeyPool(api_keys)
        self.translator = GeminiTranslator(self.key_pool, model=model)
        self.glossary = self._load_glossary()

    def _load_glossary(self) -> Dict[str, str]:
        if self.glossary_file.exists():
            try:
                with open(self.glossary_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        if self.novel_slug == "reverend-insanity" and Path("glossary.json").exists():
            try:
                with open("glossary.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _find_raw_chapter(self, chapter_num: int) -> Optional[Dict[str, Any]]:
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
                paras = [line.strip() for line in "".join(lines[1:]).split("\n\n") if line.strip()]
                return {"title": title, "paragraphs": paras}
            elif p.is_dir():
                matches = list(p.rglob(f"chapter_{chapter_num:04d}.txt"))
                if matches and matches[0].stat().st_size > 50:
                    with open(matches[0], "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    title = lines[0].replace("#", "").strip() if lines else f"Chapter {chapter_num}"
                    paras = [line.strip() for line in "".join(lines[1:]).split("\n\n") if line.strip()]
                    return {"title": title, "paragraphs": paras}

        # Scrape
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
        res = self.translator.translate_chapter(
            chapter_num=chapter_num,
            title_en=raw_data["title"],
            paragraphs=raw_data["paragraphs"],
            glossary=self.glossary,
            novel_title=self.novel_slug.replace("-", " ").title(),
        )

        if res["status"] == "success":
            text = res["text"]
            if not text.startswith("#"):
                text = f"# الفصل {chapter_num}: {raw_data['title']}\n\n" + text
            with open(trans_file, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            elapsed = time.time() - t0
            return {"chapter": chapter_num, "status": "success", "elapsed": elapsed}
        else:
            return {"chapter": chapter_num, "status": "error", "error": res.get("error")}

    def run_parallel(self, start: int, end: int, workers: int = 5):
        print("=" * 80, flush=True)
        print(f" 💎 خط إنتاج وترجمة Gemini Flash Lite الأدبي: [{self.novel_slug.upper()}]", flush=True)
        print("=" * 80, flush=True)
        print(f" • النموذج: {self.translator.model}", flush=True)
        print(f" • عدد المفاتيح المتاحة في المجمع (Key Pool): {len(self.key_pool.keys)} مفتاحاً", flush=True)
        print(f" • النطاق: من الفصل {start} إلى الفصل {end} ({end - start + 1} فصل)", flush=True)
        print(f" • المسارات المتوازية: {workers}", flush=True)
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
                    print(f"  [💎 ترجمة أدبية فائقة] الفصل {cnum:>4} (استغرق {res.get('elapsed', 0):.1f}ث)", flush=True)
                elif status == "already_done":
                    skipped_count += 1
                else:
                    error_count += 1
                    print(f"  [❌ فشل] الفصل {cnum:>4}: {res.get('error')}", flush=True)

        elapsed_total = time.time() - t_start
        print("\n" + "=" * 80, flush=True)
        print(f" 🏆 ملخص إنتاج Gemini Flash Lite: {success_count} فصل مصقول في {elapsed_total:.1f} ثانية ({elapsed_total/60:.1f} دقيقة)", flush=True)
        print("=" * 80, flush=True)

    def compile_master(self) -> Path:
        master_file = self.novel_dir / f"{self.novel_slug}_Gemini_Literary_Complete.md"
        files = sorted(
            list(self.trans_dir.glob("chapter_*.txt")),
            key=lambda x: int(re.search(r"chapter_(\d+)", x.name).group(1))
            if re.search(r"chapter_(\d+)", x.name)
            else 0,
        )
        if not files:
            return master_file

        with open(master_file, "w", encoding="utf-8") as out:
            out.write(f"# 💎 رواية {self.novel_slug.replace('-', ' ').title()} - الترجمة الأدبية الفاخرة (Gemini)\n\n")
            out.write(f"- **إجمالي الفصول المترجمة:** {len(files)} فصلاً\n\n---\n\n")
            for f in files:
                with open(f, "r", encoding="utf-8") as cf:
                    out.write(cf.read().strip() + "\n\n---\n\n")

        print(f"[Master] تم تجميع الكتاب الأدبي الكامل: {master_file.resolve()} ({len(files)} فصل)", flush=True)
        return master_file


def main():
    parser = argparse.ArgumentParser(description="Gemini Flash Lite Multi-Key Novel Translator")
    parser.add_argument("--novel", type=str, default="reverend-insanity", help="Novel slug identifier")
    parser.add_argument("--keys", type=str, default="", help="Comma or space-separated Gemini API keys")
    parser.add_argument("--model", type=str, default="gemini-2.0-flash-lite-preview-02-05", help="Gemini model")
    parser.add_argument("--start", type=int, default=1, help="Start chapter")
    parser.add_argument("--end", type=int, default=10, help="End chapter")
    parser.add_argument("--workers", type=int, default=5, help="Parallel worker threads")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing chapters")
    parser.add_argument("--compile", action="store_true", help="Compile master book only")

    args = parser.parse_args()
    key_list = [k.strip() for k in args.keys.replace(",", " ").split() if k.strip()]

    pipeline = GeminiNovelPipeline(
        novel_slug=args.novel,
        api_keys=key_list,
        model=args.model,
        overwrite=args.overwrite,
    )

    if args.compile:
        pipeline.compile_master()
    else:
        pipeline.run_parallel(start=args.start, end=args.end, workers=args.workers)
        pipeline.compile_master()


if __name__ == "__main__":
    main()
