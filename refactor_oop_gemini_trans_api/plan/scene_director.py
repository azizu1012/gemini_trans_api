"""
SceneDirector — bẻ ChapterNote thành List[SceneBeat]
Mỗi SceneBeat có enrichment types riêng, viết riêng, review riêng
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class SceneBeat:
    scene_index: int
    location: str
    characters_present: List[str]
    plot_goal: str
    enrichment_types: List[str] = field(default_factory=list)
    sensory_focus: str = "visual"  # visual, auditory, psychological, action
    key_dialogue_topics: List[str] = field(default_factory=list)
    tone: str = "dark"
    pacing: str = "medium"


class SceneDirector:

    def __init__(self):
        self._scene_counter = 0

    def plan_scenes(self, chapter_title: str, chapter_num: int,
                    required_events: List[str],
                    character_moments: Dict[str, str],
                    tone: str, pacing: str,
                    current_location: str = "") -> List[SceneBeat]:
        """
        Bẻ chapter outline → List[SceneBeat] dùng heuristics
        Không cần gọi AI — dùng rule-based để YAGNI
        """
        if not required_events:
            required_events = [f"Tiếp diễn cốt truyện tại {current_location or 'không gian hiện tại'}"]

        scenes = []
        self._scene_counter = 0

        for i, event in enumerate(required_events):
            self._scene_counter += 1
            event_lower = event.lower()

            # Xác định sensory_focus dựa trên nội dung event
            if any(w in event_lower for w in ["chiến", "đánh", "đuổi", "rượt", "chạy", "tấn công"]):
                sf = "action"
            elif any(w in event_lower for w in ["nói", "hỏi", "thương lượng", "thuyết phục", "bàn"]):
                sf = "auditory"
            elif any(w in event_lower for w in ["cảm", "xúc", "mất", "buồn", "giận", "sợ"]):
                sf = "psychological"
            else:
                # Luân phiên sensory focus
                sf = ["visual", "auditory", "psychological", "visual", "action"][i % 5]

            # Xác định characters từ character_moments
            chars = []
            for char_name, moment in character_moments.items():
                if any(w in event_lower for w in char_name.lower().split()):
                    chars.append(char_name)

            # Nếu event có nhắc tới nhân vật
            for char_name in character_moments:
                if char_name.lower() in event_lower:
                    if char_name not in chars:
                        chars.append(char_name)

            scene = SceneBeat(
                scene_index=self._scene_counter,
                location=self._infer_location(event, current_location, i),
                characters_present=chars or list(character_moments.keys())[:3],
                plot_goal=event,
                sensory_focus=sf,
                tone=tone,
                pacing=self._infer_pacing(event, pacing, i, len(required_events)),
            )

            # Dialogue topics nếu scene có hội thoại
            if sf == "auditory" or "nói" in event_lower:
                scene.key_dialogue_topics = [event]

            scenes.append(scene)

        return scenes

    def _infer_location(self, event: str, current_location: str, index: int) -> str:
        """Suy luận địa điểm từ event"""
        location_keywords = [
            ("trong", "trong"), ("ngoài", "ngoài"), ("trên đường", "trên đường"),
            ("phòng", "phòng"), ("khu", "khu"), ("thành", "thành"),
            ("cổng", "cổng"), ("tầng", "tầng"), ("đỉnh", "đỉnh"),
            ("dưới", "dưới"), ("bên", "bên"),
        ]
        for kw, hint in location_keywords:
            if kw in event.lower():
                return f"{hint} {current_location}" if current_location else hint
        return current_location or f"khu vực {index + 1}"

    def _infer_pacing(self, event: str, default_pacing: str,
                      index: int, total: int) -> str:
        """Suy luận pacing từ event"""
        event_lower = event.lower()
        action_words = ["chiến", "đánh", "đuổi", "gấp", "nguy", "chạy", "tấn công"]
        if any(w in event_lower for w in action_words):
            return "fast"
        calm_words = ["nghỉ", "chuẩn", "bị", "chuẩn bị", "nói", "bàn", "kế hoạch"]
        if any(w in event_lower for w in calm_words):
            return "slow"
        if index == total - 1:
            return "climax"
        return default_pacing

    @staticmethod
    def merge_scenes(scenes_texts: List[Tuple[int, str, str]]) -> str:
        """
        Gộp các scene đã viết thành chapter hoàn chỉnh
        scenes_texts: [(scene_index, title, content), ...]
        """
        parts = []
        for idx, title, content in scenes_texts:
            if title:
                parts.append(f"## {title}")
            parts.append(content.strip())
        return "\n\n".join(parts)
