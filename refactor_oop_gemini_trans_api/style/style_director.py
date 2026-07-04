STYLE_PROMPTS = {
    "action": """VĂN PHONG HÀNH ĐỘNG:
- Câu văn ngắn, dồn dập, nhịp nhanh
- Ưu tiên mô tả hành động và phản xạ hơn nội tâm
- Âm thanh, ánh sáng, chuyển động liên tục
- Cảm giác căng thẳng, khẩn trương xuyên suốt""",

    "psychological": """VĂN PHONG TÂM LÝ:
- Đi sâu nội tâm nhân vật, cảm xúc, mâu thuẫn
- Hội thoại giàu ẩn ý, phản ứng tâm lý tinh tế
- Mô tả cảm xúc qua hành động nhỏ (action beats) và suy tư
- Nhịp chậm, cho phép đoạn độc thoại nội tâm""",

    "descriptive": """VĂN PHONG MIÊU TẢ:
- Mô tả chi tiết thế giới, môi trường, kiến trúc
- Giàu hình ảnh: màu sắc, ánh sáng, mùi vị, kết cấu
- Xây dựng không khí, bối cảnh, world-building có chiều sâu
- Cho phép đoạn tả cảnh dài nếu cần""",

    "literary": """VĂN PHONG VĂN HỌC:
- Câu văn trau chuốt, giàu hình ảnh và ẩn dụ
- Kết hợp độc thoại nội tâm với miêu tả tinh tế
- Sử dụng biện pháp tu từ: so sánh, nhân hóa, tương phản
- Nhịp uyển chuyển, có chỗ đặc tả, có chỗ lướt nhanh""",

    "balanced": """VĂN PHONG CÂN BẰNG:
- Kết hợp hành động, tâm lý và miêu tả hài hoà
- Nhịp độ biến hoá theo cao trào
- Không thiên vị bất kỳ yếu tố tố nào""",
}

DIRECTION_PROMPTS = {
    "world": """HƯỚNG MỞ RỘNG: THẾ GIỚI
- Ưu tiên phát triển địa danh, thế lực, quy tắc thế giới
- Có thể thêm địa điểm mới, tổ chức mới, bí ẩn mới
- Bối cảnh mạt thế: các vùng an toàn, vùng hoang dã, ổ dị loại
- Power system, tài nguyên, chính trị thế giới""",

    "character": """HƯỚNG MỞ RỘNG: NHÂN VẬT
- Ưu tiên phát triển nhân vật: quá khứ, động cơ, quan hệ
- Tương tác nhóm, xung đột cá nhân, phát triển tình cảm
- Hội thoại là công cụ chính để khắc hoạ nhân vật
- Có thể thêm nhân vật phụ mới nếu cần""",

    "challenge": """HƯỚNG MỞ RỘNG: THỬ THÁCH
- Ưu tiên sinh ra tình huống nguy hiểm, quái vật mới
- Combat, sinh tồn, giải đố, áp lực thời gian
- Thử thách đẩy nhân vật vào giới hạn, buộc phải trưởng thành
- Dị loại, bẫy, môi trường khắc nghiệt""",

    "free": "",
}

CREATIVITY_PROMPTS = {
    1: """MỨC SÁNG TẠO: THẤP (1/3)
- Bám sát outline, không thêm sự kiện phụ không cần thiết
- Giữ nguyên cấu trúc chương, không kéo dài quá mức""",

    2: """MỨC SÁNG TẠO: TRUNG BÌNH (2/3)
- Có thể thêm chi tiết phụ, mở rộng tình huống
- Phát triển thêm dialogue, action beats, mô tả
- Vẫn bám outline chính, cho phép sáng tạo trong khuôn khổ""",

    3: """MỨC SÁNG TẠO: CAO (3/3)
- Thoải mái phát triển tình huống mới, plot twist nhỏ
- Có thể thêm tuyến phụ, lore bổ sung
- Mở rộng chapter vượt outline nếu hấp dẫn""",
}

STYLE_LABELS = {
    "balanced": "Cân bằng",
    "action": "Hành động",
    "psychological": "Tâm lý",
    "descriptive": "Miêu tả",
    "literary": "Văn học",
    "giu_nguyen": "Giữ nguyên",
}

DIRECTION_LABELS = {
    "free": "Tự do",
    "world": "Mở rộng thế giới",
    "character": "Phát triển nhân vật",
    "challenge": "Thử thách mới",
}

CREATIVITY_LABELS = {
    1: "1 - Thấp (bám sát)",
    2: "2 - Trung bình",
    3: "3 - Cao (bay bổng)",
}

TAG_LABELS = {
    "de_xuat": "Đề xuất",
    "co_le": "Có lẽ",
    "on": "Ổn",
    "kho": "Khó",
    "khong_kha_thi": "Không khả thi",
    "mauthuan": "Mâu thuẫn",
}


def build_style_section(style: str, direction: str, creativity: int) -> str:
    parts = []
    if style != "giu_nguyen":
        sp = STYLE_PROMPTS.get(style)
        if sp:
            parts.append(sp)
    dp = DIRECTION_PROMPTS.get(direction)
    if dp:
        parts.append(dp)
    if creativity in CREATIVITY_PROMPTS:
        parts.append(CREATIVITY_PROMPTS[creativity])
    return "\n\n".join(parts)
