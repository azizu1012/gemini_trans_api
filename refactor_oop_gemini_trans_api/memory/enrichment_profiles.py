"""
Enrichment Profiles — Làm giàu có chủ đích, thay thế expansion_rate multiplier
Mỗi enrichment type có mục đích rõ ràng, không phải "kéo dài vô nghĩa"
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


class EnrichmentType(str, Enum):
    """Loại làm giàu — mỗi loại có mục đích riêng, áp dụng theo scene"""
    SENSORY_DETAIL = "sensory_detail"
    CHARACTER_DEPTH = "character_depth"
    WORLD_BUILDING = "world_building"
    LORE_EXPOSITION = "lore_exposition"
    ACTION_PACING = "action_pacing"
    DIALOGUE_SUBTEXT = "dialogue_subtext"
    EMOTIONAL_BEAT = "emotional_beat"


ENRICHMENT_PROMPTS: Dict[EnrichmentType, str] = {
    EnrichmentType.SENSORY_DETAIL: """
📍 LÀM GIÀU CẢM GIÁC:
- Mô tả khí trời, ánh sáng, nhiệt độ tại địa điểm hiện tại
- Âm thanh xung quanh (tiếng gió, tiếng chân, tiếng thở, tiếng kim loại)
- Mùi hương/mùi vị đặc trưng (mùi máu, mùi ẩm mốc, mùi xác chết)
- Cảm giác vật lý (nóng/lạnh, ẩm/khô, đau đớn)
- Ánh sáng mạt thế: lờ mờ, xám xịt, hoặc ánh đèn neon dị loại
""",

    EnrichmentType.CHARACTER_DEPTH: """
👤 LÀM GIÀU TÂM LÝ NHÂN VẬT:
- Suy nghĩ nội tâm khi đối mặt sự kiện hiện tại
- Phản ứng cảm xúc chi tiết (không chỉ "tức giận" mà là "siết chặt nắm đấm đến răng rắc")
- Liên hệ với quá khứ/kinh nghiệm — chiến dịch trước đã dạy nhân vật bài học gì
- Trauma tác động lên quyết định hiện tại (tham chiếu CharacterState)
- Phát triển mối quan hệ qua hành động, không phải lời nói
""",

    EnrichmentType.WORLD_BUILDING: """
🌍 LÀM GIÀU THẾ GIỚI:
- Giải thích cơ chế hoạt động của dị loại/khu vực hiện tại
- Lịch sử của địa điểm — tại sao nơi này lại như thế này
- Quy luật sinh tồn: dị loại hoạt động thế nào, điểm yếu, tập tính
- Mối liên hệ giữa các khu vực (con đường, tổ chức ngầm)
- Chỉ thêm khi nhân vật đang khám phá hoặc quan sát — không exposition dump
""",

    EnrichmentType.LORE_EXPOSITION: """
📜 TIẾT LỘ THÔNG TIN CÓ CHỦ ĐÍCH:
- Tiết lộ bí mật thế giới qua hội thoại hoặc khám phá
- Giải thích quá khứ nhân vật thông qua flashback ngắn
- Manh mối về âm mưu lớn hơn — chỉ đủ để reader tò mò
- Kết nối sự kiện hiện tại với truyền thuyết/lịch sử đã được thiết lập
- MỘT LẦN MỘT LÚC — không dump toàn bộ lore
""",

    EnrichmentType.ACTION_PACING: """
⚡ LÀM GIÀU HÀNH ĐỘNG:
- Câu văn ngắn, dứt khoát, nhịp nhanh
- Mô tả chuyển động: góc đánh, hướng né, khoảng cách
- Cảm giác vật lý: va chạm, đau đớn, mệt mỏi
- Môi trường phản ứng: tường nứt, bụi bay, kính vỡ
- Hội thoại ngắt quãng, câu ngắn, khó thở
""",

    EnrichmentType.DIALOGUE_SUBTEXT: """
💬 LÀM GIÀU HỘI THOẠI:
- Thêm action beats giữa lời thoại (không để hội thoại trần)
- Ẩn ý: nhân vật nói một đằng nhưng hành động/ngữ điệu một nẻo
- Mỗi nhân vật có giọng nói riêng (tham chiếu CharacterVoice từ StyleLearner)
- Khoảng lặng, ngập ngừng, ngắt lời — tạo chiều sâu
- Hội thoại phải đẩy cốt truyện hoặc phát triển nhân vật, không chỉ lấp đầy
""",

    EnrichmentType.EMOTIONAL_BEAT: """
💔 LÀM GIÀU CẢM XÚC:
- Đây là cảnh cao trào cảm xúc: mất mát, hy sinh, phản bội, tha thứ
- Dùng kỹ thuật Show Don't Tell triệt để
- Action beats thay vì miêu tả cảm xúc trực tiếp
- Nhịp chậm lại, câu văn dài hơn, chi tiết hơn
- Cho phép silence, khoảng lặng giữa các hành động
""",
}


@dataclass
class EnrichmentSuggestion:
    """Gợi ý enrichment cho một scene"""
    types: List[EnrichmentType]
    reason: str


class EnrichmentProfile:
    """
    Gợi ý enrichment type dựa trên đặc điểm scene
    Heuristic rules — không cần gọi AI
    """

    @staticmethod
    def suggest(plot_goal: str, location_is_new: bool,
                has_dialogue: bool, has_action: bool,
                has_emotional_stakes: bool,
                sensory_focus: str = "") -> EnrichmentSuggestion:
        types = []
        reasons = []

        if location_is_new or "khám phá" in plot_goal.lower() or "lần đầu" in plot_goal.lower():
            types.append(EnrichmentType.SENSORY_DETAIL)
            types.append(EnrichmentType.WORLD_BUILDING)
            reasons.append("địa điểm mới → sensory + world building")

        if has_action or "chiến" in plot_goal.lower() or "đuổi" in plot_goal.lower():
            types.append(EnrichmentType.ACTION_PACING)
            if not location_is_new:
                types.append(EnrichmentType.SENSORY_DETAIL)
            reasons.append("hành động → action pacing + sensory")

        if has_dialogue or "nói" in plot_goal.lower() or "hỏi" in plot_goal.lower():
            types.append(EnrichmentType.DIALOGUE_SUBTEXT)
            reasons.append("hội thoại → subtext + action beats")

        if has_emotional_stakes or "mất" in plot_goal.lower() or "hy sinh" in plot_goal.lower():
            types.append(EnrichmentType.EMOTIONAL_BEAT)
            reasons.append("cảm xúc cao → emotional beat")

        if "bí mật" in plot_goal.lower() or "phát hiện" in plot_goal.lower() or "thật" in plot_goal.lower():
            types.append(EnrichmentType.LORE_EXPOSITION)
            reasons.append("tiết lộ → lore exposition")

        if has_dialogue and has_emotional_stakes:
            types.append(EnrichmentType.CHARACTER_DEPTH)
            reasons.append("hội thoại cảm xúc → character depth")

        if sensory_focus == "psychological":
            types.append(EnrichmentType.CHARACTER_DEPTH)
            if EnrichmentType.EMOTIONAL_BEAT not in types:
                reasons.append("tâm lý → character depth")

        # Loại bỏ trùng
        seen = set()
        unique = []
        for t in types:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        return EnrichmentSuggestion(
            types=unique[:4],  # Max 4 enrichment types per scene
            reason="; ".join(reasons)
        )

    @staticmethod
    def get_prompt_section(types: List[EnrichmentType]) -> str:
        """Build prompt section từ danh sách enrichment types"""
        parts = []
        for t in types:
            prompt = ENRICHMENT_PROMPTS.get(t)
            if prompt:
                parts.append(prompt.strip())
        if parts:
            return "\n" + "\n".join(parts) + "\n"
        return ""
