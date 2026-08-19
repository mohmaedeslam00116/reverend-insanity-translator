"""
📊 Comparison & Delta Reporter for Quality Improvements
========================================================
Compares 'before' and 'after' evaluation reports to show quantifiable
translation quality improvements across all novel chapters.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_comparison(before_path: Path, after_path: Path, output_md: Path) -> str:
    before = load_report(before_path)
    after = load_report(after_path)

    if not before or not after:
        print("[Compare] Error: One of the reports is missing.")
        return ""

    b_avg = before.get("overall", {}).get("average_score", 0)
    a_avg = after.get("overall", {}).get("average_score", 0)
    delta_avg = a_avg - b_avg

    b_dist = before.get("distribution", {})
    a_dist = after.get("distribution", {})

    b_sub = before.get("sub_scores", {})
    a_sub = after.get("sub_scores", {})

    md = []
    md.append("# 📈 تقرير مقارنة تحسين جودة الترجمة (Before vs After Quality Report)\n")
    md.append(f"- **تاريخ التقرير:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    md.append(f"- **عدد الفصول المفحوصة:** {after.get('total_chapters_evaluated', 0)}\n\n")

    md.append("## 1. المقارنة الإجمالية للجودة\n\n")
    md.append("| المقياس | قبل التحسين (Before) | بعد التحسين (After) | مقدار التطور (Delta) |\n")
    md.append("| :--- | :---: | :---: | :---: |\n")
    delta_sign = "+" if delta_avg >= 0 else ""
    md.append(f"| **متوسط الجودة العام** | **{b_avg:.1f}%** | **{a_avg:.1f}%** | **{delta_sign}{delta_avg:.1f}%** 🚀 |\n")
    
    b_med = before.get("overall", {}).get("median_score", 0)
    a_med = after.get("overall", {}).get("median_score", 0)
    md.append(f"| الدرجة الوسيطة (Median) | {b_med:.1f}% | {a_med:.1f}% | {'+' if a_med>=b_med else ''}{a_med-b_med:.1f}% |\n")

    b_min = before.get("overall", {}).get("min_score", 0)
    a_min = after.get("overall", {}).get("min_score", 0)
    md.append(f"| أدنى درجة مسجلة (Min) | {b_min:.1f}% | {a_min:.1f}% | {'+' if a_min>=b_min else ''}{a_min-b_min:.1f}% |\n\n")

    md.append("## 2. توزيع تصنيفات الفصول\n\n")
    md.append("| التصنيف | قبل التحسين | بعد التحسين | التغير |\n")
    md.append("| :--- | :---: | :---: | :---: |\n")
    
    exc_diff = a_dist.get("excellent_90_plus", 0) - b_dist.get("excellent_90_plus", 0)
    md.append(f"| 🟢 ممتاز (90%+) | {b_dist.get('excellent_90_plus', 0)} | {a_dist.get('excellent_90_plus', 0)} | {'+' if exc_diff>=0 else ''}{exc_diff} فصل |\n")

    good_diff = a_dist.get("good_75_89", 0) - b_dist.get("good_75_89", 0)
    md.append(f"| 🔵 جيد (75-89%) | {b_dist.get('good_75_89', 0)} | {a_dist.get('good_75_89', 0)} | {'+' if good_diff>=0 else ''}{good_diff} فصل |\n")

    acc_diff = a_dist.get("acceptable_60_74", 0) - b_dist.get("acceptable_60_74", 0)
    md.append(f"| 🟡 مقبول (60-74%) | {b_dist.get('acceptable_60_74', 0)} | {a_dist.get('acceptable_60_74', 0)} | {'+' if acc_diff>=0 else ''}{acc_diff} فصل |\n")

    rev_diff = a_dist.get("needs_review_below_60", 0) - b_dist.get("needs_review_below_60", 0)
    md.append(f"| 🔴 يحتاج مراجعة (<60%) | {b_dist.get('needs_review_below_60', 0)} | {a_dist.get('needs_review_below_60', 0)} | {'+' if rev_diff>=0 else ''}{rev_diff} فصل |\n\n")

    md.append("## 3. تطور المقاييس الفرعية الدقيقة\n\n")
    md.append("| المقياس | قبل التحسين | بعد التحسين | التطور |\n")
    md.append("| :--- | :---: | :---: | :---: |\n")
    sub_labels = {
        "arabic_ratio": "نسبة التعريب (Arabic Ratio)",
        "glossary": "تطابق المصطلحات (Glossary Match)",
        "paragraph_alignment": "محاذاة الفقرات (Paragraph Alignment)",
        "length_ratio": "تناسب الطول (Length Ratio)",
        "no_duplicates": "خلو من التكرار (No Duplicates)",
    }
    for k, label in sub_labels.items():
        bv = b_sub.get(k, 0)
        av = a_sub.get(k, 0)
        d = av - bv
        md.append(f"| {label} | {bv:.1f}% | {av:.1f}% | {'+' if d>=0 else ''}{d:.1f}% |\n")

    content = "".join(md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(content)

    print("\n" + "=" * 80)
    print(" 📈 تقرير مقارنة التحسين (Quality Delta Report):")
    print("=" * 80)
    print(f" • متوسط الجودة السابق: {b_avg:.1f}%")
    print(f" • متوسط الجودة الحالي: {a_avg:.1f}%")
    print(f" • صافي التطور: {delta_sign}{delta_avg:.1f}%")
    print(f" [✓] تم حفظ التقرير المقارن في: {output_md.resolve()}")
    print("=" * 80)

    return content


if __name__ == "__main__":
    b_file = Path("output/smart_quality_report_before.json")
    if not b_file.exists():
        b_file = Path("output/smart_quality_report.json")
    a_file = Path("output/smart_quality_report.json")
    out_file = Path("output/quality_improvement_delta.md")

    generate_comparison(b_file, a_file, out_file)
