import os
import re

# Đường dẫn thư mục chứa các chương
TEMP_CHAPTERS = r"c:\Users\Azuree\Documents\Code-make-novel\Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật\refactor_oop_gemini_trans_api\output\temp_chapters"

# Đường dẫn thư mục chứa các chương và tóm tắt
TEMP_CHAPTERS = r"c:\Users\Azuree\Documents\Code-make-novel\Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật\refactor_oop_gemini_trans_api\output\temp_chapters"
MEMORY_STORE = r"c:\Users\Azuree\Documents\Code-make-novel\Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật\refactor_oop_gemini_trans_api\output\memory_store"

# Lấy danh sách file chương
files = os.listdir(TEMP_CHAPTERS)

# Tìm các file chương gốc (không có _1, _2...)
base_chaps = [f for f in files if re.match(r"chap_\d{4}\.txt$", f)]

# Xác định các chương đã được mở rộng (có file _1, _2...)
extended_chaps = set()
for f in files:
    m = re.match(r"chap_(\d{4})_\d+\.txt$", f)
    if m:
        extended_chaps.add(m.group(1))

# Xóa các file chương gốc chưa được mở rộng (không có file _1, _2...)
deleted = []
deleted_nums = []
for f in base_chaps:
    chap_num = re.match(r"chap_(\d{4})\.txt$", f).group(1)
    if chap_num not in extended_chaps:
        path = os.path.join(TEMP_CHAPTERS, f)
        os.remove(path)
        deleted.append(f)
        deleted_nums.append(chap_num)

# Xóa các file tóm tắt tương ứng
summary_deleted = []
if os.path.exists(MEMORY_STORE):
    for fname in os.listdir(MEMORY_STORE):
        m = re.match(r"cumulative_(\d+)\.txt$", fname)
        if m and m.group(1).zfill(4) in deleted_nums:
            os.remove(os.path.join(MEMORY_STORE, fname))
            summary_deleted.append(fname)

print(f"Đã xóa {len(deleted)} file chương gốc chưa mở rộng:")
for f in deleted:
    print(f"  - {f}")
if summary_deleted:
    print(f"\nĐã xóa {len(summary_deleted)} file tóm tắt tương ứng:")
    for f in summary_deleted:
        print(f"  - {f}")
else:
    print("\nKhông có file tóm tắt nào cần xóa.")

print(f"Đã xóa {len(deleted)} file chương gốc chưa mở rộng:")
for f in deleted:
    print(f"  - {f}")
