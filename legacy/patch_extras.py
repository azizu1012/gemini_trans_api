#!/usr/bin/env python3
"""
Patch Extras - Migrate file extra cũ sang định dạng mới

File cũ: extra_001.txt, extra_002.txt, ...
File mới: chap_055_extra_001.txt (sau chương 55)

Logic:
1. Đọc EXTRA_CHAPTERS để biết vị trí chèn của từng extra
2. Rename extra_XXX.txt → chap_YYY_extra_XXX.txt
"""

import os
import re
import shutil
from typing import Dict

# Import EXTRA_CHAPTERS
try:
    from expansion_engine import EXTRA_CHAPTERS
except ImportError:
    from .expansion_engine import EXTRA_CHAPTERS

# Config
TEMP_FOLDER = os.path.join(os.path.dirname(__file__), "output", "temp_chapters")


def build_extra_position_map() -> Dict[int, int]:
    """
    Build map: extra_index → insert_after_chapter
    Ví dụ: {1: 55, 2: 105, ...}
    """
    position_map = {}
    for extra in EXTRA_CHAPTERS:
        position_map[extra.index] = extra.best_insertion_point
    return position_map


def scan_old_extras() -> list:
    """Tìm tất cả file extra cũ (extra_XXX.txt)"""
    old_extras = []
    for f in os.listdir(TEMP_FOLDER):
        match = re.match(r'extra_(\d+)\.txt', f)
        if match:
            extra_idx = int(match.group(1))
            old_extras.append((extra_idx, f))
    return sorted(old_extras)


def patch_extras(dry_run: bool = True):
    """
    Migrate file extra cũ sang định dạng mới
    
    Args:
        dry_run: True để chỉ xem preview, False để thực hiện
    """
    position_map = build_extra_position_map()
    old_extras = scan_old_extras()
    
    if not old_extras:
        print("✅ Không có file extra cũ cần patch")
        return
    
    print(f"📋 Tìm thấy {len(old_extras)} file extra cũ:")
    
    renamed = 0
    skipped = 0
    not_found = 0
    
    for extra_idx, old_name in old_extras:
        old_path = os.path.join(TEMP_FOLDER, old_name)
        
        if extra_idx in position_map:
            insert_after = position_map[extra_idx]
            new_name = f"chap_{insert_after:04d}_extra_{extra_idx:03d}.txt"
            new_path = os.path.join(TEMP_FOLDER, new_name)
            
            # Kiểm tra file mới đã tồn tại chưa
            if os.path.exists(new_path):
                print(f"  ⏩ {old_name} → {new_name} (đã tồn tại, skip)")
                skipped += 1
            else:
                print(f"  🔄 {old_name} → {new_name}")
                if not dry_run:
                    shutil.move(old_path, new_path)
                renamed += 1
        else:
            print(f"  ⚠️ {old_name} - Không tìm thấy vị trí chèn trong EXTRA_CHAPTERS")
            not_found += 1
    
    print()
    if dry_run:
        print(f"📊 Preview: {renamed} sẽ được rename, {skipped} skip, {not_found} không tìm thấy vị trí")
        print("💡 Chạy lại với --apply để thực hiện")
    else:
        print(f"✅ Đã rename: {renamed} file, {skipped} skip, {not_found} không tìm thấy vị trí")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Patch extras - migrate file extra cũ")
    parser.add_argument('--apply', action='store_true', help='Thực hiện rename (mặc định chỉ preview)')
    parser.add_argument('--list', action='store_true', help='Liệt kê vị trí chèn từ EXTRA_CHAPTERS')
    args = parser.parse_args()
    
    if args.list:
        print("📋 EXTRA_CHAPTERS positions:")
        position_map = build_extra_position_map()
        for idx, pos in sorted(position_map.items()):
            extra = next((e for e in EXTRA_CHAPTERS if e.index == idx), None)
            title = extra.title if extra else "???"
            print(f"  Extra {idx:3d}: sau chương {pos:3d} - {title}")
        return
    
    patch_extras(dry_run=not args.apply)


if __name__ == "__main__":
    main()
