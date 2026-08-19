import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup

from config import Config


class NovelFireScraper:
    """
    Scraper specialized for novelfire.net chapters with ad filtering,
    title extraction, and fallback mechanisms for missing chapters.
    """

    AD_PATTERNS = [
        re.compile(r"if you find any errors", re.IGNORECASE),
        re.compile(r"please let us know", re.IGNORECASE),
        re.compile(r"ads redirect", re.IGNORECASE),
        re.compile(r"visit novelfire\.net", re.IGNORECASE),
        re.compile(r"find authorized novels in", re.IGNORECASE),
        re.compile(r"read latest chapters at", re.IGNORECASE),
        re.compile(r"this chapter is updated by", re.IGNORECASE),
    ]

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or Config.NOVEL_BASE_URL).rstrip("/")

    def get_standard_url(self, chapter_num: int) -> str:
        """Construct the standard chapter URL."""
        return f"{self.base_url}/chapter-{chapter_num}"

    def fetch_url(self, url: str, timeout: int = 20) -> str:
        """Fetch raw HTML from a URL with browser-like headers."""
        req = urllib.request.Request(url, headers=Config.SCRAPER_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")

    def clean_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """Filter out ad texts, short promo notices, and empty paragraphs."""
        cleaned = []
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue

            # Check if matches known ad phrases
            is_ad = any(pattern.search(p_clean) for pattern in self.AD_PATTERNS)
            if is_ad:
                continue

            cleaned.append(p_clean)
        return cleaned

    def parse_chapter_html(self, html: str, chapter_num: int) -> Dict[str, Any]:
        """Parse the HTML of a chapter page and extract structured content."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Chapter Title
        title = ""
        title_tag = (
            soup.find(["h1", "h2", "h3"], class_=re.compile(r"chapter|title", re.I))
            or soup.find("span", class_=re.compile(r"chapter-title|title", re.I))
            or soup.find("h1")
        )
        if title_tag:
            title = title_tag.get_text(strip=True)
        if not title:
            title = f"Chapter {chapter_num}"

        # 2. Extract Chapter Body
        content_div = (
            soup.find("div", id=re.compile(r"chapter-container|chapter-c|chapter-content", re.I))
            or soup.find("div", class_=re.compile(r"d-chapter-content|chapter-content|reading-content", re.I))
        )

        paragraphs = []
        if content_div:
            # Remove any embedded script or style tags
            for tag in content_div(["script", "style", "iframe", "ins"]):
                tag.decompose()

            # Find all paragraph tags
            p_tags = content_div.find_all("p")
            if p_tags:
                paragraphs = [p.get_text(strip=True) for p in p_tags]
            else:
                # Fallback: split by breaks or newlines
                paragraphs = [line.strip() for line in content_div.get_text().split("\n") if line.strip()]
        else:
            # Broader fallback search
            all_p = soup.find_all("p")
            paragraphs = [p.get_text(strip=True) for p in all_p]

        # Clean ads
        cleaned_paragraphs = self.clean_paragraphs(paragraphs)
        full_text = "\n\n".join(cleaned_paragraphs)

        # 3. Detect Next Chapter Link
        next_url = None
        next_link = (
            soup.find("a", id="next_chap")
            or soup.find("a", class_=re.compile(r"next|btn-next", re.I))
            or soup.find("a", string=re.compile(r"next chapter|next", re.I))
        )
        if next_link and next_link.get("href"):
            href = next_link.get("href")
            if href.startswith("/"):
                next_url = f"https://novelfire.net{href}"
            elif href.startswith("http"):
                next_url = href

        return {
            "chapter_num": chapter_num,
            "title": title,
            "paragraphs": cleaned_paragraphs,
            "full_text": full_text,
            "paragraph_count": len(cleaned_paragraphs),
            "word_count": len(full_text.split()),
            "next_url": next_url,
            "status": "success",
        }

    def fetch_chapter(
        self,
        chapter_num: int,
        custom_url: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 3,
    ) -> Dict[str, Any]:
        """
        Fetch a chapter by number with retry logic and fallback URLs.
        """
        target_url = custom_url or self.get_standard_url(chapter_num)
        last_error = None

        # Candidate URLs to try in case of 404
        candidate_urls = [
            target_url,
            f"{self.base_url}/chapter-{chapter_num:03d}",
            f"{self.base_url}/chapter-{chapter_num}-1",
        ]

        for url in candidate_urls:
            for attempt in range(1, max_retries + 1):
                try:
                    html = self.fetch_url(url, timeout=Config.TIMEOUT_SECONDS)
                    result = self.parse_chapter_html(html, chapter_num)
                    if result["paragraph_count"] > 0:
                        result["source_url"] = url
                        return result
                    else:
                        raise ValueError("Chapter content was empty.")
                except urllib.error.HTTPError as e:
                    last_error = f"HTTP {e.code}: {e.reason}"
                    if e.code == 404:
                        # Don't retry same URL on 404; try next candidate
                        break
                    elif e.code in (429, 500, 502, 503, 504):
                        time.sleep(retry_delay * attempt)
                    else:
                        break
                except Exception as e:
                    last_error = str(e)
                    time.sleep(retry_delay * attempt)

        return {
            "chapter_num": chapter_num,
            "status": "error",
            "error": last_error or "Chapter not found",
            "source_url": target_url,
        }

    def save_raw_chapter(self, chapter_data: Dict[str, Any], filepath: Path) -> bool:
        """Save raw chapter data to a text file."""
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {chapter_data.get('title', '')}\n\n")
                f.write(chapter_data.get("full_text", ""))
            return True
        except Exception as e:
            print(f"[Scraper] Error saving raw chapter {chapter_data.get('chapter_num')}: {e}")
            return False
