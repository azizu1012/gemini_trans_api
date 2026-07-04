"""
Chapter Director - Hệ thống "Khung Truyện" cho Expansion

Concept:
- Trước khi dịch/rewrite 10 chương, API Summary đọc trước
- Output: "Direction Notes" cho từng chương
- Giống tác giả viết outline trước → viết chi tiết sau

Flow:
1. Feed 10 chương gốc (chưa dịch) + glossary + memory
2. AI tạo "Chapter Framework" với:
   - Events bắt buộc (để liên kết)
   - Foreshadowing hints
   - Easter eggs
   - Character arcs
   - Connections (trước/sau)
3. Khi dịch từng chương, feed framework này vào prompt
4. Sau khi dịch xong 10 chương, update framework cho batch tiếp
"""
import os
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ChapterNote:
    """Ghi chú định hướng cho 1 chương"""
    chapter_num: int
    
    # Events bắt buộc (để chương sau không đá chương trước)
    required_events: List[str] = field(default_factory=list)
    
    # Foreshadowing - hints cần giấu cho tương lai
    foreshadowing: List[Dict[str, str]] = field(default_factory=list)
    # Format: {"hint": "...", "payoff_chapter": 150, "importance": "high"}
    
    # Easter eggs - references nhỏ
    easter_eggs: List[str] = field(default_factory=list)
    
    # Character moments - nhân vật cần có development gì
    character_moments: Dict[str, str] = field(default_factory=dict)
    # Format: {"Trương Thành": "Nhắc đến quá khứ bệnh viện"}
    
    # Connections
    connects_to_previous: List[int] = field(default_factory=list)
    connects_to_future: List[int] = field(default_factory=list)
    
    # Tone/Style
    tone: str = "dark"  # dark, hopeful, tense, comedic
    pacing: str = "medium"  # slow, medium, fast, climax
    
    # === MỚI: Extra Integration (được plan trong batch) ===
    extra_to_integrate: Optional[Dict] = None
    # Format: {"extra_idx": 4, "strategy": "flashback", "reason": "..."}


@dataclass
class ExtraCandidate:
    """Thông tin extra có thể hook vào batch này"""
    extra_idx: int
    title: str
    characters: List[str]
    location: str  # Map/địa điểm của extra
    timeline: str  # "past", "present", "future", "parallel"
    themes: List[str]
    content_summary: str
    
    # Relevance scores (0-10)
    location_match: int = 0
    character_match: int = 0  
    timeline_match: int = 0
    theme_match: int = 0
    
    @property
    def total_relevance(self) -> int:
        return self.location_match + self.character_match + self.timeline_match + self.theme_match
    
    @property
    def is_hookable(self) -> bool:
        """Có thể hook không? (ít nhất 2 tiêu chí match)"""
        matches = sum([
            self.location_match >= 5,
            self.character_match >= 5,
            self.timeline_match >= 5,
            self.theme_match >= 5
        ])
        return matches >= 2


@dataclass
class BatchFramework:
    """Framework cho 1 batch (10 chương)"""
    batch_id: int
    start_chapter: int
    end_chapter: int
    
    # Notes cho từng chương
    chapter_notes: Dict[int, ChapterNote] = field(default_factory=dict)
    
    # Arc-level info
    arc_name: str = ""
    arc_theme: str = ""
    arc_climax_chapter: int = 0
    current_location: str = ""  # Map hiện tại của batch này
    
    # Cross-batch connections
    unresolved_from_previous: List[str] = field(default_factory=list)
    setup_for_next_batch: List[str] = field(default_factory=list)
    
    # === MỚI: Extra planning cho batch này ===
    planned_extras: List[Dict] = field(default_factory=list)
    # Format: [{"extra_idx": 4, "insert_at_chapter": 52, "strategy": "flashback", "reason": "..."}]
    skipped_extras: List[Dict] = field(default_factory=list)
    # Format: [{"extra_idx": 20, "reason": "Location mismatch: Kuwait vs Bệnh Viện"}]
    
    # Metadata
    created_at: str = ""
    api_model_used: str = ""


class ChapterDirector:
    """
    Điều phối viên chương - tạo framework trước khi dịch
    
    Sử dụng API Summary pool để:
    1. Đọc 10 chương raw
    2. Tạo framework/outline
    3. Guide việc dịch từng chương
    4. Tích hợp Extra planning (qua ExtraRegistry)
    """
    
    def __init__(
        self, 
        framework_dir: str,
        batch_size: int = 10,
        extra_registry: Optional['ExtraRegistry'] = None  # Optional ExtraRegistry
    ):
        self.framework_dir = framework_dir
        self.batch_size = batch_size
        self.extra_registry = extra_registry  # Link to ExtraRegistry for smart planning
        os.makedirs(framework_dir, exist_ok=True)
        
        # Cache frameworks đã tạo
        self._frameworks: Dict[int, BatchFramework] = {}
        self._load_existing_frameworks()
    
    def set_extra_registry(self, registry: 'ExtraRegistry'):
        """Set hoặc update ExtraRegistry"""
        self.extra_registry = registry
    
    def _load_existing_frameworks(self):
        """Load các framework đã tạo từ trước"""
        for filename in os.listdir(self.framework_dir):
            if filename.startswith("framework_batch_") and filename.endswith(".json"):
                filepath = os.path.join(self.framework_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    batch_id = data.get('batch_id', 0)
                    self._frameworks[batch_id] = self._dict_to_framework(data)
                except Exception as e:
                    print(f"⚠️ Lỗi load framework {filename}: {e}")
    
    def _dict_to_framework(self, data: dict) -> BatchFramework:
        """Convert dict to BatchFramework"""
        framework = BatchFramework(
            batch_id=data.get('batch_id', 0),
            start_chapter=data.get('start_chapter', 0),
            end_chapter=data.get('end_chapter', 0),
            arc_name=data.get('arc_name', ''),
            arc_theme=data.get('arc_theme', ''),
            arc_climax_chapter=data.get('arc_climax_chapter', 0),
            unresolved_from_previous=data.get('unresolved_from_previous', []),
            setup_for_next_batch=data.get('setup_for_next_batch', []),
            created_at=data.get('created_at', ''),
            api_model_used=data.get('api_model_used', '')
        )
        
        # Convert chapter notes
        for chap_str, note_data in data.get('chapter_notes', {}).items():
            chap_num = int(chap_str)
            framework.chapter_notes[chap_num] = ChapterNote(
                chapter_num=chap_num,
                required_events=note_data.get('required_events', []),
                foreshadowing=note_data.get('foreshadowing', []),
                easter_eggs=note_data.get('easter_eggs', []),
                character_moments=note_data.get('character_moments', {}),
                connects_to_previous=note_data.get('connects_to_previous', []),
                connects_to_future=note_data.get('connects_to_future', []),
                tone=note_data.get('tone', 'dark'),
                pacing=note_data.get('pacing', 'medium')
            )
        
        return framework
    
    def _save_framework(self, framework: BatchFramework):
        """Lưu framework ra file"""
        filename = f"framework_batch_{framework.batch_id:03d}.json"
        filepath = os.path.join(self.framework_dir, filename)
        
        # Convert to dict
        data = {
            'batch_id': framework.batch_id,
            'start_chapter': framework.start_chapter,
            'end_chapter': framework.end_chapter,
            'arc_name': framework.arc_name,
            'arc_theme': framework.arc_theme,
            'arc_climax_chapter': framework.arc_climax_chapter,
            'unresolved_from_previous': framework.unresolved_from_previous,
            'setup_for_next_batch': framework.setup_for_next_batch,
            'created_at': framework.created_at,
            'api_model_used': framework.api_model_used,
            'chapter_notes': {}
        }
        
        for chap_num, note in framework.chapter_notes.items():
            data['chapter_notes'][str(chap_num)] = asdict(note)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"   💾 Saved framework: {filename}")
    
    def get_batch_id(self, chapter_num: int) -> int:
        """Tính batch ID từ số chương"""
        return (chapter_num - 1) // self.batch_size + 1
    
    def get_framework(self, chapter_num: int) -> Optional[BatchFramework]:
        """Lấy framework cho chương này"""
        batch_id = self.get_batch_id(chapter_num)
        return self._frameworks.get(batch_id)
    
    def get_chapter_note(self, chapter_num: int) -> Optional[ChapterNote]:
        """Lấy note cho 1 chương cụ thể"""
        framework = self.get_framework(chapter_num)
        if framework:
            return framework.chapter_notes.get(chapter_num)
        return None
    
    def _get_relevant_extras_for_batch(
        self,
        batch_location: str,
        batch_characters: List[str],
        batch_themes: List[str]
    ) -> List[Dict]:
        """
        Lấy extras phù hợp từ ExtraRegistry
        Được gọi tự động trong build_direction_prompt
        """
        if not self.extra_registry:
            return []
        
        return self.extra_registry.get_extras_for_batch(
            batch_location=batch_location,
            batch_characters=batch_characters,
            batch_themes=batch_themes
        )
    
    def _mark_extras_as_placed(self, framework: BatchFramework):
        """Đánh dấu planned extras trong registry sau khi parse framework"""
        if not self.extra_registry:
            return
        
        for planned in framework.planned_extras:
            extra_idx = planned.get('extra_idx')
            if extra_idx is None:
                continue
            chapter = planned.get('insert_at_chapter', 0)
            strategy = planned.get('strategy', 'unknown')
            
            self.extra_registry.mark_as_placed(
                extra_idx=extra_idx,
                chapter=chapter,
                strategy=strategy,
                batch_id=framework.batch_id
            )
            print(f"   ✅ Registry: Marked Extra #{extra_idx} as placed at Chap {chapter}")

    def build_direction_prompt(
        self,
        raw_chapters: List[Tuple[int, str]],  # [(chap_num, content), ...]
        glossary_text: str,
        memory_context: str,
        available_extras: Optional[List[Dict]] = None,  # Extras chưa được hook (hoặc tự lấy từ registry)
        previous_framework: Optional[BatchFramework] = None
    ) -> str:
        """
        Tạo prompt để AI tạo framework cho batch
        TÍCH HỢP: Extra planning - chỉ hook extra nếu LOGIC
        
        Args:
            raw_chapters: List (chap_num, raw_content) của 10 chương sắp dịch
            glossary_text: Từ điển
            memory_context: Summary các chương trước
            available_extras: Danh sách extra chưa được tích hợp
            previous_framework: Framework của batch trước (nếu có)
        """
        # Collect chapter summaries
        chapters_text = ""
        for chap_num, content in raw_chapters:
            # Truncate to ~500 chars per chapter for prompt efficiency
            truncated = content[:500] + "..." if len(content) > 500 else content
            chapters_text += f"\n### Chương {chap_num} ###\n{truncated}\n"
        
        # Previous batch info
        prev_info = ""
        if previous_framework:
            prev_info = f"""
[BATCH TRƯỚC - {previous_framework.arc_name}]
- Địa điểm: {previous_framework.current_location}
- Các tuyến chưa giải quyết: {', '.join(previous_framework.setup_for_next_batch)}
- Arc theme: {previous_framework.arc_theme}
"""
        
        # === MỚI: Extra candidates ===
        extras_text = ""
        if available_extras:
            extras_text = "\n[NGOẠI TRUYỆN CÓ THỂ TÍCH HỢP]\n"
            extras_text += "⚠️ CHỈ hook nếu có LOGIC (cùng map, cùng timeline, có character xuất hiện)\n\n"
            for extra in available_extras[:10]:  # Max 10 extras để không quá dài
                extras_text += f"""
Extra #{extra.get('index', '?')}: "{extra.get('title', '')}"
- Nhân vật: {', '.join(extra.get('characters', []))}
- Địa điểm: {extra.get('location', 'unknown')}
- Timeline: {extra.get('timeline', 'unknown')}
- Themes: {', '.join(extra.get('themes', []))}
- Tóm tắt: {extra.get('content_summary', '')[:200]}...
"""
        
        prompt = f"""
[VAI TRÒ]
Bạn là một biên tập viên truyện chuyên nghiệp. Nhiệm vụ: Tạo "Khung Truyện" (Story Framework) 
cho batch {self.batch_size} chương sắp được dịch/rewrite.

[TỪ ĐIỂN]
{glossary_text}

[BỐI CẢNH - TÓM TẮT TRƯỚC ĐÓ]
{memory_context}

{prev_info}

[CÁC CHƯƠNG CẦN PHÂN TÍCH]
{chapters_text}

{extras_text}

[YÊU CẦU OUTPUT]
Tạo JSON với cấu trúc sau:

```json
{{
  "arc_name": "Tên arc hiện tại",
  "arc_theme": "Theme chính của arc",
  "arc_climax_chapter": <số chương cao trào>,
  "current_location": "Địa điểm/Map chính của batch này",
  
  "chapter_notes": {{
    "<chapter_num>": {{
      "required_events": ["Event 1 BẮT BUỘC", "Event 2"],
      "foreshadowing": [{{"hint": "...", "payoff_chapter": <chap>, "importance": "high/medium/low"}}],
      "easter_eggs": ["Reference nhỏ"],
      "character_moments": {{"Tên nhân vật": "Development cần có"}},
      "connects_to_previous": [<số chương>],
      "connects_to_future": [<số chương>],
      "tone": "dark/hopeful/tense/comedic",
      "pacing": "slow/medium/fast/climax",
      "extra_to_integrate": null OR {{"extra_idx": <số>, "strategy": "flashback/mention/theme", "reason": "..."}}
    }}
  }},
  
  "planned_extras": [
    {{"extra_idx": <số>, "insert_at_chapter": <chương>, "strategy": "flashback", "reason": "Logic vì sao hook ở đây"}}
  ],
  "skipped_extras": [
    {{"extra_idx": <số>, "reason": "Không hook vì: location mismatch / timeline conflict / character không xuất hiện"}}
  ],
  
  "unresolved_from_previous": ["Tuyến A chưa giải quyết"],
  "setup_for_next_batch": ["Setup cho batch sau"]
}}
```

[LOGIC HOOK EXTRA - QUAN TRỌNG]
❌ KHÔNG hook nếu:
- Extra về Map A nhưng batch đang ở Map B
- Extra timeline quá khứ nhưng không có flashback trigger tự nhiên
- Extra character không xuất hiện/được nhắc trong batch
- Đang ở cao trào (pacing=climax) - không phá flow

✅ CHỈ hook nếu:
- Extra cùng location với batch (hoặc liên quan)
- Extra character xuất hiện trong batch + có emotional moment
- Theme của extra phù hợp với arc_theme
- Có transition tự nhiên (pacing=slow hoặc chương transition)

[OUTPUT]
Chỉ trả về JSON, không có text giải thích.
"""
        return prompt
    
    def parse_framework_response(
        self,
        response_text: str,
        batch_id: int,
        start_chapter: int,
        end_chapter: int,
        model_used: str
    ) -> Optional[BatchFramework]:
        """Parse response từ AI thành BatchFramework"""
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                print("❌ Không tìm thấy JSON trong response")
                return None
            
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            
            # Build framework
            framework = BatchFramework(
                batch_id=batch_id,
                start_chapter=start_chapter,
                end_chapter=end_chapter,
                arc_name=data.get('arc_name', f'Arc {batch_id}'),
                arc_theme=data.get('arc_theme', ''),
                arc_climax_chapter=data.get('arc_climax_chapter', 0),
                current_location=data.get('current_location', ''),
                unresolved_from_previous=data.get('unresolved_from_previous', []),
                setup_for_next_batch=data.get('setup_for_next_batch', []),
                planned_extras=data.get('planned_extras', []),
                skipped_extras=data.get('skipped_extras', []),
                created_at=datetime.now().isoformat(),
                api_model_used=model_used
            )
            
            # Parse chapter notes
            for chap_str, note_data in data.get('chapter_notes', {}).items():
                try:
                    chap_num = int(chap_str)
                    framework.chapter_notes[chap_num] = ChapterNote(
                        chapter_num=chap_num,
                        required_events=note_data.get('required_events', []),
                        foreshadowing=note_data.get('foreshadowing', []),
                        easter_eggs=note_data.get('easter_eggs', []),
                        character_moments=note_data.get('character_moments', {}),
                        connects_to_previous=note_data.get('connects_to_previous', []),
                        connects_to_future=note_data.get('connects_to_future', []),
                        tone=note_data.get('tone', 'dark'),
                        pacing=note_data.get('pacing', 'medium'),
                        extra_to_integrate=note_data.get('extra_to_integrate', None)
                    )
                except (ValueError, KeyError) as e:
                    print(f"⚠️ Lỗi parse chapter {chap_str}: {e}")
            
            # Log planned extras
            if framework.planned_extras:
                print(f"   📌 Planned {len(framework.planned_extras)} extras cho batch này:")
                for pe in framework.planned_extras:
                    print(f"      • Extra #{pe.get('extra_idx')} → Chap {pe.get('insert_at_chapter')} ({pe.get('strategy')})")
            
            if framework.skipped_extras:
                print(f"   ⏭️ Skipped {len(framework.skipped_extras)} extras (không phù hợp)")
            
            # === QUAN TRỌNG: Update ExtraRegistry với placement ===
            self._mark_extras_as_placed(framework)
            
            # Cache and save
            self._frameworks[batch_id] = framework
            self._save_framework(framework)
            
            return framework
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            return None
    
    def get_direction_for_translation(self, chapter_num: int) -> str:
        """
        Lấy direction text để inject vào prompt dịch
        Được gọi khi dịch từng chương
        """
        note = self.get_chapter_note(chapter_num)
        if not note:
            return ""
        
        lines = [
            "",
            "=" * 60,
            f"[CHAPTER DIRECTION - Chương {chapter_num}]",
            "=" * 60,
        ]
        
        if note.required_events:
            lines.append("\n📌 EVENTS BẮT BUỘC (không được bỏ qua):")
            for event in note.required_events:
                lines.append(f"  • {event}")
        
        if note.foreshadowing:
            lines.append("\n🔮 FORESHADOWING (hints cần giấu):")
            for hint in note.foreshadowing:
                importance = hint.get('importance', 'medium')
                emoji = "🔴" if importance == 'high' else "🟡" if importance == 'medium' else "🟢"
                lines.append(f"  {emoji} {hint.get('hint', '')} → Payoff chương {hint.get('payoff_chapter', '?')}")
        
        if note.easter_eggs:
            lines.append("\n🥚 EASTER EGGS (references nhỏ):")
            for egg in note.easter_eggs:
                lines.append(f"  • {egg}")
        
        if note.character_moments:
            lines.append("\n👤 CHARACTER MOMENTS:")
            for char, moment in note.character_moments.items():
                lines.append(f"  • {char}: {moment}")
        
        # === MỚI: Extra được plan cho chương này ===
        if note.extra_to_integrate:
            extra = note.extra_to_integrate
            lines.append("\n" + "🎬" * 20)
            lines.append("📚 NGOẠI TRUYỆN CẦN TÍCH HỢP (đã được plan bởi Director)")
            lines.append(f"  • Extra #{extra.get('extra_idx', '?')}")
            lines.append(f"  • Strategy: {extra.get('strategy', 'unknown')}")
            lines.append(f"  • Lý do hook: {extra.get('reason', 'N/A')}")
            lines.append("🎬" * 20)
        
        if note.connects_to_previous:
            lines.append(f"\n⬅️ Liên kết với chương: {note.connects_to_previous}")
        
        if note.connects_to_future:
            lines.append(f"\n➡️ Setup cho chương: {note.connects_to_future}")
        
        lines.append(f"\n🎭 Tone: {note.tone.upper()} | Pacing: {note.pacing.upper()}")
        lines.append("=" * 60)
        
        return "\n".join(lines)


# ============================================================================
# EXTRA CHAPTERS - GIẢI QUYẾT MỌI CASE (kể cả không có hook tự nhiên)
# ============================================================================

class ExtraPlacementStrategy:
    """Enum-like cho các strategy"""
    FLASHBACK = "flashback"           # Có hook tự nhiên → chèn flashback
    EPILOGUE = "epilogue"             # Sau kết thúc → after-story
    APPENDIX = "appendix"             # Gom vào phụ lục
    STANDALONE = "standalone"         # Bonus content riêng
    
    # === MỚI: Cho extra KHÔNG có hook tự nhiên ===
    SYNTHETIC_HOOK = "synthetic_hook"   # Tạo hook nhân tạo
    INTERLUDE = "interlude"             # Chương "Màn giữa" giữa arc
    THEMATIC_BRIDGE = "thematic_bridge" # Kết nối qua theme
    CHARACTER_MENTION = "char_mention"  # Mở rộng khi nhân vật xuất hiện
    PARALLEL_STORY = "parallel"         # Song song với story chính


class ExtraChapterHandler:
    """
    Xử lý ngoại truyện - KỂ CẢ KHÔNG CÓ HOOK TỰ NHIÊN
    
    NGUYÊN TẮC: KHÔNG LÃNG PHÍ EXTRA NÀO!
    
    Các strategy từ dễ → khó:
    1. FLASHBACK: Có hook tự nhiên (character + event match)
    2. CHARACTER_MENTION: Nhân vật xuất hiện → trigger extra
    3. THEMATIC_BRIDGE: Không có character nhưng có theme chung
    4. SYNTHETIC_HOOK: Tạo hook nhân tạo trong story
    5. INTERLUDE: Chèn như màn giữa giữa các arc
    6. PARALLEL_STORY: Chạy song song, đọc xen kẽ
    7. EPILOGUE: Sau kết thúc
    8. APPENDIX: Last resort - gom vào phụ lục
    """
    
    def __init__(self):
        # Cache để track extra đã placement
        self.placed_extras: Dict[int, str] = {}  # extra_idx -> strategy used
        self.failed_placements: List[int] = []   # extras chưa place được
    
    def find_best_strategy(
        self,
        extra: dict,  # {index, title, characters, themes, content_summary}
        story_chapters: List[dict],  # [{num, characters, themes, events}]
        total_main_chapters: int = 550
    ) -> Tuple[str, int, str]:
        """
        Tìm strategy tốt nhất cho extra
        
        Returns: (strategy, insertion_point, reason)
        """
        extra_chars = set(extra.get('characters', []))
        extra_themes = set(extra.get('themes', []))
        extra_idx = extra.get('index', 0)
        
        # === STRATEGY 1: FLASHBACK (có hook tự nhiên) ===
        # Tìm chương có cả character + emotional moment
        for chap in story_chapters:
            chap_chars = set(chap.get('characters', []))
            overlap = extra_chars & chap_chars
            
            if overlap and chap.get('has_emotional_moment', False):
                return (
                    ExtraPlacementStrategy.FLASHBACK,
                    chap['num'],
                    f"Character match: {overlap} + emotional moment"
                )
        
        # === STRATEGY 2: CHARACTER_MENTION (chỉ có character, không có emotion) ===
        for chap in story_chapters:
            chap_chars = set(chap.get('characters', []))
            overlap = extra_chars & chap_chars
            
            if overlap:
                return (
                    ExtraPlacementStrategy.CHARACTER_MENTION,
                    chap['num'],
                    f"Character xuất hiện: {overlap}"
                )
        
        # === STRATEGY 3: THEMATIC_BRIDGE (không có character, có theme) ===
        for chap in story_chapters:
            chap_themes = set(chap.get('themes', []))
            theme_overlap = extra_themes & chap_themes
            
            if theme_overlap:
                return (
                    ExtraPlacementStrategy.THEMATIC_BRIDGE,
                    chap['num'],
                    f"Theme match: {theme_overlap}"
                )
        
        # === STRATEGY 4: SYNTHETIC_HOOK (tạo hook nhân tạo) ===
        # Chọn chương có pacing slow hoặc transition
        for chap in story_chapters:
            if chap.get('pacing') in ['slow', 'transition']:
                return (
                    ExtraPlacementStrategy.SYNTHETIC_HOOK,
                    chap['num'],
                    "Synthetic hook vào chương transition"
                )
        
        # === STRATEGY 5: INTERLUDE (giữa các arc) ===
        arc_boundaries = self._find_arc_boundaries(story_chapters)
        if arc_boundaries:
            # Chọn arc boundary gần nhất với thời điểm extra diễn ra
            best_boundary = min(arc_boundaries, 
                               key=lambda x: abs(x - extra_idx))
            return (
                ExtraPlacementStrategy.INTERLUDE,
                best_boundary,
                f"Interlude giữa arc (sau chap {best_boundary})"
            )
        
        # === STRATEGY 6: PARALLEL_STORY ===
        # Nếu extra có timeline rõ ràng, chạy song song
        if extra.get('has_clear_timeline', False):
            parallel_point = self._find_parallel_point(extra, story_chapters)
            return (
                ExtraPlacementStrategy.PARALLEL_STORY,
                parallel_point,
                "Parallel story - đọc xen kẽ"
            )
        
        # === STRATEGY 7: EPILOGUE (sau kết thúc) ===
        if extra_idx >= total_main_chapters * 0.9:
            return (
                ExtraPlacementStrategy.EPILOGUE,
                total_main_chapters,
                "After-story"
            )
        
        # === STRATEGY 8: APPENDIX (last resort) ===
        return (
            ExtraPlacementStrategy.APPENDIX,
            -1,  # Không có insertion point
            "Không tìm được hook → Phụ lục"
        )
    
    def _find_arc_boundaries(self, chapters: List[dict]) -> List[int]:
        """Tìm các điểm chuyển arc"""
        boundaries = []
        for i, chap in enumerate(chapters[:-1]):
            next_chap = chapters[i + 1]
            # Arc change indicators
            if (chap.get('arc_name') != next_chap.get('arc_name') or
                chap.get('location') != next_chap.get('location')):
                boundaries.append(chap['num'])
        return boundaries
    
    def _find_parallel_point(self, extra: dict, chapters: List[dict]) -> int:
        """Tìm điểm bắt đầu parallel story"""
        # Dựa vào timeline của extra
        timeline_start = extra.get('timeline_start', 0)
        for chap in chapters:
            if chap.get('timeline', 0) >= timeline_start:
                return chap['num']
        return chapters[len(chapters) // 2]['num']  # Fallback: giữa truyện
    
    # ========================================================================
    # PROMPT BUILDERS CHO TỪNG STRATEGY
    # ========================================================================
    
    def get_integration_prompt(
        self,
        strategy: str,
        extra: dict,
        target_chapter: dict,
        context: str = ""
    ) -> str:
        """Tạo prompt phù hợp với strategy"""
        
        if strategy == ExtraPlacementStrategy.FLASHBACK:
            return self._prompt_flashback(extra, target_chapter, context)
        
        elif strategy == ExtraPlacementStrategy.CHARACTER_MENTION:
            return self._prompt_character_mention(extra, target_chapter)
        
        elif strategy == ExtraPlacementStrategy.THEMATIC_BRIDGE:
            return self._prompt_thematic_bridge(extra, target_chapter)
        
        elif strategy == ExtraPlacementStrategy.SYNTHETIC_HOOK:
            return self._prompt_synthetic_hook(extra, target_chapter)
        
        elif strategy == ExtraPlacementStrategy.INTERLUDE:
            return self._prompt_interlude(extra, target_chapter)
        
        elif strategy == ExtraPlacementStrategy.PARALLEL_STORY:
            return self._prompt_parallel(extra, target_chapter)
        
        elif strategy == ExtraPlacementStrategy.EPILOGUE:
            return self._prompt_epilogue(extra, context)
        
        else:  # APPENDIX or STANDALONE
            return self._prompt_standalone(extra)
    
    def _prompt_flashback(self, extra: dict, chapter: dict, context: str) -> str:
        return f"""
[TÍCH HỢP NGOẠI TRUYỆN - FLASHBACK]

Ngoại truyện: "{extra.get('title', '')}"
Nhân vật: {', '.join(extra.get('characters', []))}

[NGỮ CẢNH CHƯƠNG HIỆN TẠI]
{context}

[NỘI DUNG NGOẠI TRUYỆN CẦN TÍCH HỢP]
{extra.get('content_summary', '')}

[YÊU CẦU]
1. Viết một đoạn flashback TỰ NHIÊN
2. Trigger: Nhân vật nhìn thấy/nghe thấy gì đó gợi nhớ
3. Độ dài: 300-500 từ
4. Kết thúc flashback phải quay lại hiện tại mượt mà
"""
    
    def _prompt_character_mention(self, extra: dict, chapter: dict) -> str:
        chars = ', '.join(extra.get('characters', []))
        return f"""
[TÍCH HỢP NGOẠI TRUYỆN - CHARACTER EXPANSION]

Khi {chars} xuất hiện/được nhắc đến, thêm chi tiết từ ngoại truyện:

Ngoại truyện: "{extra.get('title', '')}"
Nội dung: {extra.get('content_summary', '')}

[YÊU CẦU]
1. KHÔNG viết flashback đầy đủ
2. Chỉ thêm 1-2 câu gợi ý về quá khứ/bí mật của nhân vật
3. Ví dụ: "Ánh mắt hắn thoáng tối lại, như thể nhớ về điều gì đó đau buồn..."
4. Người đọc tò mò → sẽ đọc ngoại truyện sau
"""
    
    def _prompt_thematic_bridge(self, extra: dict, chapter: dict) -> str:
        themes = ', '.join(extra.get('themes', []))
        return f"""
[TÍCH HỢP NGOẠI TRUYỆN - THEMATIC BRIDGE]

Chương hiện tại có theme: {themes}
Ngoại truyện có cùng theme này.

Ngoại truyện: "{extra.get('title', '')}"
Nội dung: {extra.get('content_summary', '')}

[YÊU CẦU]
1. Thêm một đoạn suy ngẫm/triết lý liên quan đến theme
2. Ví dụ: Nếu theme là "mất mát", thêm đoạn main suy nghĩ về mất mát
3. Kết nối gián tiếp với nội dung ngoại truyện
4. Không nhắc trực tiếp đến ngoại truyện
"""
    
    def _prompt_synthetic_hook(self, extra: dict, chapter: dict) -> str:
        return f"""
[TÍCH HỢP NGOẠI TRUYỆN - SYNTHETIC HOOK]

⚠️ EXTRA NÀY KHÔNG CÓ HOOK TỰ NHIÊN
→ Cần TẠO hook nhân tạo

Ngoại truyện: "{extra.get('title', '')}"
Nhân vật: {', '.join(extra.get('characters', []))}
Nội dung: {extra.get('content_summary', '')}

[YÊU CẦU - TẠO HOOK]
1. Thêm một chi tiết MỚI vào chương hiện tại:
   - Main tìm thấy vật phẩm bí ẩn liên quan đến extra
   - Nghe được tin đồn về sự kiện trong extra
   - Gặp NPC nhắc đến extra
   - Thấy vết tích của sự kiện trong extra

2. Chi tiết này phải:
   - Hợp logic với bối cảnh
   - Gợi tò mò
   - Có thể payoff sau

3. Ví dụ: "Lâm Nhất nhặt lên một mảnh giấy ố vàng. Trên đó ghi chằng chịt 
   những ghi chú y khoa... và một cái tên: Trương Thành."
"""
    
    def _prompt_interlude(self, extra: dict, chapter: dict) -> str:
        return f"""
[CHẾ ĐỘ: INTERLUDE - MÀN GIỮA]

Đây là chương đệm giữa hai arc lớn.
Sử dụng để kể ngoại truyện như một interlude.

Ngoại truyện: "{extra.get('title', '')}"
{extra.get('content_summary', '')}

[YÊU CẦU]
1. Bắt đầu với transition từ arc trước
2. Kể ngoại truyện như một câu chuyện độc lập
3. Kết thúc với hint về arc tiếp theo
4. Format: "### Màn Giữa: {extra.get('title', '')} ###"
"""
    
    def _prompt_parallel(self, extra: dict, chapter: dict) -> str:
        return f"""
[CHẾ ĐỘ: PARALLEL STORY]

Ngoại truyện này diễn ra SONG SONG với chương chính.
Ở nơi khác, cùng thời điểm.

Ngoại truyện: "{extra.get('title', '')}"
Timeline: Đồng thời với chương {chapter.get('num', '?')}

[YÊU CẦU]
1. Bắt đầu: "Cùng lúc đó, ở [địa điểm khác]..."
2. Kể sự kiện song song
3. Có thể có connection nhỏ (cùng thấy hiện tượng gì đó)
4. Kết thúc: Hint rằng hai tuyến sẽ gặp nhau
"""
    
    def _prompt_epilogue(self, extra: dict, context: str) -> str:
        return f"""
[CHẾ ĐỘ: EPILOGUE / AFTER-STORY]

Đây là ngoại truyện diễn ra SAU kết thúc chính.

[TÓM TẮT KẾT THÚC CHÍNH]
{context}

[NGOẠI TRUYỆN]
"{extra.get('title', '')}"
{extra.get('content_summary', '')}

[YÊU CẦU]
1. Dịch như after-story
2. Reference đến sự kiện đã xảy ra
3. Tone có thể nhẹ nhàng hơn hoặc bittersweet
4. KHÔNG spoil nếu chưa đọc hết truyện chính
"""
    
    def _prompt_standalone(self, extra: dict) -> str:
        return f"""
[CHẾ ĐỘ: STANDALONE / PHỤ LỤC]

Ngoại truyện này sẽ được đặt trong Phụ Lục.
Đọc độc lập, không chèn vào story.

Ngoại truyện: "{extra.get('title', '')}"

[YÊU CẦU]
1. Dịch như câu chuyện độc lập
2. Thêm note: "(Đọc sau khi hoàn thành truyện chính)"
3. Có thể thêm context ngắn đầu chương
4. Format: "### Phụ Lục: {extra.get('title', '')} ###"
"""
    
    # ========================================================================
    # LEGACY METHODS (giữ backward compat)
    # ========================================================================
    
    @staticmethod
    def get_extra_placement_strategy(
        extra_chapter_num: int,
        total_main_chapters: int
    ) -> str:
        """
        Xác định strategy cho extra dựa trên vị trí
        (Legacy method - dùng find_best_strategy cho kết quả tốt hơn)
        """
        if extra_chapter_num < total_main_chapters * 0.8:
            return "flashback"
        if extra_chapter_num >= total_main_chapters:
            return "epilogue"
        return "appendix"
    
    @staticmethod
    def get_appendix_format(extras: List[dict]) -> str:
        """Format extras thành Appendix cho ebook"""
        lines = [
            "\n\n",
            "=" * 70,
            "PHỤ LỤC - CÁC CÂU CHUYỆN NGOẠI TRUYỆN",
            "=" * 70,
            "\n(Đọc sau khi hoàn thành truyện chính để tránh spoiler)\n"
        ]
        
        for i, extra in enumerate(extras, 1):
            lines.append(f"\n### Ngoại Truyện {i}: {extra.get('title', 'Unknown')} ###")
            lines.append(f"Nhân vật: {', '.join(extra.get('characters', []))}")
            lines.append("-" * 50)
        
        return "\n".join(lines)


# ============================================================================
# EXTRA REGISTRY - QUẢN LÝ VÀ TRACK EXTRAS
# ============================================================================

class ExtraRegistry:
    """
    Registry quản lý tất cả extras và trạng thái placement
    
    Được dùng bởi ChapterDirector để:
    1. Biết extras nào chưa được hook
    2. Track extras nào đã hook ở đâu
    3. Xác định extras nào cần đưa vào Appendix cuối cùng
    """
    
    def __init__(self, extras_file: Optional[str] = None):
        self.extras: Dict[int, Dict] = {}  # extra_idx -> extra_info
        self.placement_status: Dict[int, Dict] = {}  # extra_idx -> placement_info
        # Format: {"placed": True, "chapter": 52, "strategy": "flashback", "batch_id": 6}
        
        if extras_file:
            self._load_extras(extras_file)
    
    def _load_extras(self, filepath: str):
        """Load extras từ file JSON"""
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for extra in data.get('extras', []):
                    idx = extra.get('index', 0)
                    self.extras[idx] = extra
                    self.placement_status[idx] = {"placed": False}
            except Exception as e:
                print(f"⚠️ Không thể load extras: {e}")
    
    def register_extra(
        self,
        index: int,
        title: str,
        characters: List[str],
        location: str,
        timeline: str,  # "past", "present", "future"
        themes: List[str],
        content_summary: str
    ):
        """Đăng ký một extra mới"""
        self.extras[index] = {
            "index": index,
            "title": title,
            "characters": characters,
            "location": location,
            "timeline": timeline,
            "themes": themes,
            "content_summary": content_summary
        }
        self.placement_status[index] = {"placed": False}
    
    def get_unplaced_extras(self) -> List[Dict]:
        """Lấy danh sách extras chưa được hook"""
        return [
            self.extras[idx] 
            for idx in self.extras 
            if not self.placement_status.get(idx, {}).get("placed", False)
        ]
    
    def get_extras_for_batch(
        self,
        batch_location: str,
        batch_characters: List[str],
        batch_themes: List[str]
    ) -> List[Dict]:
        """
        Lấy extras PHÙ HỢP cho batch này
        Chỉ trả về extras có khả năng hook logic
        """
        unplaced = self.get_unplaced_extras()
        candidates = []
        
        for extra in unplaced:
            score = 0
            reasons = []
            
            # Location match (weight: 3)
            if extra.get('location', '').lower() == batch_location.lower():
                score += 3
                reasons.append("location")
            elif self._is_related_location(extra.get('location', ''), batch_location):
                score += 1
                reasons.append("related_location")
            
            # Character match (weight: 3)
            extra_chars = set(extra.get('characters', []))
            batch_chars = set(batch_characters)
            char_overlap = extra_chars & batch_chars
            if char_overlap:
                score += min(3, len(char_overlap))
                reasons.append(f"characters:{list(char_overlap)}")
            
            # Theme match (weight: 2)
            extra_themes = set(extra.get('themes', []))
            batch_theme_set = set(batch_themes)
            theme_overlap = extra_themes & batch_theme_set
            if theme_overlap:
                score += min(2, len(theme_overlap))
                reasons.append(f"themes:{list(theme_overlap)}")
            
            # Timeline compatibility (weight: 1)
            timeline = extra.get('timeline', 'present')
            if timeline in ['present', 'past']:  # past = flashback ok
                score += 1
                reasons.append("timeline_ok")
            
            # Chỉ include nếu score >= 3 (có ít nhất 1 match mạnh)
            if score >= 3:
                extra['_match_score'] = score
                extra['_match_reasons'] = reasons
                candidates.append(extra)
        
        # Sort by score descending
        candidates.sort(key=lambda x: x.get('_match_score', 0), reverse=True)
        return candidates
    
    def _is_related_location(self, loc1: str, loc2: str) -> bool:
        """Kiểm tra 2 location có liên quan không"""
        # Map relationships
        related = {
            "bệnh viện": ["thành phố", "nông trại"],
            "thành phố": ["bệnh viện", "nông trại", "kuwait"],
            "nông trại": ["bệnh viện", "thành phố"],
            "kuwait": ["thành phố", "sở mậu dịch"],
            "pease": ["kuwait", "miền đất hứa"],
        }
        loc1_lower = loc1.lower()
        loc2_lower = loc2.lower()
        return loc2_lower in related.get(loc1_lower, [])
    
    def mark_as_placed(
        self,
        extra_idx: int,
        chapter: int,
        strategy: str,
        batch_id: int
    ):
        """Đánh dấu extra đã được hook"""
        self.placement_status[extra_idx] = {
            "placed": True,
            "chapter": chapter,
            "strategy": strategy,
            "batch_id": batch_id
        }
    
    def get_appendix_candidates(self) -> List[Dict]:
        """Lấy extras không hook được → Appendix"""
        return [
            {**self.extras[idx], "reason": "Không tìm được điểm hook phù hợp"}
            for idx in self.extras
            if not self.placement_status.get(idx, {}).get("placed", False)
        ]
    
    def get_placement_report(self) -> str:
        """Báo cáo trạng thái placement"""
        lines = [
            "",
            "=" * 60,
            "📊 BÁO CÁO PLACEMENT NGOẠI TRUYỆN",
            "=" * 60,
        ]
        
        placed = []
        unplaced = []
        
        for idx, status in self.placement_status.items():
            extra = self.extras.get(idx, {})
            if status.get("placed"):
                placed.append(
                    f"  ✅ Extra #{idx} '{extra.get('title', '')}' "
                    f"→ Chap {status.get('chapter')} ({status.get('strategy')})"
                )
            else:
                unplaced.append(
                    f"  ❌ Extra #{idx} '{extra.get('title', '')}' - Chưa hook"
                )
        
        lines.append(f"\n📌 ĐÃ HOOK ({len(placed)}):")
        lines.extend(placed if placed else ["  (không có)"])
        
        lines.append(f"\n⏳ CHƯA HOOK ({len(unplaced)}):")
        lines.extend(unplaced if unplaced else ["  (tất cả đã hook!)"])
        
        lines.append("=" * 60)
        return "\n".join(lines)


# ============================================================================
# INTEGRATION WITH TRANSLATOR
# ============================================================================

def integrate_direction_to_prompt(
    base_prompt: str,
    direction_text: str,
) -> str:
    """
    Tích hợp direction vào prompt dịch
    """
    if not direction_text:
        return base_prompt
    
    injection_point = base_prompt.find('[BỐI CẢNH BỔ SUNG]')
    if injection_point != -1:
        return (
            base_prompt[:injection_point] +
            direction_text + "\n\n" +
            base_prompt[injection_point:]
        )
    
    return base_prompt + "\n\n" + direction_text


# ============================================================================
# V3.0: PACING INTEGRATION - KẾT HỢP VỚI PACING CONTROLLER
# ============================================================================

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pacing_controller import PacingController, ChapterPacingPlan, PacingType


class EnhancedChapterDirector(ChapterDirector):
    """
    ChapterDirector V3.0 - Tích hợp Pacing Controller
    
    Upgrade từ V2.0:
    - Thêm PacingController để plan nhịp độ
    - Tạo detailed outline (không chỉ direction)
    - Tích hợp CharacterTracker context
    - Thêm WorldBuilder cho dynamic locations
    """
    
    def __init__(
        self,
        framework_dir: str,
        batch_size: int = 10,
        extra_registry: Optional['ExtraRegistry'] = None,
        pacing_controller: Optional['PacingController'] = None,
        character_tracker = None,
        world_builder = None
    ):
        super().__init__(framework_dir, batch_size, extra_registry)
        
        # V3.0 components
        self.pacing_controller = pacing_controller
        self.character_tracker = character_tracker
        self.world_builder = world_builder
    
    def set_pacing_controller(self, controller: 'PacingController'):
        """Set or update PacingController"""
        self.pacing_controller = controller
    
    def set_character_tracker(self, tracker):
        """Set or update CharacterTracker"""
        self.character_tracker = tracker
    
    def set_world_builder(self, builder):
        """Set or update WorldBuilder"""
        self.world_builder = builder
    
    def create_pacing_plan_for_batch(
        self,
        batch_id: int,
        arc_name: str = "",
        arc_start: int = 0,
        arc_end: int = 0
    ) -> Dict[int, 'ChapterPacingPlan']:
        """
        Tạo pacing plan cho tất cả chương trong batch
        
        Returns: Dict[chapter_num, ChapterPacingPlan]
        """
        if not self.pacing_controller:
            return {}
        
        start_chap = (batch_id - 1) * self.batch_size + 1
        end_chap = batch_id * self.batch_size
        
        pacing_plans = {}
        for chap_num in range(start_chap, end_chap + 1):
            plan = self.pacing_controller.create_pacing_plan(
                chapter_num=chap_num,
                arc_name=arc_name,
                arc_start=arc_start if arc_start else start_chap,
                arc_end=arc_end if arc_end else end_chap + 20,  # Estimate
            )
            pacing_plans[chap_num] = plan
        
        return pacing_plans
    
    def build_enhanced_direction_prompt(
        self,
        raw_chapters: List[Tuple[int, str]],
        glossary_text: str,
        memory_context: str,
        available_extras: Optional[List[Dict]] = None,
        previous_framework: Optional[BatchFramework] = None,
        arc_info: Optional[Dict] = None  # {name, start, end, theme}
    ) -> str:
        """
        Build prompt với PACING + CHARACTER + WORLD context
        
        V3.0 Upgrade: Thêm pacing analysis vào prompt
        """
        # Base prompt từ parent
        base_prompt = self.build_direction_prompt(
            raw_chapters, glossary_text, memory_context,
            available_extras, previous_framework
        )
        
        # === V3.0: THÊM PACING CONTEXT ===
        pacing_context = ""
        if self.pacing_controller and arc_info:
            batch_id = self.get_batch_id(raw_chapters[0][0])
            pacing_plans = self.create_pacing_plan_for_batch(
                batch_id=batch_id,
                arc_name=arc_info.get('name', ''),
                arc_start=arc_info.get('start', 0),
                arc_end=arc_info.get('end', 0)
            )
            
            pacing_context = "\n[PACING PLAN - TỪ CONTROLLER]\n"
            pacing_context += "Dưới đây là kế hoạch nhịp độ đã được tính toán:\n\n"
            
            for chap_num, plan in pacing_plans.items():
                pacing_context += f"Chương {chap_num}:\n"
                pacing_context += f"  - Pacing: {plan.pacing_type.value}\n"
                pacing_context += f"  - Length: {plan.rule.min_length}-{plan.rule.max_length} chars\n"
                pacing_context += f"  - Key rule: {plan.rule.guidance[0] if plan.rule.guidance else 'N/A'}\n\n"
        
        # === V3.0: THÊM CHARACTER CONTEXT ===
        char_context = ""
        if self.character_tracker:
            char_context = "\n[CHARACTER STATES - TRƯỚC BATCH]\n"
            char_context += self.character_tracker.get_character_context(raw_chapters[0][0])
        
        # === V3.0: THÊM WORLD CONTEXT ===
        world_context = ""
        if self.world_builder:
            world_context = "\n" + self.world_builder.get_current_context(raw_chapters[0][0])
        
        # Inject vào prompt
        injection_marker = "[YÊU CẦU OUTPUT]"
        injection_point = base_prompt.find(injection_marker)
        
        if injection_point != -1:
            enhanced_prompt = (
                base_prompt[:injection_point] +
                pacing_context +
                char_context +
                world_context +
                "\n\n" +
                base_prompt[injection_point:]
            )
            return enhanced_prompt
        
        return base_prompt + pacing_context + char_context + world_context
    
    def get_enhanced_direction_for_translation(
        self,
        chapter_num: int,
        include_pacing: bool = True,
        include_characters: bool = True
    ) -> str:
        """
        V3.0: Lấy direction + pacing + character cho 1 chương
        
        Returns: Full direction text cho prompt dịch
        """
        # Base direction
        base_direction = self.get_direction_for_translation(chapter_num)
        
        parts = [base_direction] if base_direction else []
        
        # === PACING ===
        if include_pacing and self.pacing_controller:
            # Get framework để lấy arc info
            framework = self.get_framework(chapter_num)
            arc_name = framework.arc_name if framework else ""
            
            # Create pacing plan
            pacing_plan = self.pacing_controller.create_pacing_plan(
                chapter_num=chapter_num,
                arc_name=arc_name,
                arc_start=framework.start_chapter if framework else chapter_num - 5,
                arc_end=framework.end_chapter if framework else chapter_num + 5,
            )
            
            parts.append(pacing_plan.to_prompt_instruction())
        
        # === CHARACTERS ===
        if include_characters and self.character_tracker:
            char_ctx = self.character_tracker.get_character_context(chapter_num)
            if char_ctx:
                parts.append(f"\n[CHARACTER STATES]\n{char_ctx}")
        
        return "\n".join(parts)
    
    def post_translation_update(
        self,
        chapter_num: int,
        translated_content: str
    ):
        """
        V3.0: Update dynamic systems sau khi dịch xong 1 chương
        
        Được gọi sau khi translation pass QA
        """
        # Update CharacterTracker
        if self.character_tracker:
            events = self.character_tracker.analyze_chapter(
                translated_content, chapter_num
            )
            if events:
                self.character_tracker.apply_events(events)  # Chỉ cần events
                print(f"   👤 [CHARACTER] Applied {len(events)} events")
        
        # Update WorldBuilder  
        if self.world_builder:
            changes = self.world_builder.analyze_chapter(
                translated_content, chapter_num
            )
            if changes.get('new_locations'):
                print(f"   🗺️ New locations: {changes['new_locations']}")
            if changes.get('new_arc'):
                print(f"   📖 New arc detected: {changes['new_arc']}")


# ============================================================================
# V3.0: DETAILED OUTLINE GENERATOR
# ============================================================================

@dataclass 
class ChapterOutline:
    """Detailed outline cho 1 chương (V3.0)"""
    chapter_num: int
    
    # Structure
    opening_scene: str = ""
    main_scenes: List[str] = field(default_factory=list)
    closing_scene: str = ""
    
    # Key elements
    key_dialogues: List[str] = field(default_factory=list)
    action_beats: List[str] = field(default_factory=list)
    emotional_beats: List[str] = field(default_factory=list)
    
    # From ChapterNote
    required_events: List[str] = field(default_factory=list)
    character_moments: Dict[str, str] = field(default_factory=dict)
    
    # Pacing (from PacingController)
    pacing_type: str = "medium"
    content_restrictions: List[str] = field(default_factory=list)
    target_length: Tuple[int, int] = (4000, 6000)
    
    def to_prompt(self) -> str:
        """Convert to prompt instruction"""
        lines = [
            "=" * 60,
            f"[DETAILED OUTLINE - Chương {self.chapter_num}]",
            "=" * 60,
            "",
        ]
        
        if self.opening_scene:
            lines.append(f"🎬 MỞ ĐẦU: {self.opening_scene}")
        
        if self.main_scenes:
            lines.append("\n📍 CÁC SCENE CHÍNH:")
            for i, scene in enumerate(self.main_scenes, 1):
                lines.append(f"  {i}. {scene}")
        
        if self.closing_scene:
            lines.append(f"\n🎬 KẾT THÚC: {self.closing_scene}")
        
        if self.key_dialogues:
            lines.append("\n💬 DIALOGUE QUAN TRỌNG:")
            for dlg in self.key_dialogues:
                lines.append(f"  • {dlg}")
        
        if self.action_beats:
            lines.append("\n⚔️ ACTION BEATS:")
            for beat in self.action_beats:
                lines.append(f"  • {beat}")
        
        if self.emotional_beats:
            lines.append("\n❤️ EMOTIONAL BEATS:")
            for beat in self.emotional_beats:
                lines.append(f"  • {beat}")
        
        if self.content_restrictions:
            lines.append("\n⚠️ CONTENT RESTRICTIONS:")
            for restriction in self.content_restrictions:
                lines.append(f"  ❌ {restriction}")
        
        lines.append(f"\n📏 TARGET LENGTH: {self.target_length[0]}-{self.target_length[1]} chars")
        lines.append(f"🎭 PACING: {self.pacing_type.upper()}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


class OutlineGenerator:
    """
    Generator chi tiết outline từ raw content + framework
    
    Flow:
    1. Nhận raw content + ChapterNote + PacingPlan
    2. Phân tích cấu trúc chương
    3. Tạo detailed outline
    4. Return để inject vào prompt
    """
    
    def __init__(self, pacing_controller: Optional['PacingController'] = None):
        self.pacing_controller = pacing_controller
    
    def generate_outline(
        self,
        chapter_num: int,
        raw_content: str,
        chapter_note: Optional[ChapterNote] = None,
        pacing_plan: Optional['ChapterPacingPlan'] = None
    ) -> ChapterOutline:
        """
        Generate detailed outline cho 1 chương
        """
        outline = ChapterOutline(chapter_num=chapter_num)
        
        # === Parse raw content ===
        scenes = self._extract_scenes(raw_content)
        
        if scenes:
            outline.opening_scene = scenes[0][:100] + "..." if len(scenes[0]) > 100 else scenes[0]
            outline.main_scenes = scenes[1:-1] if len(scenes) > 2 else scenes
            outline.closing_scene = scenes[-1][:100] + "..." if scenes and len(scenes[-1]) > 100 else (scenes[-1] if scenes else "")
        
        # === From ChapterNote ===
        if chapter_note:
            outline.required_events = chapter_note.required_events
            outline.character_moments = chapter_note.character_moments
        
        # === From PacingPlan ===
        if pacing_plan:
            outline.pacing_type = pacing_plan.pacing_type.value
            outline.target_length = (pacing_plan.rule.min_length, pacing_plan.rule.max_length)
            
            # Extract restrictions
            from pacing_controller import ContentRestriction
            for content_type, restriction in pacing_plan.get_effective_rules().items():
                    if restriction == ContentRestriction.FORBIDDEN:
                        outline.content_restrictions.append(f"KHÔNG {content_type}")
        
        return outline
    
    def _extract_scenes(self, content: str) -> List[str]:
        """Extract scenes từ raw content"""
        # Split by double newlines or scene markers
        import re
        
        # Try scene markers first
        scenes = re.split(r'\n\s*[*]{3,}\s*\n|\n\s*[-]{3,}\s*\n', content)
        
        if len(scenes) < 2:
            # Fall back to paragraph splitting
            scenes = re.split(r'\n\n+', content)
        
        # Filter empty and too short
        scenes = [s.strip() for s in scenes if len(s.strip()) > 50]
        
        return scenes
    
    def generate_batch_outlines(
        self,
        raw_chapters: List[Tuple[int, str]],
        framework: BatchFramework,
        pacing_plans: Optional[Dict[int, 'ChapterPacingPlan']] = None
    ) -> Dict[int, ChapterOutline]:
        """
        Generate outlines cho cả batch
        """
        outlines = {}
        
        for chap_num, content in raw_chapters:
            note = framework.chapter_notes.get(chap_num)
            plan = pacing_plans.get(chap_num) if pacing_plans else None
            
            outlines[chap_num] = self.generate_outline(
                chapter_num=chap_num,
                raw_content=content,
                chapter_note=note,
                pacing_plan=plan
            )
        
        return outlines
