"""
s4_director.py - Director cho S4: Lập khung truyện, kiểm soát continuity, chỉ đạo writer
"""
from typing import List

class S4Director:
    def __init__(self, context: str, main_characters: List[str], locations: List[str]):
        self.context = context
        self.main_characters = main_characters
        self.locations = locations

    def build_outline(self):
        """
        Sinh outline S4: các arc, sự kiện chính, wrap-up cho từng nhân vật
        """
        # Gợi ý: Có thể dùng AI hoặc template để sinh outline dựa trên context, nhân vật, địa điểm
        outline = f"""
# OUTLINE S4 - HẬU TRUYỆN
- Tiếp nối kết mở ở chương cuối, tập trung vào Lâm Nhất và Anna.
- Phát triển mối quan hệ, dẫn đến happy ending.
- Lồng ghép wrap-up cho các nhân vật: {', '.join(self.main_characters)}.
- Khai thác các địa điểm: {', '.join(self.locations)}.
- Đảm bảo continuity, không để writer tự ý phá vỡ logic truyện.
- Kết thúc mở nhưng tích cực, hướng về tương lai.
"""
        return outline

    def get_writer_prompt(self, outline: str):
        """
        Sinh prompt cho writer dựa trên outline đã kiểm duyệt
        """
        prompt = f"""
Bạn là writer, hãy viết ngoại truyện S4 dựa trên outline sau (do Director kiểm duyệt):
{outline}

Lưu ý:
- Giữ continuity, không phá vỡ logic truyện.
- Ưu tiên happy ending cho Lâm Nhất, Anna và wrap-up cho các nhân vật khác.
- Khai thác các địa điểm đã có.
- Văn phong đồng nhất với truyện gốc.
"""
        return prompt
