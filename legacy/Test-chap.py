
import re
import os

def count_chapters(file_path):
    chapter_count = 0
    extra_count = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if re.match(r'^### Chương \d+: .+\s*###$', line.strip()):
                    chapter_count += 1
                elif re.match(r'^### Ngoại truyện: .+\s*###$', line.strip()):
                    extra_count += 1
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file tại đường dẫn: {file_path}")
        return 0, 0
    
    return chapter_count, extra_count

if __name__ == "__main__":
    file_to_count = os.path.join(os.path.dirname(__file__), "Truyen_Dich_Hoan_Chinh.txt")
    main_chapters, extra_chapters = count_chapters(file_to_count)
    
    print(f"Tổng số chương chính: {main_chapters}")
    print(f"Tổng số ngoại truyện: {extra_chapters}")
