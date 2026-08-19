import sys
import time
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

from config import Config
from organize_volumes import get_volume_dir

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class CometNovelEvaluator:
    """
    Evaluates translation quality using Unbabel's State-of-the-Art COMET-Kiwi
    Quality Estimation (QE) neural model without requiring human reference translations.
    """

    DEFAULT_MODEL = "Unbabel/wmt20-comet-qe-da"

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.model = None
        self.device = "cuda" if self._has_cuda() else "cpu"

    def _has_cuda(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def load_model(self):
        """Load COMET model from checkpoint."""
        if self.model is not None:
            return

        from comet import download_model, load_from_checkpoint
        print("=" * 75)
        print(f" 🚀 جاري تحميل نموذج التقييم العالمي Unbabel / COMET...")
        print(f" • النموذج: {self.model_name}")
        print(f" • المعالج المستخدم: {'CUDA (كرت الشاشة GPU ⚡)' if self.device == 'cuda' else 'CPU (المعالج المركزي)'}")
        print("=" * 75)

        model_path = download_model(self.model_name)
        self.model = load_from_checkpoint(model_path)
        print("[✓] تم تحميل نموذج COMET بنجاح وجاهز للتقييم العصبوني الفوري!\n")

    def find_file(self, base_dir: Path, chapter_num: int) -> Path:
        vol_path = get_volume_dir(base_dir, chapter_num) / f"chapter_{chapter_num:04d}.txt"
        if vol_path.exists():
            return vol_path
        return base_dir / f"chapter_{chapter_num:04d}.txt"

    def evaluate_chapter(self, chapter_num: int) -> Dict[str, Any]:
        """Evaluate semantic translation quality of a single chapter."""
        self.load_model()

        raw_file = self.find_file(Config.RAW_EN_DIR, chapter_num)
        trans_file = self.find_file(Config.TRANSLATED_AR_DIR, chapter_num)

        if not raw_file.exists() or not trans_file.exists():
            return {"chapter": chapter_num, "status": "error", "error": "Chapter files not found"}

        with open(raw_file, "r", encoding="utf-8") as f:
            raw_text = f.read()

        with open(trans_file, "r", encoding="utf-8") as f:
            trans_text = f.read()

        raw_paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip() and not p.startswith("#")]
        trans_paragraphs = [p.strip() for p in trans_text.split("\n\n") if p.strip() and not p.startswith("#")]

        # Align paragraphs
        min_len = min(len(raw_paragraphs), len(trans_paragraphs))
        if min_len == 0:
            return {"chapter": chapter_num, "status": "error", "error": "Empty chapter content"}

        eval_data = [
            {"src": raw_paragraphs[i], "mt": trans_paragraphs[i]}
            for i in range(min_len)
        ]

        # Run COMET prediction
        gpus = 1 if self.device == "cuda" else 0
        accelerator = "cuda" if self.device == "cuda" else "cpu"
        prediction = self.model.predict(
            eval_data,
            batch_size=8,
            gpus=gpus,
            accelerator=accelerator,
            progress_bar=False,
        )

        segment_scores = prediction.scores
        system_score = prediction.system_score

        # COMET-Kiwi DA direct assessment score normalized to percentage (0 - 100%)
        normalized_score = round(system_score * 100, 1)

        low_quality_segments = []
        for idx, score in enumerate(segment_scores):
            if score < 0.65:
                low_quality_segments.append({
                    "paragraph_index": idx + 1,
                    "score": round(score * 100, 1),
                    "src": raw_paragraphs[idx][:150] + "...",
                    "mt": trans_paragraphs[idx][:150] + "...",
                })

        return {
            "chapter": chapter_num,
            "status": "success",
            "comet_score": normalized_score,
            "raw_comet_system_score": round(system_score, 4),
            "paragraphs_evaluated": min_len,
            "low_quality_count": len(low_quality_segments),
            "low_quality_samples": low_quality_segments[:3],
        }

    def run_evaluation_suite(self, chapters: List[int], output_report: bool = True) -> List[Dict[str, Any]]:
        """Run COMET evaluation on a list of chapters and generate reports."""
        self.load_model()

        print("=" * 80)
        print(f" 📊 بدء فحص جودة الترجمة الدلالية بنموذج Unbabel COMET-Kiwi ({len(chapters)} فصول)")
        print("=" * 80)

        results = []
        for cnum in chapters:
            t0 = time.time()
            res = self.evaluate_chapter(cnum)
            elapsed = time.time() - t0

            if res["status"] == "success":
                score = res["comet_score"]
                status_icon = "🟢" if score >= 80 else ("🟡" if score >= 65 else "🔴")
                print(
                    f" {status_icon} الفصل {cnum:04d}: درجة COMET = {score}% | تم تقييم {res['paragraphs_evaluated']} فقرة في {elapsed:.1f}ث"
                )
                if res["low_quality_count"] > 0:
                    print(f"    ⚠️ تم اكتشاف {res['low_quality_count']} فقرة ذات تقييم منخفض قد تحتاج مراجعة.")
                results.append(res)
            else:
                print(f" ❌ الفصل {cnum:04d}: فشل التقييم ({res.get('error')})")

        if results and output_report:
            avg_comet = sum(r["comet_score"] for r in results) / len(results)
            print("\n" + "=" * 80)
            print(" 🏆 التقرير الإجمالي لجودة الرواية (COMET-Kiwi Quality Assessment):")
            print("=" * 80)
            print(f" • متوسط تقييم COMET الدلالي: {avg_comet:.1f}%")
            if avg_comet >= 80:
                verdict = "ممتازة واحترافية جداً (Excellent Quality)"
            elif avg_comet >= 70:
                verdict = "جيدة جداً ومطابقة للأصل (Very Good Quality)"
            else:
                verdict = "مقبولة وتتطلب بعض التحسينات (Needs Review)"
            print(f" • التصنيف العالمي للجودة: {verdict}")
            print("=" * 80)

            # Save JSON report
            report_json = Path("output/comet_quality_report.json")
            report_json.parent.mkdir(parents=True, exist_ok=True)
            with open(report_json, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "model": self.model_name,
                        "average_score": round(avg_comet, 2),
                        "verdict": verdict,
                        "chapters_evaluated": len(results),
                        "details": results,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            # Save Markdown report
            report_md = Path("output/comet_quality_report.md")
            with open(report_md, "w", encoding="utf-8") as f:
                f.write("# تقرير جودة الترجمة العصبي (Unbabel / COMET-Kiwi Evaluation Report)\n\n")
                f.write(f"- **النموذج المستخدم:** `{self.model_name}`\n")
                f.write(f"- **المتوسط العام للجودة:** **{avg_comet:.1f}%**\n")
                f.write(f"- **التقييم:** {verdict}\n")
                f.write(f"- **عدد الفصول المفحوصة:** {len(results)}\n\n")
                f.write("## تفاصيل تقييم الفصول المفحوصة\n\n")
                f.write("| الفصل | درجة COMET | عدد الفقرات المفحوصة | الفقرات التي تحتاج تحسين | الحالة |\n")
                f.write("| :---: | :---: | :---: | :---: | :---: |\n")
                for r in results:
                    score = r["comet_score"]
                    icon = "🟢 ممتاز" if score >= 80 else ("🟡 جيد" if score >= 65 else "🔴 يحتاج تدقيق")
                    f.write(f"| الفصل {r['chapter']:04d} | {score}% | {r['paragraphs_evaluated']} | {r['low_quality_count']} | {icon} |\n")

            print(f"\n[✓] تم حفظ التقرير المفصل JSON: {report_json.resolve()}")
            print(f"[✓] تم حفظ تقرير Markdown: {report_md.resolve()}")

        return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate novel translation quality using Unbabel COMET.")
    parser.add_argument("--chapters", nargs="+", type=int, help="Specific chapter numbers to evaluate.")
    parser.add_argument("--start", type=int, help="Start chapter number.")
    parser.add_argument("--end", type=int, help="End chapter number.")
    parser.add_argument("--sample", action="store_true", help="Run on representative sample chapters across all 5 volumes.")

    args = parser.parse_args()
    evaluator = CometNovelEvaluator()

    if args.chapters:
        chaps = args.chapters
    elif args.start and args.end:
        chaps = list(range(args.start, args.end + 1))
    else:
        # Default sample covering early, middle, and late volumes (V1 through V5)
        chaps = [1, 5, 250, 500, 750, 1000, 1020, 1500, 1800, 2000, 2334]

    evaluator.run_evaluation_suite(chaps)


if __name__ == "__main__":
    main()
