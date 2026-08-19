import shutil
import re
from pathlib import Path
from config import Config

VOLUME_RANGES = [
    (1, 500, "Volume_1 (Chapters 0001 - 0500)"),
    (501, 1000, "Volume_2 (Chapters 0501 - 1000)"),
    (1001, 1500, "Volume_3 (Chapters 1001 - 1500)"),
    (1501, 2000, "Volume_4 (Chapters 1501 - 2000)"),
    (2001, 2500, "Volume_5 (Chapters 2001 - 2334)"),
]


def get_volume_dir(base_dir: Path, chapter_num: int) -> Path:
    """Return the proper volume subfolder for a given chapter number."""
    for start_num, end_num, vol_name in VOLUME_RANGES:
        if start_num <= chapter_num <= end_num:
            target = base_dir / vol_name
            target.mkdir(parents=True, exist_ok=True)
            return target
    target = base_dir / "Volume_Other"
    target.mkdir(parents=True, exist_ok=True)
    return target


def organize_directory(base_dir: Path):
    """Move all loose chapter_XXXX.txt files in base_dir into their volume subfolders."""
    if not base_dir.exists():
        return 0

    files = list(base_dir.glob("chapter_*.txt"))
    moved = 0
    for f in files:
        m = re.search(r"chapter_(\d+)", f.name)
        if not m:
            continue
        cnum = int(m.group(1))
        target_dir = get_volume_dir(base_dir, cnum)
        target_path = target_dir / f.name
        shutil.move(str(f), str(target_path))
        moved += 1
    return moved


def organize_all():
    Config.init_directories()
    print("=" * 70)
    print(" 🗂️ تنظيم الفصول في مجلدات أجزاء (Volumes)")
    print("=" * 70)

    trans_moved = organize_directory(Config.TRANSLATED_AR_DIR)
    print(f" • تم تنظيم {trans_moved} فصلاً مترجماً في مجلدات الأجزاء (output/translated_ar/Volume_X).")

    raw_moved = organize_directory(Config.RAW_EN_DIR)
    print(f" • تم تنظيم {raw_moved} فصلاً خام في مجلدات الأجزاء (output/raw_en/Volume_X).")
    print("=" * 70)


if __name__ == "__main__":
    organize_all()
