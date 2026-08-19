"""
🧠 Neural Novel Translator (محرك الترجمة العصبية المفتوح)
=========================================================
Runs specialized neural machine translation models (Helsinki-NLP/opus-mt-en-ar
and Meta NLLB-200) locally in memory on CPU/GPU with high-speed tensor batching
and automatic glossary injection.
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

from bs4 import BeautifulSoup

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class NeuralEngine:
    """
    In-memory Neural Machine Translation engine using HuggingFace Transformers.
    """

    def __init__(self, model_name: str = "Helsinki-NLP/opus-mt-en-ar", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.tokenizer = None
        self.model = None
        self.is_nllb = "nllb" in model_name.lower()
        self._load_model()

    def _load_model(self):
        print(f"[NeuralEngine] ⏳ جاري تحميل نموذج الترجمة العصبي ({self.model_name})...")
        t0 = time.time()
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        import torch

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)

        if self.device == "cuda" and torch.cuda.is_available():
            self.model = self.model.to("cuda")
            print("[NeuralEngine] 🚀 تم التفعيل على كرت الشاشة (CUDA GPU)!")
        else:
            self.model = self.model.to("cpu")
            print("[NeuralEngine] ⚡ تم التفعيل على المعالج (CPU)!")

        self.model.eval()
        print(f"[NeuralEngine] ✓ تم تجهيز النموذج في {time.time() - t0:.2f} ثانية.")

    def translate_batch(self, texts: List[str], batch_size: int = 16) -> List[str]:
        """Translate a batch of sentences/paragraphs using vectorized tensor batches."""
        if not texts:
            return []

        import torch

        results = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            clean_chunk = [t.strip() if t.strip() else "." for t in chunk]

            try:
                if self.is_nllb:
                    # NLLB-200 specific kwargs
                    inputs = self.tokenizer(
                        clean_chunk,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=512,
                    ).to(self.model.device)
                    # Modern Standard Arabic code in NLLB is arb_Arab
                    forced_bos_token_id = self.tokenizer.convert_tokens_to_ids("arb_Arab")
                    with torch.no_grad():
                        translated_tokens = self.model.generate(
                            **inputs,
                            forced_bos_token_id=forced_bos_token_id,
                            max_length=512,
                            num_beams=2,
                        )
                else:
                    # MarianMT / OPUS-MT
                    inputs = self.tokenizer(
                        clean_chunk,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=512,
                    ).to(self.model.device)
                    with torch.no_grad():
                        translated_tokens = self.model.generate(
                            **inputs,
                            max_length=512,
                            num_beams=2,
                        )

                decoded = self.tokenizer.batch_decode(
                    translated_tokens, skip_special_tokens=True
                )
                results.extend(decoded)
            except Exception as e:
                print(f"[NeuralEngine Error] {e}")
                results.extend(chunk)

        return results


class NovelScraper:
    """Universal robust scraper for webnovels."""

    AD_PATTERNS = [
        re.compile(r"if you find any errors", re.I),
        re.compile(r"please let us know", re.I),
        re.compile(r"ads redirect", re.I),
        re.compile(r"visit novelfire", re.I),
        re.compile(r"patreon\.com", re.I),
        re.compile(r"discord\.gg", re.I),
        re.compile(r"read latest chapters at", re.I),
    ]

    def __init__(self, novel_slug: str):
        self.novel_slug = novel_slug
        self.base_url = f"https://novelfire.net/book/{novel_slug}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.base_url,
        }

    def fetch_chapter(self, chapter_num: int, max_retries: int = 4) -> Dict[str, Any]:
        url = f"{self.base_url}/chapter-{chapter_num}"
        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    charset = resp.headers.get_content_charset() or "utf-8"
                    html = resp.read().decode(charset, errors="ignore")

                soup = BeautifulSoup(html, "html.parser")
                title_tag = soup.find("span", class_="chapter-title") or soup.find("h1") or soup.find("h2")
                title = title_tag.get_text(strip=True) if title_tag else f"Chapter {chapter_num}"

                content_div = (
                    soup.find("div", id="chapter-container")
                    or soup.find("div", class_="chapter-content")
                    or soup.find("div", class_="content")
                )
                if not content_div:
                    return {"status": "error", "error": "Content container not found"}

                paragraphs = []
                for p in content_div.find_all("p"):
                    txt = p.get_text(strip=True)
                    if txt and not any(pat.search(txt) for pat in self.AD_PATTERNS):
                        paragraphs.append(txt)

                return {"status": "success", "chapter": chapter_num, "title": title, "paragraphs": paragraphs}
            except Exception as e:
                time.sleep(1.5 * attempt)

        return {"status": "error", "chapter": chapter_num, "error": "Max retries exceeded"}


class NeuralNovelPipeline:
    """Full pipeline linking Scraper, Neural Engine, Glossary, and Book Builder."""

    def __init__(self, novel_slug: str, model_name: str = "Helsinki-NLP/opus-mt-en-ar"):
        self.novel_slug = novel_slug
        self.novel_dir = Path("novels") / novel_slug
        self.raw_dir = self.novel_dir / "raw_en"
        self.trans_dir = self.novel_dir / "translated_ar"
        self.glossary_file = self.novel_dir / "glossary.json"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.trans_dir.mkdir(parents=True, exist_ok=True)

        self.scraper = NovelScraper(novel_slug)
        self.engine = NeuralEngine(model_name=model_name)
        self.glossary = self._load_glossary()

    def _load_glossary(self) -> Dict[str, str]:
        if self.glossary_file.exists():
            try:
                with open(self.glossary_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def apply_glossary(self, text: str) -> str:
        for en_term, ar_term in sorted(self.glossary.items(), key=lambda x: len(x[0]), reverse=True):
            if en_term in text:
                text = text.replace(en_term, ar_term)
        return text

    def run(self, start: int, end: int, batch_size: int = 16):
        print("=" * 80)
        print(f" 🧠 خط الترجمة العصبية المباشر: رواية [{self.novel_slug.upper()}]")
        print("=" * 80)
        print(f" • النموذج العصبي: {self.engine.model_name}")
        print(f" • النطاق: الفصول من {start} إلى {end}")
        print(f" • حجم دفعة التنسور (Batch Size): {batch_size}")
        print("=" * 80)

        t0 = time.time()
        success_count = 0

        for cnum in range(start, end + 1):
            raw_file = self.raw_dir / f"chapter_{cnum:04d}.txt"
            trans_file = self.trans_dir / f"chapter_{cnum:04d}.txt"

            if trans_file.exists() and trans_file.stat().st_size > 100:
                continue

            # 1. Scrape raw
            paragraphs = []
            title = f"Chapter {cnum}"
            if raw_file.exists():
                with open(raw_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    title = lines[0].replace("#", "").strip()
                    paragraphs = [p.strip() for p in "".join(lines[1:]).split("\n\n") if p.strip()]
            else:
                res = self.scraper.fetch_chapter(cnum)
                if res["status"] != "success":
                    print(f"  [❌ فشل سحب] الفصل {cnum}: {res.get('error')}")
                    continue
                title = res["title"]
                paragraphs = res["paragraphs"]
                with open(raw_file, "w", encoding="utf-8") as f:
                    f.write(f"# {title}\n\n" + "\n\n".join(paragraphs) + "\n")

            if not paragraphs:
                continue

            # 2. Neural Vectorized Batch Translation
            tc0 = time.time()
            trans_paras = self.engine.translate_batch(paragraphs, batch_size=batch_size)
            clean_trans_paras = [self.apply_glossary(p) for p in trans_paras]

            # Translate Title
            clean_title_en = re.sub(r"^(?:Chapter\s*\d+\s*-\s*\d+:\s*)?", "", title, flags=re.I).strip()
            trans_title = self.engine.translate_batch([clean_title_en], batch_size=1)[0]
            trans_title = self.apply_glossary(trans_title)

            final_text = f"# الفصل {cnum}: {trans_title}\n\n" + "\n\n".join(clean_trans_paras) + "\n"
            with open(trans_file, "w", encoding="utf-8") as f:
                f.write(final_text)

            tc_elapsed = time.time() - tc0
            success_count += 1
            print(f"  [✓ ترجمة عصبية] الفصل {cnum:>4}: {trans_title[:35]}... ({len(paragraphs)} فقرة | {tc_elapsed:.1f}ث)")

        elapsed_total = time.time() - t0
        print("\n" + "=" * 80)
        print(f" 🏆 اكتملت الترجمة العصبية بنجاح: {success_count} فصل في {elapsed_total:.1f} ثانية")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Neural Novel Translation Pipeline")
    parser.add_argument("--novel", type=str, default="shadow-slave", help="Novel slug identifier")
    parser.add_argument("--model", type=str, default="Helsinki-NLP/opus-mt-en-ar", help="HuggingFace model ID")
    parser.add_argument("--start", type=int, default=1, help="Start chapter")
    parser.add_argument("--end", type=int, default=10, help="End chapter")
    parser.add_argument("--batch-size", type=int, default=16, help="Tensor batch size")

    args = parser.parse_args()
    pipeline = NeuralNovelPipeline(novel_slug=args.novel, model_name=args.model)
    pipeline.run(start=args.start, end=args.end, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
