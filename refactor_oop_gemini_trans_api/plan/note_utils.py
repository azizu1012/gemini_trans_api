"""
Note Utils — persist chapter plan constraints to JSON + inject into prompt
"""

import os, json
from typing import Dict, List, Optional


def _notes_dir(temp_folder: str) -> str:
    path = os.path.join(temp_folder, "chapter_notes")
    os.makedirs(path, exist_ok=True)
    return path


def save_chapter_note(temp_folder: str, chapter_plan: Dict):
    """Lưu chapter plan (constraints) vào JSON để Writer + Critic dùng"""
    ch_num = chapter_plan.get("num", 0)
    path = os.path.join(_notes_dir(temp_folder), f"note_{ch_num:04d}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chapter_plan, f, ensure_ascii=False, indent=2)


def load_chapter_note(temp_folder: str, ch_num: int) -> Optional[Dict]:
    """Load chapter note từ JSON"""
    path = os.path.join(_notes_dir(temp_folder), f"note_{ch_num:04d}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_constraint_section(note: Optional[Dict],
                              forbidden_new_chars: bool = False,
                              known_characters: Optional[List[str]] = None,
                              avg_words: int = 0) -> str:
    """Build prompt section từ chapter note → inject vào Writer prompt"""
    if not note:
        return ""

    lines = []
    chars = note.get("characters", [])
    events = note.get("events", [])
    outline = note.get("outline", "")

    if outline:
        lines.append(f"OUTLINE: {outline}")

    if events:
        lines.append("SỰ KIỆN BẮT BUỘC:")
        for e in events:
            lines.append(f"  - {e}")

    if chars:
        lines.append("NHÂN VẬT ĐƯỢC PHÉP:")
        lines.append(f"  {', '.join(chars)}")

    if forbidden_new_chars and known_characters:
        lines.append("⚠️ KHÔNG tạo nhân vật mới — chỉ dùng các nhân vật đã biết.")

    if avg_words > 0:
        lower = int(avg_words * 0.8)
        upper = int(avg_words * 1.5)
        lines.append(f"ĐỘ DÀI MỤC TIÊU: ~{avg_words} từ (khoảng {lower}-{upper})")

    return "\n".join(lines)


def check_forbidden_characters_in_text(text: str,
                                        allowed_chars: List[str],
                                        known_chars: List[str]) -> List[str]:
    """
    Quét text tìm tên nhân vật không nằm trong danh sách cho phép.
    Heuristic: tìm các cụm 2-3 từ viết hoa (kiểu tên người Việt/Hoa).
    Returns: list of suspected new character names.
    """
    if not allowed_chars and not known_chars:
        return []

    import re
    known_set = set(c.lower() for c in (allowed_chars + known_chars) if c)

    found = []
    for match in re.finditer(r'\b([A-ZĐ][a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]+(?:\s+[A-ZĐ][a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]+)*)', text):
        name = match.group(0).strip()
        if len(name) > 1 and name.lower() not in known_set:
            found.append(name)

    # Lọc bỏ các từ viết hoa đầu câu (false positive)
    filtered = []
    for name in found:
        if name.lower() in {"sau", "khi", "và", "nhưng", "hoặc", "nếu", "vì", "nên"}:
            continue
        if name in {"Đây", "Đó", "Ở", "Từ", "Với", "Bằng", "Của"}:
            continue
        if len(name) <= 3:
            continue
        filtered.append(name)

    return filtered[:5]  # Max 5 cảnh báo
