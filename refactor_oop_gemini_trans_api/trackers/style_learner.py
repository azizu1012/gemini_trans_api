"""
Style Learner - Hệ Thống Tự Học Phong Cách Dịch
================================================

Học từ ví dụ dịch của user để:
1. Tự động áp dụng cho các trường hợp tương tự
2. Dịch dễ hiểu thay vì dịch thô
3. Giữ nhất quán style xuyên suốt truyện

Ví dụ User dạy:
- "以太之力" (Aether chi lực) → "Sức mạnh Aether" 
- "神赐之力" (Thần ban chi lực) → "Thần lực"
- "神赐之晶" (Thần ban chi tinh) → "Tinh thể Thần lực"
- "噬神器" (Thí thần khí) → "Thần Khí" (vũ khí dùng thần lực)

System học pattern:
- "[X]之力" → "Sức mạnh [X]" hoặc "Năng lượng [X]"
- "[X]之晶" → "Tinh thể [X]"
- Các quy tắc tương tự...
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class PatternType(Enum):
    """Loại pattern dịch"""
    SUFFIX = "suffix"       # X之力 → Sức mạnh X
    PREFIX = "prefix"       # 神赐X → Thần ban X  
    COMPOUND = "compound"   # A + B → C
    DIRECT = "direct"       # Dịch 1-1
    CONTEXT = "context"     # Dịch khác nhau tùy context


@dataclass
class TranslationExample:
    """Một ví dụ dịch từ user"""
    id: str
    source_cn: str           # Nguồn tiếng Trung
    target_vn: str           # Kết quả tiếng Việt user muốn
    
    # Analysis
    pattern_type: PatternType = PatternType.DIRECT
    extracted_pattern: str = ""  # Pattern rút ra (nếu có)
    
    # Context
    category: str = ""       # power, weapon, creature, etc.
    explanation: str = ""    # Giải thích tại sao dịch như vậy
    
    # Tracking
    created_at: str = ""
    used_count: int = 0
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['pattern_type'] = self.pattern_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TranslationExample':
        data['pattern_type'] = PatternType(data.get('pattern_type', 'direct'))
        return cls(**data)


@dataclass
class LearnedPattern:
    """Pattern đã học được"""
    id: str
    pattern_cn: str          # Pattern tiếng Trung (regex hoặc template)
    pattern_vn: str          # Pattern tiếng Việt (template)
    
    pattern_type: PatternType = PatternType.SUFFIX
    
    # Examples that taught this pattern
    source_examples: List[str] = field(default_factory=list)  # Example IDs
    
    # Stats
    confidence: float = 0.0  # 0-1, tăng theo số examples
    applications: int = 0    # Số lần áp dụng thành công
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['pattern_type'] = self.pattern_type.value
        return data


@dataclass 
class StyleRule:
    """Quy tắc style tổng quát"""
    id: str
    name: str
    description: str
    
    # Rule content
    rule_type: str = "terminology"  # terminology, tone, structure
    examples: List[Tuple[str, str]] = field(default_factory=list)  # (wrong, correct)
    
    # Priority
    priority: int = 5  # 1-10, cao hơn = quan trọng hơn
    
    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# PRE-BUILT TRANSLATION PATTERNS - Học từ ví dụ của user
# =============================================================================

# Pattern "X之力" → "Sức mạnh X" hoặc "Năng lượng X"
POWER_PATTERNS: Dict[str, Tuple[str, str]] = {
    # Format: "Chinese" → ("Vietnamese", "Explanation")
    "以太之力": ("Sức mạnh Aether", "Aether = nguồn năng lượng vũ trụ"),
    "神赐之力": ("Thần lực", "Sức mạnh thần linh ban tặng"),
    "黑暗之力": ("Sức mạnh Bóng tối", "Năng lượng thuộc tính tối"),
    "生命之力": ("Sinh lực", "Năng lượng sự sống"),
    "死亡之力": ("Tử lực", "Năng lượng chết chóc"),
}

# Pattern "X之晶" → "Tinh thể X"
CRYSTAL_PATTERNS: Dict[str, Tuple[str, str]] = {
    "神赐之晶": ("Tinh thể Thần lực", "Tinh thể chứa thần lực cô đọng"),
    "以太之晶": ("Tinh thể Aether", "Tinh thể chứa năng lượng Aether"),
    "生命之晶": ("Tinh thể Sinh mệnh", "Tinh thể chứa sinh lực"),
}

# Special terms
SPECIAL_TERMS: Dict[str, Tuple[str, str]] = {
    "噬神器": ("Thần Khí", "Vũ khí sử dụng Thần lực (KHÔNG phải vũ khí diệt thần)"),
    "神泉者": ("Thần Tuyền Giả", "Người sở hữu Suối Thần"),
    "异类": ("Dị loại", "Quái vật/sinh vật đột biến trong Mạt thế"),
    "觉醒者": ("Giác Ngộ Giả", "Người thức tỉnh năng lực"),
    "进化者": ("Tiến Hóa Giả", "Người đã tiến hóa năng lực"),
}

# Common suffixes and their translations
SUFFIX_RULES: Dict[str, str] = {
    "之力": "Sức mạnh {}",    # X之力 → Sức mạnh X
    "之晶": "Tinh thể {}",    # X之晶 → Tinh thể X
    "之心": "Tâm {}",         # X之心 → Tâm X  
    "之眼": "Mắt {}",         # X之眼 → Mắt X
    "之剑": "Kiếm {}",        # X之剑 → Kiếm X
    "之盾": "Khiên {}",       # X之盾 → Khiên X
}

# Common prefixes
PREFIX_RULES: Dict[str, str] = {
    "神赐": "Thần ban",       # 神赐X → Thần ban X (hoặc đơn giản hơn)
    "黑暗": "Bóng tối",       # 黑暗X → Bóng tối X
    "光明": "Ánh sáng",       # 光明X → Ánh sáng X
    "死亡": "Tử",             # 死亡X → Tử X
    "生命": "Sinh",           # 生命X → Sinh X
}


class StyleLearner:
    """
    Học và áp dụng phong cách dịch từ user
    
    Features:
    1. Học từ ví dụ dịch của user
    2. Tự động rút ra patterns
    3. Áp dụng patterns cho text mới
    4. Suggest translations dựa trên đã học
    5. Export rules cho prompt
    """
    
    def __init__(self, save_dir: str = "style_data"):
        self.save_dir = save_dir
        self.save_dir = save_dir
        # os.makedirs(save_dir, exist_ok=True)  <-- REMOVED: Lazy creation
        
        # Databases
        self.examples: Dict[str, TranslationExample] = {}
        self.patterns: Dict[str, LearnedPattern] = {}
        self.style_rules: Dict[str, StyleRule] = {}
        
        # Quick lookup
        self.direct_translations: Dict[str, str] = {}  # cn → vn
        
        # Initialize with pre-built data
        self._init_default_patterns()
        
        # Load saved data
        self._load_from_files()

    def _ensure_save_dir(self):
        """Đảm bảo thư mục lưu trữ tồn tại"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)
    
    def _init_default_patterns(self):
        """Initialize với patterns mặc định"""
        # Add power patterns
        for cn, (vn, explanation) in POWER_PATTERNS.items():
            self.direct_translations[cn] = vn
            self._add_example_internal(cn, vn, "power", explanation)
        
        # Add crystal patterns
        for cn, (vn, explanation) in CRYSTAL_PATTERNS.items():
            self.direct_translations[cn] = vn
            self._add_example_internal(cn, vn, "item", explanation)
        
        # Add special terms
        for cn, (vn, explanation) in SPECIAL_TERMS.items():
            self.direct_translations[cn] = vn
            self._add_example_internal(cn, vn, "special", explanation)
    
    def _add_example_internal(
        self, 
        source_cn: str, 
        target_vn: str, 
        category: str,
        explanation: str = ""
    ):
        """Internal: thêm example không save"""
        example_id = f"ex_{len(self.examples):04d}"
        self.examples[example_id] = TranslationExample(
            id=example_id,
            source_cn=source_cn,
            target_vn=target_vn,
            category=category,
            explanation=explanation,
            created_at=datetime.now().isoformat()
        )
    
    def _load_from_files(self):
        """Load data từ files"""
        # Examples
        examples_file = os.path.join(self.save_dir, "examples.json")
        if os.path.exists(examples_file):
            try:
                with open(examples_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for ex_id, ex_data in data.items():
                    if ex_id not in self.examples:
                        self.examples[ex_id] = TranslationExample.from_dict(ex_data)
                        self.direct_translations[ex_data['source_cn']] = ex_data['target_vn']
            except Exception as e:
                print(f"⚠️ Failed to load examples: {e}")
        
        # Patterns
        patterns_file = os.path.join(self.save_dir, "patterns.json")
        if os.path.exists(patterns_file):
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for pat_id, pat_data in data.items():
                    self.patterns[pat_id] = LearnedPattern(
                        id=pat_id,
                        pattern_cn=pat_data['pattern_cn'],
                        pattern_vn=pat_data['pattern_vn'],
                        pattern_type=PatternType(pat_data.get('pattern_type', 'suffix')),
                        source_examples=pat_data.get('source_examples', []),
                        confidence=pat_data.get('confidence', 0.5),
                        applications=pat_data.get('applications', 0)
                    )
            except Exception as e:
                print(f"⚠️ Failed to load patterns: {e}")
    
    def save_all(self):
        """Lưu tất cả data"""
        self._ensure_save_dir()
        # Examples
        examples_file = os.path.join(self.save_dir, "examples.json")
        with open(examples_file, 'w', encoding='utf-8') as f:
            json.dump(
                {k: v.to_dict() for k, v in self.examples.items()},
                f, ensure_ascii=False, indent=2
            )
        
        # Patterns
        patterns_file = os.path.join(self.save_dir, "patterns.json")
        with open(patterns_file, 'w', encoding='utf-8') as f:
            json.dump(
                {k: v.to_dict() for k, v in self.patterns.items()},
                f, ensure_ascii=False, indent=2
            )
    
    def teach(
        self, 
        source_cn: str, 
        target_vn: str, 
        category: str = "",
        explanation: str = ""
    ) -> TranslationExample:
        """
        Dạy một cách dịch mới
        
        Args:
            source_cn: Text gốc tiếng Trung
            target_vn: Cách dịch mong muốn
            category: Loại (power, weapon, creature, etc.)
            explanation: Giải thích tại sao dịch như vậy
        """
        # Check if already exists
        for ex in self.examples.values():
            if ex.source_cn == source_cn:
                # Update existing
                ex.target_vn = target_vn
                ex.explanation = explanation or ex.explanation
                self.direct_translations[source_cn] = target_vn
                self.save_all()
                return ex
        
        # Create new example
        example_id = f"ex_{len(self.examples):04d}"
        example = TranslationExample(
            id=example_id,
            source_cn=source_cn,
            target_vn=target_vn,
            category=category,
            explanation=explanation,
            created_at=datetime.now().isoformat()
        )
        
        # Analyze pattern
        pattern_type, extracted = self._analyze_pattern(source_cn, target_vn)
        example.pattern_type = pattern_type
        example.extracted_pattern = extracted
        
        # Add to databases
        self.examples[example_id] = example
        self.direct_translations[source_cn] = target_vn
        
        # Try to learn pattern
        self._learn_pattern_from_example(example)
        
        self.save_all()
        return example
    
    def _analyze_pattern(self, source_cn: str, target_vn: str) -> Tuple[PatternType, str]:
        """Phân tích pattern từ ví dụ"""
        # Check suffix patterns
        for suffix, template in SUFFIX_RULES.items():
            if source_cn.endswith(suffix):
                return PatternType.SUFFIX, f"*{suffix} → {template}"
        
        # Check prefix patterns
        for prefix, trans in PREFIX_RULES.items():
            if source_cn.startswith(prefix):
                return PatternType.PREFIX, f"{prefix}* → {trans}*"
        
        return PatternType.DIRECT, ""
    
    def _learn_pattern_from_example(self, example: TranslationExample):
        """Học pattern từ example"""
        if example.pattern_type == PatternType.DIRECT:
            return  # Không có pattern để học
        
        # Tìm các examples tương tự để confirm pattern
        similar = []
        for ex in self.examples.values():
            if (ex.id != example.id and 
                ex.pattern_type == example.pattern_type and
                ex.extracted_pattern == example.extracted_pattern):
                similar.append(ex)
        
        # Nếu có >= 2 examples tương tự, tạo/update pattern
        if len(similar) >= 1:  # 1 + current = 2
            pattern_id = f"pat_{example.extracted_pattern[:10]}"
            
            if pattern_id in self.patterns:
                # Update confidence
                self.patterns[pattern_id].confidence = min(1.0, 
                    self.patterns[pattern_id].confidence + 0.1)
                self.patterns[pattern_id].source_examples.append(example.id)
            else:
                # Create new pattern
                self.patterns[pattern_id] = LearnedPattern(
                    id=pattern_id,
                    pattern_cn=example.extracted_pattern.split(" → ")[0],
                    pattern_vn=example.extracted_pattern.split(" → ")[1] if " → " in example.extracted_pattern else "",
                    pattern_type=example.pattern_type,
                    source_examples=[ex.id for ex in similar] + [example.id],
                    confidence=0.5 + 0.1 * len(similar)
                )
    
    def translate(self, text_cn: str) -> Optional[str]:
        """
        Dịch text dựa trên đã học
        
        Returns: Vietnamese translation hoặc None nếu không biết
        """
        # 1. Check direct translation
        if text_cn in self.direct_translations:
            return self.direct_translations[text_cn]
        
        # 2. Try suffix patterns
        for suffix, template in SUFFIX_RULES.items():
            if text_cn.endswith(suffix):
                prefix_cn = text_cn[:-len(suffix)]
                # Translate prefix if known
                if prefix_cn in self.direct_translations:
                    prefix_vn = self.direct_translations[prefix_cn]
                else:
                    prefix_vn = prefix_cn  # Keep as-is
                return template.format(prefix_vn)
        
        # 3. Try prefix patterns
        for prefix_cn, prefix_vn in PREFIX_RULES.items():
            if text_cn.startswith(prefix_cn):
                suffix_cn = text_cn[len(prefix_cn):]
                # Translate suffix if known
                if suffix_cn in self.direct_translations:
                    suffix_vn = self.direct_translations[suffix_cn]
                else:
                    suffix_vn = suffix_cn
                return f"{prefix_vn} {suffix_vn}"
        
        return None
    
    def suggest_translation(self, text_cn: str) -> List[Tuple[str, float]]:
        """
        Gợi ý các cách dịch có thể
        
        Returns: List[(suggested_translation, confidence)]
        """
        suggestions = []
        
        # Direct match
        if text_cn in self.direct_translations:
            suggestions.append((self.direct_translations[text_cn], 1.0))
        
        # Pattern matches
        for pattern in self.patterns.values():
            if pattern.pattern_type == PatternType.SUFFIX:
                suffix = pattern.pattern_cn.replace("*", "")
                if text_cn.endswith(suffix):
                    prefix = text_cn[:-len(suffix)]
                    suggested = pattern.pattern_vn.replace("{}", prefix)
                    suggestions.append((suggested, pattern.confidence))
        
        # Similar examples
        for ex in self.examples.values():
            # Simple similarity check
            if len(set(text_cn) & set(ex.source_cn)) > len(text_cn) * 0.5:
                suggestions.append((f"(tương tự {ex.target_vn})", 0.3))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:5]
    
    def apply_to_text(self, text: str) -> str:
        """
        Áp dụng tất cả translations đã học vào một đoạn text
        
        Returns: Text với các thuật ngữ đã được dịch
        """
        result = text
        
        # Sort by length (longer first) để tránh partial matches
        sorted_terms = sorted(
            self.direct_translations.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )
        
        for cn, vn in sorted_terms:
            result = result.replace(cn, vn)
        
        return result
    
    def export_to_glossary(self) -> str:
        """Export thành glossary text cho prompt"""
        lines = [
            "[STYLE GUIDE - HỌC TỪ USER]",
            "Các cách dịch đã được xác nhận:",
            ""
        ]
        
        # Group by category
        categories: Dict[str, List[TranslationExample]] = {}
        for ex in self.examples.values():
            cat = ex.category or "other"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(ex)
        
        for cat, examples in categories.items():
            lines.append(f"📌 {cat.upper()}:")
            for ex in examples[:10]:  # Limit per category
                explanation = f" ({ex.explanation})" if ex.explanation else ""
                lines.append(f"  • {ex.source_cn} → {ex.target_vn}{explanation}")
            lines.append("")
        
        # Pattern rules
        lines.append("📐 PATTERNS ĐÃ HỌC:")
        for suffix, template in SUFFIX_RULES.items():
            lines.append(f"  • X{suffix} → {template.format('X')}")
        
        return "\n".join(lines)
    
    def get_prompt_instruction(self) -> str:
        """Tạo instruction cho AI prompt"""
        return f"""
[PHONG CÁCH DỊCH - TỰ ĐỘNG HỌC]

Các quy tắc dịch thuật ngữ đặc biệt:

1. NĂNG LỰC (之力 patterns):
   • 以太之力 → Sức mạnh Aether (KHÔNG dịch là "Aether chi lực")
   • 神赐之力 → Thần lực (KHÔNG dịch là "Thần ban chi lực")
   • [X]之力 → Sức mạnh [X] hoặc [X] lực

2. VẬT PHẨM (之晶 patterns):
   • 神赐之晶 → Tinh thể Thần lực (KHÔNG dịch là "Thần ban chi tinh")
   • [X]之晶 → Tinh thể [X]

3. VŨ KHÍ ĐẶC BIỆT:
   • 噬神器 → Thần Khí (vũ khí DÙNG thần lực, KHÔNG PHẢI vũ khí diệt thần)

4. NHÂN VẬT ĐẶC BIỆT:
   • 神泉者 → Thần Tuyền Giả (người sở hữu Suối Thần)
   • 觉醒者 → Giác Ngộ Giả
   • 进化者 → Tiến Hóa Giả

5. NGUYÊN TẮC CHUNG:
   • Dịch DỄ HIỂU, không dịch thô
   • Tránh cấu trúc "X chi Y" - dịch thành "Y của X" hoặc đơn giản hơn
   • Giữ tên riêng (Aether, etc.) không cần dịch
   • Nhất quán với các lần dịch trước

{self.export_to_glossary()}
"""
    
    def interactive_teach(self):
        """Mode tương tác để user dạy"""
        print("=" * 60)
        print("STYLE LEARNER - CHẾ ĐỘ HỌC")
        print("=" * 60)
        print("Nhập 'q' để thoát")
        print()
        
        while True:
            source = input("Nhập text Trung: ").strip()
            if source.lower() == 'q':
                break
            
            # Check existing
            if source in self.direct_translations:
                print(f"   Đã có: {source} → {self.direct_translations[source]}")
                update = input("   Cập nhật? (y/n): ").strip().lower()
                if update != 'y':
                    continue
            
            target = input("Nhập cách dịch Việt: ").strip()
            category = input("Category (power/weapon/creature/other): ").strip() or "other"
            explanation = input("Giải thích (optional): ").strip()
            
            example = self.teach(source, target, category, explanation)
            print(f"   ✅ Đã học: {example.source_cn} → {example.target_vn}")
            print()
        
        print(f"\nĐã học {len(self.examples)} examples, {len(self.patterns)} patterns")


# Global instance
_style_learner: Optional[StyleLearner] = None

def get_style_learner(save_dir: str = "style_data") -> StyleLearner:
    """Lấy global style learner"""
    global _style_learner
    if _style_learner is None:
        _style_learner = StyleLearner(save_dir)
    return _style_learner
