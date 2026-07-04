import re
import os
from pathlib import Path

def fix_chapter_format(file_path):
    """
    Sửa định dạng tiêu đề chương theo chuẩn:
    - ### Chương XXX: Title ###
    - ### Ngoại truyện: Title ###
    Nếu thiếu ### ở cuối, sẽ tự động thêm vào
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return False, "File trống"
        
        first_line = lines[0].strip()
        
        # Regex để check định dạng chuẩn
        standard_chapter = re.compile(r'^### Chương \d+: .+\s*###$')
        standard_extra = re.compile(r'^### (?:Ngoại truyện|Phiên ngoại|Phiên Ngoại): .+\s*###$')
        
        # Nếu đã đúng định dạng, không cần sửa
        if standard_chapter.match(first_line) or standard_extra.match(first_line):
            return False, "Đã đúng định dạng"
        
        # Regex để tìm dòng bắt đầu bằng "### Chương"
        chapter_pattern = re.compile(r'^### (Chương \d+): (.+?)(?:\s*###)?$')
        extra_pattern = re.compile(r'^### ((?:Ngoại truyện|Phiên ngoại|Phiên Ngoại)): (.+?)(?:\s*###)?$')
        
        match = chapter_pattern.match(first_line)
        if match:
            # Chương chính
            prefix = match.group(1)
            title = match.group(2).strip()
            new_first_line = f"### {prefix}: {title} ###\n"
            lines[0] = new_first_line
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return True, f"Sửa từ: {first_line[:80]}"
        
        # Kiểm tra ngoại truyện
        match = extra_pattern.match(first_line)
        if match:
            # Ngoại truyện
            prefix = match.group(1)
            title = match.group(2).strip()
            new_first_line = f"### {prefix}: {title} ###\n"
            lines[0] = new_first_line
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return True, f"Sửa từ: {first_line[:80]}"
        
        return False, f"Không tìm được định dạng Chương"
    
    except Exception as e:
        return False, str(e)

def scan_and_fix_all(directory, test_mode=False):
    """
    Quét tất cả file chương và sửa những file có lỗi
    test_mode=True: chỉ quét, không sửa
    """
    standard_chapter = re.compile(r'^### Chương \d+: .+\s*###$')
    standard_extra = re.compile(r'^### (?:Ngoại truyện|Phiên ngoại|Phiên Ngoại): .+\s*###$')
    
    files = sorted([f for f in os.listdir(directory) if f.startswith(('chap_', 'extra_')) and f.endswith('.txt')])
    
    incorrect_files = []
    fixed_count = 0
    
    print(f"Tổng số file: {len(files)}")
    print("-" * 80)
    
    for chap_file in files:
        file_path = os.path.join(directory, chap_file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        
        if not (standard_chapter.match(first_line) or standard_extra.match(first_line)):
            incorrect_files.append(chap_file)
            
            if not test_mode:
                success, msg = fix_chapter_format(file_path)
                if success:
                    fixed_count += 1
                    print(f"✓ {chap_file}: {msg}")
                else:
                    print(f"✗ {chap_file}: {msg}")
    
    print("-" * 80)
    print(f"Tổng file có lỗi: {len(incorrect_files)}")
    if not test_mode:
        print(f"Đã sửa: {fixed_count} file")
    
    if incorrect_files and test_mode:
        print("\nDanh sách file có lỗi (test mode):")
        for f in incorrect_files[:20]:
            print(f"  - {f}")
        if len(incorrect_files) > 20:
            print(f"  ... và {len(incorrect_files) - 20} file khác")
    
    return incorrect_files, fixed_count

if __name__ == "__main__":
    current_dir = os.path.dirname(__file__)
    temp_dir = os.path.join(current_dir, "temp_chapters")
    
    print("=" * 80)
    print("QUÉT ĐỊNH DẠNG CÁC FILE CHƯƠNG (Test Mode)")
    print("=" * 80)
    
    # Test mode first
    incorrect, _ = scan_and_fix_all(temp_dir, test_mode=True)
    
    print("\n" + "=" * 80)
    print("SỬA ĐỊNH DẠNG TẤT CẢ FILE CÓ LỖI")
    print("=" * 80)
    
    # Fix all
    _, fixed = scan_and_fix_all(temp_dir, test_mode=False)
    
    print("\n" + "=" * 80)
    print(f"Hoàn thành! Đã sửa {fixed} file.")
    print("=" * 80)
