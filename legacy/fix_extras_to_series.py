"""
Script để rename các file ngoại truyện về format series

Ngoại truyện có 3 chuỗi (từ Danh_sach_ten_chuong.txt):
1. Trương thành truyền (1-21): extra_001 đến extra_021
2. Phụ hướng kết cục thiên (1-15): extra_022 đến extra_036  
3. Đang hướng kết cục thiên (1-11): extra_037 đến extra_047

Format mới: extra_S{series}_{chapter_in_series}.txt
Ví dụ:
- extra_001.txt → extra_S1_01.txt (Trương thành truyền, chương 1)
- extra_022.txt → extra_S2_01.txt (Phụ hướng kết cục thiên, chương 1)
- extra_037.txt → extra_S3_01.txt (Đang hướng kết cục thiên, chương 1)
"""

import os
import re
import glob

TEMP_FOLDER = r"C:\Users\Azuree\Documents\Code-make-novel\Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật\refactor_oop_gemini_trans_api\output\temp_chapters"

# Mapping extra index → (series, chapter trong series)
# Series 1: Trương thành truyền (extra 1-21)
# Series 2: Phụ hướng kết cục thiên (extra 22-36)
# Series 3: Đang hướng kết cục thiên (extra 37-47)

def get_series_info(extra_index: int) -> tuple:
    """
    Trả về (series_num, chapter_in_series) từ extra index
    
    Extra 1-21 → Series 1, chapter 1-21
    Extra 22-36 → Series 2, chapter 1-15
    Extra 37-47 → Series 3, chapter 1-11
    """
    if 1 <= extra_index <= 21:
        return (1, extra_index)
    elif 22 <= extra_index <= 36:
        return (2, extra_index - 21)  # 22→1, 23→2, ...
    elif 37 <= extra_index <= 47:
        return (3, extra_index - 36)  # 37→1, 38→2, ...
    else:
        return None

def extract_extra_index(filename: str) -> int:
    """Lấy extra index từ filename"""
    basename = os.path.basename(filename)
    
    # Pattern 1: chap_XXXX_extra_YYY.txt
    match = re.match(r'chap_\d+_extra_(\d+)\.txt', basename)
    if match:
        return int(match.group(1))
    
    # Pattern 2: extra_YYY.txt
    match = re.match(r'extra_(\d+)\.txt', basename)
    if match:
        return int(match.group(1))
    
    return None

def main():
    print("=" * 60)
    print("FIX EXTRAS TO SERIES FORMAT")
    print("=" * 60)
    
    # Tìm tất cả file extra
    all_files = glob.glob(os.path.join(TEMP_FOLDER, "*.txt"))
    extra_files = []
    
    for f in all_files:
        basename = os.path.basename(f)
        if 'extra' in basename:
            extra_files.append(f)
    
    print(f"\n📁 Tìm thấy {len(extra_files)} file extra\n")
    
    renamed = 0
    skipped = 0
    errors = 0
    
    for filepath in sorted(extra_files):
        basename = os.path.basename(filepath)
        extra_idx = extract_extra_index(filepath)
        
        if extra_idx is None:
            print(f"⚠️ Không parse được: {basename}")
            errors += 1
            continue
        
        series_info = get_series_info(extra_idx)
        
        if series_info is None:
            print(f"⚠️ Extra {extra_idx} không thuộc series nào: {basename}")
            errors += 1
            continue
        
        series_num, chapter_in_series = series_info
        new_name = f"extra_S{series_num}_{chapter_in_series:02d}.txt"
        new_path = os.path.join(TEMP_FOLDER, new_name)
        
        if os.path.exists(new_path) and new_path != filepath:
            print(f"⚠️ Đã tồn tại: {new_name}, skip {basename}")
            skipped += 1
            continue
        
        if basename == new_name:
            print(f"✓ Đã đúng format: {basename}")
            skipped += 1
            continue
        
        # Rename
        os.rename(filepath, new_path)
        print(f"✅ {basename} → {new_name}")
        renamed += 1
    
    print("\n" + "=" * 60)
    print(f"KẾT QUẢ: {renamed} renamed, {skipped} skipped, {errors} errors")
    print("=" * 60)
    
    # Kiểm tra file mới
    print("\n📋 Danh sách file extra sau khi rename:")
    new_files = sorted(glob.glob(os.path.join(TEMP_FOLDER, "extra_S*.txt")))
    for f in new_files:
        print(f"   {os.path.basename(f)}")

if __name__ == "__main__":
    main()
