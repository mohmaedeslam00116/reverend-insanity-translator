import sys
from pathlib import Path
from config import Config


def compile_translated_chapters(output_filename: str = "Reverend_Insanity_Arabic_Complete.md"):
    """
    Combines all individual translated chapter files into a single ordered book file.
    """
    Config.init_directories()
    chapter_files = sorted(Config.TRANSLATED_AR_DIR.glob("chapter_*.txt"))

    if not chapter_files:
        print("[!] لم يتم العثور على فصول مترجمة لدمجها.")
        return

    output_path = Config.OUTPUT_DIR / output_filename
    print(f"[*] جاري دمج {len(chapter_files)} فصلاً في ملف واحد: {output_path.name}...")

    with open(output_path, "w", encoding="utf-8") as outfile:
        outfile.write("# رواية Reverend Insanity (القس المجنون / Gu Zhen Ren)\n")
        outfile.write("### الترجمة الأدبية العربية الفصحى\n\n")
        outfile.write("---\n\n")

        for cfile in chapter_files:
            try:
                with open(cfile, "r", encoding="utf-8") as infile:
                    content = infile.read()
                    outfile.write(content.strip() + "\n\n---\n\n")
            except Exception as e:
                print(f"[!] خطأ أثناء قراءة {cfile.name}: {e}")

    print(f"[✓] تم إنشاء الكتاب المجمع بنجاح في: {output_path.resolve()}")


if __name__ == "__main__":
    compile_translated_chapters()
