#!/usr/bin/env python3
"""
Main Entry Point - Gemini Translator OOP Version
Tích hợp: V3.5 GUI Framework + OneShot Brain + Dynamic Glossary

Usage:
  python main.py          # Mở GUI
  python main.py --cli    # Chạy CLI mode
  python main.py --help   # Xem help
"""

import os
import sys
import argparse
from typing import Tuple, Any
from dataclasses import replace

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import với try/except để hỗ trợ cả relative và absolute imports
try:
    from .config.config import TranslatorConfig
    from .data.content_loader import ContentLoader, ContentMerger
    from .workflow.workflow_v3 import WorkflowV3Runner
except ImportError:
    from config.config import TranslatorConfig
    from data.content_loader import ContentLoader, ContentMerger
    from workflow.workflow_v3 import WorkflowV3Runner


def ensure_output_dirs(config: TranslatorConfig):
    """Tạo các thư mục output nếu chưa có"""
    os.makedirs(config.output_dir, exist_ok=True)
    os.makedirs(config.temp_folder, exist_ok=True)
    print(f"📁 Output folder: {config.output_dir}")


def get_config_from_args() -> Tuple[TranslatorConfig, Any]:
    """Parse command line arguments và tạo config"""
    parser = argparse.ArgumentParser(
        description="Gemini Translator - OOP Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                        # Mở GUI (default)
  python main.py --cli                  # Chạy CLI mode
  python main.py --cli -s 100 -e 200    # CLI: Dịch từ chương 100 đến 200
  python main.py --cli --merge          # CLI: Chỉ merge output
        """
    )
    
    # Mode selection
    parser.add_argument('--cli', action='store_true',
                        help='Chạy CLI mode thay vì GUI')
    
    # Range options
    parser.add_argument('-s', '--start', type=int, default=1,
                        help='Chương bắt đầu (default: 1)')
    parser.add_argument('-e', '--end', type=int, default=9999,
                        help='Chương kết thúc (default: 9999)')
    
    # Threading options
    parser.add_argument('-t', '--threads', type=int, default=3,
                        help='Số threads tối đa (default: 3)')
    
    # Feature toggles
    parser.add_argument('--no-glossary', action='store_true',
                        help='Tắt dynamic glossary learning')
    parser.add_argument('--no-memory', action='store_true',
                        help='Tắt memory system')
    parser.add_argument('--no-lite-critic', action='store_true',
                        help='Tắt chế độ Critic thu gọn (chạy Critic đầy đủ với 3 lần sửa)')
    
    # Path options
    parser.add_argument('--raw', type=str, default=None,
                        help='Đường dẫn file nội dung thô')
    parser.add_argument('--titles', type=str, default=None,
                        help='Đường dẫn file tên chương')
    parser.add_argument('--output', type=str, default=None,
                        help='Đường dẫn file output')
    
    # API options
    parser.add_argument('--key', type=str, default=None,
                        help='Auth key của Router API (override api_config.json)')
    parser.add_argument('--endpoint', type=str, default=None,
                        help='Endpoint của Router API (override api_config.json)')
    
    # Merge only mode
    parser.add_argument('--merge', action='store_true',
                        help='Chỉ merge output, không dịch')

    # Import mode
    parser.add_argument('--import-novel', dest='import_novel', action='store_true',
                        help='Import novel thô và phân tích thực thể gối đầu')
    
    # Expansion options
    parser.add_argument('--expand', action='store_true',
                        help='Bật expansion mode (mở rộng truyện)')
    
    # Verbose
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='In thêm thông tin debug')
    
    args = parser.parse_args()
    
    # Tạo config base
    config = TranslatorConfig()
    config.load_api_config()
    
    # Ensure output dirs exist
    ensure_output_dirs(config)
    
    # Override với command line args
    config = replace(
        config,
        start_chapter=args.start,
        end_chapter=args.end,
        max_threads=args.threads,
        enable_dynamic_glossary=not args.no_glossary,
        enable_expansion=args.expand,  # Bật expansion mode
        lite_critic=not args.no_lite_critic,
    )
    
    # Override paths nếu có
    if args.raw:
        config = replace(config, raw_content_file=args.raw)
    if args.titles:
        config = replace(config, title_list_file=args.titles)
    if args.output:
        config = replace(config, output_file=args.output)
    
    # Override API credentials
    has_api_override = False
    if args.key:
        config = replace(config, auth_key=args.key)
        has_api_override = True
    if args.endpoint:
        config = replace(config, api_endpoint=args.endpoint)
        has_api_override = True

    # Nếu có override từ CLI → fetch lại model registry để cập nhật context và model list mới
    if has_api_override:
        try:
            from config.model_registry import model_registry
            model_registry.configure(config.api_endpoint, config.auth_key)
            model_registry.fetch(force=True)
            for role, mid in config.role_models.items():
                ctx = model_registry.get_context_length(mid)
                if ctx > 0:
                    config.role_max_context[role] = ctx
        except Exception:
            pass
    
    return config, args


def validate_paths(config: TranslatorConfig) -> bool:
    """Kiểm tra các file path cần thiết"""
    errors = []
    
    if not os.path.exists(config.raw_content_file):
        errors.append(f"❌ Không tìm thấy file nội dung: {config.raw_content_file}")
    
    if not os.path.exists(config.title_list_file):
        errors.append(f"❌ Không tìm thấy file tên chương: {config.title_list_file}")
    
    if errors:
        for err in errors:
            print(err)
        return False
    
    return True


def print_banner():
    """In banner khởi động"""
    banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ██████╗ ███████╗███╗   ███╗██╗███╗   ██╗██╗                        ║
║  ██╔════╝ ██╔════╝████╗ ████║██║████╗  ██║██║                        ║
║  ██║  ███╗█████╗  ██╔████╔██║██║██╔██╗ ██║██║                        ║
║  ██║   ██║██╔══╝  ██║╚██╔╝██║██║██║╚██╗██║██║                        ║
║  ╚██████╔╝███████╗██║ ╚═╝ ██║██║██║ ╚████║██║                        ║
║   ╚═════╝ ╚══════╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝                        ║
║                                                                      ║
║              🔄 TRANSLATOR OOP v3.1 - TAM QUYỀN PHÂN LẬP 🔄         ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_config_summary(config: TranslatorConfig):
    """In tóm tắt cấu hình"""
    print("📋 CẤU HÌNH:")
    print(f"   📖 Chương:        {config.start_chapter} → {config.end_chapter}")
    print(f"   🧠 Memory:        {'ON' if config.enable_memory else 'OFF'}")
    print(f"   📚 Dyn Glossary:  {'ON' if config.enable_dynamic_glossary else 'OFF'}")
    # Expansion settings
    if hasattr(config, 'enable_expansion') and config.enable_expansion:
        print(f"   🔥 Expansion:     ON")
    else:
        print(f"   📝 Expansion:     OFF")
    print(f"   📁 Raw file:      {os.path.basename(config.raw_content_file)}")
    print(f"   📄 Title file:    {os.path.basename(config.title_list_file)}")
    print(f"   💾 Output:        {os.path.basename(config.output_file)}")
    print("-" * 70)


def run_cli_mode():
    """Chạy CLI mode"""
    print_banner()
    
    # Parse config
    config, args = get_config_from_args()
    
    # Validate paths
    if not args.merge and not args.import_novel:
        if not validate_paths(config):
            print("\n💡 Hint: Kiểm tra lại đường dẫn file hoặc dùng --raw/--titles flags")
            sys.exit(1)
    
    # Auto-detect chapter count nếu end_chapter = 9999 (default)
    loader = ContentLoader(config)
    if config.end_chapter == 9999:
        max_chap, extra_count = loader.get_chapter_count()
        if max_chap > 0:
            config = replace(config, end_chapter=max_chap)
            print(f"📊 Auto-detect: {max_chap} chương chính + {extra_count} ngoại truyện")
    
    # Print config
    print_config_summary(config)
    
    if args.merge:
        # Merge only mode
        print("🔀 Chế độ MERGE - Chỉ gộp file output")
        merger = ContentMerger(config)
        output_content = merger.merge_chapters()
        
        with open(config.output_file, 'w', encoding='utf-8') as f:
            f.write(output_content)
        
        print(f"✅ Đã gộp và lưu vào: {config.output_file}")
        return

    if args.import_novel:
        print("🚀 Chế độ IMPORT - Bắt đầu import truyện thô và phân tích thực thể")
        try:
            from .data.novel_importer import NovelImporter
            from .config.api_manager import APIManagerV2
        except ImportError:
            from data.novel_importer import NovelImporter
            from config.api_manager import APIManagerV2
        
        api_manager = APIManagerV2(config)
        runner = WorkflowV3Runner(config)
        importer = NovelImporter(config, runner.translator, api_manager)
        
        result = importer.run(
            file_path=config.raw_content_file,
            sample_every=5,
            max_samples=30,
            qa_review=True
        )
        print("🎉 Import hoàn tất!")
        return
    
    # Normal mode: Load and match chapters
    all_chapters = loader.match_chapters()
    
    if not all_chapters:
        print("❌ Không tìm thấy chương nào!")
        sys.exit(1)
    
    # Filter chỉ main chapters theo range (extras sẽ được chèn tự động bởi workflow nếu enable)
    chapters = [
        ch for ch in all_chapters 
        if not ch.is_extra and config.start_chapter <= ch.num <= config.end_chapter
    ]
    
    total_main = sum(1 for ch in all_chapters if not ch.is_extra)
    total_extra = sum(1 for ch in all_chapters if ch.is_extra)
    
    print(f"📚 Tổng cộng: {len(all_chapters)} ({total_main} chương + {total_extra} ngoại truyện)")
    print(f"🎯 Sẽ dịch: {len(chapters)} chương chính (#{config.start_chapter} → #{config.end_chapter})")
    
    if not chapters:
        print("❌ Không có chương nào trong phạm vi này!")
        sys.exit(1)
    
    # Auto-start - không cần confirm
    print("\n🚀 Bắt đầu dịch với V3 Workflow...")
    
    # Run translation với WorkflowV3Runner
    runner = WorkflowV3Runner(config)
    success, total = runner.run(chapters)
    
    # Auto merge if successful
    if success > 0:
        print("\n🔀 Tự động gộp file output...")
        merger = ContentMerger(config)
        output_content = merger.merge_chapters()
        
        if output_content:
            with open(config.output_file, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"✅ Đã lưu: {config.output_file}")
        else:
            print("⚠️ Không có nội dung để gộp (merger đã tự lưu)")
    
    print("\n🎉 HOÀN THÀNH!")


def run_gui_mode():
    """Mở GUI"""
    print("❌ GUI mode không khả dụng (module gui_expansion không tồn tại)")
    print("💡 Dùng Textual TUI thay thế: python -m refactor_oop_gemini_trans_api.tui.app")


def main():
    """Main entry point - Default mở GUI, --cli để chạy CLI"""
    # Quick check for --cli flag
    if '--cli' in sys.argv or '--merge' in sys.argv or '--import-novel' in sys.argv or '--help' in sys.argv or '-h' in sys.argv:
        run_cli_mode()
    else:
        run_gui_mode()


if __name__ == "__main__":
    main()
