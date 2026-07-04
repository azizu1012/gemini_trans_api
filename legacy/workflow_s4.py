"""
workflow_s4.py - Workflow S4 kế thừa cấu trúc tam quyền từ workflow_v3, chỉ dùng cho logic hậu truyện S4
"""
from workflow_v3 import AgenticTranslator
from core import TranslatorConfig, APIManager, GlossaryManager, MemoryManager, ChapterData
from directors import EnhancedChapterDirector, QualityAssurance, PacingController
from trackers import CharacterTracker, DynamicWorldBuilder
from expansion_engine import SmartExpansionEngine

class S4WorkflowRunner:
    def __init__(self, config: TranslatorConfig, s4_outline: str, s4_prompt: str):
        self.config = config
        self.s4_outline = s4_outline
        self.s4_prompt = s4_prompt
        # Khởi tạo các thành phần như workflow_v3
        self.api_manager = APIManager(config)
        self.glossary_manager = GlossaryManager(config)
        self.memory_manager = MemoryManager(config)
        self.director = EnhancedChapterDirector(config)
        self.qa = QualityAssurance(glossary_terms=self.glossary_manager.get_glossary_dict())
        self.pacing = PacingController()
        self.character_tracker = CharacterTracker()
        self.world_builder = DynamicWorldBuilder()
        self.expansion_engine = SmartExpansionEngine(config)
        self.translator = AgenticTranslator(
            config,
            self.api_manager,
            self.glossary_manager,
            self.memory_manager,
            director=self.director,
            qa=self.qa,
            pacing=self.pacing,
            character_tracker=self.character_tracker,
            world_builder=self.world_builder,
            expansion_engine=self.expansion_engine
        )

    def run_s4(self):
        """
        Chạy workflow S4: chỉ sinh ngoại truyện S4 dựa trên outline và prompt đã kiểm duyệt
        """
        # Tạo 1 ChapterData đặc biệt cho S4
        s4_chapter = ChapterData(
            num=1,
            title_raw="S4 - Hậu truyện: Kết mở cho Lâm Nhất và Anna",
            content=self.s4_prompt,
            is_extra=True
        )
        # Chạy workflow cho 1 chương ngoại truyện S4
        print("\n🚀 BẮT ĐẦU SINH NGOẠI TRUYỆN S4...")
        result = self.translator.process_chapter_with_qa(s4_chapter)
        if result.status == "SUCCESS":
            print("\n✅ ĐÃ SINH NGOẠI TRUYỆN S4!")
            print(result.translated_text)
        else:
            print(f"\n❌ LỖI: {result.error_message}")
        return result
