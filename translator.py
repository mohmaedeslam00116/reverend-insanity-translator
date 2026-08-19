import time
import json
import random
from pathlib import Path
from typing import Optional, Dict, Any, List
import requests

from config import Config
from prompt_templates import build_translation_prompt, GLOSSARY


class KiloTranslator:
    """
    Translator module interfacing with Kilo AI Gateway.
    Features:
    - Smart paragraph chunking for long chapters.
    - Automatic exponential backoff for rate limits and gateway errors.
    - High-fidelity literary Arabic output validation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or Config.KILO_API_KEY
        self.api_url = api_url or Config.KILO_API_URL
        self.model = model or Config.KILO_MODEL

        self.session = requests.Session()
        self.session.headers.update(Config.get_api_headers())

    def split_paragraphs_into_chunks(
        self, paragraphs: List[str], chunk_size: int = 30
    ) -> List[List[str]]:
        """Group paragraphs into chunks of reasonable size for LLM context limits."""
        if not paragraphs:
            return []
        chunks = []
        for i in range(0, len(paragraphs), chunk_size):
            chunks.append(paragraphs[i : i + chunk_size])
        return chunks

    def _call_api_with_retry(
        self,
        messages: List[Dict[str, str]],
        max_retries: int = 5,
        base_delay: int = 5,
    ) -> str:
        """
        Send chat completion request to Kilo AI Gateway with exponential backoff.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.6,
        }

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.post(
                    self.api_url,
                    json=payload,
                    timeout=Config.TIMEOUT_SECONDS,
                )

                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        content = choices[0]["message"].get("content", "").strip()
                        if content:
                            return content
                    raise ValueError(f"Invalid API response format: {response.text[:200]}")

                # Handle Rate Limit (429)
                elif response.status_code == 429:
                    wait_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(1, 3)
                    print(
                        f"  [!] تم بلوغ حد الطلبات (429 Rate Limit). انتهاء المحاولة {attempt}/{max_retries}. الانتظار {wait_seconds:.1f} ثانية..."
                    )
                    time.sleep(wait_seconds)

                # Handle Gateway / Server Errors (500, 502, 503, 504)
                elif response.status_code in (500, 502, 503, 504):
                    wait_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(1, 3)
                    print(
                        f"  [!] خطأ في خادم Kilo AI ({response.status_code}). المحاولة {attempt}/{max_retries}. الانتظار {wait_seconds:.1f} ثانية..."
                    )
                    time.sleep(wait_seconds)

                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:300]}"
                    print(f"  [!] خطأ من API: {error_msg}")
                    last_err = error_msg
                    time.sleep(base_delay)

            except requests.exceptions.Timeout:
                wait_seconds = base_delay * attempt
                print(f"  [!] انتهت مهلة الاتصال (Timeout). المحاولة {attempt}/{max_retries}. الانتظار {wait_seconds} ثوانٍ...")
                time.sleep(wait_seconds)
            except requests.exceptions.RequestException as e:
                last_err = str(e)
                wait_seconds = base_delay * attempt
                print(f"  [!] خطأ في الاتصال بالشبكة: {e}. الانتظار {wait_seconds} ثوانٍ...")
                time.sleep(wait_seconds)
            except Exception as e:
                last_err = str(e)
                print(f"  [!] خطأ غير متوقع أثناء معالجة الاستجابة: {e}")
                time.sleep(base_delay)

        raise RuntimeError(f"فشلت الترجمة بعد {max_retries} محاولات. آخر خطأ: {last_err}")

    def translate_chapter(
        self,
        chapter_title: str,
        paragraphs: List[str],
        chunk_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Translate a full chapter with automatic chunking and stitching.
        """
        if not paragraphs:
            return {
                "status": "error",
                "error": "No paragraphs provided for translation",
            }

        effective_chunk_size = chunk_size or Config.CHUNK_SIZE_PARAGRAPHS
        chunks = self.split_paragraphs_into_chunks(paragraphs, effective_chunk_size)
        total_chunks = len(chunks)

        translated_parts = []
        print(f"  -> جاري ترجمة الفصل: \"{chapter_title}\" (مقسم إلى {total_chunks} جزء/أجزاء)...")

        for idx, chunk in enumerate(chunks, 1):
            chunk_text = "\n\n".join(chunk)
            messages = build_translation_prompt(
                chapter_title=chapter_title,
                text=chunk_text,
                is_chunk=(total_chunks > 1),
                chunk_num=idx,
                total_chunks=total_chunks,
            )

            if total_chunks > 1:
                print(f"     * جاري معالجة الجزء {idx}/{total_chunks} ({len(chunk)} فقرة)...")

            translated_chunk = self._call_api_with_retry(
                messages, max_retries=Config.MAX_RETRIES
            )
            translated_parts.append(translated_chunk)

            # Small breather between chunks if multiple chunks exist
            if idx < total_chunks:
                time.sleep(2)

        # Stitch translated parts together
        full_translated_text = "\n\n".join(translated_parts)

        return {
            "status": "success",
            "title": chapter_title,
            "translated_text": full_translated_text,
            "chunk_count": total_chunks,
        }

    @staticmethod
    def clean_and_format_arabic_text(text: str) -> str:
        """
        Cleans up LLM metadata artifacts, ensures clear double spacing between paragraphs,
        formats dialogue quotes cleanly on their own lines, and normalizes typography.
        """
        import re
        lines = text.split("\n")
        cleaned_paragraphs = []

        # Patterns to remove (chunk headers, subheadings, leftover markers)
        meta_patterns = [
            re.compile(r"^#+\s*(الفصل|Chapter)\b.*", re.IGNORECASE),
            re.compile(r"^\(?(الجزء|Part)\s*\d+.*", re.IGNORECASE),
            re.compile(r"^ترجمة\s*(الفصل|الجزء).*", re.IGNORECASE),
            re.compile(r"^\(تكملة\s*الفصل.*\)", re.IGNORECASE),
            re.compile(r"^\s*[-=_*~]{3,}\s*$"),  # horizontal dividers
        ]

        for raw_line in lines:
            line_str = raw_line.strip()
            if not line_str:
                continue

            # Remove meta headers
            if any(pat.match(line_str) for pat in meta_patterns):
                continue

            # Handle multiple dialogue quotes or sentences merged into one line
            # If line contains multiple quotes like "«...» «...»", split them
            split_dialogues = re.split(r"(?<=[»\"”])\s*(?=[«\"“])", line_str)
            for d in split_dialogues:
                d_str = d.strip()
                if d_str and not any(pat.match(d_str) for pat in meta_patterns):
                    cleaned_paragraphs.append(d_str)

        # Join all paragraphs with clear double line breaks (\n\n)
        formatted_text = "\n\n".join(p for p in cleaned_paragraphs if p.strip())
        return formatted_text

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
            formatted_body = self.clean_and_format_arabic_text(translated_text)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# الفصل {chapter_num}: {title}\n\n")
                f.write(formatted_body.strip())
                f.write("\n")
            return True
        except Exception as e:
            print(f"[Translator] خطأ أثناء حفظ الفصل المترجم {chapter_num}: {e}")
            return False

