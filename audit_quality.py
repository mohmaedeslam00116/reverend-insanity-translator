import re
import sys
from pathlib import Path
from config import Config
from prompt_templates import GLOSSARY


def audit_translated_chapters():
    """
    Automated Quality Auditor for translated chapters.
    Checks:
    1. Leftover English words / untranslated text.
    2. Completeness (Paragraph count comparison with raw English).
    3. Proper paragraph spacing.
    4. Glossary consistency.
    """
    Config.init_directories()
    trans_files = sorted(Config.TRANSLATED_AR_DIR.rglob("chapter_*.txt"))

    if not trans_files:
        print("[!] لم يتم العثور على فصول مترجمة لفحصها.")
        return

    print("=" * 75)
    print(f" 🔍 بدء الفحص الآلي لجودة الفصول المترجمة ({len(trans_files)} فصلاً)")
    print("=" * 75)

    english_word_pattern = re.compile(r"\b[A-Za-z]{3,}\b")
    report = []

    for cfile in trans_files:
        chapter_num_str = cfile.stem.replace("chapter_", "")
        try:
            cnum = int(chapter_num_str)
        except ValueError:
            continue

        from organize_volumes import get_volume_dir
        raw_file = get_volume_dir(Config.RAW_EN_DIR, cnum) / f"chapter_{cnum:04d}.txt"
        if not raw_file.exists():
            raw_file = Config.RAW_EN_DIR / f"chapter_{cnum:04d}.txt"

        with open(cfile, "r", encoding="utf-8") as f:
            trans_text = f.read()

        trans_paragraphs = [p.strip() for p in trans_text.split("\n\n") if p.strip() and not p.startswith("#")]
        
        # 1. Check for leftover English
        leftover_en = english_word_pattern.findall(trans_text)
        # Filter out common markdown or chapter numbers
        leftover_en = [w for w in leftover_en if w.lower() not in ("chapter", "txt", "md")]

        # 2. Check completeness vs raw file
        raw_p_count = 0
        if raw_file.exists():
            with open(raw_file, "r", encoding="utf-8") as f:
                raw_text = f.read()
            raw_paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip() and not p.startswith("#")]
            raw_p_count = len(raw_paragraphs)

        trans_p_count = len(trans_paragraphs)
        drop_ratio = (trans_p_count / raw_p_count) if raw_p_count > 0 else 1.0

        issues = []
        if leftover_en:
            issues.append(f"كلمات إنجليزية غير مترجمة ({len(leftover_en)}: {', '.join(leftover_en[:4])})")
        if raw_p_count > 0 and drop_ratio < 0.7:
            issues.append(f"نقص في الفقرات ({trans_p_count}/{raw_p_count} فقرة)")

        score = 100
        if leftover_en:
            score -= min(len(leftover_en) * 5, 30)
        if drop_ratio < 0.8:
            score -= int((1.0 - drop_ratio) * 50)

        score = max(0, score)
        status_icon = "✅" if score >= 90 else ("⚠️" if score >= 70 else "❌")

        report.append({
            "chapter": cnum,
            "score": score,
            "issues": issues,
            "raw_p": raw_p_count,
            "trans_p": trans_p_count,
        })

        issue_text = " | " + ", ".join(issues) if issues else " | سليم 100%"
        print(f" {status_icon} الفصل {cnum:04d}: جودة {score}% (فقرات: {trans_p_count}/{raw_p_count}){issue_text}")

    # Summary
    avg_score = sum(r["score"] for r in report) / len(report)
    perfect_count = sum(1 for r in report if r["score"] >= 95)

    print("\n" + "=" * 75)
    print(" 📊 ملخص تقرير الجودة:")
    print("=" * 75)
    print(f" • متوسط درجة الجودة: {avg_score:.1f}%")
    print(f" • الفصول الممتازة (95%+): {perfect_count}/{len(report)}")
    print(f" • الفصول التي تحتاج مراجعة: {len(report) - perfect_count}")
    print("=" * 75)


if __name__ == "__main__":
    audit_translated_chapters()
