"""
Pacing Controller Module
========================
Bộ điều soát nhịp độ chương

Vấn đề: "Cuốn chiếu" chỉ nhìn sự kiện, không nhìn cảm xúc hay nhịp độ
- AI có thể nhồi nhét sự kiện tương lai vào quá sớm (Spoil)
- Hoặc viết quá lan man vì thấy còn nhiều chỗ trống

Giải pháp: Pacing Controller
- Biết "Chương này là khoảng lặng, cấm đánh nhau"
- Hoặc "Chương này là cao trào, phải viết dồn dập"
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class PacingType(Enum):
    """Loại nhịp độ"""
    SLOW = "slow"           # Chậm - Miêu tả, tâm lý, world-building
    BUILDUP = "buildup"     # Dựng - Chuẩn bị cho cao trào
    MEDIUM = "medium"       # Trung bình - Cân bằng
    FAST = "fast"           # Nhanh - Action, căng thẳng
    CLIMAX = "climax"       # Cao trào - Đỉnh điểm
    RESOLUTION = "resolution"  # Giải quyết - Sau cao trào
    TRANSITION = "transition"  # Chuyển tiếp - Giữa các arc


class ContentRestriction(Enum):
    """Hạn chế nội dung theo nhịp độ"""
    FORBIDDEN = "forbidden"   # Cấm tuyệt đối
    DISCOURAGED = "discouraged"  # Không khuyến khích
    NEUTRAL = "neutral"       # Tùy ý
    ENCOURAGED = "encouraged"  # Khuyến khích
    REQUIRED = "required"     # Bắt buộc phải có


@dataclass
class PacingRule:
    """Quy tắc cho một loại nhịp độ"""
    pacing_type: PacingType
    
    # Yêu cầu nội dung
    content_rules: Dict[str, ContentRestriction] = field(default_factory=dict)
    # Ví dụ: {"action": FORBIDDEN, "dialogue": REQUIRED, "flashback": ENCOURAGED}
    
    # Độ dài mong muốn
    min_length: int = 4000
    max_length: int = 10000
    ideal_length: int = 6000
    
    # Cấu trúc
    min_paragraphs: int = 10
    min_dialogues: int = 5
    
    # Kết thúc
    ending_type: str = "open"  # "open", "cliffhanger", "resolution", "transition"
    
    # Hướng dẫn bổ sung
    guidance: List[str] = field(default_factory=list)


# Định nghĩa các quy tắc pacing
PACING_RULES: Dict[PacingType, PacingRule] = {
    PacingType.SLOW: PacingRule(
        pacing_type=PacingType.SLOW,
        content_rules={
            "major_battle": ContentRestriction.FORBIDDEN,
            "boss_fight": ContentRestriction.FORBIDDEN,
            "death": ContentRestriction.DISCOURAGED,
            "dialogue": ContentRestriction.REQUIRED,
            "flashback": ContentRestriction.ENCOURAGED,
            "world_building": ContentRestriction.REQUIRED,
            "character_development": ContentRestriction.REQUIRED,
            "romance_hint": ContentRestriction.ENCOURAGED,
        },
        min_length=5000,
        max_length=8000,
        ideal_length=6000,
        ending_type="open",
        guidance=[
            "Tập trung vào tâm lý nhân vật",
            "Miêu tả môi trường chi tiết",
            "Có thể có flashback hoặc hồi ức",
            "Đối thoại nhẹ nhàng, không căng thẳng",
            "CẤM có trận đánh lớn",
        ]
    ),
    
    PacingType.BUILDUP: PacingRule(
        pacing_type=PacingType.BUILDUP,
        content_rules={
            "major_battle": ContentRestriction.FORBIDDEN,
            "boss_fight": ContentRestriction.FORBIDDEN,
            "minor_conflict": ContentRestriction.ENCOURAGED,
            "foreshadowing": ContentRestriction.REQUIRED,
            "tension": ContentRestriction.REQUIRED,
            "preparation": ContentRestriction.ENCOURAGED,
        },
        min_length=5000,
        max_length=9000,
        ideal_length=7000,
        ending_type="cliffhanger",
        guidance=[
            "Xây dựng căng thẳng từ từ",
            "Hint về mối đe dọa sắp tới",
            "Nhân vật chuẩn bị hoặc lên kế hoạch",
            "KẾT THÚC BẰNG CLIFFHANGER",
            "Chưa được giải quyết xung đột chính",
        ]
    ),
    
    PacingType.MEDIUM: PacingRule(
        pacing_type=PacingType.MEDIUM,
        content_rules={
            "action": ContentRestriction.NEUTRAL,
            "dialogue": ContentRestriction.REQUIRED,
            "description": ContentRestriction.ENCOURAGED,
        },
        min_length=4000,
        max_length=10000,
        ideal_length=6000,
        ending_type="open",
        guidance=[
            "Cân bằng action và đối thoại",
            "Có thể có xung đột nhỏ",
            "Tiến triển plot vừa phải",
        ]
    ),
    
    PacingType.FAST: PacingRule(
        pacing_type=PacingType.FAST,
        content_rules={
            "action": ContentRestriction.REQUIRED,
            "long_description": ContentRestriction.FORBIDDEN,
            "flashback": ContentRestriction.FORBIDDEN,
            "tension": ContentRestriction.REQUIRED,
            "quick_dialogue": ContentRestriction.REQUIRED,
        },
        min_length=4000,
        max_length=8000,
        ideal_length=5500,
        min_paragraphs=15,  # Nhiều đoạn ngắn
        ending_type="cliffhanger",
        guidance=[
            "Viết CÂU NGẮN, dứt khoát",
            "Action liên tục, không miêu tả lan man",
            "Đối thoại ngắn, căng thẳng",
            "CẤM flashback, CẤM hồi ức",
            "Nhịp độ nhanh, dồn dập",
        ]
    ),
    
    PacingType.CLIMAX: PacingRule(
        pacing_type=PacingType.CLIMAX,
        content_rules={
            "major_battle": ContentRestriction.REQUIRED,
            "death": ContentRestriction.ENCOURAGED,
            "revelation": ContentRestriction.ENCOURAGED,
            "emotional_peak": ContentRestriction.REQUIRED,
            "flashback": ContentRestriction.FORBIDDEN,
            "comedy": ContentRestriction.FORBIDDEN,
        },
        min_length=6000,
        max_length=12000,
        ideal_length=8000,
        min_dialogues=10,
        ending_type="resolution",
        guidance=[
            "⚡ CAO TRÀO - Phải có IMPACT lớn",
            "Trận đánh quyết định hoặc revelation quan trọng",
            "Có thể có nhân vật chết hoặc bị thương nặng",
            "Cảm xúc mãnh liệt, căng thẳng tột độ",
            "CẤM đùa cợt, CẤM flashback",
            "Kết thúc với quyết định/kết quả rõ ràng",
        ]
    ),
    
    PacingType.RESOLUTION: PacingRule(
        pacing_type=PacingType.RESOLUTION,
        content_rules={
            "major_battle": ContentRestriction.FORBIDDEN,
            "aftermath": ContentRestriction.REQUIRED,
            "healing": ContentRestriction.ENCOURAGED,
            "reflection": ContentRestriction.REQUIRED,
            "setup_next": ContentRestriction.ENCOURAGED,
        },
        min_length=4000,
        max_length=8000,
        ideal_length=5000,
        ending_type="transition",
        guidance=[
            "Xử lý hậu quả của cao trào",
            "Nhân vật phản ánh về những gì đã xảy ra",
            "Có thể có hồi phục, chữa lành",
            "CẤM chiến đấu lớn",
            "Setup nhẹ cho arc tiếp theo",
        ]
    ),
    
    PacingType.TRANSITION: PacingRule(
        pacing_type=PacingType.TRANSITION,
        content_rules={
            "travel": ContentRestriction.REQUIRED,
            "new_location": ContentRestriction.ENCOURAGED,
            "world_building": ContentRestriction.REQUIRED,
            "major_battle": ContentRestriction.FORBIDDEN,
        },
        min_length=3000,
        max_length=6000,
        ideal_length=4500,
        ending_type="open",
        guidance=[
            "Chuyển từ location/arc cũ sang mới",
            "Giới thiệu địa điểm mới",
            "Không có chiến đấu lớn",
            "Có thể gặp nhân vật mới",
        ]
    ),
}


@dataclass
class ChapterPacingPlan:
    """Kế hoạch pacing cho một chương"""
    chapter_num: int
    pacing_type: PacingType
    rule: PacingRule
    
    # Override cho chương này
    custom_restrictions: Dict[str, ContentRestriction] = field(default_factory=dict)
    custom_guidance: List[str] = field(default_factory=list)
    
    # Meta
    reason: str = ""  # Lý do chọn pacing này
    arc_context: str = ""  # Context từ arc
    
    def get_effective_rules(self) -> Dict[str, ContentRestriction]:
        """Lấy rules hiệu lực (rule + custom override)"""
        rules = dict(self.rule.content_rules)
        rules.update(self.custom_restrictions)
        return rules
    
    def get_all_guidance(self) -> List[str]:
        """Lấy tất cả hướng dẫn"""
        return self.rule.guidance + self.custom_guidance
    
    def to_prompt_instruction(self) -> str:
        """Tạo instruction cho prompt"""
        lines = [
            f"[PACING - NHỊP ĐỘ CHƯƠNG]",
            f"📊 Loại: {self.pacing_type.value.upper()}",
            f"📖 Lý do: {self.reason}",
            "",
            f"📏 ĐỘ DÀI:",
            f"   Min: {self.rule.min_length} chars",
            f"   Ideal: {self.rule.ideal_length} chars", 
            f"   Max: {self.rule.max_length} chars",
            "",
            f"✅ BẮT BUỘC:",
        ]
        
        for content_type, restriction in self.get_effective_rules().items():
            if restriction == ContentRestriction.REQUIRED:
                lines.append(f"   • {content_type.replace('_', ' ').title()}")
        
        lines.append("")
        lines.append("❌ CẤM:")
        
        for content_type, restriction in self.get_effective_rules().items():
            if restriction == ContentRestriction.FORBIDDEN:
                lines.append(f"   • {content_type.replace('_', ' ').title()}")
        
        lines.append("")
        lines.append("📝 HƯỚNG DẪN:")
        for guide in self.get_all_guidance():
            lines.append(f"   • {guide}")
        
        lines.append("")
        lines.append(f"🔚 KẾT THÚC: {self.rule.ending_type.upper()}")
        
        return "\n".join(lines)


class PacingController:
    """
    Bộ điều soát nhịp độ
    
    Chức năng:
    1. Xác định nhịp độ phù hợp cho từng chương
    2. Tạo restrictions và guidance
    3. Kiểm tra output có tuân thủ pacing không
    """
    
    def __init__(self):
        self.chapter_plans: Dict[int, ChapterPacingPlan] = {}
    
    def analyze_arc_position(
        self, 
        chapter_num: int, 
        arc_start: int, 
        arc_end: int,
        arc_climax_chapters: List[int]
    ) -> PacingType:
        """
        Phân tích vị trí trong arc để xác định pacing
        """
        total = arc_end - arc_start + 1
        position = chapter_num - arc_start
        progress = position / total
        
        # Nếu là chương climax được định sẵn
        if chapter_num in arc_climax_chapters:
            return PacingType.CLIMAX
        
        # Chương ngay sau climax
        if chapter_num - 1 in arc_climax_chapters:
            return PacingType.RESOLUTION
        
        # Chương trước climax
        for climax in arc_climax_chapters:
            if chapter_num == climax - 1:
                return PacingType.BUILDUP
            if chapter_num == climax - 2:
                return PacingType.FAST
        
        # Theo progress
        if progress < 0.15:
            return PacingType.SLOW  # Mở đầu arc
        elif progress < 0.3:
            return PacingType.MEDIUM
        elif progress > 0.9:
            return PacingType.TRANSITION  # Chuẩn bị sang arc mới
        else:
            return PacingType.MEDIUM
    
    def create_pacing_plan(
        self,
        chapter_num: int,
        arc_name: str = "",
        arc_start: int = 1,
        arc_end: int = 100,
        arc_climax_chapters: Optional[List[int]] = None,
        custom_pacing: Optional[PacingType] = None,
        custom_guidance: Optional[List[str]] = None
    ) -> ChapterPacingPlan:
        """
        Tạo kế hoạch pacing cho chương
        """
        if arc_climax_chapters is None:
            arc_climax_chapters = []
        
        # Xác định pacing type
        if custom_pacing:
            pacing_type = custom_pacing
            reason = "Custom override"
        else:
            pacing_type = self.analyze_arc_position(
                chapter_num, arc_start, arc_end, arc_climax_chapters
            )
            reason = f"Auto: vị trí trong arc {arc_name}"
        
        # Tạo plan
        plan = ChapterPacingPlan(
            chapter_num=chapter_num,
            pacing_type=pacing_type,
            rule=PACING_RULES[pacing_type],
            reason=reason,
            arc_context=arc_name,
            custom_guidance=custom_guidance or []
        )
        
        # Lưu cache
        self.chapter_plans[chapter_num] = plan
        
        return plan
    
    def get_pacing_plan(self, chapter_num: int) -> Optional[ChapterPacingPlan]:
        """Lấy pacing plan đã tạo"""
        return self.chapter_plans.get(chapter_num)
    
    def validate_content(
        self, 
        content: str, 
        plan: ChapterPacingPlan
    ) -> Tuple[bool, List[str]]:
        """
        Kiểm tra content có tuân thủ pacing không
        
        Returns: (passed, list of violations)
        """
        violations = []
        rules = plan.get_effective_rules()
        
        # Check length
        content_len = len(content)
        if content_len < plan.rule.min_length:
            violations.append(f"Quá ngắn: {content_len} < {plan.rule.min_length}")
        if content_len > plan.rule.max_length:
            violations.append(f"Quá dài: {content_len} > {plan.rule.max_length}")
        
        # Check content restrictions
        content_lower = content.lower()
        
        # Major battle detection
        battle_keywords = ["đánh", "chiến đấu", "tấn công", "xông vào", "giết"]
        battle_count = sum(content_lower.count(kw) for kw in battle_keywords)
        
        if rules.get("major_battle") == ContentRestriction.FORBIDDEN and battle_count > 10:
            violations.append(f"Có battle ({battle_count} keywords) trong chương SLOW/RESOLUTION")
        
        if rules.get("major_battle") == ContentRestriction.REQUIRED and battle_count < 5:
            violations.append("Chương CLIMAX cần có battle nhưng không đủ action")
        
        # Flashback detection
        flashback_keywords = ["năm trước", "ngày xưa", "hồi đó", "nhớ lại", "hồi ức"]
        has_flashback = any(kw in content_lower for kw in flashback_keywords)
        
        if rules.get("flashback") == ContentRestriction.FORBIDDEN and has_flashback:
            violations.append("Có flashback trong chương FAST/CLIMAX (cấm)")
        
        # Dialogue check
        dialogue_count = len(re.findall(r'[""「」『』]', content))
        if rules.get("dialogue") == ContentRestriction.REQUIRED and dialogue_count < 10:
            violations.append(f"Thiếu dialogue: chỉ có {dialogue_count} dấu ngoặc kép")
        
        # Ending check
        paragraphs = content.strip().split('\n\n')
        last_para = paragraphs[-1] if paragraphs else ""
        
        if plan.rule.ending_type == "cliffhanger":
            cliffhanger_indicators = ["...", "?!", "nhưng—", "bất ngờ", "đột nhiên"]
            if not any(ind in last_para for ind in cliffhanger_indicators):
                violations.append("Kết thúc không có cliffhanger (yêu cầu)")
        
        passed = len(violations) == 0
        return passed, violations
    
    def get_batch_pacing_overview(
        self, 
        start_chap: int, 
        end_chap: int
    ) -> str:
        """Lấy overview pacing cho batch chương"""
        lines = ["📊 PACING OVERVIEW:"]
        
        for chap in range(start_chap, end_chap + 1):
            plan = self.chapter_plans.get(chap)
            if plan:
                emoji = {
                    PacingType.SLOW: "🐢",
                    PacingType.BUILDUP: "📈",
                    PacingType.MEDIUM: "➡️",
                    PacingType.FAST: "⚡",
                    PacingType.CLIMAX: "🔥",
                    PacingType.RESOLUTION: "💤",
                    PacingType.TRANSITION: "🚶",
                }.get(plan.pacing_type, "❓")
                
                lines.append(f"   {chap}: {emoji} {plan.pacing_type.value}")
            else:
                lines.append(f"   {chap}: ❓ (chưa plan)")
        
        return "\n".join(lines)
