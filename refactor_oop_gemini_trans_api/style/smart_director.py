import json
from typing import Optional, List, Dict
from google import genai
from google.genai import types

try:
    from ..data.novel_profile import NovelProfile
    from .style_director import TAG_LABELS, DIRECTION_LABELS
except ImportError:
    from refactor_oop_gemini_trans_api.data.novel_profile import NovelProfile
    from .style_director import TAG_LABELS, DIRECTION_LABELS


ANALYZE_SYSTEM_PROMPT = """Bạn là chuyên gia phân tích tiểu thuyết.
Dựa vào NovelProfile (thế giới, nhân vật, cốt truyện đã học được),
hãy gợi ý hướng mở rộng phù hợp nhất cho những chương sắp tới.

Trả về JSON array, mỗi item có cấu trúc:
{
  "direction": "world" | "character" | "challenge" | "free",
  "tag": "de_xuat" | "co_le" | "on" | "kho" | "khong_kha_thi" | "mauthuan",
  "reason": "Giải thích ngắn gọn tại sao có tag này (dựa trên dữ liệu có sẵn)",
  "detail": "Phân tích chi tiết dựa trên dữ liệu novel (2-3 câu)"
}

QUY TẮC GÁN TAG:
- de_xuat: Novel đang có dữ liệu/setup sẵn để phát triển hướng này (ưu tiên chọn)
- co_le: Phù hợp nhưng cần cân nhắc, không có setup sẵn rõ ràng
- on: Không xuất sắc nhưng không có hại, có thể làm nếu cần chương
- kho: Khó triển khai vì thiếu dữ liệu nền, cần invent nhiều
- khong_kha_thi: Không khả thi vì mâu thuẫn với lore hiện tại
- mauthuan: Mâu thuẫn trực tiếp với dữ kiện có sẵn

Hãy phân tích JSON hợp lệ, đừng thêm markdown."""

CHAT_SYSTEM_PROMPT = """Bạn là trợ lý phân tích truyện.
User hỏi về một hướng mở rộng đề xuất cho tiểu thuyết.
Hãy giải thích dựa trên NovelProfile (thế giới, nhân vật, cốt truyện).
Trả lời ngắn gọn, có dẫn chứng cụ thể từ dữ liệu."""


class SmartDirector:
    """Phân tích NovelProfile → gợi ý hướng mở rộng có tag + chat"""

    def __init__(self, api_endpoint: str, auth_key: str):
        base_url = api_endpoint.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        self.client = genai.Client(
            api_key=auth_key or "sk-no-key-required",
            http_options={"base_url": base_url}
        )

    async def analyze(self, profile: Optional[NovelProfile],
                      recent_chapters_summary: str = "") -> List[Dict]:
        profile_text = profile.get_prompt_section() if profile else ""
        user_content = f"""NOVEL PROFILE:
{profile_text}

{"TÓM TẮT CHƯƠNG GẦN ĐÂY:" + recent_chapters_summary if recent_chapters_summary else ""}

Hãy phân tích và trả về JSON array các hướng mở rộng (tối đa 5)."""
        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-flash-lite",
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=ANALYZE_SYSTEM_PROMPT,
                    temperature=0.3,
                    tools=[]
                )
            )
            raw = (response.text or "").strip()
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "suggestions" in data:
                return data["suggestions"]
            if isinstance(data, dict):
                return [data]
            return self._fallback()
        except Exception:
            return self._fallback()

    async def chat(self, suggestion: Dict,
                   profile: Optional[NovelProfile]) -> str:
        profile_text = profile.get_prompt_section() if profile else ""
        direction = suggestion.get("direction", "free")
        tag = suggestion.get("tag", "on")
        reason = suggestion.get("reason", "")
        detail = suggestion.get("detail", "")
        user_content = f"""NOVEL PROFILE:
{profile_text}

HƯỚNG ĐƯỢC ĐỀ XUẤT: {DIRECTION_LABELS.get(direction, direction)}
TAG: {TAG_LABELS.get(tag, tag)}
LÝ DO: {reason}
PHÂN TÍCH: {detail}

Câu hỏi của user: """
        try:
            response = await self.client.aio.models.generate_content(
                model="gemini-flash-lite",
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT,
                    temperature=0.2,
                    tools=[]
                )
            )
            return (response.text or "").strip()
        except Exception as e:
            return f"Lỗi: {e}"

    def _fallback(self) -> List[Dict]:
        return [
            {"direction": "world", "tag": "on", "reason": "Fallback: không phân tích được profile",
             "detail": "Không có dữ liệu, đề xuất mặc định."},
            {"direction": "free", "tag": "on", "reason": "Fallback mặc định",
             "detail": "Mở rộng tự do, không ràng buộc."},
        ]
