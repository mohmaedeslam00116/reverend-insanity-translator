import sys
import time
import json
import urllib.request
import urllib.parse
from pathlib import Path

from config import Config
from prompt_templates import GLOSSARY
from scraper import NovelFireScraper
from translator import KiloTranslator

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class FastGoogleTranslator:
    """
    Ultra-fast free Google Translate engine with specialized
    Reverend Insanity glossary replacement and paragraph formatting.
    """

    def __init__(self):
        # Sort glossary by length descending to replace longest phrases first
        self.glossary_sorted = sorted(
            GLOSSARY.items(), key=lambda x: len(x[0]), reverse=True
        )

    def apply_glossary_pre(self, text: str) -> str:
        """Replace specific Xianxia terms before translation if needed."""
        # Some terms are better replaced post-translation or preserved
        return text

    def translate_paragraph(self, text: str, src: str = "en", dest: str = "ar") -> str:
        """Translate a single paragraph or sentence chunk using Google Translate API."""
        if not text.strip():
            return ""
        try:
            url = (
                "https://translate.googleapis.com/translate_a/single?client=gtx&sl="
                + src
                + "&tl="
                + dest
                + "&dt=t&q="
                + urllib.parse.quote(text)
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                translated = "".join(
                    [s[0] for s in res_json[0] if s and s[0]]
                )
                return translated
        except Exception as e:
            # Fallback retry once
            time.sleep(1)
            try:
                url = (
                    "https://translate.googleapis.com/translate_a/single?client=gtx&sl="
                    + src
                    + "&tl="
                    + dest
                    + "&dt=t&q="
                    + urllib.parse.quote(text)
                )
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    return "".join([s[0] for s in res_json[0] if s and s[0]])
            except Exception:
                return text

    def translate_chapter(self, chapter_title: str, paragraphs: list) -> dict:
        """
        Translates a full chapter paragraph by paragraph at lightning speed (~1-2 seconds).
        """
        start_t = time.time()
        translated_paragraphs = []

        # Batch translate in chunks of 5 paragraphs to speed up HTTP requests
        batch_size = 5
        for i in range(0, len(paragraphs), batch_size):
            chunk = paragraphs[i : i + batch_size]
            combined_chunk = "\n\n".join(chunk)
            translated_chunk = self.translate_paragraph(combined_chunk)
            
            # Split back
            parts = translated_chunk.split("\n\n")
            for p in parts:
                p_clean = p.strip()
                if p_clean:
                    # Apply glossary fixes for known terms
                    for en_term, ar_term in self.glossary_sorted:
                        # Fix literal translations of key names if found
                        p_clean = p_clean.replace(en_term, ar_term)
                    translated_paragraphs.append(p_clean)

        elapsed = time.time() - start_t
        full_translated_text = "\n\n".join(translated_paragraphs)

        return {
            "status": "success",
            "title": chapter_title,
            "translated_text": full_translated_text,
            "elapsed_seconds": round(elapsed, 2),
        }

    def save_translated_chapter(
        self,
        chapter_num: int,
        title: str,
        translated_text: str,
        filepath: Path,
    ) -> bool:
        """Save translated chapter text with clean formatting and paragraph spacing."""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            cleaned = KiloTranslator.clean_and_format_arabic_text(translated_text)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# الفصل {chapter_num}: {title}\n\n")
                f.write(cleaned.strip())
                f.write("\n")
            return True
        except Exception as e:
            print(f"[FastTranslator] خطأ أثناء حفظ الفصل المترجم {chapter_num}: {e}")
            return False


# Quick test on Chapter 10
if __name__ == "__main__":
    scraper = NovelFireScraper()
    g_translator = FastGoogleTranslator()
    
    print("Scraping chapter 10...")
    c_data = scraper.fetch_chapter(10)
    print(f"Scraped {len(c_data['paragraphs'])} paragraphs. Translating with Fast Google Engine...")
    
    res = g_translator.translate_chapter(c_data['title'], c_data['paragraphs'])
    print(f"Done in {res['elapsed_seconds']}s! Output length: {len(res['translated_text'])} chars.")
    
    # Save to file
    out_file = Path("output/translated_ar/chapter_0010_fast.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"# الفصل 10: {c_data['title']}\n\n" + res['translated_text'] + "\n")
    print(f"Saved to: {out_file}")
