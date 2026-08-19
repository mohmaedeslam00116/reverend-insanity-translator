"""
📊 Smart Quality Evaluator for Reverend Insanity Novel Translation
===================================================================
Lightweight, fast, and free translation quality assessment tool.
Evaluates all 2,334 chapters using statistical and heuristic analysis
without requiring any AI model downloads.

Checks performed:
  1. Length Ratio Analysis   - Detects truncated/bloated translations
  2. Paragraph Alignment     - Ensures structural consistency  
  3. Arabic Language Check    - Verifies translation is actually Arabic
  4. Glossary Consistency     - Checks key term translations
  5. Duplicate Detection      - Finds repeated paragraphs
  6. Empty/Corrupt Detection  - Catches missing content

Usage:
  python smart_quality_evaluator.py                    # Evaluate all chapters
  python smart_quality_evaluator.py --chapters 1 2 3   # Specific chapters
  python smart_quality_evaluator.py --volume 1          # Entire volume
  python smart_quality_evaluator.py --summary           # Quick summary only
"""

import sys
import os
import re
import json
import time
import argparse
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import Config
from organize_volumes import get_volume_dir, VOLUME_RANGES


# ─────────────────────────────────────────────────────────────────────
# Core & Extended Glossary for Reverend Insanity
# ─────────────────────────────────────────────────────────────────────
GLOSSARY_FILE = Path("glossary.json")
GLOSSARY: Dict[str, List[str]] = {}

# Default core glossary with common variants
CORE_GLOSSARY = {
    "Fang Yuan": ["فانغ يوان"],
    "Fang Zheng": ["فانغ تشنغ", "فانغ جينغ", "فانغ تشينغ"],
    "Bai Ning Bing": ["باي نينغ بينغ"],
    "Hei Lou Lan": ["هي لو لان", "هاي لو لان"],
    "Spectral Soul": ["الروح الشبحية", "الروح الطيفية"],
    "Giant Sun": ["الشمس العملاقة"],
    "Star Constellation": ["كوكبة النجوم", "كوكبة النجم"],
    "Thieving Heaven": ["سارق السماء", "لص السماء"],
    "Spring Autumn Cicada": ["زيز الربيع والخريف"],
    "Gu Master": ["سيد غو", "سيد القو", "سيد الغو", "معلم القو"],
    "Gu Immortal": ["خالد غو", "خالد القو", "خالد الغو"],
    "Gu worm": ["دودة غو", "دودة القو", "دودة الغو", "حشرة القو", "قو", "غو"],
    "aperture": ["الفتحة", "فتحة"],
    "primeval essence": ["الجوهر البدائي", "جوهر بدائي"],
    "immortal essence": ["الجوهر الخالد", "جوهر خالد"],
    "blessed land": ["الأرض المباركة", "أرض مباركة"],
    "grotto-heaven": ["الكهف السماوي", "كهف سماوي"],
    "dao marks": ["علامات الداو", "علامات داو", "علامة داو"],
    "killer move": ["حركة قاتلة", "الحركة القاتلة"],
    "heavenly court": ["المحكمة السماوية", "البلاط السماوي"],
    "river of time": ["نهر الزمن", "نهر الوقت"],
}

GLOSSARY.update(CORE_GLOSSARY)

# Load full extracted glossary if available
if GLOSSARY_FILE.exists():
    try:
        with open(GLOSSARY_FILE, "r", encoding="utf-8") as f:
            ext_gloss = json.load(f)
            for k, v in ext_gloss.items():
                if k not in GLOSSARY:
                    GLOSSARY[k] = [v]
                elif v not in GLOSSARY[k]:
                    GLOSSARY[k].append(v)
    except Exception:
        pass

# Arabic Unicode ranges for detection
ARABIC_RANGES = [
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
]


def is_arabic_char(char: str) -> bool:
    """Check if a character is an Arabic Unicode character."""
    cp = ord(char)
    return any(start <= cp <= end for start, end in ARABIC_RANGES)


def arabic_ratio(text: str) -> float:
    """Calculate the ratio of Arabic characters in text."""
    if not text:
        return 0.0
    chars = [c for c in text if not c.isspace() and c not in '.,;:!?()[]{}"-\'«»#\n\r\t0123456789']
    if not chars:
        return 0.0
    arabic_count = sum(1 for c in chars if is_arabic_char(c))
    return arabic_count / len(chars)


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def paragraph_count(text: str) -> int:
    """Count non-empty paragraphs (split by double newline)."""
    return len([p for p in text.split("\n\n") if p.strip() and not p.strip().startswith("#")])


def find_duplicates(text: str, min_length: int = 50) -> List[str]:
    """Find duplicate paragraphs in text."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) >= min_length and not p.strip().startswith("#")]
    counter = Counter(paragraphs)
    return [p[:100] + "..." for p, count in counter.items() if count > 1]


# Pre-process glossary for microsecond-fast search
GLOSSARY_LOWER = [
    (en_term.lower(), [var.lower() for var in variants], en_term)
    for en_term, variants in GLOSSARY.items()
]


def check_glossary(en_text: str, ar_text: str) -> Dict[str, Any]:
    """Check if key glossary terms are properly translated."""
    found = 0
    missing = []
    checked = 0

    en_lower = en_text.lower()
    ar_lower = ar_text.lower()

    for en_term_lower, ar_vars_lower, original_en in GLOSSARY_LOWER:
        if en_term_lower in en_lower:
            checked += 1
            if any(v in ar_lower for v in ar_vars_lower):
                found += 1
            else:
                missing.append(original_en)

    return {
        "checked": checked,
        "found": found,
        "missing": missing,
        "score": (found / checked * 100) if checked > 0 else 100.0,
    }


class SmartQualityEvaluator:
    """
    Fast, lightweight translation quality evaluator using statistical
    and heuristic analysis. No AI models required.
    """

    # Acceptable length ratio range (AR words / EN words)
    # Arabic text is typically 60-90% of English word count
    MIN_LENGTH_RATIO = 0.35
    MAX_LENGTH_RATIO = 1.50

    # Minimum Arabic character ratio to confirm it's Arabic
    MIN_ARABIC_RATIO = 0.60

    # Maximum paragraph count difference allowed
    MAX_PARA_DIFF_RATIO = 0.40  # 40% difference allowed

    def __init__(self):
        self.results = []
        self.errors = []

    def find_chapter_file(self, base_dir: Path, chapter_num: int) -> Path:
        """Find chapter file in volume subdirectory."""
        vol_dir = get_volume_dir(base_dir, chapter_num)
        return vol_dir / f"chapter_{chapter_num:04d}.txt"

    def evaluate_chapter(self, chapter_num: int) -> Dict[str, Any]:
        """Evaluate a single chapter's translation quality."""
        en_file = self.find_chapter_file(Config.RAW_EN_DIR, chapter_num)
        ar_file = self.find_chapter_file(Config.TRANSLATED_AR_DIR, chapter_num)

        result = {
            "chapter": chapter_num,
            "status": "success",
            "scores": {},
            "issues": [],
            "overall_score": 0.0,
        }

        # Check file existence
        if not en_file.exists():
            result["status"] = "error"
            result["issues"].append("EN_FILE_MISSING")
            return result

        if not ar_file.exists():
            result["status"] = "error"
            result["issues"].append("AR_FILE_MISSING")
            return result

        # Read files
        try:
            with open(en_file, "r", encoding="utf-8") as f:
                en_text = f.read()
            with open(ar_file, "r", encoding="utf-8") as f:
                ar_text = f.read()
        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"READ_ERROR: {e}")
            return result

        # ── Check 1: Empty/Corrupt Detection ──
        if len(en_text.strip()) < 50:
            result["issues"].append("EN_TOO_SHORT")
        if len(ar_text.strip()) < 50:
            result["issues"].append("AR_TOO_SHORT")
            result["status"] = "warning"

        en_words = word_count(en_text)
        ar_words = word_count(ar_text)

        # ── Check 2: Length Ratio ──
        if en_words > 0:
            ratio = ar_words / en_words
            ratio_score = 100.0
            if ratio < self.MIN_LENGTH_RATIO:
                ratio_score = max(0, ratio / self.MIN_LENGTH_RATIO * 60)
                result["issues"].append(f"TOO_SHORT (ratio={ratio:.2f})")
            elif ratio > self.MAX_LENGTH_RATIO:
                ratio_score = max(0, (2.0 - ratio) / (2.0 - self.MAX_LENGTH_RATIO) * 60)
                result["issues"].append(f"TOO_LONG (ratio={ratio:.2f})")
            else:
                # Perfect range: 0.55 - 1.0
                if 0.55 <= ratio <= 1.0:
                    ratio_score = 100.0
                else:
                    ratio_score = 80.0
            result["scores"]["length_ratio"] = round(ratio_score, 1)
            result["length_ratio"] = round(ratio, 3)
        else:
            result["scores"]["length_ratio"] = 0.0

        # ── Check 3: Arabic Language Verification ──
        ar_ratio_val = arabic_ratio(ar_text)
        if ar_ratio_val >= 0.85:
            lang_score = 100.0
        elif ar_ratio_val >= self.MIN_ARABIC_RATIO:
            lang_score = 70 + (ar_ratio_val - self.MIN_ARABIC_RATIO) / (0.85 - self.MIN_ARABIC_RATIO) * 30
        else:
            lang_score = ar_ratio_val / self.MIN_ARABIC_RATIO * 60
            result["issues"].append(f"LOW_ARABIC_RATIO ({ar_ratio_val:.1%})")
        result["scores"]["arabic_ratio"] = round(lang_score, 1)
        result["arabic_ratio"] = round(ar_ratio_val, 3)

        # ── Check 4: Paragraph Alignment ──
        en_paras = paragraph_count(en_text)
        ar_paras = paragraph_count(ar_text)
        if en_paras > 0:
            para_diff = abs(en_paras - ar_paras) / en_paras
            if para_diff <= 0.10:
                para_score = 100.0
            elif para_diff <= self.MAX_PARA_DIFF_RATIO:
                para_score = 100 - (para_diff - 0.10) / (self.MAX_PARA_DIFF_RATIO - 0.10) * 40
            else:
                para_score = max(0, 60 - (para_diff - self.MAX_PARA_DIFF_RATIO) * 100)
                result["issues"].append(f"PARA_MISMATCH (en={en_paras}, ar={ar_paras})")
            result["scores"]["paragraph_alignment"] = round(para_score, 1)
        else:
            result["scores"]["paragraph_alignment"] = 0.0
        result["en_paragraphs"] = en_paras
        result["ar_paragraphs"] = ar_paras

        # ── Check 5: Glossary Consistency ──
        glossary_result = check_glossary(en_text, ar_text)
        result["scores"]["glossary"] = round(glossary_result["score"], 1)
        result["glossary_checked"] = glossary_result["checked"]
        result["glossary_found"] = glossary_result["found"]
        if glossary_result["missing"]:
            result["issues"].append(f"GLOSSARY_MISSING: {', '.join(glossary_result['missing'][:3])}")

        # ── Check 6: Duplicate Detection ──
        duplicates = find_duplicates(ar_text)
        if duplicates:
            dup_score = max(0, 100 - len(duplicates) * 25)
            result["issues"].append(f"DUPLICATES_FOUND ({len(duplicates)})")
        else:
            dup_score = 100.0
        result["scores"]["no_duplicates"] = round(dup_score, 1)
        result["duplicate_count"] = len(duplicates)

        # ── Calculate Overall Score (weighted average) ──
        weights = {
            "length_ratio": 0.25,
            "arabic_ratio": 0.25,
            "paragraph_alignment": 0.20,
            "glossary": 0.20,
            "no_duplicates": 0.10,
        }
        overall = sum(result["scores"].get(k, 0) * w for k, w in weights.items())
        result["overall_score"] = round(overall, 1)
        result["en_words"] = en_words
        result["ar_words"] = ar_words

        return result

    def run_full_evaluation(self, chapters: List[int], max_workers: int = 8) -> Dict[str, Any]:
        """Run evaluation on all specified chapters using thread pool for speed."""
        total = len(chapters)
        print("=" * 80)
        print(f" 📊 Smart Quality Evaluator — فحص جودة الترجمة الذكي")
        print(f" 📚 عدد الفصول: {total}")
        print("=" * 80)

        t0 = time.time()
        results = []
        errors = []

        # Use ThreadPoolExecutor for parallel I/O
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self.evaluate_chapter, ch): ch for ch in chapters}

            done_count = 0
            for future in as_completed(future_map):
                done_count += 1
                res = future.result()
                if res["status"] == "error":
                    errors.append(res)
                else:
                    results.append(res)

                # Progress update every 100 chapters or at boundaries
                if done_count % 200 == 0 or done_count == total:
                    elapsed = time.time() - t0
                    speed = done_count / elapsed if elapsed > 0 else 0
                    print(f"   ⏳ تقدم: {done_count}/{total} فصل ({done_count/total*100:.0f}%) | {speed:.0f} فصل/ثانية | {elapsed:.1f}ث")

        elapsed_total = time.time() - t0

        # Sort results by chapter number
        results.sort(key=lambda r: r["chapter"])
        errors.sort(key=lambda r: r["chapter"])

        # Generate report
        report = self._generate_report(results, errors, elapsed_total)
        return report

    def _generate_report(self, results: List[Dict], errors: List[Dict], elapsed: float) -> Dict[str, Any]:
        """Generate comprehensive quality report."""
        if not results:
            print(" ❌ لا توجد نتائج لعرضها!")
            return {}

        # Statistics
        scores = [r["overall_score"] for r in results]
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        median_score = sorted(scores)[len(scores) // 2]

        # Score distribution
        excellent = sum(1 for s in scores if s >= 90)
        good = sum(1 for s in scores if 75 <= s < 90)
        acceptable = sum(1 for s in scores if 60 <= s < 75)
        needs_review = sum(1 for s in scores if s < 60)

        # Common issues
        all_issues = []
        for r in results:
            all_issues.extend(r["issues"])
        issue_counter = Counter(
            issue.split("(")[0].split(":")[0].strip() for issue in all_issues
        )

        # Chapters needing attention (lowest scores)
        worst_chapters = sorted(results, key=lambda r: r["overall_score"])[:10]

        # Sub-score averages
        sub_scores = {}
        for key in ["length_ratio", "arabic_ratio", "paragraph_alignment", "glossary", "no_duplicates"]:
            vals = [r["scores"].get(key, 0) for r in results]
            sub_scores[key] = round(sum(vals) / len(vals), 1) if vals else 0

        # Verdict
        if avg_score >= 90:
            verdict = "🏆 ممتازة — جودة احترافية عالية (Excellent Quality)"
            verdict_en = "Excellent"
        elif avg_score >= 75:
            verdict = "🟢 جيدة جداً — ترجمة متسقة ومتكاملة (Very Good Quality)"
            verdict_en = "Very Good"
        elif avg_score >= 60:
            verdict = "🟡 مقبولة — تحتاج بعض التحسينات (Acceptable Quality)"
            verdict_en = "Acceptable"
        else:
            verdict = "🔴 تحتاج مراجعة شاملة (Needs Review)"
            verdict_en = "Needs Review"

        # ──────── Console Output ────────
        print("\n" + "=" * 80)
        print(" 🏆 التقرير الإجمالي لجودة الترجمة (Smart Quality Report)")
        print("=" * 80)
        print(f" • إجمالي الفصول المفحوصة: {len(results)}")
        print(f" • الأخطاء (ملفات مفقودة): {len(errors)}")
        print(f" • الزمن الكلي: {elapsed:.1f} ثانية ({elapsed/60:.1f} دقيقة)")
        print(f" • السرعة: {len(results)/elapsed:.0f} فصل/ثانية")
        print()
        print(f" 📈 متوسط الجودة العام: {avg_score:.1f}%")
        print(f" 📊 الوسيط: {median_score:.1f}% | الأدنى: {min_score:.1f}% | الأعلى: {max_score:.1f}%")
        print(f" 🎯 التصنيف: {verdict}")
        print()
        print(" 📊 توزيع الدرجات:")
        print(f"   🟢 ممتاز (90%+):     {excellent:>5} فصل ({excellent/len(results)*100:.1f}%)")
        print(f"   🔵 جيد (75-89%):      {good:>5} فصل ({good/len(results)*100:.1f}%)")
        print(f"   🟡 مقبول (60-74%):    {acceptable:>5} فصل ({acceptable/len(results)*100:.1f}%)")
        print(f"   🔴 يحتاج مراجعة (<60%): {needs_review:>5} فصل ({needs_review/len(results)*100:.1f}%)")
        print()
        print(" 📋 تفصيل المقاييس الفرعية:")
        labels = {
            "length_ratio": "نسبة الطول",
            "arabic_ratio": "نسبة العربية",
            "paragraph_alignment": "محاذاة الفقرات",
            "glossary": "تطابق المصطلحات",
            "no_duplicates": "خلو من التكرار",
        }
        for key, label in labels.items():
            bar_len = int(sub_scores[key] / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"   {label:>20}: {bar} {sub_scores[key]:.1f}%")

        if issue_counter:
            print()
            print(" ⚠️ المشاكل الأكثر شيوعاً:")
            for issue, count in issue_counter.most_common(5):
                print(f"   • {issue}: {count} فصل")

        if worst_chapters:
            print()
            print(" 🔍 أسوأ 10 فصول (تحتاج مراجعة):")
            for r in worst_chapters:
                issues_str = ", ".join(r["issues"][:2]) if r["issues"] else "—"
                print(f"   • الفصل {r['chapter']:>4}: {r['overall_score']:.1f}% | {issues_str}")

        print("=" * 80)

        # ──────── Save JSON Report ────────
        report_data = {
            "evaluation_tool": "Smart Quality Evaluator v1.0",
            "evaluation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "novel": "Reverend Insanity (رواية القس المجنون)",
            "total_chapters_evaluated": len(results),
            "total_errors": len(errors),
            "elapsed_seconds": round(elapsed, 1),
            "overall": {
                "average_score": round(avg_score, 1),
                "median_score": round(median_score, 1),
                "min_score": round(min_score, 1),
                "max_score": round(max_score, 1),
                "verdict": verdict_en,
            },
            "distribution": {
                "excellent_90_plus": excellent,
                "good_75_89": good,
                "acceptable_60_74": acceptable,
                "needs_review_below_60": needs_review,
            },
            "sub_scores": sub_scores,
            "common_issues": dict(issue_counter.most_common(10)),
            "worst_chapters": [
                {
                    "chapter": r["chapter"],
                    "score": r["overall_score"],
                    "issues": r["issues"],
                }
                for r in worst_chapters
            ],
            "all_results": results,
            "errors": errors,
        }

        json_path = Path("output/smart_quality_report.json")
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        print(f"\n [✓] تقرير JSON: {json_path.resolve()}")

        # ──────── Save Markdown Report ────────
        md_path = Path("output/smart_quality_report.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 📊 تقرير جودة ترجمة رواية القس المجنون\n")
            f.write("## Smart Quality Evaluator Report\n\n")
            f.write(f"- **تاريخ التقييم:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **عدد الفصول:** {len(results)}\n")
            f.write(f"- **زمن الفحص:** {elapsed:.1f} ثانية\n\n")

            f.write("## النتيجة الإجمالية\n\n")
            f.write(f"| المقياس | القيمة |\n")
            f.write(f"| :--- | :---: |\n")
            f.write(f"| **متوسط الجودة** | **{avg_score:.1f}%** |\n")
            f.write(f"| الوسيط | {median_score:.1f}% |\n")
            f.write(f"| الأدنى | {min_score:.1f}% |\n")
            f.write(f"| الأعلى | {max_score:.1f}% |\n")
            f.write(f"| **التصنيف** | **{verdict}** |\n\n")

            f.write("## توزيع الدرجات\n\n")
            f.write("| الفئة | العدد | النسبة |\n")
            f.write("| :--- | :---: | :---: |\n")
            f.write(f"| 🟢 ممتاز (90%+) | {excellent} | {excellent/len(results)*100:.1f}% |\n")
            f.write(f"| 🔵 جيد (75-89%) | {good} | {good/len(results)*100:.1f}% |\n")
            f.write(f"| 🟡 مقبول (60-74%) | {acceptable} | {acceptable/len(results)*100:.1f}% |\n")
            f.write(f"| 🔴 يحتاج مراجعة (<60%) | {needs_review} | {needs_review/len(results)*100:.1f}% |\n\n")

            f.write("## المقاييس الفرعية\n\n")
            f.write("| المقياس | الدرجة |\n")
            f.write("| :--- | :---: |\n")
            for key, label in labels.items():
                f.write(f"| {label} | {sub_scores[key]:.1f}% |\n")

            if issue_counter:
                f.write("\n## المشاكل الشائعة\n\n")
                f.write("| المشكلة | عدد الفصول |\n")
                f.write("| :--- | :---: |\n")
                for issue, count in issue_counter.most_common(10):
                    f.write(f"| {issue} | {count} |\n")

            if worst_chapters:
                f.write("\n## الفصول التي تحتاج مراجعة\n\n")
                f.write("| الفصل | الدرجة | المشاكل |\n")
                f.write("| :---: | :---: | :--- |\n")
                for r in worst_chapters:
                    issues_str = ", ".join(r["issues"][:3]) if r["issues"] else "—"
                    f.write(f"| {r['chapter']} | {r['overall_score']:.1f}% | {issues_str} |\n")

            # Per-volume summary
            f.write("\n## ملخص حسب المجلد\n\n")
            f.write("| المجلد | عدد الفصول | متوسط الجودة | أدنى درجة |\n")
            f.write("| :--- | :---: | :---: | :---: |\n")
            for start, end, vol_name in VOLUME_RANGES:
                vol_results = [r for r in results if start <= r["chapter"] <= end]
                if vol_results:
                    vol_avg = sum(r["overall_score"] for r in vol_results) / len(vol_results)
                    vol_min = min(r["overall_score"] for r in vol_results)
                    short_name = vol_name.split("(")[0].strip()
                    f.write(f"| {short_name} | {len(vol_results)} | {vol_avg:.1f}% | {vol_min:.1f}% |\n")

        print(f" [✓] تقرير Markdown: {md_path.resolve()}")

        return report_data


def main():
    parser = argparse.ArgumentParser(
        description="Smart Quality Evaluator — فحص جودة ترجمة رواية القس المجنون"
    )
    parser.add_argument("--chapters", nargs="+", type=int, help="أرقام فصول محددة للفحص")
    parser.add_argument("--volume", type=int, choices=[1, 2, 3, 4, 5], help="فحص مجلد كامل")
    parser.add_argument("--start", type=int, help="بداية نطاق الفصول")
    parser.add_argument("--end", type=int, help="نهاية نطاق الفصول")
    parser.add_argument("--summary", action="store_true", help="عرض ملخص سريع فقط")
    parser.add_argument("--workers", type=int, default=8, help="عدد المعالجات المتوازية (افتراضي: 8)")

    args = parser.parse_args()
    evaluator = SmartQualityEvaluator()

    if args.chapters:
        chapters = args.chapters
    elif args.volume:
        for start, end, _ in VOLUME_RANGES:
            if args.volume == VOLUME_RANGES.index((start, end, _)) + 1:
                chapters = list(range(start, min(end, 2334) + 1))
                break
        else:
            # Fallback
            vol_idx = args.volume - 1
            s, e, _ = VOLUME_RANGES[vol_idx]
            chapters = list(range(s, min(e, 2334) + 1))
    elif args.start and args.end:
        chapters = list(range(args.start, args.end + 1))
    else:
        # All chapters
        chapters = list(range(1, 2335))

    evaluator.run_full_evaluation(chapters, max_workers=args.workers)


if __name__ == "__main__":
    main()
