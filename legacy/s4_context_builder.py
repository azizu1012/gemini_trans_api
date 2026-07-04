"""
s4_context_builder.py - Tạo context tổng hợp cho S4 dựa trên các cumulative và chương cuối S2/S3
"""
import os

def read_cumulative_summaries(memory_store_dir):
    """Đọc và ghép tất cả các file cumulative thành 1 tóm tắt lớn"""
    summaries = []
    for fname in sorted(os.listdir(memory_store_dir)):
        if fname.startswith('cumulative_') and fname.endswith('.txt'):
            with open(os.path.join(memory_store_dir, fname), 'r', encoding='utf-8') as f:
                summaries.append(f.read().strip())
    return '\n\n'.join(summaries)

def read_last_chapters(temp_chapters_dir, chapter_files):
    """Đọc nội dung các chương cuối (S2, S3) theo danh sách file"""
    chapters = []
    for fname in chapter_files:
        path = os.path.join(temp_chapters_dir, fname)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                chapters.append(f.read().strip())
    return '\n\n'.join(chapters)

def build_s4_context(memory_store_dir, temp_chapters_dir, last_chap_files):
    """Ghép tóm tắt cumulative + các chương cuối thành context cho S4"""
    summary = read_cumulative_summaries(memory_store_dir)
    last_chaps = read_last_chapters(temp_chapters_dir, last_chap_files)
    context = f"""
# TÓM TẮT TOÀN TRUYỆN
{summary}

# CÁC CHƯƠNG CUỐI S2/S3
{last_chaps}
"""
    return context
