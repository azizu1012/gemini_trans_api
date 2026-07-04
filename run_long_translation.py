import os
import re
import sys
import asyncio
import time
import traceback

from refactor_oop_gemini_trans_api.config.config import TranslatorConfig
from refactor_oop_gemini_trans_api.workflow.workflow_v3 import WorkflowV3Runner
from refactor_oop_gemini_trans_api.data.content_loader import ContentLoader, ContentMerger
from refactor_oop_gemini_trans_api.output.ebook_maker import EbookMaker

async def main():
    print("====================================================")
    print("🚀 BẮT ĐẦU DỊCH TRUYỆN TOÀN BỘ VÀ XUẤT EBOOK PDF")
    print("====================================================")
    
    cfg = TranslatorConfig()
    cfg.load_api_config()
    cfg.max_threads = 5  # Sử dụng 5 luồng dịch song song để tăng tốc độ
    
    print(f"🔗 API Endpoint: {cfg.api_endpoint}")
    print(f"🧠 Architect Model: {cfg.model_architect}")
    print(f"✍️  Writer Model: {cfg.model_writer}")
    print(f"🔍 Critic Model: {cfg.model_critic}")
    print(f"⚙️  Số luồng tối đa: {cfg.max_threads}")
    print(f"📄 Lite Critic: {cfg.lite_critic}")
    print("-" * 52)
    
    # 1. Tải toàn bộ danh sách chương từ raw file
    print("⏳ Đang tải và phân tích dữ liệu chương raw...")
    loader = ContentLoader(cfg)
    all_chapters = loader.match_chapters()
    if not all_chapters:
        print("❌ LỖI: Không tìm thấy chương nào trong file raw!")
        sys.exit(1)
        
    print(f"📚 Đã tải thành công {len(all_chapters)} chương từ raw.")
    
    # 2. Lọc ra các chương chưa dịch trong dải từ 1 đến 604
    translated_dir = os.path.join(cfg.temp_folder, 'translated')
    os.makedirs(translated_dir, exist_ok=True)
    
    chapters_to_translate = []
    skipped_count = 0
    for ch in all_chapters:
        temp_file = os.path.join(translated_dir, f"chap_{ch.index:04d}.txt")
        # Check if file exists and has content
        if os.path.exists(temp_file):
            try:
                with open(temp_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if len(content) > 50 and not "[QA_STATUS: FAILED" in content:
                    skipped_count += 1
                    continue
            except Exception:
                pass
        chapters_to_translate.append(ch)
        
    print(f"⏭️  Đã có {skipped_count} chương đã dịch trước đó (sẽ bỏ qua).")
    print(f"🎯 Cần dịch mới: {len(chapters_to_translate)} chương.")
    print("-" * 52)
    
    if chapters_to_translate:
        runner = WorkflowV3Runner(cfg)
        runner.translator.all_raw_chapters = all_chapters
        start_time = time.time()
        
        print(f"🔥 Khởi chạy dịch tự động cho {len(chapters_to_translate)} chương...")
        try:
            success, total = await runner.run_async(chapters_to_translate)
            elapsed = time.time() - start_time
            print("-" * 52)
            print(f"🎉 Hoàn thành dịch thuật trong {elapsed/60:.1f} phút!")
            print(f"✅ Kết quả dịch: {success}/{total} chương thành công.")
        except Exception as e:
            print(f"❌ LỖI TRONG QUÁ TRÌNH DỊCH TỰ ĐỘNG: {e}")
            traceback.print_exc()
            sys.exit(1)
    else:
        print("✅ Tất cả các chương đã được dịch xong từ trước!")
        
    # 3. Tiến hành gộp chương và biên soạn PDF Ebook
    print("-" * 52)
    print("⏳ Bắt đầu biên soạn Ebook PDF (A5 Times New Roman)...")
    
    # Gộp tất cả chương đã dịch thành file output duy nhất trước
    print("⏳ Đang gộp các chương đã dịch...")
    merger = ContentMerger(cfg)
    output_content = merger.merge_chapters()
    if not output_content:
        print("❌ LỖI: Không có nội dung chương đã dịch để gộp!")
        sys.exit(1)
        
    os.makedirs(os.path.dirname(cfg.output_file), exist_ok=True)
    with open(cfg.output_file, 'w', encoding='utf-8') as f:
        f.write(output_content)
    print(f"✅ Đã lưu file gộp tại: {cfg.output_file}")
    
    # Render PDF
    maker = EbookMaker(cfg)
    pdf_success = maker.build_pdf()
    
    print("-" * 52)
    if pdf_success:
        print("🎉 XUẤT FILE EBOOK PDF THÀNH CÔNG!")
        print(f"📂 File PDF: {maker.output_pdf_path}")
    else:
        print("❌ LỖI: Xuất PDF thất bại! Vui lòng kiểm tra log lỗi.")
        sys.exit(1)
    print("====================================================")

if __name__ == "__main__":
    asyncio.run(main())
