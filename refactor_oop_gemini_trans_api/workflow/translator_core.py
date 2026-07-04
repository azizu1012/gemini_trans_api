"""
Translator Core Module - Logic dịch chương sử dụng AsyncOpenAI
Hỗ trợ Router API v2, AsyncOpenAI bất đồng bộ, và model động.
Tối ưu hóa Tuyến Tính Tuyệt Đối (Strictly Linear Pipeline) loại bỏ ExtraRegistry thừa.
"""
import os
import re
import asyncio
from typing import Tuple, Optional, List, Dict
from google import genai
from google.genai import types

from ..config.config import TranslatorConfig
from ..memory.memory_manager import MemoryManager
from ..data.content_loader import ChapterData
from ..plan.chapter_director import ChapterDirector
from ..review.quality_assurance import QualityAssurance, ReviewResult
from .expansion_engine import CHAPTER_NAMER, SmartExpansionEngine
from ..trackers import CharacterTracker
from ..world.glossary import GlossaryManager
class PromptBuilder:
    """Xây dựng prompt cho AI"""

    def __init__(self, glossary_manager: GlossaryManager):
        self.glossary = glossary_manager

    def build_system_prompt(
    self,
    memory_context: str = "",
    is_extra: bool = False,
    chapter_num: int = 0,
    enable_world_building: bool = True,
    enable_character_depth: bool = True,
    enable_map_exploration: bool = True,
    character_context: str = "",
    style_guide: str = "",
    genre_prompt: str = "",
    expansion_types: Optional[List[str]] = None
    ) -> str:
        """
Tạo system prompt cho translation
expansion_types: list từ SmartExpansionEngine (optional, chỉ khi enable_expansion)
        """
        glossary_text = self.glossary.get_glossary_text() if hasattr(self.glossary, 'get_glossary_text') else ""

        extra_instruction = (
        "Đây là phiên ngoại (Extra/Side Story). "
        "Hãy dịch với giọng văn thoải mái hơn nhưng vẫn giữ chất Mạt thế."
        ) if is_extra else ""

        # Lấy naming instruction từ arc context
        naming_instruction = ""
        if chapter_num > 0:
            naming_instruction = CHAPTER_NAMER.generate_naming_instruction(chapter_num)

        # EXPANSION INSTRUCTION - từ SmartExpansionEngine (nếu enable_expansion)
        expansion_instruction = ""
        if expansion_types:
            type_prompts = []
            if enable_world_building and "WORLD" in str(expansion_types):
                type_prompts.append("WORLD-BUILDING: Giải thích hệ thống thế giới, lịch sử, chi tiết quái vật/vật phẩm")
            if enable_character_depth and "CHARACTER" in str(expansion_types):
                type_prompts.append("CHARACTER DEPTH: Tâm lý nhân vật, nội tâm, flashback, backstory")
            if enable_map_exploration and "DETAIL" in str(expansion_types):
                type_prompts.append("MAP EXPLORATION: Mô tả môi trường chi tiết, khám phá khu vực mới")
            if type_prompts:
                expansion_instruction = "\n[MỞ RỘNG NỘI DUNG]\n" + "\n".join(f"- {t}" for t in type_prompts) + "\n"

        prompt = f"""
{expansion_instruction}
[VAI TRÒ]
Bạn là một dịch giả tiểu thuyết chuyên nghiệp, chuyên dòng Mạt thế/Khoa huyễn u tối (Lovecraftian/Post-Apocalyptic).
Nhiệm vụ: Dịch văn bản từ tiếng Trung (Convert/Thô) sang tiếng Việt THUẦN VIỆT.

⚠️ LƯU Ý QUAN TRỌNG VỀ INPUT:
- Input là bản CONVERT THÔ từ tiếng Trung, KHÔNG phải tiếng Việt chuẩn.
- Có nhiều từ vẫn còn dạng PHIÊN ÂM SAI hoặc dịch máy kém chất lượng.
- Nhiệm vụ của bạn là BIẾN ĐỔI thành tiếng Việt TỰ NHIÊN, TRÔI CHẢY.

PHẦN 1: BỘ NHỚ (MEMORY) - TÓM TẮT TRƯỚC ĐÓ
{memory_context}

PHẦN 2: TỪ ĐIỂN BẮT BUỘC (GLOSSARY)
{glossary_text}

PHẦN 2.5: XỬ LÝ PHIÊN ÂM SAI / CONVERT THÔ (CỰC KỲ QUAN TRỌNG - ĐỌC KỸ!)
Vì input là convert thô, bạn SẼ GẶP các lỗi sau và PHẢI SỬA NGAY LẬP TỨC:

⚠️ LỖI NGHIÊM TRỌNG NHẤT - "Từng cái" / "Từng Cái" / "Tùng Tử":
→ Đây là BIỆT DANH cha mẹ gọi Lâm Nhất (聪仔 = Cōng zǎi)
→ PHẢI DỊCH thành: "con" hoặc "thằng nhỏ" hoặc "nhóc"
→ KHÔNG BAO GIỜ giữ nguyên "Từng cái" trong output!
→ Ví dụ: "Từng cái, con dậy rồi sao?" → "Con ơi, con dậy rồi hả?"

1. **Tên gọi thân mật PHẢI VIỆT HÓA:**
- "Từng Cái", "Từng cái", "Tùng Tử" → "con", "thằng nhỏ", "nhóc" (cha mẹ gọi Lâm Nhất)
- "Tiểu Gia Hỏa" → "thằng nhỏ", "nhóc"
- "Tiểu Tử" → "thằng nhóc"
- "Tiểu Quỷ" → "nhóc quỷ"
- "Bảo Bối" → "con yêu", "cưng"

2. **Xưng hô gia đình PHẢI VIỆT HÓA:**
- "Mụ mụ" → "mẹ"
- "Ba ba" → "ba", "cha"
- "Ca ca" → "anh"
- "Muội muội" → "em gái"
- "Đệ đệ" → "em trai"

3. **Từ vựng phiên âm cần Việt hóa:**
- "Điện thoại di động" → "điện thoại"
- "Ô tô" / "Tiểu xa" → "xe"
- "Thanh âm" → "giọng nói", "tiếng"
- "Thân thể" → "người", "cơ thể"
- "Khảo thí" → "thi cử", "kỳ thi"
- "Nam Thành Bang" / "nam thành bang" → "bang Nam Thành"
- "Bắc Lầu Phái" / "bắc lầu phái" → "phái Bắc Lầu"
- "Thành Pease" / "thành Pease" → "thành phố Pease"
- "Tư Đức Farrell" / "tư đức farrel" → "Stefarrel"
- "Oán Mệnh Ở Giữa" / "oán mệnh ở giữa" → "Cõi Oán Mệnh"

4. **Cấu trúc câu Trung Quốc cần chuyển sang Việt:**
- "Ta đã không thể chờ đợi được" → "Ta nóng lòng muốn"
- "Ngươi làm sao ra một đầu mồ hôi" → "Sao con đổ mồ hôi thế"
- Bỏ các từ đệm vô nghĩa: "a", "nha", "đi"

**NGUYÊN TẮC:** Khi gặp từ/cụm từ có vẻ là phiên âm hoặc dịch máy, HÃY DỊCH LẠI thành tiếng Việt tự nhiên dựa trên ngữ cảnh.

PHẦN 3: QUY TẮC DỊCH (NGHIÊM NGẶT)
1. **XƯNG HÔ (QUAN TRỌNG NHẤT - HÃY DỊCH TỰ NHIÊN):**
- Xưng hô phải tự nhiên và phù hợp với mối quan hệ giữa các nhân vật:
  * Giữa bạn bè bình thường/đồng nghiệp/người lạ có thiện ý: Dùng **Tôi - Cậu** hoặc **Tôi - Anh** cho lịch sự, tự nhiên.
  * Giữa bạn bè cực kỳ thân thiết/suồng sã: Dùng **Tao - Mày**.
  * Giữa kẻ thù/đối thủ hoặc trong tình huống đối đầu gay gắt: Dùng **Ta - Ngươi** hoặc **Tao - Mày**.
  * Khi xưng hô với người bề trên/lớn tuổi (như An đại thúc): Xưng **con/em/cháu** và gọi **đại thúc/bác/anh/chị** cho đúng phép tắc tiếng Việt. Tuyệt đối không dùng "ta - ngươi" bừa bãi với người lớn tuổi.
  * Bố mẹ gọi con: Dùng **con/mẹ/ba** (hoặc "nhóc", "thằng nhỏ"). Tuyệt đối cấm giữ nguyên phiên âm như "Từng Cái", "Mụ mụ", "Ba ba".

2. **Xử lý nội dung:**
- Tuyệt đối không để lại chữ Hán hoặc phiên âm thô.
- **TUÂN THỦ TỪ ĐIỂN:** Các từ trong GLOSSARY phải được giữ nguyên 100%.
- Văn phong: Ngắn gọn, lạnh lùng, dứt khoát.

3. **Tiêu đề & Định dạng (QUAN TRỌNG):**
- **BIÊN SOẠN LẠI TÊN CHƯƠNG SÁNG TẠO:** Ở đầu văn bản đầu vào có cung cấp "Tiêu đề gốc (Tiếng Trung/Convert)". Hãy dịch và biên soạn lại tiêu đề này sang tiếng Việt hấp dẫn, mượt mà dựa trên nội dung chương thực tế đã dịch.
- **ĐỊNH DẠNG BẮT BUỘC:**
  * Nếu Tiêu đề gốc là Ngoại truyện/Phiên ngoại (chứa các từ như Ngoại truyện, Phiên ngoại, Spinoff, Hậu truyện, v.v.), hãy bắt đầu bằng: `### Ngoại truyện: [Tên ngoại truyện mới biên soạn] ###`. Tuyệt đối KHÔNG sử dụng định dạng 'Chương X'.
  * Nếu Tiêu đề gốc là chương thông thường (chứa số chương như Chương X), hãy dùng định dạng: `### Chương {chapter_num}: [Tên chương mới biên soạn] ###`. (Thay {chapter_num} bằng số chương thực tế được chỉ định).
- **TRẢ VỀ KẾT QUẢ:** Bắt đầu câu trả lời **TRỰC TIẾP** bằng dòng tiêu đề được định dạng ở trên.
- **TUYỆT ĐỐI KHÔNG** thêm bất kỳ lời dẫn hay ghi chú nào trước dòng tiêu đề.

{naming_instruction}

[BỐI CẢNH BỔ SUNG]
{extra_instruction}
        """

        # === REMAKE ENGINE — NÂNG CẤP CHẤT LƯỢNG BIỂU ĐẠT ===
        prompt += """

PHẦN 4: REMAKE ENGINE — NÂNG CẤP CHẤT LƯỢNG BIỂU ĐẠT
⚠️ NGUYÊN TẮC BẤT KHẢ XÂM PHẠM: Giữ nguyên 100% chuỗi sự kiện lõi.
Chỉ nâng cấp cách DIỄN ĐẠT, không thay đổi ĐIỀU GÌ XẢY RA.

KỸ THUẬT 1: HỢP LÝ HÓA ĐỘNG CƠ TÂM LÝ (Psychological Rationalization)
- Khi gặp hành động nhân vật có vẻ "vô lý" hoặc "gượng ép", hãy BƠM THÊM suy nghĩ nội tâm,
trauma, áp lực ngoại cảnh (thời tiết, quái vật, đói khát) để người đọc thấy hành động đó HỢP LÝ.
- Tham chiếu [TRẠNG THÁI NHÂN VẬT] bên dưới (trauma_score, emotion).
- VD: Nhân vật lao vào nguy hiểm → bổ sung: "Di chứng quay ngược thời gian khiến đầu đau như búa bổ,
phán đoán suy giảm. Cộng thêm sương mù mạt thế che khuất tầm nhìn, cậu bước nhầm vào vùng cấm."

KỸ THUẬT 2: TẢ THAY VÌ KỂ (Show, Don't Tell)
- Chuyển câu kể phẳng ("Hắn rất tức giận") thành Action Beats + Sensory Details.
- VD: "Tức giận" → "Siết chặt nắm đấm đến mức khớp xương kêu răng rắc, đôi mắt hằn lên tia máu."
- Mô tả qua 5 giác quan: nhìn, nghe, ngửi, chạm, vị.
- ĐẶC BIỆT ƯU TIÊN: Mùi máu, tiếng kim loại, ánh sáng lờ mờ mạt thế, gió lạnh.

KỸ THUẬT 3: BẮC CẦU LOGIC CHUYỂN CẢNH (Logic Bridging)
- Khi chuyển từ địa điểm A → B, THÊM mô tả di chuyển ngắn (1-2 câu).
- VD: "Luồn lách qua đống đổ nát, né tầm quét camera sinh học của Yêu Thụ Thiên Mục."
- Tham chiếu [WORLD CONTEXT] ở PHẦN 1 để biết map, dị loại khu vực hiện tại.
        """

        # === INJECT CHARACTER STATES cho Psychological Rationalization ===
        if character_context:
            prompt += f"\n\nPHẦN 5: TRẠNG THÁI NHÂN VẬT (Dùng cho Kỹ thuật 1 - Hợp lý hóa)\n{character_context}"

        # === INJECT STYLE GUIDE từ StyleLearner ===
        if style_guide:
            prompt += f"\n\n{style_guide}"

        # === INJECT GENRE PROFILE ===
        if genre_prompt:
            prompt += f"\n\n{genre_prompt}"

        return prompt.strip()


class ChapterTranslator:
    """Xử lý dịch từng chương sử dụng AsyncOpenAI"""

    QA_PASS_THRESHOLD = 80
    QA_MAX_RETRIES = 2
    BATCH_SIZE = 10

    def __init__(
    self,
    config: TranslatorConfig,
    glossary_manager: GlossaryManager,
    memory_manager: MemoryManager
    ):
        self.config = config
        self.glossary = glossary_manager
        self.memory = memory_manager
        self.prompt_builder = PromptBuilder(glossary_manager)

        # Khởi tạo google-genai client từ config
        base_url = config.api_endpoint.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        self.client = genai.Client(
            api_key=config.auth_key or "sk-no-key-required",
            http_options={"base_url": base_url}
        )

        # Monkey-patch client để gửi trực tiếp web_search: False qua JSON body (tránh Pydantic validation)
        original_async_request = self.client._api_client.async_request
        async def custom_async_request(http_method, path, request_dict=None, http_options=None):
            if request_dict is not None and isinstance(request_dict, dict):
                request_dict["web_search"] = False  # type: ignore[arg-type]
            return await original_async_request(http_method, path, request_dict, http_options)  # type: ignore[arg-type]
        self.client._api_client.async_request = custom_async_request

        original_request = self.client._api_client.request
        def custom_request(http_method, path, request_dict=None, http_options=None):
            if request_dict is not None and isinstance(request_dict, dict):
                request_dict["web_search"] = False  # type: ignore[arg-type]
            return original_request(http_method, path, request_dict, http_options)  # type: ignore[arg-type]
        self.client._api_client.request = custom_request

        # Director
        framework_dir = os.path.join(config.temp_folder, 'frameworks')

        # ĐỘC LẬP TUYẾN TÍNH TUYỆT ĐỐI: Loại bỏ hoàn toàn ExtraRegistry phi tuyến tính
        self.director = ChapterDirector(
            framework_dir=framework_dir,
            batch_size=self.BATCH_SIZE
        )

        # QA
        glossary_dict = glossary_manager.get_glossary_dict() if hasattr(glossary_manager, 'get_glossary_dict') else {}
        self.qa = QualityAssurance(glossary_terms=glossary_dict)
        self.enable_qa = getattr(config, 'enable_qa', True)

        # Character Tracker
        character_save_dir = os.path.join(config.temp_folder, 'character_states')
        self.character_tracker = CharacterTracker(save_dir=character_save_dir)


        # Expansion Engine
        if config.enable_expansion:
            self.expansion_engine = SmartExpansionEngine(
                min_expansion_rate=1.5,  # Fixed rate, expansion chỉ là on/off
                auto_adjust=True,
                enable_splitting=True,
                enable_side_plots=True,
                max_retries=2
            )
        else:
            self.expansion_engine = None

        # Style Learner (v3.5)
        try:
            from ..trackers.style_learner import get_style_learner
            style_data_dir = os.path.join(os.path.dirname(__file__), 'style_data')
            self.style_learner = get_style_learner(style_data_dir)
        except Exception:
            self.style_learner = None

        # Genre Mixer (v3.5)
        try:
            from ..output.genre_mixer import GenreMixer
            fallback_dir = os.path.join(os.path.dirname(__file__), 'style_data', 'genre_profiles')
            self.genre_mixer = GenreMixer(
                profile_path=getattr(config, 'genre_profile_path', ''),
                fallback_dir=fallback_dir
            )
        except Exception:
            self.genre_mixer = None

        self.split_tracker = {}
        self.total_output_chapters = 0
        self.all_raw_chapters = []
        self._framework_lock = asyncio.Lock()
        os.makedirs(self.config.temp_folder, exist_ok=True)

    async def call_api(
    self,
    model: str,
    system_prompt: str,
    user_content: str,
    temperature: float = 0.3
    ) -> str:
        """Thực hiện gọi API bất đồng bộ sử dụng google-genai client với cơ chế Retry lũy tiến"""
        import time
        import random
        retries = 0
        delay = self.config.retry_initial_delay
        
        while True:
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        tools=[]  # Tắt Google Search Grounding để không bị lẫn link
                    )
                )
                text = (response.text or "").strip()
                # Loại bỏ các khối liên kết nguồn tìm kiếm (Vertex AI Search Grounding) tự động chèn ở cuối
                text = re.sub(r'\n\s*---\s*\n\s*\*\*🔗 Nguồn thông tin:\*\*.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'\n\s*\*\*🔗 Nguồn thông tin:\*\*.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'\n\s*---\s*\n\s*\*\*🔗 Grounding Sources:\*\*.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'\n\s*\*\*🔗 Grounding Sources:\*\*.*$', '', text, flags=re.DOTALL | re.IGNORECASE)
                return text.strip()
            except Exception as e:
                retries += 1
                if retries > self.config.retry_limit:
                    raise RuntimeError(f"Lỗi gọi API ({model}) sau {self.config.retry_limit} lần thử: {e}")
                
                err_str = str(e).lower()
                is_quota = "500" in err_str and ("internal server error" in err_str or "quota" in err_str)
                is_rate_limit = "429" in err_str or "rate_limit" in err_str or "quota" in err_str or "exhausted" in err_str or is_quota
                
                if is_rate_limit:
                    base_wait = 85.0 * (1.4 ** (retries - 1))
                    sleep_time = base_wait + random.uniform(0, 5)
                else:
                    sleep_time = delay * (1.5 ** (retries - 1)) + random.uniform(0, 2)
                    sleep_time = min(sleep_time, self.config.retry_max_delay)
                
                level = "RATE_LIMIT" if is_rate_limit else "ERROR"
                print(f"⚠️ [{level}] Lỗi gọi API ({model}): {e}. Đang thử lại lần {retries}/{self.config.retry_limit} sau {sleep_time:.1f}s...")
                await asyncio.sleep(sleep_time)

    def _track_split(self, chapter_num: int, split_count: int):
        """Track split count for dynamic estimate"""
        self.split_tracker[chapter_num] = split_count
        self.total_output_chapters += (split_count - 1)

    def get_dynamic_estimate(self, total_source_chapters: int) -> int:
        """Ước tính số chương đầu ra động"""
        if not self.expansion_engine:
            return total_source_chapters

        completed = len(self.split_tracker) + self.get_current_output_count() - self.total_output_chapters
        if completed < 1:
            completed = 1

        if self.split_tracker:
            avg_split_ratio = sum(self.split_tracker.values()) / len(self.split_tracker)
        else:
            avg_split_ratio = 1.2 if self.config.enable_expansion else 1.0

        remaining_source = total_source_chapters - completed
        estimated_remaining_output = 0
        for chap in range(completed + 1, total_source_chapters + 1):
            _, potential, _, _ = self.expansion_engine.get_map_info(chap)
            chapter_estimate = 1 + (avg_split_ratio - 1) * (potential / 10)
            estimated_remaining_output += chapter_estimate

        current_output = self.get_current_output_count()
        return current_output + int(estimated_remaining_output)

    def get_current_output_count(self) -> int:
        """Đếm số file đã dịch trong temp_folder"""
        try:
            files = os.listdir(self.config.temp_folder)
            return len([f for f in files if f.startswith('chap_') and f.endswith('.txt')])
        except:
            return 0

    async def ensure_batch_framework_async(
        self,
        batch_id: int,
        force_regenerate: bool = False
    ) -> bool:
        """Đảm bảo framework cho batch_id đã được tạo (Thread-safe với asyncio.Lock)"""
        start_chap = (batch_id - 1) * self.BATCH_SIZE + 1
        end_chap = batch_id * self.BATCH_SIZE

        # Kiểm tra nhanh không cần Lock xem có framework chưa
        existing = self.director.get_framework(start_chap)
        if existing and not force_regenerate:
            return True

        async with self._framework_lock:
            # Check lại lần nữa sau khi có lock
            existing = self.director.get_framework(start_chap)
            if existing and not force_regenerate:
                return True

            print(f"🎬 [DIRECTOR] Đang tạo động Batch Framework {batch_id} (Chương {start_chap}-{end_chap})...")
            
            # Lọc ra các chương thuộc batch này từ all_raw_chapters
            raw_chapters = []
            source_list = self.all_raw_chapters if self.all_raw_chapters else []
            for chap in source_list:
                if start_chap <= chap.index <= end_chap:
                    raw_chapters.append((chap.index, chap.content))

            if not raw_chapters:
                # Fallback: không có danh sách full thì không sinh được
                print(f"   ⚠️ [DIRECTOR] Không tìm thấy dữ liệu raw cho Batch {batch_id} trong cache!")
                return False

            memory_ctx = self.memory.get_latest_memory(start_chap)
            glossary_text = self.glossary.get_glossary_text() if hasattr(self.glossary, 'get_glossary_text') else ""

            prev_batch_id = batch_id - 1
            prev_framework = self.director.get_framework(prev_batch_id * self.BATCH_SIZE) if prev_batch_id > 0 else None

            prompt = self.director.build_direction_prompt(
                raw_chapters=raw_chapters,
                glossary_text=glossary_text,
                memory_context=memory_ctx,
                previous_framework=prev_framework
            )

            try:
                system_instruction = "Bạn là một biên tập viên truyện chuyên nghiệp. Trả về JSON theo format yêu cầu."
                response_text = await self.call_api(
                    model=self.config.model_architect,
                    system_prompt=system_instruction,
                    user_content=prompt,
                    temperature=0.2
                )

                framework = self.director.parse_framework_response(
                    response_text,
                    batch_id,
                    start_chap,
                    end_chap,
                    self.config.model_architect
                )
                if framework:
                    print(f"   ✅ [DIRECTOR] Framework Batch {batch_id} created dynamically! Arc: {framework.arc_name}")
                    return True
            except Exception as e:
                print(f"   ❌ [DIRECTOR] Lỗi tạo động framework cho Batch {batch_id}: {e}")
                return False
        return False

    async def prepare_batch_framework_async(
        self,
        chapters: List[ChapterData],
        force_regenerate: bool = False
    ) -> bool:
        """Chuẩn bị trước tối đa 2 batch gối đầu chưa có sẵn để tránh bị nghẽn khởi động"""
        if not chapters:
            return True

        # Đồng bộ danh sách raw nếu rỗng
        if not self.all_raw_chapters:
            self.all_raw_chapters = chapters

        chapter_indexes = sorted([c.index for c in chapters])
        batches_needed = sorted(list(set(self.director.get_batch_id(idx) for idx in chapter_indexes)))
        
        # Chỉ tìm tối đa 2 batch chưa có sẵn để khởi tạo gối đầu
        batches_to_create = []
        for bid in batches_needed:
            start_chap = (bid - 1) * self.BATCH_SIZE + 1
            if not self.director.get_framework(start_chap):
                batches_to_create.append(bid)
                if len(batches_to_create) >= 2:
                    break
                    
        if not batches_to_create:
            print("   ✅ Tất cả các batch framework gối đầu đã sẵn sàng.")
            return True
            
        print(f"🎬 [DIRECTOR] Chuẩn bị trước {len(batches_to_create)} batch frameworks gối đầu: {batches_to_create}")
        for bid in batches_to_create:
            await self.ensure_batch_framework_async(bid, force_regenerate)
            
        return True