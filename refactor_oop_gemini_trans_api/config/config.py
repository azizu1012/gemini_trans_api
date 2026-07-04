# lp"""
# Configuration Module - Cấu hình chung cho translator
# Nâng cấp cho Router API v2 và CLI tương tác
# """
import os
import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Union

# Base directory (thư mục truyện)
BASE_DIR = r"C:\Users\Azuree\Documents\Code-make-novel\Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật"

# Thư mục dữ liệu đầu vào và tài nguyên ảnh
DATA_DIR = os.path.join(BASE_DIR, "data")

# Thư mục chứa code
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Thư mục đầu ra và log
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


@dataclass
class TranslatorConfig:
    """Cấu hình cho Translator"""
    # Paths - Input từ DATA_DIR
    base_dir: str = BASE_DIR
    raw_content_file: str = os.path.join(DATA_DIR, "Truyen_Dich_Hoan_Chinh.txt")
    title_list_file: str = os.path.join(DATA_DIR, "Danh_sach_ten_chuong.txt")
    glossary_file: str = os.path.join(DATA_DIR, "glossary.txt")

    # Paths - Output vào OUTPUT_DIR
    output_dir: str = OUTPUT_DIR
    output_file: str = os.path.join(OUTPUT_DIR, "Truyen_Dich_Hoan_Chinh.txt")
    temp_folder: str = os.path.join(OUTPUT_DIR, "temp_chapters")
    memory_folder: str = os.path.join(OUTPUT_DIR, "memory_store")
    glossary_pending_file: str = os.path.join(OUTPUT_DIR, "glossary_pending.txt")
    model_config_file: str = os.path.join(OUTPUT_DIR, "model_config.json")
    quota_state_file: str = os.path.join(OUTPUT_DIR, "quota_state.json")
    log_file: str = os.path.join(OUTPUT_DIR, "translation.log")

    # API Router v2 Configuration
    api_endpoint: str = "http://127.0.0.1:58100/v1"
    auth_key: str = ""
    model_architect: str = "gemini-flash-lite"
    model_writer: str = "gemini-flash"
    model_critic: str = "gemini-flash-lite"
    lite_critic: bool = True

    # Per-role model selection v3.5
    role_models: Dict[str, str] = field(default_factory=lambda: {
        "architect": "gemini-flash-lite",
        "writer": "gemini-flash",
        "critic": "gemini-flash-lite",
        "coordinator": "gemini-flash",
    })

    # Context window tracking (đọc từ ModelRegistry, auto-update)
    role_max_context: Dict[str, int] = field(default_factory=lambda: {
        "architect": 220000,
        "writer": 220000,
        "critic": 220000,
        "coordinator": 220000,
    })

    # Chapter range
    start_chapter: int = 1
    end_chapter: int = 9999

    # Threading - Sequential cho Expansion Mode (1), Parallel cho dịch thường (3-4)
    max_threads: int = 1

    # Retry settings
    retry_limit: int = 6
    retry_initial_delay: float = 6.0
    retry_max_delay: float = 30.0
    min_request_interval: float = 8.0  # 8s between requests (safe for 15 RPM)

    # Features
    enable_dynamic_glossary: bool = True
    enable_memory: bool = True
    glossary_scan_interval: int = 10

    # Memory settings
    memory_block_size: int = 10
    cumulative_interval: int = 50

    # Expansion Mode (Translation) — bật/tắt mở rộng độ dài khi dịch
    enable_expansion: bool = False
    sequential_expansion: bool = True

    # Enrichment Mode (Generation) — bật/tắt làm giàu có chủ đích
    enable_enrichment: bool = False

    # Expansion/Enrichment Options — dùng chung cho cả 2 mode
    enable_world_building: bool = True
    enable_character_depth: bool = True
    enable_map_exploration: bool = True

    # Extra Integration (RAG cho ngoại truyện)
    enable_extra_rag: bool = True
    enable_extra_integration: bool = True
    smart_extra_placement: bool = True

    # Genre Mixer (v3.5 Remake Engine)
    genre_profile_path: str = ""  # Path tới file genre profile JSON (override)
    enable_remake_engine: bool = True  # Bật/tắt Remake Engine trong prompt

    # Style & Direction (Generation Mode)
    expansion_style: str = "giu_nguyen"  # balanced|action|psychological|descriptive|literary|giu_nguyen
    hallucination_direction: str = "free"  # free|world|character|challenge
    creativity_level: int = 2  # 1|2|3

    # Character & Word Count Control (v3.5)
    forbidden_new_characters: bool = False  # Cấm tạo nhân vật mới khi generation
    avg_words_per_chapter: Any = "auto"  # Target word count (nhập 'auto' hoặc số cụ thể)

    # Model names (legacy support)
    summary_model: str = "gemini-flash-lite"

    # Import concurrency (0 = tự động tính từ router RPM; >0 = override thủ công)
    # Đảm bảo luôn còn đủ slot cho writer + QA khi dịch song song
    import_max_concurrent: int = 0

    def load_api_config(self) -> bool:
        """Tải api_endpoint và auth_key từ file api_config.json"""
        config_path = os.path.join(self.output_dir, "api_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.api_endpoint = data.get("api_endpoint", self.api_endpoint)
                    self.auth_key = data.get("auth_key", self.auth_key)
                    self.model_architect = data.get("model_architect", self.model_architect)
                    self.model_writer = data.get("model_writer", self.model_writer)
                    self.model_critic = data.get("model_critic", self.model_critic)
                    self.lite_critic = data.get("lite_critic", self.lite_critic)
                    # v3.5: load role_models nếu có
                    loaded_roles = data.get("role_models", {})
                    if loaded_roles:
                        self.role_models.update(loaded_roles)
                    loaded_context = data.get("role_max_context", {})
                    if loaded_context:
                        self.role_max_context.update(loaded_context)
                    self.import_max_concurrent = data.get("import_max_concurrent", self.import_max_concurrent)
                    self.expansion_style = data.get("expansion_style", self.expansion_style)
                    self.hallucination_direction = data.get("hallucination_direction", self.hallucination_direction)
                    self.creativity_level = data.get("creativity_level", self.creativity_level)
                    self.forbidden_new_characters = data.get("forbidden_new_characters", self.forbidden_new_characters)
                    self.avg_words_per_chapter = data.get("avg_words_per_chapter", self.avg_words_per_chapter)

                # Cập nhật context window động từ router (nếu router đang chạy)
                try:
                    from .model_registry import model_registry
                    model_registry.configure(self.api_endpoint, self.auth_key)
                    # Gọi fetch đồng bộ (có cơ chế fallback nếu router offline)
                    model_registry.fetch(force=True)
                    for role, mid in self.role_models.items():
                        ctx = model_registry.get_context_length(mid)
                        if ctx > 0:
                            self.role_max_context[role] = ctx
                except Exception as reg_err:
                    # In debug nếu có lỗi nhưng không chặn luồng khởi động
                    pass

                return True
            except Exception as e:
                print(f"⚠️ Không thể tải cấu hình API: {e}")
        return False

    def save_api_config(self, endpoint: Optional[str] = None, key: Optional[str] = None, architect: Optional[str] = None, writer: Optional[str] = None, critic: Optional[str] = None, lite_critic: Optional[bool] = None, role_models: Optional[Dict[str, str]] = None):
        """Lưu api_endpoint và auth_key vào file api_config.json"""
        os.makedirs(self.output_dir, exist_ok=True)
        config_path = os.path.join(self.output_dir, "api_config.json")
        try:
            if endpoint is not None: self.api_endpoint = endpoint
            if key is not None: self.auth_key = key
            if architect: self.model_architect = architect
            if writer: self.model_writer = writer
            if critic: self.model_critic = critic
            if lite_critic is not None: self.lite_critic = lite_critic
            if role_models: self.role_models.update(role_models)
            # Backward compat: sync role_models từ 3 field cũ
            self.role_models.setdefault("architect", self.model_architect)
            self.role_models.setdefault("writer", self.model_writer)
            self.role_models.setdefault("critic", self.model_critic)

            data = {
                "api_endpoint": self.api_endpoint,
                "auth_key": self.auth_key,
                "model_architect": self.model_architect,
                "model_writer": self.model_writer,
                "model_critic": self.model_critic,
                "lite_critic": self.lite_critic,
                "role_models": dict(self.role_models),
                "role_max_context": dict(self.role_max_context),
                "expansion_style": self.expansion_style,
                "hallucination_direction": self.hallucination_direction,
                "creativity_level": self.creativity_level,
                "forbidden_new_characters": self.forbidden_new_characters,
                "avg_words_per_chapter": self.avg_words_per_chapter,
                "import_max_concurrent": self.import_max_concurrent,
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Không thể lưu cấu hình API: {e}")


@dataclass
class GlossaryEntry:
    """Entry trong glossary"""
    key: str
    replace_with: str = ""
    entry_type: str = ""
    visual: str = ""
    action: str = ""
    behavior: str = ""
    describe: str = ""
    context: str = ""
    note: str = ""
    relation: str = ""
    source_chapter: int = 0


# Static Glossary (hardcoded) - SỬA Chu Khải theo feedback
STATIC_GLOSSARY: Dict[str, str] = {
    # === NHÂN VẬT CHÍNH ===
    "Lâm Nhất": "Lâm Nhất (Nam chính - Năng lực quay ngược thời gian, xưng Ta/Tao)",
    "Anna": "Anna (Nữ nhân vật)",
    "Trương Thành": "Trương Thành (Đồng đội - Cựu bác sĩ)",
    "Lục Lâm Hải": "Lục Lâm Hải (Đồng đội)",
    "Đại Bảo": "Đại Bảo (Đồng đội)",
    "Nhị Bảo": "Nhị Bảo (Đồng đội)",

    # === NHÂN VẬT PHỤ (Sửa Chu Khải - không gắt) ===
    "Chu Vân": "Chu Vân (Em gái Chu Khải)",
    "Chu Khải": "Chu Khải (Anh trai Chu Vân - Ban đầu có giúp main sống sót, sau này hành xử mất não theo hướng tác giả build)",
    "Tinh Thành Đạo": "An Thành Đạo",
    "An Thành Đạo": "An Thành Đạo",
    "Huyễn Huyễn": "Huyễn Huyễn (Dị loại đặc biệt)",
    "Giang Thần": "Giang Thần",
    "Khải Sâm": "Khải Sâm",
    "Leo Hãp Đức": "Reohard",
    "Lôi Cáp Đức": "Reohard",
    "Ba Nhĩ Khắc": "Baelk",

    # === DỊ LOẠI ===
    "Sờ lang": "Bọ Ngựa Thiết Giáp (Dị loại bọ ngựa - lỗi convert gốc 'Sờ lang')",
    "Giáp Lang": "Thiết Giáp Lang (Dị loại chó chăn cừu)",
    "Thiên Mục Ngụy": "Yêu Thụ Thiên Mục (Thực vật đột biến)",
    "Yêu Thụ Thiên Mục": "Yêu Thụ Thiên Mục",
    "Oa Trùng": "Oa Trùng (Dị loại ký sinh)",
    "Kình Đào": "Kình Đào (Dị loại biển)",
    "Bất Mãn": "Bất Mãn (Thực thể)",

    # === ĐỊA DANH / TỔ CHỨC ===
    "Tư Đức Farrell": "Stefarrel (Tổ chức - KHÔNG dịch là tên người)",
    "Pease": "thành phố Pease (Thành phố thiên đường thối nát)",
    "Oán Mệnh Ở Giữa": "Cõi Oán Mệnh (Không gian vùng đệm chứa các timeline bị hủy bỏ)",
    "Nam Thành Bang": "bang Nam Thành",
    "Bắc Lầu Phái": "phái Bắc Lầu",
    "nam thành bang": "bang Nam Thành",
    "bắc lầu phái": "phái Bắc Lầu",
    "Buôn Bán Sở": "Sở Giao Dịch",
    "buôn bán sở": "Sở Giao Dịch",
    "Cứu Thế Tổ Chức": "Tổ chức Cứu Thế",
    "cứu thế tổ chức": "Tổ chức Cứu Thế",
    "Kuwait": "Kuwait (Thành phố dục vọng)",
    "Sở Mậu Dịch": "Sở Mậu Dịch (Trung tâm giao dịch Kuwait)",
    "Miền Đất Hứa": "Miền Đất Hứa (Quốc gia trên không)",
    "Côn Luân": "Côn Luân (Núi thần thoại)",
    "Đào Nguyên": "Đào Nguyên",
    "Nông Trại Nhân Loại": "Trang Trại Nhân Loại (Khu chăn nuôi con người)",
    "KTV": "Karaoke",

    # === THUẬT NGỮ ===
    "Dị loại": "Dị loại (Quái vật)",
    "Mạt thế": "Mạt thế",
    "Dị năng": "Dị năng",
    "Tân Nhân Loại": "Tân Nhân Loại (Thực thể cao cấp)",
    "Thần Tuyển Giả": "Kẻ Được Chọn / Thiên Tuyển Giả (Thần Tuyển Giả)",
    "Thần Ban Chi Lực": "Quyền Năng Thần Ban / Sức Mạnh Thần Ban",
    "Thánh Nữ": "Thánh Nữ",
    "Sợi tơ vận mệnh": "Sợi Tơ Vận Mệnh",
    "Thần Ban Chi Tinh": "Tinh Ngọc Thần Ban (Tiền tệ giao dịch)",
    "Giác tỉnh": "Thức tỉnh (Dị năng)",
    "Nhân loại ban sơ": "Nhân Loại Thủy Tổ (Chủng tộc nguyên thủy)",
    "Ý chí địa cầu": "Ý Chí Địa Cầu",

    # === XƯNG HÔ ===
    "Ta": "Ta / Tao (Xưng hô mặc định - Cấm dùng Tôi)",
    "Hắn": "Hắn (ngôi thứ 3 nam)",
    "Nàng": "Nàng (ngôi thứ 3 nữ)",
    "Cô ấy": "Cô ấy (ngôi thứ 3 nữ)",
    "Bọn họ": "Bọn họ",

    # === VIỆT HÓA ===
    "ba ba mụ mụ": "ba mẹ",
    "tiểu tử": "thằng nhóc / gã trai trẻ",
    "cô nương": "cô gái",
}