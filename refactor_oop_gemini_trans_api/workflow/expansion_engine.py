"""
Smart Expansion Engine V2
=========================
Hệ thống mở rộng thông minh với:
- LENGTH ENFORCEMENT: Đảm bảo output đạt target
- CHAPTER SPLITTING: Tự tách chương khi quá dài
- SIDE PLOT GENERATION: Thêm tuyến truyện mới
- AUTO ADJUSTMENT: Điều chỉnh theo map potential

Thanh trượt = MỨC KÉO DÀI TỐI THIỂU
x2 = Chắc chắn output >= x2 độ dài gốc
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ============================================================================
# CORE DATACLASSES
# ============================================================================

@dataclass
class ChapterMetrics:
    """Metrics của một chương"""
    chapter_num: int
    raw_length: int          # Độ dài raw (chars)
    translated_length: int   # Độ dài sau dịch
    expansion_ratio: float   # translated / raw
    word_count: int          # Số từ
    paragraph_count: int     # Số đoạn
    dialogue_ratio: float    # % hội thoại


@dataclass
class ExpansionTarget:
    """Target expansion cho một chương"""
    chapter_num: int
    min_ratio: float         # Tỉ lệ tối thiểu (từ slider)
    recommended_ratio: float # Tỉ lệ được recommend (từ potential)
    max_ratio: float         # Tỉ lệ tối đa (tránh quá dài)
    should_split: bool       # Nên tách thành nhiều chương?
    split_count: int         # Tách thành bao nhiêu chương?
    expansion_types: List[str]  # Loại expansion nên dùng
    side_plot_suggestions: List[str]  # Gợi ý side plot


@dataclass 
class SidePlot:
    """Một tuyến truyện phụ"""
    id: str
    name: str
    description: str
    characters: List[str]
    start_chapter: int
    end_chapter: int
    key_events: List[Dict]   # [{"chapter": 52, "event": "..."}]
    status: str = "pending"  # pending, active, resolved


@dataclass
class ExpansionResult:
    """Kết quả sau khi expand"""
    original_chapter: int
    output_chapters: List[int]  # Có thể là [52] hoặc [52, 52.1, 52.2]
    original_length: int
    final_length: int
    actual_ratio: float
    met_target: bool
    retries: int
    side_plots_added: List[str]
    notes: str


# ============================================================================
# MAP POTENTIAL DATABASE - Dynamic from config
# ============================================================================

def _load_map_potentials() -> Dict:
    """
    Load MAP_POTENTIALS từ world_config.json
    Nếu không có file → trả về empty dict, sẽ dùng default values
    
    KHÔNG hardcode data sai cho story khác!
    System sẽ tự học qua WorldBuilder khi dịch.
    """
    # Check output folder first, then root
    base_dir = os.path.dirname(__file__)
    output_config_path = os.path.join(base_dir, "output", "world_config.json")
    root_config_path = os.path.join(base_dir, "world_config.json")
    
    config_path = output_config_path if os.path.exists(output_config_path) else root_config_path
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {}
            for map_id, map_data in data.get('maps', {}).items():
                # Get chapter range - support both formats
                chapter_range = map_data.get('chapter_range', [1, 999])
                if isinstance(chapter_range, list) and len(chapter_range) >= 2:
                    start, end = chapter_range[0], chapter_range[1]
                else:
                    continue
                    
                # Get other properties with defaults
                name = map_data.get('name', map_id)
                danger = map_data.get('danger_level', map_data.get('exploration_potential', 5))
                
                # Get rate from rate_range or default
                rate_range = map_data.get('rate_range', [1.1, 1.3])
                if isinstance(rate_range, list) and len(rate_range) >= 2:
                    expand = (rate_range[0] + rate_range[1]) / 2  # Average
                else:
                    expand = 1.2
                
                side_plots = max(0, (danger - 5) // 2)
                
                result[(start, end)] = (name, danger, expand, side_plots)
            
            if result:
                print(f"[ExpansionEngine] Loaded {len(result)} maps from world_config.json")
                return result
        except Exception as e:
            print(f"[ExpansionEngine] Error loading config: {e}")
    
    # Không hardcode - trả về empty, sẽ dùng default values trong get_map_info()
    return {}

# Load dynamically - có thể empty nếu chưa có config
MAP_POTENTIALS = _load_map_potentials()

# EXTRA_CHAPTERS: danh sách các chương ngoại truyện (WorldBuilder populate sau)
EXTRA_CHAPTERS: List = []

# ============================================================================
# ARC/STORYLINE DATABASE - Dữ liệu tuyến truyện để đặt tên chương thông minh
# ============================================================================

@dataclass
class StoryArc:
    """Thông tin về một arc trong truyện"""
    name: str                          # Tên arc
    chapter_range: Tuple[int, int]     # Range chương
    theme: str                         # Theme chính
    main_conflict: str                 # Xung đột chính
    key_characters: List[str]          # Nhân vật chính của arc
    sub_arcs: List[Dict]               # Sub-arcs trong arc lớn
    naming_pattern: str                # Pattern đặt tên chương
    climax_chapters: List[int]         # Các chương cao trào
    keywords: List[str]                # Keywords đặc trưng


ARC_DATABASE: Dict[str, StoryArc] = {
    "nha_lam_nhat": StoryArc(
        name="Mở đầu - Nhà Lâm Nhất",
        chapter_range=(1, 18),
        theme="Thức tỉnh & Sinh tồn đầu tiên",
        main_conflict="Khám phá thế giới mới, hiểu luật lệ dị loại",
        key_characters=["Lâm Nhất"],
        sub_arcs=[
            {"range": (1, 5), "name": "Thức Tỉnh", "pattern": "Thức Tỉnh: {content}"},
            {"range": (6, 12), "name": "Quy Tắc", "pattern": "Quy Tắc: {content}"},
            {"range": (13, 18), "name": "Bước Ra", "pattern": "Ra Ngoài: {content}"},
        ],
        naming_pattern="{arc_prefix}: {content_summary}",
        climax_chapters=[5, 12, 18],
        keywords=["nhà", "quy tắc", "thức tỉnh", "dị loại đầu tiên"]
    ),
    
    "thanh_pho": StoryArc(
        name="Thành Phố Hoang Tàn",
        chapter_range=(19, 24),
        theme="Khám phá thế giới bên ngoài",
        main_conflict="Thành phố đầy dị loại, tìm nguồn cung cấp",
        key_characters=["Lâm Nhất"],
        sub_arcs=[
            {"range": (19, 21), "name": "Phố Hoang", "pattern": "Phố Hoang: {content}"},
            {"range": (22, 24), "name": "Phát Hiện", "pattern": "Manh Mối: {content}"},
        ],
        naming_pattern="Thành Phố: {content_summary}",
        climax_chapters=[24],
        keywords=["thành phố", "phố", "siêu thị", "xe", "đường"]
    ),
    
    "nong_trai": StoryArc(
        name="Nông Trại Nhân Loại",
        chapter_range=(25, 49),
        theme="Địa ngục trần gian - Con người là gia súc",
        main_conflict="Thoát khỏi nông trại, đối đầu hệ thống nuôi người",
        key_characters=["Lâm Nhất", "Trương Thành", "Nhóm sinh tồn"],
        sub_arcs=[
            {"range": (25, 30), "name": "Bị Bắt", "pattern": "Nông Trại: {content}"},
            {"range": (31, 38), "name": "Thích Nghi", "pattern": "Sinh Tồn: {content}"},
            {"range": (39, 45), "name": "Kế Hoạch", "pattern": "Âm Mưu: {content}"},
            {"range": (46, 49), "name": "Trốn Thoát", "pattern": "Đào Thoát: {content}"},
        ],
        naming_pattern="Nông Trại: {content_summary}",
        climax_chapters=[30, 38, 49],
        keywords=["nông trại", "nuôi", "gia súc", "quản lý", "đồ ăn", "thu hoạch"]
    ),
    
    "benh_vien": StoryArc(
        name="Bệnh Viện Kinh Hoàng",
        chapter_range=(50, 59),
        theme="Kinh dị y tế - Bác sĩ và y tá dị loại",
        main_conflict="Khám phá bệnh viện, đối đầu dị loại y tế",
        key_characters=["Lâm Nhất", "Trương Thành"],
        sub_arcs=[
            {"range": (50, 52), "name": "Tiến Vào", "pattern": "Bệnh Viện: {content}"},
            {"range": (53, 56), "name": "Đối Đầu", "pattern": "Y Tá: {content}"},
            {"range": (57, 59), "name": "Bí Mật", "pattern": "Bí Mật: {content}"},
        ],
        naming_pattern="Bệnh Viện: {content_summary}",
        climax_chapters=[55, 59],
        keywords=["bệnh viện", "bác sĩ", "y tá", "khám", "tiêm", "phòng mổ"]
    ),
    
    "lang_gu_lung": StoryArc(
        name="Làng Gù Lưng",
        chapter_range=(60, 138),
        theme="Ngôi làng bí ẩn với tục lệ kỳ quái",
        main_conflict="Giải mã bí mật làng, đối đầu tín ngưỡng",
        key_characters=["Lâm Nhất", "Trương Thành", "Dân làng"],
        sub_arcs=[
            {"range": (60, 75), "name": "Đến Làng", "pattern": "Làng: {content}"},
            {"range": (76, 95), "name": "Tục Lệ", "pattern": "Tục Lệ: {content}"},
            {"range": (96, 115), "name": "Bí Mật", "pattern": "Bí Ẩn: {content}"},
            {"range": (116, 138), "name": "Rời Đi", "pattern": "Thoát Ly: {content}"},
        ],
        naming_pattern="Làng Gù: {content_summary}",
        climax_chapters=[75, 95, 115, 138],
        keywords=["làng", "gù lưng", "tục", "lễ", "đền", "cúng"]
    ),
    
    "dao_nguyen_gia": StoryArc(
        name="Đào Nguyên Giả",
        chapter_range=(139, 169),
        theme="Thiên đường giả tạo",
        main_conflict="Phát hiện sự thật về thiên đường giả",
        key_characters=["Lâm Nhất", "Trương Thành", "Cư dân Đào Nguyên"],
        sub_arcs=[
            {"range": (139, 150), "name": "Đến Đào Nguyên", "pattern": "Đào Nguyên: {content}"},
            {"range": (151, 160), "name": "Nghi Ngờ", "pattern": "Hoài Nghi: {content}"},
            {"range": (161, 169), "name": "Sự Thật", "pattern": "Vạch Trần: {content}"},
        ],
        naming_pattern="Đào Nguyên: {content_summary}",
        climax_chapters=[150, 160, 169],
        keywords=["đào nguyên", "thiên đường", "bình yên", "giả", "ảo"]
    ),
    
    "kuwait": StoryArc(
        name="Kuwait - Thành Phố Dị Loại",
        chapter_range=(170, 295),
        theme="Thành phố của dị loại - Nền văn minh quái vật",
        main_conflict="Sinh tồn giữa văn minh dị loại, khám phá nguồn gốc",
        key_characters=["Lâm Nhất", "Trương Thành", "Sở Mậu Dịch", "Chu Khải"],
        sub_arcs=[
            {"range": (170, 190), "name": "Vào Kuwait", "pattern": "Kuwait: {content}"},
            {"range": (191, 220), "name": "Khám Phá", "pattern": "Phố Đen: {content}"},
            {"range": (221, 250), "name": "Đấu Trường", "pattern": "Đấu Trường: {content}"},
            {"range": (251, 280), "name": "Gánh Xiếc", "pattern": "Gánh Xiếc: {content}"},
            {"range": (281, 295), "name": "Rời Đi", "pattern": "Rời Kuwait: {content}"},
        ],
        naming_pattern="Kuwait: {content_summary}",
        climax_chapters=[190, 220, 250, 280, 295],
        keywords=["kuwait", "thành phố", "nô lệ", "đấu trường", "gánh xiếc", "mậu dịch"]
    ),
    
    "ganh_xiec": StoryArc(
        name="Gánh Xiếc Nữ Oa",
        chapter_range=(295, 309),
        theme="Nghệ thuật dị loại",
        main_conflict="Đối đầu với gánh xiếc, quyết định lựa chọn",
        key_characters=["Lâm Nhất", "Thành viên gánh xiếc"],
        sub_arcs=[
            {"range": (295, 300), "name": "Gia Nhập", "pattern": "Xiếc: {content}"},
            {"range": (301, 309), "name": "Biểu Diễn", "pattern": "Màn Trình: {content}"},
        ],
        naming_pattern="Gánh Xiếc: {content_summary}",
        climax_chapters=[305, 309],
        keywords=["xiếc", "biểu diễn", "ảo thuật", "khán giả", "sân khấu"]
    ),
    
    "pease_thanh": StoryArc(
        name="Pease Thành",
        chapter_range=(310, 380),
        theme="Thành phố giai cấp - Hệ thống tầng lớp",
        main_conflict="Leo lên đỉnh tháp, phá vỡ hệ thống",
        key_characters=["Lâm Nhất", "Trương Thành", "Cư dân Pease"],
        sub_arcs=[
            {"range": (310, 330), "name": "Đến Pease", "pattern": "Pease: {content}"},
            {"range": (331, 355), "name": "Leo Tầng", "pattern": "Thăng Cấp: {content}"},
            {"range": (356, 370), "name": "Đỉnh Tháp", "pattern": "Đỉnh Cao: {content}"},
            {"range": (371, 380), "name": "Rời Đi", "pattern": "Hạ Sơn: {content}"},
        ],
        naming_pattern="Pease: {content_summary}",
        climax_chapters=[330, 355, 370, 380],
        keywords=["pease", "tầng", "giai cấp", "thang", "đỉnh", "hoàng"]
    ),
    
    "dao_nguyen_that": StoryArc(
        name="Đào Nguyên Thật",
        chapter_range=(380, 428),
        theme="Thiên đường thật sự",
        main_conflict="Khám phá nguồn gốc thật, đối mặt chân lý",
        key_characters=["Lâm Nhất", "Trương Thành"],
        sub_arcs=[
            {"range": (380, 400), "name": "Tìm Kiếm", "pattern": "Hành Trình: {content}"},
            {"range": (401, 415), "name": "Khám Phá", "pattern": "Chân Tướng: {content}"},
            {"range": (416, 428), "name": "Giác Ngộ", "pattern": "Giác Ngộ: {content}"},
        ],
        naming_pattern="Đào Nguyên Thật: {content_summary}",
        climax_chapters=[400, 415, 428],
        keywords=["đào nguyên thật", "nguồn gốc", "chân lý", "thần"]
    ),
    
    "man_troi": StoryArc(
        name="Màn Trời",
        chapter_range=(429, 450),
        theme="Biên giới thế giới",
        main_conflict="Đối mặt với giới hạn thế giới",
        key_characters=["Lâm Nhất", "Thực thể màn trời"],
        sub_arcs=[
            {"range": (429, 438), "name": "Tiến Đến", "pattern": "Màn Trời: {content}"},
            {"range": (439, 450), "name": "Đối Đầu", "pattern": "Biên Giới: {content}"},
        ],
        naming_pattern="Màn Trời: {content_summary}",
        climax_chapters=[445, 450],
        keywords=["màn trời", "biên giới", "bên kia", "thế giới"]
    ),
    
    "dai_chien": StoryArc(
        name="Đại Chiến Cuối Cùng",
        chapter_range=(451, 500),
        theme="Trận chiến quyết định",
        main_conflict="Đại chiến giữa loài người và dị loại",
        key_characters=["Lâm Nhất", "Trương Thành", "Tất cả nhân vật"],
        sub_arcs=[
            {"range": (451, 470), "name": "Chuẩn Bị", "pattern": "Chiến Tranh: {content}"},
            {"range": (471, 490), "name": "Khai Mào", "pattern": "Xung Đột: {content}"},
            {"range": (491, 500), "name": "Cao Trào", "pattern": "Quyết Chiến: {content}"},
        ],
        naming_pattern="Đại Chiến: {content_summary}",
        climax_chapters=[470, 490, 500],
        keywords=["chiến", "đánh", "quân", "trận", "thắng", "bại"]
    ),
    
    "ket_thuc": StoryArc(
        name="Kết Thúc",
        chapter_range=(501, 550),
        theme="Hậu chiến và tương lai",
        main_conflict="Xây dựng lại, tìm kiếm ý nghĩa",
        key_characters=["Lâm Nhất", "Các nhân vật sống sót"],
        sub_arcs=[
            {"range": (501, 520), "name": "Hậu Chiến", "pattern": "Tái Thiết: {content}"},
            {"range": (521, 540), "name": "Ổn Định", "pattern": "Bình Yên: {content}"},
            {"range": (541, 550), "name": "Kết Thúc", "pattern": "Hồi Kết: {content}"},
        ],
        naming_pattern="Kết: {content_summary}",
        climax_chapters=[520, 540, 550],
        keywords=["kết", "cuối", "hậu", "tương lai", "bình yên"]
    ),
}


class SmartChapterNamer:
    """
    Hệ thống đặt tên chương thông minh
    
    Dựa trên:
    1. Arc hiện tại
    2. Sub-arc trong arc
    3. Vị trí trong arc (đầu/giữa/cao trào/kết)
    4. Nội dung chương
    5. Liên kết với các chương khác trong cùng arc
    """
    
    def __init__(self):
        self.arc_db = ARC_DATABASE
    
    def get_arc_for_chapter(self, chapter_num: int) -> Optional[StoryArc]:
        """Lấy arc chứa chương này"""
        for arc in self.arc_db.values():
            if arc.chapter_range[0] <= chapter_num <= arc.chapter_range[1]:
                return arc
        return None
    
    def get_sub_arc(self, chapter_num: int, arc: StoryArc) -> Optional[Dict]:
        """Lấy sub-arc chứa chương này"""
        for sub in arc.sub_arcs:
            if sub["range"][0] <= chapter_num <= sub["range"][1]:
                return sub
        return None
    
    def get_chapter_position(self, chapter_num: int, arc: StoryArc) -> str:
        """
        Xác định vị trí của chương trong arc
        Returns: 'intro', 'development', 'climax', 'resolution'
        """
        start, end = arc.chapter_range
        total = end - start + 1
        position = chapter_num - start
        progress = position / total
        
        if chapter_num in arc.climax_chapters:
            return "climax"
        elif progress < 0.2:
            return "intro"
        elif progress > 0.85:
            return "resolution"
        else:
            return "development"
    
    def build_naming_context(self, chapter_num: int) -> Dict:
        """
        Xây dựng context đầy đủ cho việc đặt tên chương
        """
        arc = self.get_arc_for_chapter(chapter_num)
        if not arc:
            return {"has_context": False}
        
        sub_arc = self.get_sub_arc(chapter_num, arc)
        position = self.get_chapter_position(chapter_num, arc)
        
        # Xác định các chương liên quan (cùng sub-arc)
        related_chapters = []
        if sub_arc:
            related_chapters = list(range(sub_arc["range"][0], sub_arc["range"][1] + 1))
            related_chapters.remove(chapter_num)
        
        return {
            "has_context": True,
            "arc_name": arc.name,
            "arc_theme": arc.theme,
            "main_conflict": arc.main_conflict,
            "key_characters": arc.key_characters,
            "sub_arc_name": sub_arc["name"] if sub_arc else "",
            "sub_arc_pattern": sub_arc["pattern"] if sub_arc else "",
            "position": position,
            "is_climax": chapter_num in arc.climax_chapters,
            "related_chapters": related_chapters[:3],  # Max 3 chương liên quan
            "keywords": arc.keywords,
            "naming_pattern": arc.naming_pattern,
        }
    
    def generate_naming_instruction(self, chapter_num: int) -> str:
        """
        Tạo instruction cho AI để đặt tên chương phù hợp với arc
        """
        ctx = self.build_naming_context(chapter_num)
        
        if not ctx["has_context"]:
            return ""
        
        position_hint = {
            "intro": "Đây là chương mở đầu arc, tên nên giới thiệu/dẫn dắt",
            "development": "Đây là chương phát triển, tên nên thể hiện sự tiến triển",
            "climax": "⚡ ĐÂY LÀ CHƯƠNG CAO TRÀO! Tên phải mạnh mẽ, quyết định",
            "resolution": "Đây là chương kết thúc arc, tên nên thể hiện sự giải quyết/chuyển tiếp",
        }
        
        instruction = f"""
[HƯỚNG DẪN ĐẶT TÊN CHƯƠNG - THEO KỊCH BẢN]

📍 VỊ TRÍ TRONG TRUYỆN:
- Arc: {ctx['arc_name']}
- Theme arc: {ctx['arc_theme']}  
- Sub-arc: {ctx['sub_arc_name']}
- Xung đột chính: {ctx['main_conflict']}
- Nhân vật chính arc: {', '.join(ctx['key_characters'])}

📊 VỊ TRÍ CHƯƠNG:
- Loại: {ctx['position'].upper()}
- {position_hint.get(ctx['position'], '')}
{"- ⚡ CHƯƠNG CAO TRÀO - Tên cần ấn tượng!" if ctx['is_climax'] else ''}

📝 PATTERN ĐẶT TÊN:
- Pattern: {ctx['sub_arc_pattern']}
- Keywords đặc trưng arc: {', '.join(ctx['keywords'][:5])}

⚠️ YÊU CẦU:
1. Tên PHẢI phù hợp với theme của arc
2. Tên nên liên kết với các chương cùng sub-arc
3. Dùng pattern nếu phù hợp: {ctx['sub_arc_pattern']}
4. Nếu là cao trào: tên phải mạnh, có impact
5. KHÔNG đặt tên chung chung, phải cụ thể với nội dung
"""
        return instruction.strip()
    
    def get_split_title_for_arc(
        self, 
        chapter_num: int, 
        base_title: str, 
        part_num: int, 
        total_parts: int
    ) -> str:
        """
        Tạo tiêu đề cho chương split - dùng "- Phần X" cho ebook offline
        
        Ví dụ:
            Chương 1: Thức Tỉnh - Phần 1
            Chương 1: Thức Tỉnh - Phần 2
        """
        # Xử lý tiêu đề gốc - loại bỏ "Chương X:" nếu có
        clean_title = re.sub(r'^Chương\s*[\d.]+[:.：]?\s*', '', base_title).strip()
        
        if clean_title:
            return f"Chương {chapter_num}: {clean_title} - Phần {part_num}"
        else:
            return f"Chương {chapter_num} - Phần {part_num}"


# Global instance
CHAPTER_NAMER = SmartChapterNamer()


SIDE_PLOT_TEMPLATES = {
    "thanh_pho": [
        SidePlot(
            id="sp_thanh_pho_01",
            name="Bí Mật Cống Ngầm",
            description="Khám phá hệ thống cống ngầm dưới thành phố, nơi có nhóm sinh tồn khác",
            characters=["Lâm Nhất", "Nhóm sinh tồn mới"],
            start_chapter=20, end_chapter=24,
            key_events=[
                {"chapter": 20, "event": "Phát hiện lối vào cống"},
                {"chapter": 22, "event": "Gặp nhóm sinh tồn"},
                {"chapter": 24, "event": "Liên minh hoặc xung đột"}
            ]
        ),
        SidePlot(
            id="sp_thanh_pho_02",
            name="Tòa Nhà Cao Tầng",
            description="Khám phá tòa nhà cao tầng, nơi có tầm nhìn toàn cảnh thành phố",
            characters=["Lâm Nhất"],
            start_chapter=21, end_chapter=23,
            key_events=[
                {"chapter": 21, "event": "Leo lên tòa nhà"},
                {"chapter": 23, "event": "Phát hiện pattern của dị loại"}
            ]
        ),
    ],
    "nong_trai": [
        SidePlot(
            id="sp_nong_trai_01",
            name="Nông Trại 27",
            description="Khám phá nông trại bên cạnh, nơi có cơ chế khác",
            characters=["Lâm Nhất", "Trương Thành"],
            start_chapter=30, end_chapter=40,
            key_events=[
                {"chapter": 30, "event": "Nghe tin về nông trại 27"},
                {"chapter": 35, "event": "Xâm nhập nông trại 27"},
                {"chapter": 40, "event": "Phát hiện bí mật"}
            ]
        ),
        SidePlot(
            id="sp_nong_trai_02", 
            name="Hệ Thống Quản Lý",
            description="Tìm hiểu về hệ thống quản lý của dị loại",
            characters=["Trương Thành"],
            start_chapter=35, end_chapter=45,
            key_events=[
                {"chapter": 35, "event": "Phát hiện tài liệu"},
                {"chapter": 42, "event": "Giải mã hệ thống"}
            ]
        ),
    ],
    "kuwait": [
        SidePlot(
            id="sp_kuwait_01",
            name="Khu Phố Đen",
            description="Khám phá khu phố ngầm của Kuwait",
            characters=["Lâm Nhất", "Đội nhóm"],
            start_chapter=180, end_chapter=200,
            key_events=[
                {"chapter": 180, "event": "Nghe tin đồn về khu phố đen"},
                {"chapter": 190, "event": "Xâm nhập"},
                {"chapter": 200, "event": "Phát hiện thế lực mới"}
            ]
        ),
        SidePlot(
            id="sp_kuwait_02",
            name="Đấu Trường Nô Lệ",
            description="Tham gia hoặc phá hủy đấu trường nô lệ",
            characters=["Lâm Nhất", "Chu Khải"],
            start_chapter=210, end_chapter=240,
            key_events=[
                {"chapter": 210, "event": "Phát hiện đấu trường"},
                {"chapter": 225, "event": "Bị ép tham gia"},
                {"chapter": 240, "event": "Phá hủy đấu trường"}
            ]
        ),
        SidePlot(
            id="sp_kuwait_03",
            name="Các Gánh Xiếc Khác",
            description="Gặp gỡ các gánh xiếc khác ngoài Nữ Oa",
            characters=["Lâm Nhất"],
            start_chapter=250, end_chapter=280,
            key_events=[
                {"chapter": 250, "event": "Nghe về gánh xiếc khác"},
                {"chapter": 265, "event": "Gặp gỡ"},
                {"chapter": 280, "event": "Liên minh hoặc đối đầu"}
            ]
        ),
        SidePlot(
            id="sp_kuwait_04",
            name="Chợ Đen Công Nghệ",
            description="Khám phá chợ đen công nghệ của dị loại",
            characters=["Trương Thành", "Kình Đào"],
            start_chapter=220, end_chapter=250,
            key_events=[
                {"chapter": 220, "event": "Phát hiện chợ đen"},
                {"chapter": 235, "event": "Mua/lấy được vật phẩm quan trọng"},
            ]
        ),
        SidePlot(
            id="sp_kuwait_05",
            name="Lịch Sử Kuwait",
            description="Khám phá lịch sử thành lập Kuwait",
            characters=["Lâm Nhất", "Người kể chuyện"],
            start_chapter=200, end_chapter=220,
            key_events=[
                {"chapter": 200, "event": "Gặp người biết lịch sử"},
                {"chapter": 210, "event": "Nghe kể về quá khứ"},
            ]
        ),
    ],
    "pease": [
        SidePlot(
            id="sp_pease_01",
            name="Hệ Thống Giai Cấp",
            description="Khám phá chi tiết hệ thống giai cấp Pease",
            characters=["Lâm Nhất", "Cư dân Pease"],
            start_chapter=320, end_chapter=350,
            key_events=[
                {"chapter": 320, "event": "Quan sát giai cấp"},
                {"chapter": 335, "event": "Xâm nhập tầng trên"},
                {"chapter": 350, "event": "Phát hiện bí mật đỉnh tháp"}
            ]
        ),
        SidePlot(
            id="sp_pease_02",
            name="Hoàng Lăng Dị Loại",
            description="Khám phá Hoàng Lăng Dị Loại",
            characters=["Lâm Nhất", "Trương Thành"],
            start_chapter=355, end_chapter=375,
            key_events=[
                {"chapter": 355, "event": "Phát hiện lối vào"},
                {"chapter": 365, "event": "Khám phá bên trong"},
                {"chapter": 375, "event": "Đối mặt với guardian"}
            ]
        ),
    ],
}


# ============================================================================
# SMART EXPANSION ENGINE
# ============================================================================

class SmartExpansionEngine:
    """
    Engine mở rộng thông minh
    
    Đảm bảo:
    1. Output đạt TỐI THIỂU target ratio
    2. Tự động split chapter nếu quá dài
    3. Thêm side plots phù hợp
    4. Retry nếu chưa đạt
    """
    
    # Thresholds
    CHARS_PER_CHAPTER_MIN: int = 3000    # Tối thiểu mỗi chương
    CHARS_PER_CHAPTER_MAX: int = 12000   # Tối đa trước khi split
    CHARS_PER_CHAPTER_IDEAL: int = 6000  # Lý tưởng
    
    def __init__(
        self,
        min_expansion_rate: float = 1.0,  # Từ slider
        auto_adjust: bool = True,          # Tự điều chỉnh theo potential
        enable_splitting: bool = True,     # Cho phép tách chương
        enable_side_plots: bool = True,    # Cho phép thêm side plots
        max_retries: int = 2               # Số lần retry nếu ngắn
    ):
        self.min_rate = min_expansion_rate
        self.auto_adjust = auto_adjust
        self.enable_splitting = enable_splitting
        self.enable_side_plots = enable_side_plots
        self.max_retries = max_retries
        
        # State tracking
        self.active_side_plots: Dict[str, SidePlot] = {}
        self.completed_side_plots: List[str] = []
        self.expansion_history: List[ExpansionResult] = []
        
    def get_map_info(self, chapter_num: int) -> Tuple[str, int, float, int]:
        """
        Lấy thông tin map cho chương này
        
        Nếu có world_config.json → dùng data từ file
        Nếu không → dùng default values (flat rate từ slider)
        
        Returns: (name, potential, max_expand, side_count)
        """
        # Tìm trong MAP_POTENTIALS nếu có
        for (start, end), (name, potential, max_expand, side_count) in MAP_POTENTIALS.items():
            if start <= chapter_num <= end:
                return name, potential, max_expand, side_count
        
        # Default: dùng slider rate, không có side plots
        # potential=5 (neutral), max_expand từ slider, side_count=0
        return f"Chapter {chapter_num}", 5, self.min_rate, 0
    
    def calculate_expansion_target(self, chapter_num: int, raw_length: int) -> ExpansionTarget:
        """
        Tính toán target expansion cho một chương
        
        Returns ExpansionTarget với:
        - min_ratio: Từ slider (LUÔN phải đạt)
        - recommended_ratio: Dựa trên map potential, nhưng không thấp hơn min_ratio
        - should_split: Nếu output quá dài
        """
        map_name, potential, max_expand, side_count = self.get_map_info(chapter_num)
        
        # Base ratios - min_ratio từ slider là bắt buộc
        min_ratio = self.min_rate  # Từ slider
        
        # Auto adjust based on potential - nhưng KHÔNG thấp hơn min_ratio
        if self.auto_adjust:
            # Potential 1-4: x1.2-x1.5
            # Potential 5-7: x1.5-x2.5  
            # Potential 8-10: x2.5-x4.0
            if potential >= 8:
                recommended = 2.5 + (potential - 8) * 0.5
            elif potential >= 5:
                recommended = 1.5 + (potential - 5) * 0.3
            else:
                recommended = 1.0 + potential * 0.1
            # recommended không được thấp hơn min_ratio từ slider
            recommended = max(min_ratio, recommended)
        else:
            recommended = min_ratio
        
        # max_ratio là MAX có thể đạt (map limit hoặc slider, cái nào cao hơn)
        max_ratio = max(max_expand, min_ratio)
        
        # Calculate if should split - dùng min_ratio vì đó là target thực sự
        estimated_length = raw_length * min_ratio
        should_split = estimated_length > self.CHARS_PER_CHAPTER_MAX and self.enable_splitting
        split_count = max(1, int(estimated_length / self.CHARS_PER_CHAPTER_IDEAL)) if should_split else 1
        
        # Determine expansion types - dùng min_ratio
        expansion_types = self._get_expansion_types(chapter_num, potential, min_ratio)
        
        # Get side plot suggestions
        side_plot_suggestions = self._get_side_plot_suggestions(chapter_num, map_name)
        
        return ExpansionTarget(
            chapter_num=chapter_num,
            min_ratio=min_ratio,
            recommended_ratio=recommended,
            max_ratio=max_ratio,
            should_split=should_split,
            split_count=split_count,
            expansion_types=expansion_types,
            side_plot_suggestions=side_plot_suggestions
        )
    
    def _get_expansion_types(self, chapter_num: int, potential: int, ratio: float) -> List[str]:
        """Xác định các loại expansion nên dùng"""
        types = []
        
        if ratio >= 1.5:
            types.append("DETAIL")  # Thêm chi tiết môi trường
        
        if ratio >= 2.0:
            types.append("CHARACTER")  # Tâm lý nhân vật
            types.append("WORLD")  # World building
        
        if ratio >= 2.5:
            types.append("BACKSTORY")  # Quá khứ
            types.append("SIDE_QUEST")  # Nhiệm vụ phụ
        
        if ratio >= 3.0:
            types.append("DEEP_EXPLORE")  # Khám phá sâu
            types.append("FLASHBACK")  # Hồi ức
        
        if ratio >= 3.5:
            types.append("NEW_STORYLINE")  # Tuyến mới
            types.append("SMART_CHARACTER")  # Nhân vật thông minh
        
        return types
    
    def _get_side_plot_suggestions(self, chapter_num: int, map_name: str) -> List[str]:
        """Lấy gợi ý side plot cho chương này"""
        suggestions = []
        
        # Map name to key
        map_key = {
            "Thành Phố": "thanh_pho",
            "Nông Trại Nhân Loại": "nong_trai",
            "Kuwait": "kuwait",
            "Pease Thành": "pease",
        }.get(map_name)
        
        if not map_key or map_key not in SIDE_PLOT_TEMPLATES:
            return suggestions
        
        for sp in SIDE_PLOT_TEMPLATES[map_key]:
            if sp.start_chapter <= chapter_num <= sp.end_chapter:
                if sp.id not in self.completed_side_plots:
                    suggestions.append(f"{sp.name}: {sp.description}")
        
        return suggestions[:2]  # Max 2 suggestions
    
    def verify_expansion(self, raw_length: int, output_length: int, target: ExpansionTarget) -> Tuple[bool, str]:
        """
        Verify expansion đạt target chưa - NGHIÊM NGẶT
        
        Returns: (passed, reason)
        """
        actual_ratio = output_length / raw_length if raw_length > 0 else 0
        target_ratio = target.min_ratio
        
        # Tính minimum chars cần có
        min_required = int(raw_length * target_ratio * 0.85)  # 85% của target
        
        # Check minimum ratio - nghiêm ngặt hơn (85% tolerance thay vì 90%)
        if actual_ratio < target_ratio * 0.85:
            shortage = int((target_ratio - actual_ratio) * raw_length)
            percent_short = int((1 - actual_ratio / target_ratio) * 100)
            return False, f"Quá ngắn {percent_short}%: {output_length:,} chars (cần ít nhất {min_required:,}, thiếu ~{shortage:,})"
        
        # Check if too short in absolute terms
        if output_length < self.CHARS_PER_CHAPTER_MIN:
            return False, f"Chương quá ngắn: {output_length:,} < {self.CHARS_PER_CHAPTER_MIN:,} chars"
        
        # Check if output shorter than input (trường hợp xấu nhất)
        if output_length < raw_length:
            return False, f"Output ngắn hơn input! {output_length:,} < {raw_length:,}"
        
        return True, f"OK: x{actual_ratio:.2f} (target: x{target_ratio:.2f})"
    
    def should_split_output(self, output_length: int) -> Tuple[bool, int]:
        """
        Kiểm tra có nên split output không
        
        Returns: (should_split, split_count)
        """
        if not self.enable_splitting:
            return False, 1
        
        if output_length <= self.CHARS_PER_CHAPTER_MAX:
            return False, 1
        
        split_count = max(2, int(output_length / self.CHARS_PER_CHAPTER_IDEAL))
        return True, split_count
    
    def split_chapter(
        self, 
        content: str, 
        chapter_num: int, 
        chapter_title: str,
        split_count: int
    ) -> List[Tuple[str, str, str]]:
        """
        Tách một chương thành nhiều chương con VỚI TIÊU ĐỀ THÔNG MINH
        
        Args:
            content: Nội dung đã dịch
            chapter_num: Số chương gốc
            chapter_title: Tiêu đề chương gốc
            split_count: Tách thành bao nhiêu phần
        
        Returns: [(chapter_id, chapter_title, content), ...]
        Ví dụ: 
            [
                ("52", "Chương 52: Bệnh Viện Kinh Hoàng (Thượng)", "..."),
                ("52.1", "Chương 52: Bệnh Viện Kinh Hoàng (Hạ)", "...")
            ]
        """
        if split_count <= 1:
            return [(str(chapter_num), chapter_title, content)]
        
        # Split by paragraphs - tìm điểm cắt tự nhiên
        paragraphs = content.split('\n\n')
        total_paragraphs = len(paragraphs)
        
        # Tính số paragraph mỗi phần
        per_split = max(1, total_paragraphs // split_count)
        
        results = []
        for i in range(split_count):
            start_idx = i * per_split
            if i == split_count - 1:
                # Phần cuối lấy hết
                end_idx = total_paragraphs
            else:
                end_idx = (i + 1) * per_split
            
            split_content = '\n\n'.join(paragraphs[start_idx:end_idx])
            
            # Tạo chapter ID
            if i == 0:
                chapter_id = str(chapter_num)
            else:
                chapter_id = f"{chapter_num}.{i}"
            
            # Tạo tiêu đề THÔNG MINH theo arc context
            part_num = i + 1
            split_title = CHAPTER_NAMER.get_split_title_for_arc(
                chapter_num=chapter_num,
                base_title=chapter_title,
                part_num=part_num,
                total_parts=split_count
            )
            
            # Thêm separator cho rõ ràng
            if i > 0:
                split_content = f"[Tiếp theo phần trước]\n\n{split_content}"
            if i < split_count - 1:
                split_content = f"{split_content}\n\n[Còn tiếp...]"
            
            results.append((chapter_id, split_title, split_content))
        
        return results
    
    def smart_split_at_scene_break(self, content: str, target_parts: int) -> List[str]:
        """
        Tách nội dung tại điểm chuyển cảnh tự nhiên
        Ưu tiên: scene break > dialogue end > paragraph end
        """
        # Tìm các scene breaks
        scene_markers = [
            '\n\n***\n\n',
            '\n\n---\n\n', 
            '\n\n* * *\n\n',
            '\n\n...\n\n',
            '\n\n——\n\n',
        ]
        
        # Thử split tại scene break trước
        for marker in scene_markers:
            if marker in content:
                parts = content.split(marker)
                if len(parts) >= target_parts:
                    # Gộp lại thành đúng số phần cần
                    result = []
                    per_group = max(1, len(parts) // target_parts)
                    for i in range(target_parts):
                        start = i * per_group
                        end = start + per_group if i < target_parts - 1 else len(parts)
                        result.append(marker.join(parts[start:end]))
                    return result
        
        # Fallback: split theo paragraphs
        paragraphs = content.split('\n\n')
        per_group = max(1, len(paragraphs) // target_parts)
        
        result = []
        for i in range(target_parts):
            start = i * per_group
            end = start + per_group if i < target_parts - 1 else len(paragraphs)
            result.append('\n\n'.join(paragraphs[start:end]))
        
        return result
    
    def get_retry_prompt(self, original_prompt: str, current_length: int, target: ExpansionTarget) -> str:
        """
        Tạo prompt retry khi output chưa đạt
        """
        needed_length = int(target.min_ratio * current_length / (current_length / target.min_ratio * 0.9))
        
        retry_instruction = f"""
[⚠️ OUTPUT CHƯA ĐẠT TARGET - YÊU CẦU MỞ RỘNG THÊM]

Bản dịch trước quá ngắn. Cần mở rộng thêm!

📊 THỐNG KÊ:
- Độ dài hiện tại: {current_length} chars
- Độ dài cần đạt: {needed_length} chars (tối thiểu)
- Tỉ lệ cần: {target.min_ratio:.1f}x

📝 YÊU CẦU MỞ RỘNG THÊM:
"""
        
        for exp_type in target.expansion_types:
            if exp_type == "DETAIL":
                retry_instruction += "- Thêm chi tiết môi trường: mùi, âm thanh, cảm giác\n"
            elif exp_type == "CHARACTER":
                retry_instruction += "- Thêm suy nghĩ nội tâm của nhân vật\n"
            elif exp_type == "WORLD":
                retry_instruction += "- Giải thích thêm về cơ chế của thế giới\n"
            elif exp_type == "BACKSTORY":
                retry_instruction += "- Thêm hồi tưởng về quá khứ nhân vật\n"
            elif exp_type == "SIDE_QUEST":
                retry_instruction += "- Thêm nhiệm vụ phụ hoặc sự kiện phụ\n"
            elif exp_type == "FLASHBACK":
                retry_instruction += "- Thêm flashback về sự kiện liên quan\n"
            elif exp_type == "NEW_STORYLINE":
                retry_instruction += "- Bắt đầu tuyến truyện mới\n"
        
        if target.side_plot_suggestions:
            retry_instruction += "\n💡 GỢI Ý SIDE PLOT:\n"
            for sp in target.side_plot_suggestions:
                retry_instruction += f"- {sp}\n"
        
        retry_instruction += "\n" + "=" * 50 + "\n\n"
        
        return retry_instruction + original_prompt
    
    def build_expansion_prompt(self, chapter_num: int, raw_content: str) -> str:
        """
        Build prompt với expansion instructions
        """
        raw_length = len(raw_content)
        target = self.calculate_expansion_target(chapter_num, raw_length)
        
        prompt_parts = []
        
        # Header
        map_name, potential, _, _ = self.get_map_info(chapter_num)
        prompt_parts.append(f"""
╔══════════════════════════════════════════════════════════════╗
║  SMART EXPANSION - Chương {chapter_num}
║  Map: {map_name} (Potential: {potential}/10)
║  Target: {target.min_ratio:.1f}x → {target.recommended_ratio:.1f}x
╚══════════════════════════════════════════════════════════════╝
""")
        
        # Expansion instructions
        prompt_parts.append("[YÊU CẦU MỞ RỘNG NỘI DUNG]\n")
        
        for exp_type in target.expansion_types:
            if exp_type == "DETAIL":
                prompt_parts.append("""
📍 CHI TIẾT MÔI TRƯỜNG:
- Mô tả khí trời, ánh sáng, nhiệt độ
- Âm thanh xung quanh (tiếng gió, tiếng chân, tiếng thở)
- Mùi hương/mùi vị đặc trưng
- Cảm giác vật lý (nóng/lạnh, ẩm/khô)
""")
            elif exp_type == "CHARACTER":
                prompt_parts.append("""
👤 TÂM LÝ NHÂN VẬT:
- Suy nghĩ nội tâm khi đối mặt sự kiện
- Phản ứng cảm xúc chi tiết
- Liên hệ với quá khứ/kinh nghiệm trước
- Phát triển mối quan hệ giữa các nhân vật
""")
            elif exp_type == "WORLD":
                prompt_parts.append("""
🌍 WORLD BUILDING:
- Giải thích cơ chế hoạt động của thế giới
- Lịch sử của địa điểm/sự kiện
- Quy luật của dị loại/siêu nhiên
- Mối liên hệ giữa các khu vực
""")
            elif exp_type == "BACKSTORY":
                prompt_parts.append("""
📜 BACKSTORY:
- Hồi ức về quá khứ nhân vật
- Giải thích tại sao nhân vật hành xử như vậy
- Tiết lộ bí mật từng chút một
""")
            elif exp_type == "SIDE_QUEST":
                prompt_parts.append("""
🎯 NHIỆM VỤ PHỤ:
- Thêm mục tiêu phụ cho nhân vật
- Các thử thách nhỏ trên đường đi
- Phần thưởng hoặc thông tin từ nhiệm vụ phụ
""")
            elif exp_type == "DEEP_EXPLORE":
                prompt_parts.append("""
🔍 KHÁM PHÁ SÂU:
- Khám phá các ngóc ngách của địa điểm
- Phát hiện bí mật ẩn giấu
- Gặp gỡ NPC/dị loại mới
""")
            elif exp_type == "FLASHBACK":
                prompt_parts.append("""
⏪ FLASHBACK:
- Hồi ức về sự kiện quan trọng trong quá khứ
- Liên kết với ngoại truyện nếu có
- Tiết lộ thông tin mới qua hồi ức
""")
            elif exp_type == "NEW_STORYLINE":
                prompt_parts.append("""
🆕 TUYẾN TRUYỆN MỚI:
- Giới thiệu nhân vật/thế lực mới
- Đặt ra bí ẩn cần giải đáp
- Mở ra hướng đi mới cho cốt truyện
""")
            elif exp_type == "SMART_CHARACTER":
                prompt_parts.append("""
🧠 NHÂN VẬT THÔNG MINH (CHỐNG NGÁO NGƠ):
❌ TRÁNH:
- Nhân vật bỏ lỡ thông tin rõ ràng trước mắt
- Không sử dụng kiến thức từ loop trước
- Hành động ngu ngốc để phục vụ plot

✅ YÊU CẦU:
- Lâm Nhất LUÔN sử dụng thông tin từ loop trước
- Phân tích trước khi hành động
- Mọi hành động phải có logic
""")
        
        # Side plot suggestions
        if target.side_plot_suggestions:
            prompt_parts.append("\n💡 GỢI Ý SIDE PLOT (có thể tích hợp):\n")
            for sp in target.side_plot_suggestions:
                prompt_parts.append(f"• {sp}\n")
        
        # Target reminder
        prompt_parts.append(f"""
═══════════════════════════════════════════════════════════════
⚠️ QUAN TRỌNG: Output phải có độ dài TỐI THIỂU {target.min_ratio:.1f}x so với input
   Input: ~{raw_length} chars → Output: ~{int(raw_length * target.min_ratio)} chars trở lên
═══════════════════════════════════════════════════════════════
""")
        
        return '\n'.join(prompt_parts)
    
    def record_result(self, result: ExpansionResult):
        """Ghi lại kết quả expansion"""
        self.expansion_history.append(result)
    
    def get_stats(self) -> Dict:
        """Thống kê expansion"""
        if not self.expansion_history:
            return {"total": 0}
        
        total = len(self.expansion_history)
        met_target = sum(1 for r in self.expansion_history if r.met_target)
        avg_ratio = sum(r.actual_ratio for r in self.expansion_history) / total
        total_splits = sum(len(r.output_chapters) - 1 for r in self.expansion_history)
        
        return {
            "total_chapters": total,
            "met_target": met_target,
            "success_rate": f"{met_target/total*100:.1f}%",
            "average_ratio": f"{avg_ratio:.2f}x",
            "chapters_added_by_split": total_splits,
            "side_plots_added": len(self.completed_side_plots),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def estimate_final_chapter_count(
    total_raw_chapters: int,
    extra_chapters: int,
    min_expansion_rate: float,
    auto_adjust: bool = True
) -> Dict:
    """
    Ước tính số chương cuối cùng
    
    Returns dict với các thông tin ước tính
    """
    engine = SmartExpansionEngine(min_expansion_rate, auto_adjust)
    
    estimated_splits = 0
    estimated_side_plots = 0
    
    for chap in range(1, total_raw_chapters + 1):
        target = engine.calculate_expansion_target(chap, 5000)  # Assume 5000 chars avg
        
        # Count splits
        if target.should_split:
            estimated_splits += target.split_count - 1
        
        # Count unique side plots
        map_name, _, _, _ = engine.get_map_info(chap)
        estimated_side_plots += len(target.side_plot_suggestions)
    
    # Deduplicate side plots
    estimated_side_plots = estimated_side_plots // 3  # Rough estimate
    
    base_chapters = total_raw_chapters + extra_chapters
    final_estimate_min = base_chapters + estimated_splits
    final_estimate_max = final_estimate_min + estimated_side_plots
    
    return {
        "raw_main_chapters": total_raw_chapters,
        "extra_chapters": extra_chapters,
        "base_total": base_chapters,
        "estimated_splits": estimated_splits,
        "estimated_side_plots": estimated_side_plots,
        "final_estimate_min": final_estimate_min,
        "final_estimate_max": final_estimate_max,
        "expansion_ratio": f"{final_estimate_max / total_raw_chapters:.2f}x"
    }


# ============================================================================
# STORY MAPS - Dữ liệu map cho GUI visualization
# ============================================================================

@dataclass
class StoryMap:
    """Thông tin một map trong truyện"""
    name: str
    chapter_range: Tuple[int, int]
    exploration_potential: int  # 1-10
    unexplored_areas: List[str]
    max_expansion: float
    side_plots_available: int


# Tạo STORY_MAPS từ MAP_POTENTIALS - dynamic, không hardcode
STORY_MAPS: Dict[str, StoryMap] = {}

# Build STORY_MAPS từ loaded MAP_POTENTIALS (có thể empty nếu chưa có config)
for (start, end), (name, potential, max_expand, side_count) in MAP_POTENTIALS.items():
    STORY_MAPS[name] = StoryMap(
        name=name,
        chapter_range=(start, end),
        exploration_potential=potential,
        unexplored_areas=[],  # Sẽ được WorldBuilder tự học
        max_expansion=max_expand,
        side_plots_available=side_count
    )


def reload_map_data():
    """
    Reload MAP_POTENTIALS và STORY_MAPS từ world_config.json
    Call this để refresh data sau khi WorldBuilder update
    """
    global MAP_POTENTIALS, STORY_MAPS
    
    # Reload from config
    MAP_POTENTIALS = _load_map_potentials()

    # Rebuild STORY_MAPS
    STORY_MAPS.clear()
    for (start, end), (name, potential, max_expand, side_count) in MAP_POTENTIALS.items():
        STORY_MAPS[name] = StoryMap(
            name=name,
            chapter_range=(start, end),
            exploration_potential=potential,
            unexplored_areas=[],
            max_expansion=max_expand,
            side_plots_available=side_count
        )
    
    print(f"[ExpansionEngine] Reloaded: {len(MAP_POTENTIALS)} maps, {len(STORY_MAPS)} story maps")


# ============================================================================
# STORY ANALYZER - Phân tích truyện cho GUI
# ============================================================================

class StoryAnalyzer:
    """Class phân tích truyện - dùng cho GUI"""
    
    @staticmethod
    def get_expansion_potential(chapter_num: int) -> Dict:
        """
        Phân tích tiềm năng mở rộng của một chương
        
        Returns dict với thông tin phân tích
        """
        # Tìm map hiện tại - dynamic từ MAP_POTENTIALS
        current_map = None
        for (start, end), (name, potential, max_expand, side_count) in MAP_POTENTIALS.items():
            if start <= chapter_num <= end:
                current_map = {
                    'name': name,
                    'potential': potential,
                    'max_expand': max_expand,
                    'unexplored': [],  # Sẽ được WorldBuilder tự học
                }
                break
        
        # Tìm extra chapter có thể chèn
        extra_available = None
        for extra in EXTRA_CHAPTERS:
            if extra.best_insertion_point == chapter_num:
                extra_available = {
                    'title': extra.title,
                    'characters': extra.characters,
                    'trigger': extra.insertion_trigger,
                }
                break
        
        # Tính recommended expansion
        if current_map:
            pot = current_map['potential']
            if pot >= 8:
                recommended = 2.5 + (pot - 8) * 0.5
            elif pot >= 5:
                recommended = 1.5 + (pot - 5) * 0.3
            else:
                recommended = 1.0 + pot * 0.1
        else:
            # Không có map data → dùng default
            recommended = 1.5
        
        return {
            'chapter': chapter_num,
            'current_map': current_map,
            'extra_available': extra_available,
            'recommended_expansion': round(recommended, 1),
        }
    
    @staticmethod
    def generate_expansion_plan(start_chap: int, end_chap: int, expansion_rate: float) -> List[Dict]:
        """
        Tạo kế hoạch mở rộng cho range chương
        
        Returns list of dicts với thông tin từng chương
        """
        engine = SmartExpansionEngine(min_expansion_rate=expansion_rate, auto_adjust=True)
        plan = []
        
        for chap in range(start_chap, end_chap + 1):
            # Estimate raw length (average)
            raw_length = 5000
            target = engine.calculate_expansion_target(chap, raw_length)
            
            # Check for extra chapter
            insert_extra = False
            extra_title = None
            for extra in EXTRA_CHAPTERS:
                if extra.best_insertion_point == chap:
                    insert_extra = True
                    extra_title = extra.title
                    break
            
            plan.append({
                'chapter': chap,
                'min_ratio': target.min_ratio,
                'recommended_ratio': target.recommended_ratio,
                'should_split': target.should_split,
                'split_count': target.split_count,
                'expansion_types': target.expansion_types,
                'side_plots': target.side_plot_suggestions,
                'insert_extra': insert_extra,
                'extra_title': extra_title,
            })
        
        return plan


# ============================================================================
# EXPANSION CONFIG - Config cho expansion engine
# ============================================================================

@dataclass
class ExpansionConfig:
    """Config cho expansion engine"""
    min_expansion_rate: float = 1.5
    auto_adjust: bool = True
    enable_splitting: bool = True
    enable_side_plots: bool = True
    max_retries: int = 2
    chars_per_chapter_min: int = 3000
    chars_per_chapter_max: int = 12000
    chars_per_chapter_ideal: int = 6000
    
    def to_dict(self) -> Dict:
        """Convert to dict for saving"""
        return {
            'min_expansion_rate': self.min_expansion_rate,
            'auto_adjust': self.auto_adjust,
            'enable_splitting': self.enable_splitting,
            'enable_side_plots': self.enable_side_plots,
            'max_retries': self.max_retries,
            'chars_per_chapter_min': self.chars_per_chapter_min,
            'chars_per_chapter_max': self.chars_per_chapter_max,
            'chars_per_chapter_ideal': self.chars_per_chapter_ideal,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ExpansionConfig':
        """Create from dict"""
        return cls(**data)
    
    def create_engine(self) -> SmartExpansionEngine:
        """Tạo engine từ config"""
        engine = SmartExpansionEngine(
            min_expansion_rate=self.min_expansion_rate,
            auto_adjust=self.auto_adjust,
            enable_splitting=self.enable_splitting,
            enable_side_plots=self.enable_side_plots,
            max_retries=self.max_retries
        )
        # Set thresholds
        engine.CHARS_PER_CHAPTER_MIN = self.chars_per_chapter_min
        engine.CHARS_PER_CHAPTER_MAX = self.chars_per_chapter_max
        engine.CHARS_PER_CHAPTER_IDEAL = self.chars_per_chapter_ideal
        return engine
