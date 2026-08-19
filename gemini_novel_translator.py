"""
💎 Gemini Flash Lite Multi-Key Novel Translator (مترجم جيميني الروائي متعدد المفاتيح)
=================================================================================
Ultra-high quality literary novel translator powered by Google Gemini 3.5 Flash Lite
with Multi-Key Round-Robin Rotation, auto rate-limit failover, batch commits,
and UNSTOPPABLE error recovery (never crashes, never stops).
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
import urllib.parse
import subprocess
import threading
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
        self.keys = [k.strip() for k in api_keys if k and k.strip()]
        if not self.keys:
            env_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEYS", "")
            if env_key:
                self.keys = [k.strip() for k in env_key.replace(",", " ").split() if k.strip()]

        self.current_idx = 0
        self.cooldowns: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get_key(self) -> str:
        """Get next available key that is not in cooldown (thread-safe)."""
        if not self.keys:
            raise ValueError("No Gemini API keys provided!")

        with self._lock:
            now = time.time()
            for _ in range(len(self.keys)):
                key = self.keys[self.current_idx]
                self.current_idx = (self.current_idx + 1) % len(self.keys)
                cooldown_until = self.cooldowns.get(key, 0)
                if now >= cooldown_until:
                    return key

            # All in cooldown - find shortest wait
            min_key = min(self.cooldowns, key=self.cooldowns.get)
            wait_time = max(1.0, self.cooldowns[min_key] - now)

        print(f"[KeyPool] All keys cooling down, waiting {wait_time:.0f}s...", flush=True)
        time.sleep(wait_time)
        return min_key

    def mark_rate_limited(self, key: str, cooldown_seconds: float = 30.0):
        """Mark key as rate-limited for specified duration."""
        with self._lock:
            self.cooldowns[key] = time.time() + cooldown_seconds


class GeminiTranslator:
    """
    Communicates directly with Google Gemini REST API.
    Designed to NEVER crash - catches and recovers from every possible error.
    """

    def __init__(self, key_pool: GeminiKeyPool, model: str = "gemini-3.5-flash-lite"):
        self.key_pool = key_pool
        self.model = model

    def translate_chapter(
        self,
        chapter_num: int,
        title_en: str,
        paragraphs: List[str],
        glossary: Dict[str, str],
        novel_title: str = "Reverend Insanity",
        max_retries: int = 10,
    ) -> Dict[str, Any]:
        """Translate a single chapter. Retries up to 10 times with exponential backoff."""
        try:
            full_text = "\n\n".join(paragraphs)
        except Exception:
            return {"status": "error", "error": "Bad paragraph data"}

        # Match relevant glossary terms
        relevant_terms = {}
        try:
            for en, ar in glossary.items():
                if re.search(rf"\b{re.escape(en)}\b", full_text, re.IGNORECASE):
                    relevant_terms[en] = ar
        except Exception:
            pass

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

        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                key = self.key_pool.get_key()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={key}"

                resp = requests.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=90,
                )

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates and candidates[0].get("content"):
                            content = candidates[0]["content"]["parts"][0]["text"].strip()
                            content = re.sub(r"^```(?:markdown)?\s*", "", content)
                            content = re.sub(r"\s*```$", "", content)
                            if len(content) > 50:
                                return {"status": "success", "text": content}
                            else:
                                last_error = "Empty/short response"
                        else:
                            # Safety filter or empty response
                            last_error = f"No candidates: {str(data.get('promptFeedback', ''))[:80]}"
                    except Exception as e:
                        last_error = f"Parse error: {e}"

                elif resp.status_code == 429:
                    self.key_pool.mark_rate_limited(key, cooldown_seconds=30.0)
                    last_error = "Rate limited"
                    time.sleep(2.0)
                    continue

                elif resp.status_code == 503 or resp.status_code == 500:
                    last_error = f"Server error {resp.status_code}"
                    time.sleep(3.0 * attempt)
                    continue

                else:
                    last_error = f"HTTP {resp.status_code}"
                    time.sleep(2.0)

            except requests.exceptions.Timeout:
                last_error = "Timeout"
                time.sleep(2.0)
            except requests.exceptions.ConnectionError:
                last_error = "Connection error"
                time.sleep(5.0)
            except Exception as e:
                last_error = str(e)[:80]
                time.sleep(2.0)

        return {"status": "error", "error": f"{last_error} (after {max_retries} retries)"}


class GeminiNovelPipeline:
    """
    Universal pipeline: scraper + glossary + multi-key pool + batch commits.
    NEVER stops on errors. Logs failures and continues to next chapter.
    """

    def __init__(
        self,
        novel_slug: str,
        api_keys: List[str],
        model: str = "gemini-3.5-flash-lite",
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

        # Counters (thread-safe)
        self._lock = threading.Lock()
        self.success_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.failed_chapters: List[int] = []

    def _load_glossary(self) -> Dict[str, str]:
        for path in [self.glossary_file, Path("glossary.json")]:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
        return {}

    def _find_raw_chapter(self, chapter_num: int) -> Optional[Dict[str, Any]]:
        """Find raw chapter locally or scrape it. NEVER crashes."""
        try:
            # Check local files first
            raw_file = self.raw_dir / f"chapter_{chapter_num:04d}.txt"
            if raw_file.is_file() and raw_file.stat().st_size > 50:
                with open(raw_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                title = lines[0].replace("#", "").strip() if lines else f"Chapter {chapter_num}"
                paras = [line.strip() for line in "".join(lines[1:]).split("\n\n") if line.strip()]
                if paras:
                    return {"title": title, "paragraphs": paras}

            # Check output/raw_en
            alt_file = Path("output/raw_en") / f"chapter_{chapter_num:04d}.txt"
            if alt_file.is_file() and alt_file.stat().st_size > 50:
                with open(alt_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                title = lines[0].replace("#", "").strip() if lines else f"Chapter {chapter_num}"
                paras = [line.strip() for line in "".join(lines[1:]).split("\n\n") if line.strip()]
                if paras:
                    return {"title": title, "paragraphs": paras}
        except Exception:
            pass

        # Scrape from web with retries
        for scrape_attempt in range(3):
            try:
                url = f"https://novelfire.net/book/{self.novel_slug}/chapter-{chapter_num}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
                    "Referer": f"https://novelfire.net/book/{self.novel_slug}",
                    "Accept": "text/html,application/xhtml+xml",
                    "Connection": "keep-alive",
                }
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.find("span", class_="chapter-title") or soup.find("h1")
                title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_num}"
                content_div = soup.find("div", id="chapter-container") or soup.find("div", class_="chapter-content")
                paras = [p.get_text(strip=True) for p in content_div.find_all("p")] if content_div else []

                if paras:
                    raw_path = self.raw_dir / f"chapter_{chapter_num:04d}.txt"
                    with open(raw_path, "w", encoding="utf-8") as f:
                        f.write(f"# {title}\n\n" + "\n\n".join(paras) + "\n")
                    return {"title": title, "paragraphs": paras}
            except Exception:
                time.sleep(2.0 * (scrape_attempt + 1))

        return None

    def process_chapter(self, chapter_num: int) -> Dict[str, Any]:
        """Process a single chapter. NEVER raises exceptions."""
        try:
            trans_file = self.trans_dir / f"chapter_{chapter_num:04d}.txt"
            if trans_file.exists() and trans_file.stat().st_size > 100 and not self.overwrite:
                with self._lock:
                    self.skipped_count += 1
                return {"chapter": chapter_num, "status": "already_done"}

            raw_data = self._find_raw_chapter(chapter_num)
            if not raw_data or not raw_data.get("paragraphs"):
                with self._lock:
                    self.error_count += 1
                    self.failed_chapters.append(chapter_num)
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
                with self._lock:
                    self.success_count += 1
                return {"chapter": chapter_num, "status": "success", "elapsed": elapsed}
            else:
                with self._lock:
                    self.error_count += 1
                    self.failed_chapters.append(chapter_num)
                return {"chapter": chapter_num, "status": "error", "error": res.get("error")}

        except Exception as e:
            with self._lock:
                self.error_count += 1
                self.failed_chapters.append(chapter_num)
            return {"chapter": chapter_num, "status": "error", "error": str(e)[:80]}

    def _git_commit_batch(self, batch_label: str):
        """Commit and push current progress. NEVER crashes."""
        try:
            subprocess.run(["git", "add", f"novels/{self.novel_slug}/"], capture_output=True, timeout=30)
            result = subprocess.run(
                ["git", "diff", "--staged", "--quiet"], capture_output=True, timeout=10
            )
            if result.returncode != 0:
                subprocess.run(
                    ["git", "commit", "-m",
                     f"feat(gemini): {batch_label} for {self.novel_slug} [skip ci]"],
                    capture_output=True, timeout=30
                )
                for push_attempt in range(3):
                    r = subprocess.run(
                        ["git", "push", "origin", "main"], capture_output=True, timeout=60
                    )
                    if r.returncode == 0:
                        print(f"  [GIT] Batch saved & pushed: {batch_label}", flush=True)
                        return
                    subprocess.run(["git", "pull", "--rebase", "origin", "main"], capture_output=True, timeout=60)
                print(f"  [GIT] Committed locally: {batch_label} (push pending)", flush=True)
        except Exception as e:
            print(f"  [GIT] Commit skipped: {e}", flush=True)

    def run_batch_translation(self, start: int, end: int, workers: int = 5, batch_size: int = 100):
        """
        Translate chapters in sequential batches with periodic git commits.
        NEVER stops on errors - logs them and continues.
        """
        print("=" * 80, flush=True)
        print(f" 💎 Gemini 3.5 Flash Lite UNSTOPPABLE Translator: [{self.novel_slug.upper()}]", flush=True)
        print("=" * 80, flush=True)
        print(f" Model:    {self.translator.model}", flush=True)
        print(f" Keys:     {len(self.key_pool.keys)} API keys in rotation pool", flush=True)
        print(f" Range:    Chapter {start} -> {end} ({end - start + 1} chapters)", flush=True)
        print(f" Workers:  {workers} parallel threads", flush=True)
        print(f" Batches:  Every {batch_size} chapters -> auto git commit & push", flush=True)
        print("=" * 80, flush=True)

        t_global = time.time()

        # Process in batches
        for batch_start in range(start, end + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, end)
            chapters = list(range(batch_start, batch_end + 1))
            batch_label = f"chapters {batch_start}-{batch_end}"

            print(f"\n{'─' * 60}", flush=True)
            print(f" 📦 Batch: {batch_label} ({len(chapters)} chapters)", flush=True)
            print(f"{'─' * 60}", flush=True)

            t_batch = time.time()
            batch_success = 0

            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(self.process_chapter, c): c for c in chapters}
                for future in as_completed(future_map):
                    try:
                        res = future.result(timeout=300)
                    except Exception:
                        continue
                    cnum = res.get("chapter", "?")
                    status = res.get("status")

                    if status == "success":
                        batch_success += 1
                        elapsed_ch = res.get("elapsed", 0)
                        print(f"  [OK] Ch.{cnum:>4} ({elapsed_ch:.1f}s) | Total: {self.success_count}/{end - start + 1}", flush=True)
                    elif status == "already_done":
                        pass
                    else:
                        print(f"  [SKIP] Ch.{cnum:>4}: {res.get('error', 'unknown')[:60]}", flush=True)

            batch_elapsed = time.time() - t_batch
            print(f"  Batch done: {batch_success} translated in {batch_elapsed:.0f}s", flush=True)

            # Auto commit & push after each batch
            self._git_commit_batch(batch_label)

        # Final summary
        total_elapsed = time.time() - t_global
        print("\n" + "=" * 80, flush=True)
        print(f" 🏆 TRANSLATION COMPLETE", flush=True)
        print(f"    Translated: {self.success_count} chapters", flush=True)
        print(f"    Skipped:    {self.skipped_count} (already existed)", flush=True)
        print(f"    Failed:     {self.error_count} chapters", flush=True)
        print(f"    Time:       {total_elapsed:.0f}s ({total_elapsed/60:.1f} min / {total_elapsed/3600:.1f} hr)", flush=True)
        if self.failed_chapters:
            print(f"    Failed IDs: {self.failed_chapters[:50]}", flush=True)
        print("=" * 80, flush=True)

        # Save failed chapters list for retry
        if self.failed_chapters:
            fail_file = self.novel_dir / "failed_chapters.json"
            try:
                with open(fail_file, "w") as f:
                    json.dump(sorted(set(self.failed_chapters)), f)
                print(f"  Failed chapters saved to: {fail_file}", flush=True)
            except Exception:
                pass

    def compile_master(self) -> Path:
        """Compile all translated chapters into one master file."""
        master_file = self.novel_dir / f"{self.novel_slug}_Gemini_Literary_Complete.md"
        try:
            files = sorted(
                list(self.trans_dir.glob("chapter_*.txt")),
                key=lambda x: int(re.search(r"chapter_(\d+)", x.name).group(1))
                if re.search(r"chapter_(\d+)", x.name) else 0,
            )
            if not files:
                return master_file

            with open(master_file, "w", encoding="utf-8") as out:
                out.write(f"# رواية {self.novel_slug.replace('-', ' ').title()} - الترجمة الأدبية (Gemini)\n\n")
                out.write(f"- **إجمالي الفصول:** {len(files)} فصلاً\n\n---\n\n")
                for f in files:
                    try:
                        with open(f, "r", encoding="utf-8") as cf:
                            out.write(cf.read().strip() + "\n\n---\n\n")
                    except Exception:
                        pass

            print(f"[Master] Compiled {len(files)} chapters -> {master_file}", flush=True)
        except Exception as e:
            print(f"[Master] Compile error (non-fatal): {e}", flush=True)
        return master_file


def main():
    parser = argparse.ArgumentParser(description="Gemini 3.5 Flash Lite Multi-Key Novel Translator")
    parser.add_argument("--novel", type=str, default="reverend-insanity")
    parser.add_argument("--keys", type=str, default="")
    parser.add_argument("--model", type=str, default="gemini-3.5-flash-lite")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=1900)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--compile", action="store_true")

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
        pipeline.run_batch_translation(
            start=args.start,
            end=args.end,
            workers=args.workers,
            batch_size=args.batch_size,
        )
        pipeline.compile_master()


if __name__ == "__main__":
    main()
