"""
Main Entry Point - Interactive CLI for Novel Translation System
==============================================================

Hệ thống dịch thuật "Tam Quyền Phân Lập" sử dụng Router API v2.
Tích hợp Ebook Maker chuyên nghiệp.
"""

import os
import sys
import asyncio
import time
import json
import httpx
from colorama import init, Fore, Style

# Thêm thư mục hiện tại vào sys.path để import gói đóng gói
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from refactor_oop_gemini_trans_api.config.config import TranslatorConfig
    from refactor_oop_gemini_trans_api.config.api_manager import APIManagerV2
    from refactor_oop_gemini_trans_api.data.content_loader import ContentLoader, ContentMerger
    from refactor_oop_gemini_trans_api.workflow.workflow_v3 import WorkflowV3Runner
    from refactor_oop_gemini_trans_api.output.ebook_maker import EbookMaker
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "refactor_oop_gemini_trans_api"))
    from config.config import TranslatorConfig
    from config.api_manager import APIManagerV2
    from data.content_loader import ContentLoader, ContentMerger
    from workflow.workflow_v3 import WorkflowV3Runner
    from output.ebook_maker import EbookMaker

# Khởi tạo colorama
init(autoreset=True)


def clear_screen():
    """Xóa sạch màn hình CLI"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """In banner chính của hệ thống"""
    banner = f"""
{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ██████╗ ███████╗███╗   ███╗██╗███╗   ██╗██╗                        ║
║  ██╔════╝ ██╔════╝████╗ ████║██║████╗  ██║██║                        ║
║  ██║  ███╗█████╗  ██╔████╔██║██║██╔██╗ ██║██║                        ║
║  ██║   ██║██╔══╝  ██║╚██╔╝██║██║██║╚██╗██║██║                        ║
║  ╚██████╔╝███████╗██║ ╚═╝ ██║██║██║ ╚████║██║                        ║
║   ╚═════╝ ╚══════╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝                        ║
║                                                                      ║
║         🔄 NOVEL TRANSLATOR v3.5 — INTERACTIVE PRODUCTION ENGINE 🔄      ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def get_input(prompt: str, default: str = "") -> str:
    """Hàm nhập liệu có hỗ trợ giá trị mặc định"""
    default_str = f" [{default}]" if default else ""
    val = input(f"{Fore.GREEN}{prompt}{default_str}: {Style.RESET_ALL}").strip()
    return val if val else default


async def configure_api(config: TranslatorConfig, api_manager: APIManagerV2):
    """Giao diện cấu hình API & Endpoint tương tác"""
    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}⚙️  CẤU HÌNH API & ENDPOINT")
    print("-" * 70)

    # 1. Nhập Endpoint
    current_endpoint = config.api_endpoint
    endpoint = get_input("Nhập API Endpoint", current_endpoint)

    # Tự động chuẩn hóa đuôi endpoint
    endpoint = endpoint.rstrip("/")
    if "openrouter.ai" in endpoint:
        if not endpoint.endswith("/api/v1"):
            endpoint = f"{endpoint}/api/v1"
    else:
        if not endpoint.endswith("/v1"):
            endpoint = f"{endpoint}/v1"

    # 2. Nhập Key
    current_key = config.auth_key
    auth_key = get_input("Nhập Auth Key (sk-...)", current_key)

    print(f"\n{Fore.CYAN}⏳ Đang kết nối thử tới endpoint để lấy danh sách model...")
    api_manager.update_config(endpoint, auth_key)
    models = await api_manager.fetch_available_models_async()

    if models:
        print(f"✅ {Fore.GREEN}Kết nối thành công! Đã tìm thấy {len(models)} models.")
        print(f"\n{Fore.YELLOW}Chọn Model cho từng vai trò:")

        # Gợi ý model mặc định
        default_arch = config.model_architect if config.model_architect in models else models[0]
        default_writer = config.model_writer if config.model_writer in models else models[-1]
        default_critic = config.model_critic if config.model_critic in models else models[-1]

        print(f"\n{Fore.WHITE}Danh sách model khả dụng:")
        for idx, m in enumerate(models[:15]):
            print(f"  [{idx + 1}] {m}")
        if len(models) > 15:
            print(f"  ... và {len(models) - 15} models khác.")

        architect_model = get_input("\nModel cho Architect (Phân tích bối cảnh/Glossary)", default_arch)
        writer_model = get_input("Model cho Writer (Dịch thuật văn học)", default_writer)
        critic_model = get_input("Model cho Critic (QA/Chấm điểm)", default_critic)

        # Lưu cấu hình
        config.save_api_config(
            endpoint=endpoint,
            key=auth_key,
            architect=architect_model,
            writer=writer_model,
            critic=critic_model
        )
        print(f"\n🎉 {Fore.GREEN}Cấu hình đã được lưu thành công vào output/api_config.json!")
    else:
        print(f"\n❌ {Fore.RED}Kết nối thất bại! Vui lòng kiểm tra lại Endpoint hoặc Auth Key.")

    input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")


async def show_models(api_manager: APIManagerV2):
    """Hiển thị danh sách model khả dụng"""
    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}📊 DANH SÁCH MODEL KHẢ DỤNG TỪ ENDPOINT")
    print("-" * 70)
    print(f"🔗 Endpoint: {api_manager.api_endpoint}")
    print("-" * 70)

    print(f"{Fore.CYAN}⏳ Đang quét danh sách model...")
    models = await api_manager.fetch_available_models_async()

    if models:
        print(f"\n{Fore.GREEN}Tìm thấy {len(models)} models khả dụng:\n")
        for idx, m in enumerate(models):
            print(f"  [{idx + 1:02d}] {Fore.WHITE}{m}")
    else:
        print(f"\n❌ {Fore.RED}Không thể quét danh sách model. Hãy kiểm tra lại cấu hình API.")

    input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")


def show_quarantine_log(config: TranslatorConfig):
    """Hiển thị quarantine_chapters.log"""
    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}⚠️ DANH SÁCH CHƯƠNG LỖI CÁCH LY (QUARANTINE LOG)")
    print("-" * 70)

    log_path = os.path.join(config.output_dir, "quarantine_chapters.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if lines:
                print(f"{Fore.RED}Phát hiện {len(lines)} chương không đạt chuẩn QA (Score < 80):\n")
                for line in lines[-20:]:  # Show 20 lines gần nhất
                    print(f"  {Fore.WHITE}{line.strip()}")
                if len(lines) > 20:
                    print(f"\n  ... và {len(lines) - 20} dòng lỗi cũ hơn.")
            else:
                print(f"✅ {Fore.GREEN}Tuyệt vời! Không có chương nào bị cách ly lỗi.")
        except Exception as e:
            print(f"❌ Lỗi đọc file log: {e}")
    else:
        print(f"✅ {Fore.GREEN}Tuyệt vời! Không có chương nào bị cách ly lỗi (File log chưa được tạo).")

    input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")


def clean_temp_folders(config: TranslatorConfig):
    """Dọn dẹp tệp tạm thời"""
    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}🧹 DỌN DẸP TỆP TẠM THỜI")
    print("-" * 70)

    confirm = get_input("Bạn có CHẮC CHẮN muốn dọn dẹp toàn bộ temp_chapters và memory_store để dịch lại từ đầu không? (y/n)", "n")
    if confirm.lower() == "y":
        temp_count = 0
        memory_count = 0

        # Clear temp chapters
        if os.path.exists(config.temp_folder):
            for file in os.listdir(config.temp_folder):
                file_path = os.path.join(config.temp_folder, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    temp_count += 1
                elif os.path.isdir(file_path) and file == "frameworks":
                    for sub_file in os.listdir(file_path):
                        os.remove(os.path.join(file_path, sub_file))
                        temp_count += 1

        # Clear memory store
        if os.path.exists(config.memory_folder):
            for file in os.listdir(config.memory_folder):
                file_path = os.path.join(config.memory_folder, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    memory_count += 1

        print(f"\n🧹 {Fore.GREEN}Đã dọn dẹp thành công {temp_count} tệp tạm và {memory_count} tệp bộ nhớ!")
    else:
        print(f"\n{Fore.YELLOW}Đã hủy dọn dẹp.")

    input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")


def make_ebook(config: TranslatorConfig):
    """Biên soạn Ebook PDF"""
    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}📚 BIÊN SOẠN SÁCH ĐIỆN TỬ (EBOOK MAKER)")
    print("-" * 70)

    # 1. Gộp các file tạm trước
    print(f"{Fore.CYAN}⏳ Bước 1: Gộp toàn bộ chương đã dịch trong temp_chapters...")
    merger = ContentMerger(config)
    output_content = merger.merge_chapters()

    if not output_content:
        print(f"❌ {Fore.RED}Không tìm thấy chương dịch tạm thời nào trong {config.temp_folder}!")
        input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")
        return

    # Ghi file gộp
    os.makedirs(os.path.dirname(config.output_file), exist_ok=True)
    with open(config.output_file, 'w', encoding='utf-8') as f:
        f.write(output_content)
    print(f"✅ {Fore.GREEN}Đã gộp thành công toàn bộ chương vào {config.output_file}!")

    # 2. Tạo PDF Ebook
    print(f"\n{Fore.CYAN}⏳ Bước 2: Bắt đầu biên soạn thành Ebook PDF (Times New Roman A5)...")
    maker = EbookMaker(config)
    success = maker.build_pdf()

    if success:
        print(f"\n🎉 {Fore.GREEN}{Style.BRIGHT}BIÊN SOẠN EBOOK THÀNH CÔNG!")
        print(f"📂 File PDF lưu tại: {Fore.WHITE}{os.path.join(config.output_dir, 'Dung_Chay_Noi_Nay_Khap_Noi_La_Quai_Vat.pdf')}")
    else:
        print(f"\n❌ {Fore.RED}Biên soạn Ebook thất bại! Vui lòng kiểm tra log lỗi hoặc thư viện WeasyPrint.")

    input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")


async def run_translation(config: TranslatorConfig):
    """Chạy quy trình dịch thuật chính"""
    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}🚀 KHỞI CHẠY PIPELINE DỊCH THUẬT")
    print("-" * 70)

    # Load API config
    if not config.auth_key:
        print(f"❌ {Fore.RED}Chưa cấu hình API Key và Endpoint! Vui lòng cấu hình trước khi dịch.")
        input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")
        return

    print(f"🔗 Endpoint: {Fore.WHITE}{config.api_endpoint}")
    print(f"🧠 Architect Model: {Fore.WHITE}{config.model_architect}")
    print(f"✍️  Writer Model: {Fore.WHITE}{config.model_writer}")
    print(f"🔍 Critic Model: {Fore.WHITE}{config.model_critic}")
    print("-" * 70)

    # Nhập dải chương
    start_chap = int(get_input("Chương bắt đầu", str(config.start_chapter)))
    end_chap = int(get_input("Chương kết thúc", str(config.end_chapter)))
    threads = int(get_input("Số luồng xử lý song song (threads)", str(config.max_threads)))

    config.start_chapter = start_chap
    config.end_chapter = end_chap
    config.max_threads = threads

    print(f"\n{Fore.CYAN}⏳ Đang tải và phân tích file raw truyện...")
    loader = ContentLoader(config)
    all_chapters = loader.match_chapters()

    if not all_chapters:
        print(f"❌ {Fore.RED}Không tìm thấy chương nào trong raw file: {config.raw_content_file}!")
        input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")
        return

    # Lọc chương theo dải chương vật lý tuyệt đối
    chapters = [
        ch for ch in all_chapters
        if config.start_chapter <= ch.index <= config.end_chapter
    ]

    print(f"📚 {Fore.GREEN}Tải thành công tổng cộng {len(all_chapters)} chương từ file raw.")
    print(f"🎯 {Fore.GREEN}Sẽ tiến hành dịch {len(chapters)} chương (Vị trí vật lý #{config.start_chapter} → #{config.end_chapter}).")

    if not chapters:
        print(f"❌ {Fore.RED}Không có chương nào trong phạm vi này!")
        input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")
        return

    confirm = get_input("\nBắt đầu dịch ngay? (y/n)", "y")
    if confirm.lower() != "y":
        print(f"\n{Fore.YELLOW}Đã hủy dịch thuật.")
        input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")
        return

    clear_screen()
    print_banner()
    print(f"{Fore.YELLOW}{Style.BRIGHT}🚀 PIPELINE DỊCH THUẬT ĐANG CHẠY...")
    print("=" * 70)

    # Chạy runner bất đồng bộ
    runner = WorkflowV3Runner(config)
    success, total = await runner.run_async(chapters)

    # Tự động hỏi tạo ebook sau khi dịch xong
    print("\n" + "=" * 70)
    print(f"🎉 {Fore.GREEN}Đã hoàn thành dịch thuật {success}/{total} chương!")

    make_ebook_confirm = get_input("\nBạn có muốn tiến hành biên soạn toàn bộ chương đã dịch thành Ebook PDF ngay bây giờ không? (y/n)", "y")
    if make_ebook_confirm.lower() == "y":
        make_ebook(config)
    else:
        input(f"\n{Fore.CYAN}Nhấn Enter để quay lại Menu chính...")


async def main_menu():
    """Vòng lặp menu chính tương tác"""
    config = TranslatorConfig()
    # Tự động nạp cấu hình API cũ nếu có
    config.load_api_config()
    api_manager = APIManagerV2(config)

    while True:
        clear_screen()
        print_banner()

        # Hiển thị trạng thái cấu hình hiện tại
        status_endpoint = config.api_endpoint if config.api_endpoint else "Chưa cấu hình"
        status_key = f"sk-...{config.auth_key[-6:]}" if config.auth_key else "Chưa cấu hình"
        print(f"{Fore.CYAN}🔗 Endpoint: {Fore.WHITE}{status_endpoint} | {Fore.CYAN}🔑 Key: {Fore.WHITE}{status_key}")
        print(f"{Fore.CYAN}🤖 Models: Arch: {Fore.WHITE}{config.model_architect}{Fore.CYAN} | Writer: {Fore.WHITE}{config.model_writer}{Fore.CYAN} | Critic: {Fore.WHITE}{config.model_critic}")
        print("=" * 70)
        print(f"{Fore.YELLOW}{Style.BRIGHT}DANH SÁCH TÍNH NĂNG:")
        print(f"  [{Fore.GREEN}1{Fore.YELLOW}] 🚀 Bắt đầu dịch thuật (Agentic Pipeline)")
        print(f"  [{Fore.GREEN}2{Fore.YELLOW}] 📚 Biên soạn sách điện tử (Ebook Maker)")
        print(f"  [{Fore.GREEN}3{Fore.YELLOW}] ⚙️  Cấu hình API & Endpoint")
        print(f"  [{Fore.GREEN}4{Fore.YELLOW}] 📊 Xem danh sách Model khả dụng")
        print(f"  [{Fore.GREEN}5{Fore.YELLOW}] ⚠️  Xem danh sách chương lỗi (Quarantine Log)")
        print(f"  [{Fore.GREEN}6{Fore.YELLOW}] 🧹 Dọn dẹp tệp tạm thời")
        print(f"  [{Fore.GREEN}7{Fore.YELLOW}] ❌ Thoát chương trình")
        print("=" * 70)

        choice = input(f"{Fore.GREEN}Vui lòng chọn tính năng (1-7): {Style.RESET_ALL}").strip()

        if choice == "1":
            await run_translation(config)
        elif choice == "2":
            make_ebook(config)
        elif choice == "3":
            await configure_api(config, api_manager)
        elif choice == "4":
            await show_models(api_manager)
        elif choice == "5":
            show_quarantine_log(config)
        elif choice == "6":
            clean_temp_folders(config)
        elif choice == "7":
            clear_screen()
            print("\n👋 Cảm ơn bạn đã sử dụng Novel Translator. Tạm biệt!\n")
            break
        else:
            print(f"\n❌ {Fore.RED}Lựa chọn không hợp lệ! Vui lòng chọn từ 1 đến 7.")
            time.sleep(1.5)


if __name__ == "__main__":
    try:
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        clear_screen()
        print("\n👋 Chương trình bị ngắt bởi người dùng. Tạm biệt!\n")
        sys.exit(0)
