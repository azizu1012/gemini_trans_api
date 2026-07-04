#!/usr/bin/env python3
"""
main_s4.py - Entry point sinh ngoại truyện S4 (hậu truyện) với cấu trúc tam quyền
"""
import os
from s4_context_builder import build_s4_context
from s4_director import S4Director

# Đường dẫn thư mục
BASE = os.path.dirname(os.path.abspath(__file__))
MEMORY_STORE = os.path.join(BASE, 'output', 'memory_store')
TEMP_CHAPS = os.path.join(BASE, 'output', 'temp_chapters')

# Các file chương cuối S2/S3 (có thể mở rộng)
LAST_CHAPS = [
    'extra_S3_11.txt',
    # Thêm các chương khác nếu cần
]

# Danh sách nhân vật chính/phụ (có thể tự động lấy từ memory hoặc nhập tay)
MAIN_CHARACTERS = [
    'Lâm Nhất', 'Anna', 'Giang Thần', 'Allan', 'Lục Lâm Hải', 'Trương Thành', 'Chu Vân', 'Tinh Thành Đạo',
    # ...
]

# Danh sách địa điểm chính (có thể tự động lấy từ memory hoặc nhập tay)
LOCATIONS = [
    'Khu Tái Sinh', 'Miền Đất Hứa', 'Kuwait', 'dãy núi phía Tây',
    # ...
]


def main():
    print("==== S4 GENERATOR (HẬU TRUYỆN) ====")
    # 1. Build context
    context = build_s4_context(MEMORY_STORE, TEMP_CHAPS, LAST_CHAPS)
    # 2. Director lập outline
    director = S4Director(context, MAIN_CHARACTERS, LOCATIONS)
    outline = director.build_outline()
    print("\n--- OUTLINE S4 ---\n")
    print(outline)
    # 3. Sinh prompt cho writer
    prompt = director.get_writer_prompt(outline)
    print("\n--- PROMPT CHO WRITER ---\n")
    print(prompt)

    # 4. Gọi workflow_s4 để sinh ngoại truyện S4 hoàn chỉnh
    from workflow_s4 import S4WorkflowRunner
    from core import TranslatorConfig
    config = TranslatorConfig()  # Có thể cần chỉnh lại config nếu muốn custom
    runner = S4WorkflowRunner(config, outline, prompt)
    result = runner.run_s4()
    if result.status == "SUCCESS":
        print("\n--- NGOẠI TRUYỆN S4 HOÀN CHỈNH ---\n")
        print(result.translated_text)
    else:
        print(f"\n❌ LỖI: {result.error_message}")

if __name__ == "__main__":
    main()
