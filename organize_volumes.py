import shutil
import re
from pathlib import Path
from config import Config


def organize_into_volumes():
    """
    Organizes all translated chapters into 5 clean volume directories
    to avoid GitHub's 1,000-file per directory display limit.
    """
    Config.init_directories()
    trans_dir = Config.TRANSLATED_AR_DIR
    files = list(trans_dir.glob("chapter_*.txt"))

    if not files:
        print("[!] لم يتم العثور على فصول مترجمة لتنظيمها.")
        return

    print(f"[*] جاري تنظيم {len(files)} فصلاً في مجلدات أجزاء مرتبة...")

    volume_ranges = [
        (1, 500, "Volume_1 (الفصول 0001 - 0500)"),
        (501, 1000, "Volume_2 (الفصول 0501 - 1000)"),
        (1001, 1500, "Volume_3 (الفصول 1001 - 1500)"),
        (1501, 2000, "Volume_4 (الفصول 1501 - 2000)"),
        (2001, 2500, "Volume_5 (الفصول 2001 - 2334)"),
    ]

    for start_num, end_num, vol_name in volume_ranges:
        vol_dir = trans_dir / vol_name
        vol_dir.mkdir(parents=True, exist_ok=True)

    moved_count = 0
    for f in files:
        m = re.search(r"chapter_(\d+)", f.name)
        if not m:
            continue
        cnum = int(m.group(1))

        for start_num, end_num, vol_name in volume_ranges:
            if start_num <= cnum <= end_num:
                target_dir = trans_dir / vol_name
                target_path = target_dir / f.name
                shutil.move(str(f), str(target_path))
                moved_count += 1
                break

    print(f"[✓] تم تنظيم وتوزيع {moved_count} فصلاً في 5 مجلدات بنجاح!")


if __name__ == "__main__":
    organize_into_volumes()
