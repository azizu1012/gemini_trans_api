"""
Quality Assurance Module - THE CRITIC
=====================================
Biên tập viên AI - Kiểm duyệt chất lượng bản dịch/viết

Checklist kiểm duyệt:
1. Glossary Compliance - Tuân thủ từ điển
2. Pacing Check - Nhịp độ phù hợp
3. Consistency Check - Không mâu thuẫn với chương trước
4. Character Voice - Giọng văn nhân vật đúng
5. Plot Coherence - Logic cốt truyện

Nếu < 80 điểm -> Bắt viết lại (max 3 lần)
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


class QualityLevel(Enum):
    """Mức độ chất lượng"""
    EXCELLENT = "excellent"   # 90-100: Xuất sắc
    GOOD = "good"            # 80-89: Tốt - Pass
    ACCEPTABLE = "acceptable" # 70-79: Chấp nhận được - Cần xem xét
    POOR = "poor"            # 50-69: Kém - Cần viết lại
    FAIL = "fail"            # <50: Thất bại hoàn toàn


@dataclass
class QualityScore:
    """Điểm số chi tiết cho từng tiêu chí"""
    glossary_compliance: int = 0      # 0-20: Tuân thủ từ điển
    pacing_score: int = 0             # 0-20: Nhịp độ
    consistency_score: int = 0        # 0-20: Tính nhất quán
    character_voice: int = 0          # 0-20: Giọng văn nhân vật
    plot_coherence: int = 0           # 0-20: Logic cốt truyện

    # Mở rộng: forbidden characters + word count
    forbidden_char_penalty: int = 0   # 0 to -10: Phạt tạo nhân vật mới
    word_count_penalty: int = 0       # 0 to -10: Phạt chênh word count
    
    # Chi tiết lỗi
    glossary_errors: List[str] = field(default_factory=list)
    pacing_issues: List[str] = field(default_factory=list)
    consistency_issues: List[str] = field(default_factory=list)
    character_issues: List[str] = field(default_factory=list)
    plot_issues: List[str] = field(default_factory=list)
    extra_issues: List[str] = field(default_factory=list)
    
    @property
    def total_score(self) -> int:
        return (
            self.glossary_compliance + 
            self.pacing_score + 
            self.consistency_score + 
            self.character_voice + 
            self.plot_coherence +
            self.forbidden_char_penalty +
            self.word_count_penalty
        )
    
    @property
    def level(self) -> QualityLevel:
        score = self.total_score
        if score >= 90:
            return QualityLevel.EXCELLENT
        elif score >= 80:
            return QualityLevel.GOOD
        elif score >= 70:
            return QualityLevel.ACCEPTABLE
        elif score >= 50:
            return QualityLevel.POOR
        else:
            return QualityLevel.FAIL
    
    @property
    def passed(self) -> bool:
        """Pass nếu >= 80 điểm"""
        return self.total_score >= 80
    
    def get_feedback(self) -> str:
        """Tạo feedback chi tiết để yêu cầu viết lại"""
        feedback = []
        
        if self.glossary_errors:
            feedback.append("❌ LỖI TỪ ĐIỂN:")
            for err in self.glossary_errors[:5]:  # Max 5 lỗi
                feedback.append(f"   • {err}")
        
        if self.pacing_issues:
            feedback.append("⚠️ VẤN ĐỀ NHỊP ĐỘ:")
            for issue in self.pacing_issues[:3]:
                feedback.append(f"   • {issue}")
        
        if self.consistency_issues:
            feedback.append("🔄 MÂU THUẪN VỚI TRƯỚC:")
            for issue in self.consistency_issues[:3]:
                feedback.append(f"   • {issue}")
        
        if self.character_issues:
            feedback.append("👤 VẤN ĐỀ NHÂN VẬT:")
            for issue in self.character_issues[:3]:
                feedback.append(f"   • {issue}")
        
        if self.plot_issues:
            feedback.append("📖 VẤN ĐỀ CỐT TRUYỆN:")
            for issue in self.plot_issues[:3]:
                feedback.append(f"   • {issue}")

        if self.extra_issues:
            feedback.append("🔒 KIỂM SOÁT BỔ SUNG:")
            for issue in self.extra_issues[:3]:
                feedback.append(f"   • {issue}")
        
        return "\n".join(feedback)


@dataclass
class ReviewResult:
    """Kết quả review một chương"""
    chapter_num: int
    attempt: int
    score: QualityScore
    passed: bool
    feedback: str
    reviewed_at: str = ""
    
    def __post_init__(self):
        if not self.reviewed_at:
            self.reviewed_at = datetime.now().isoformat()


class QualityAssurance:
    """
    THE CRITIC - Biên tập viên AI
    
    Kiểm duyệt chất lượng bản dịch/viết và quyết định:
    - PASS: Cho phép lưu file
    - FAIL: Bắt viết lại với feedback cụ thể
    """
    
    PASS_THRESHOLD = 80  # Điểm tối thiểu để pass
    MAX_RETRIES = 3      # Số lần viết lại tối đa
    
    def __init__(
        self,
        glossary_terms: Optional[Dict[str, str]] = None,
        previous_chapters_summary: str = "",
        expected_pacing: str = "medium",
        character_states: Optional[Dict[str, Dict[str, Any]]] = None,
        *,
        character_allowed_list: Optional[List[str]] = None,
        known_characters: Optional[List[str]] = None,
        forbidden_new_chars: bool = False,
        avg_word_count_target: int = 0,
    ):
        self.glossary = glossary_terms or {}
        self.previous_summary = previous_chapters_summary
        self.expected_pacing = expected_pacing
        self.character_states = character_states or {}
        self.system_instruction: str = ""  # Set dynamically per review
        self.character_allowed_list: List[str] = character_allowed_list or []
        self.known_characters: List[str] = known_characters or []
        self.forbidden_new_chars: bool = forbidden_new_chars
        self.avg_word_count_target: int = avg_word_count_target

        # History
        self.review_history: List[ReviewResult] = []
    
    def update_context(
        self,
        glossary: Optional[Dict[str, str]] = None,
        previous_summary: Optional[str] = None,
        pacing: Optional[str] = None,
        character_states: Optional[Dict[str, Dict[str, Any]]] = None,
        *,
        character_allowed_list: Optional[List[str]] = None,
        known_characters: Optional[List[str]] = None,
        forbidden_new_chars: Optional[bool] = None,
        avg_word_count_target: Optional[int] = None,
    ):
        """Cập nhật context trước khi review"""
        if glossary:
            self.glossary = glossary
        if previous_summary:
            self.previous_summary = previous_summary
        if pacing:
            self.expected_pacing = pacing
        if character_states:
            self.character_states = character_states
        if character_allowed_list is not None:
            self.character_allowed_list = character_allowed_list
        if known_characters is not None:
            self.known_characters = known_characters
        if forbidden_new_chars is not None:
            self.forbidden_new_chars = forbidden_new_chars
        if avg_word_count_target is not None:
            self.avg_word_count_target = avg_word_count_target
    
    def check_glossary_compliance(self, content: str) -> Tuple[int, List[str]]:
        """
        Kiểm tra tuân thủ từ điển
        Returns: (score 0-20, list of errors)
        """
        errors = []
        
        # Kiểm tra các từ trong glossary có được dùng đúng không
        # Và kiểm tra có còn chữ Hán không
        
        # 1. Kiểm tra chữ Hán còn sót
        han_pattern = re.compile(r'[\u4e00-\u9fff]+')
        han_matches = han_pattern.findall(content)
        if han_matches:
            for han in han_matches[:5]:  # Max 5
                errors.append(f"Còn chữ Hán: '{han}'")
        
        # 2. Kiểm tra xưng hô sai
        if re.search(r'\bTôi\b', content):
            # Kiểm tra context - nếu không phải đang diễn kịch
            toi_count = len(re.findall(r'\bTôi\b', content))
            if toi_count > 3:  # Cho phép 1-2 lần trong context đặc biệt
                errors.append(f"Dùng 'Tôi' quá nhiều ({toi_count} lần) - Phải dùng 'Ta/Tao'")
        
        # 3. Kiểm tra các tên trong glossary
        for cn_term, vn_term in self.glossary.items():
            # Nếu có từ Trung mà không có từ Việt tương ứng
            if cn_term in content and vn_term not in content:
                errors.append(f"'{cn_term}' chưa được dịch thành '{vn_term}'")
        
        # Tính điểm
        if not errors:
            score = 20
        elif len(errors) <= 2:
            score = 15
        elif len(errors) <= 5:
            score = 10
        else:
            score = 5
        
        return score, errors
    
    def check_pacing(self, content: str) -> Tuple[int, List[str]]:
        """
        Kiểm tra nhịp độ
        Returns: (score 0-20, list of issues)
        """
        issues = []
        
        # Phân tích content
        paragraphs = content.split('\n\n')
        dialogue_count = len(re.findall(r'[""「」『』]', content))
        action_words = len(re.findall(r'đánh|chém|đâm|bắn|chạy|nhảy|lao|xông', content, re.IGNORECASE))
        description_ratio = len(re.findall(r'[,.;:]', content)) / max(1, len(content)) * 100
        
        # Kiểm tra theo expected pacing
        if self.expected_pacing == "slow":
            # Slow: Nhiều miêu tả, ít action
            if action_words > 10:
                issues.append("Quá nhiều action cho chương cần nhịp chậm")
            if len(paragraphs) < 5:
                issues.append("Chương slow cần nhiều đoạn văn miêu tả hơn")
        
        elif self.expected_pacing == "climax":
            # Climax: Phải có action, ít miêu tả lan man
            if action_words < 5:
                issues.append("Chương cao trào cần nhiều action hơn")
            if dialogue_count < 10:
                issues.append("Chương cao trào cần nhiều đối thoại căng thẳng")
        
        elif self.expected_pacing == "fast":
            # Fast: Câu ngắn, nhiều dialogue
            avg_paragraph_len = sum(len(p) for p in paragraphs) / max(1, len(paragraphs))
            if avg_paragraph_len > 500:
                issues.append("Đoạn văn quá dài cho nhịp nhanh")
        
        # Kiểm tra độ dài chương
        content_len = len(content)
        is_truncated = False
        if content_len < 3000:
            issues.append(f"Chương quá ngắn ({content_len} chars)")
            is_truncated = True
        elif content_len > 15000:
            issues.append(f"Chương quá dài ({content_len} chars)")
        
        # Kiểm tra câu bị cắt cụt ở cuối chương (truncation check)
        clean_end = content.strip()
        if clean_end and not clean_end[-1] in {'.', '"', '!', '?', '”', '…', '`', '*', ']', '}', '>', '’', ')'}:
            issues.append("Bản dịch bị cắt cụt ở cuối câu/chương")
            is_truncated = True
        
        # Tính điểm
        if is_truncated:
            # Phạt cực nặng nếu bị cắt cụt hoặc quá ngắn để đảm bảo không qua được QA
            score = -35
        elif not issues:
            score = 20
        elif len(issues) == 1:
            score = 15
        elif len(issues) == 2:
            score = 10
        else:
            score = 5
        
        return score, issues
    
    def check_consistency(self, content: str) -> Tuple[int, List[str]]:
        """
        Kiểm tra tính nhất quán với chương trước
        Returns: (score 0-20, list of issues)
        """
        issues = []
        
        if not self.previous_summary:
            # Không có context trước -> Skip check, cho điểm trung bình
            return 15, []
        
        # TODO: Đây là phần cần gọi API để check sâu hơn
        # Tạm thời check cơ bản bằng regex
        
        # Check location consistency
        locations_in_prev = re.findall(r'(?:tại|ở|đến|rời)\s+([A-ZĐ][a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]+(?:\s+[A-ZĐ][a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]+)*)', self.previous_summary)
        
        return 15, issues  # Default OK
    
    def check_character_voice(self, content: str) -> Tuple[int, List[str]]:
        """
        Kiểm tra giọng văn nhân vật
        Returns: (score 0-20, list of issues)
        """
        issues = []
        
        # Kiểm tra các nhân vật chính có nói đúng giọng không
        for char_name, state in self.character_states.items():
            # Tìm dialogue của nhân vật này
            char_dialogue_pattern = rf'{char_name}\s*(?:nói|đáp|hỏi|gầm|cười|thở dài)[^"「]*["「]([^"」]+)["」]'
            dialogues = re.findall(char_dialogue_pattern, content, re.IGNORECASE)
            
            if dialogues and 'personality' in state:
                # Check personality match
                personality = state.get('personality', '')
                if personality == 'cold' and any('haha' in d.lower() for d in dialogues):
                    issues.append(f"{char_name} là lạnh lùng nhưng đang cười nhiều")
        
        # Tính điểm
        if not issues:
            score = 18
        else:
            score = max(5, 18 - len(issues) * 4)
        
        return score, issues
    
    def check_plot_coherence(self, content: str) -> Tuple[int, List[str]]:
        """
        Kiểm tra logic cốt truyện
        Returns: (score 0-20, list of issues)
        """
        issues = []
        
        # Kiểm tra có title đúng format không
        if not re.search(r'###\s*Chương\s*\d+', content):
            issues.append("Thiếu tiêu đề chương đúng format")
        
        # Kiểm tra có ending (cliffhanger hoặc resolution) không
        last_paragraph = content.split('\n\n')[-1] if content else ""
        if len(last_paragraph) < 50:
            issues.append("Kết thúc chương quá đột ngột")
        
        # Tính điểm
        if not issues:
            score = 18
        else:
            score = max(5, 18 - len(issues) * 5)
        
        return score, issues
    
    def check_forbidden_characters(self, content: str) -> Tuple[int, List[str]]:
        """
        [KIỂM SOÁT NHÂN VẬT] Phát hiện nhân vật mới không được phép
        Returns: (penalty -10 to 0, list of issues)
        """
        issues = []
        if not self.forbidden_new_chars:
            return 0, []

        from ..plan.note_utils import check_forbidden_characters_in_text
        found = check_forbidden_characters_in_text(
            content,
            allowed_chars=self.character_allowed_list,
            known_chars=self.known_characters
        )
        if found:
            issues.append(f"Nhân vật mới không được phép: {', '.join(found[:3])}")
            penalty = min(-10, -2 * len(found))
            return penalty, issues

        return 0, issues

    def check_word_count_target(self, content: str) -> Tuple[int, List[str]]:
        """
        [KIỂM SOÁT ĐỘ DÀI] So sánh word count với target
        Returns: (penalty -10 to 0, list of issues)
        """
        issues = []
        if self.avg_word_count_target <= 0:
            return 0, []

        wc = len(content.split())
        ratio = wc / self.avg_word_count_target

        if ratio < 0.5:
            issues.append(f"Chapter quá ngắn ({wc} từ, target ~{self.avg_word_count_target})")
            return -8, issues
        elif ratio < 0.7:
            issues.append(f"Chapter hơi ngắn ({wc} từ, target ~{self.avg_word_count_target})")
            return -4, issues
        elif ratio > 2.0:
            issues.append(f"Chapter quá dài ({wc} từ, target ~{self.avg_word_count_target})")
            return -6, issues
        elif ratio > 1.5:
            issues.append(f"Chapter hơi dài ({wc} từ, target ~{self.avg_word_count_target})")
            return -3, issues

        return 0, issues

    def check_narrative_quality(self, content: str) -> Tuple[int, List[str]]:
        """
        [REMAKE ENGINE + AESTHETIC] Kiểm tra chất lượng biểu đạt văn học.
        Phát hiện câu kể phẳng, chuyển cảnh đột ngột, mật độ cảm giác,
        phân biệt giọng nhân vật, từ vựng cảm xúc.
        Returns: (bonus/penalty -15 to +15, list of issues)
        """
        issues = []

        # 1. Phát hiện "Tả phẳng" — câu kiểu "Hắn rất X"
        flat_patterns = [
            r'[Hh]ắn\s+(?:rất|vô cùng|cực kỳ|hết sức)\s+\w+',
            r'[Cc]ô\s+(?:rất|vô cùng|cực kỳ)\s+\w+',
            r'[Aa]nh\s+(?:rất|vô cùng|cực kỳ)\s+\w+',
            r'[Nn]àng\s+(?:rất|vô cùng|cực kỳ)\s+\w+',
        ]
        flat_count = sum(len(re.findall(p, content)) for p in flat_patterns)

        if flat_count > 8:
            issues.append(f"⚠️ Quá nhiều câu kể phẳng ({flat_count} lần) — cần Show Don't Tell")
            flat_penalty = 5
        elif flat_count > 4:
            issues.append(f"Có {flat_count} câu kể phẳng — nên chuyển sang Action Beats")
            flat_penalty = 3
        else:
            flat_penalty = 0

        # 2. Phát hiện chuyển cảnh đột ngột
        abrupt_transitions = len(re.findall(r'\n\n(?:Lúc này|Cùng lúc đó|Một lúc sau|Đến nơi)', content))
        if abrupt_transitions > 3:
            issues.append(f"Chuyển cảnh đột ngột {abrupt_transitions} lần — cần thêm mô tả di chuyển")
            trans_penalty = 3
        elif abrupt_transitions > 0:
            trans_penalty = min(2, abrupt_transitions)
        else:
            trans_penalty = 0

        # 3. Mật độ chi tiết cảm giác (sensory detail density)
        sensory_words = [
            'mùi', 'hương', 'thơm', 'tanh', 'khét',  # khứu giác
            'lạnh', 'nóng', 'ấm', 'buốt', 'đau', 'nhói', 'rát',  # xúc giác
            'tối', 'sáng', 'lờ mờ', 'chói', 'lấp lánh',  # thị giác
            'vọng', 'vang', 'rít', 'ầm ầm', 'ríu rít', 'thì thầm',  # thính giác
        ]
        sensory_count = sum(len(re.findall(w, content, re.IGNORECASE)) for w in sensory_words)
        content_len = len(content)
        sensory_ratio = sensory_count / max(1, content_len) * 1000  # per 1000 chars

        if sensory_ratio >= 8:
            sensory_bonus = 3  # giàu chi tiết cảm giác
        elif sensory_ratio >= 4:
            sensory_bonus = 1
        elif sensory_ratio < 1 and content_len > 2000:
            issues.append("Nghèo chi tiết cảm giác — cần thêm mô tả mùi, âm thanh, cảm giác")
            sensory_bonus = -2
        else:
            sensory_bonus = 0

        # 4. Phân biệt giọng nhân vật qua hội thoại
        dialogue_markers = re.findall(r'[""「」]([^"」]+)[""「」]', content)
        unique_speech = len(set(d.strip()[:10] for d in dialogue_markers if d.strip()))
        if len(dialogue_markers) >= 4 and unique_speech >= len(dialogue_markers) * 0.7:
            voice_bonus = 2  # giọng nhân vật đa dạng
        elif len(dialogue_markers) >= 4 and unique_speech < len(dialogue_markers) * 0.3:
            issues.append("Hội thoại các nhân vật quá giống nhau — cần phân biệt giọng nói")
            voice_bonus = -2
        else:
            voice_bonus = 0

        # 5. Từ vựng cảm xúc (emotional vocabulary richness)
        emotion_words = [
            'sợ', 'hãi', 'hoảng', 'loạn', 'kinh', 'hoàng',  # sợ hãi
            'giận', 'căm', 'hận', 'tức', 'điên',  # giận dữ
            'vui', 'mừng', 'hạnh phúc', 'phấn khích',  # vui
            'buồn', 'đau', 'khổ', 'thảm', 'bi thương',  # buồn
            'hy vọng', 'tuyệt vọng', 'chán',  # hy vọng/tuyệt vọng
        ]
        emotion_count = sum(len(re.findall(w, content, re.IGNORECASE)) for w in emotion_words)
        emotion_ratio = emotion_count / max(1, content_len) * 1000

        if emotion_ratio >= 6:
            emotion_bonus = 2  # giàu cảm xúc
        elif emotion_ratio < 1 and content_len > 2000:
            issues.append("Thiếu từ vựng cảm xúc — cần khai thác nội tâm nhân vật")
            emotion_bonus = -2
        else:
            emotion_bonus = 0

        # Tính tổng adjustment: -15 to +15
        total_penalty = flat_penalty + trans_penalty
        total_bonus = sensory_bonus + voice_bonus + emotion_bonus
        adjustment = max(-15, min(15, total_bonus - total_penalty))

        if adjustment > 0 and not issues:
            issues.append(f"Biểu đạt văn học tốt: giàu cảm giác, giọng đa dạng, cảm xúc sâu (+{adjustment})")

        return adjustment, issues
    
    def review(self, content: str, chapter_num: int, attempt: int = 1) -> ReviewResult:
        """
        Review một chương
        
        Args:
            content: Nội dung chương đã dịch/viết
            chapter_num: Số chương
            attempt: Lần thử thứ mấy
        
        Returns: ReviewResult với điểm và feedback
        """
        # Chạy tất cả checks
        glossary_score, glossary_errors = self.check_glossary_compliance(content)
        pacing_score, pacing_issues = self.check_pacing(content)
        consistency_score, consistency_issues = self.check_consistency(content)
        character_score, character_issues = self.check_character_voice(content)
        plot_score, plot_issues = self.check_plot_coherence(content)
        
        # [REMAKE ENGINE] Narrative quality check
        narrative_adj, narrative_issues = self.check_narrative_quality(content)
        
        # [KIỂM SOÁT BỔ SUNG] Forbidden characters + word count
        forbidden_penalty, forbidden_issues = self.check_forbidden_characters(content)
        wordcount_penalty, wordcount_issues = self.check_word_count_target(content)
        
        # Tạo QualityScore (cộng narrative adjustment vào plot_coherence)
        adjusted_plot = max(0, min(20, plot_score + narrative_adj))
        
        score = QualityScore(
            glossary_compliance=glossary_score,
            pacing_score=pacing_score,
            consistency_score=consistency_score,
            character_voice=character_score,
            plot_coherence=adjusted_plot,
            forbidden_char_penalty=forbidden_penalty,
            word_count_penalty=wordcount_penalty,
            glossary_errors=glossary_errors,
            pacing_issues=pacing_issues,
            consistency_issues=consistency_issues,
            character_issues=character_issues,
            plot_issues=plot_issues + narrative_issues,
            extra_issues=forbidden_issues + wordcount_issues,
        )
        
        # Tạo kết quả
        result = ReviewResult(
            chapter_num=chapter_num,
            attempt=attempt,
            score=score,
            passed=score.passed,
            feedback=score.get_feedback() if not score.passed else "✅ PASSED"
        )
        
        # Lưu history
        self.review_history.append(result)
        
        return result
    
    def build_revision_prompt(self, original_content: str, feedback: str, attempt: int) -> str:
        """
        Tạo prompt yêu cầu viết lại
        
        Args:
            original_content: Bản dịch/viết gốc
            feedback: Feedback từ review
            attempt: Lần viết lại thứ mấy
        
        Returns: Prompt cho AI viết lại
        """
        prompt = f"""
[⚠️ YÊU CẦU VIẾT LẠI - LẦN {attempt}/{self.MAX_RETRIES}]

Bản dịch trước KHÔNG ĐẠT CHẤT LƯỢNG. Phải viết lại!

📋 FEEDBACK TỪ BIÊN TẬP VIÊN:
{feedback}

📝 BẢN GỐC CẦN SỬA:
{original_content[:2000]}...

🎯 YÊU CẦU:
1. SỬA TẤT CẢ các lỗi được nêu ở trên
2. GIỮ NGUYÊN nội dung cốt truyện
3. CẢI THIỆN chất lượng văn phong
4. TUÂN THỦ 100% từ điển (Glossary)

⚡ LƯU Ý: Đây là lần viết lại cuối cùng, hãy làm thật tốt!
"""
        return prompt
    
    def get_review_summary(self) -> Dict:
        """Lấy tổng kết review"""
        if not self.review_history:
            return {"total_reviews": 0}
        
        total = len(self.review_history)
        passed = sum(1 for r in self.review_history if r.passed)
        avg_score = sum(r.score.total_score for r in self.review_history) / total
        
        return {
            "total_reviews": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed/total*100:.1f}%",
            "average_score": f"{avg_score:.1f}",
        }
