"""
Workflow V3.0 - Tam Quyền Phân Lập (Tuyến Tính Tuyệt Đối)
========================================================

Architect → Writer → Critic

Cơ chế Fail-safe nghiêm ngặt: "Cương Chế Sát Nghĩa + Ghi Vết Lỗi"
Đập bỏ hoàn toàn logic ExtraRegistry phi tuyến tính.
Hệ thống xử lý tuyến tính tuyệt đối theo vị trí vật lý để tránh lỗi nuốt chương 234 trùng lặp.
"""

import os
import re
import asyncio
import time
from typing import Tuple, Optional, List, Dict
from ..world.glossary import Glossary, GlossaryManager
from dataclasses import dataclass, field

from ..config.config import TranslatorConfig
from ..memory.memory_manager import MemoryManager
from ..data.content_loader import ChapterData
from ..plan.chapter_director import ChapterDirector
from ..review.quality_assurance import QualityAssurance, ReviewResult
from .expansion_engine import SmartExpansionEngine
from ..trackers import CharacterTracker
from .translator_core import ChapterTranslator, PromptBuilder
@dataclass
class TranslationResult:
    """Kết quả dịch 1 chương"""
    chapter_index: int
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    translated_text: str = ""
    final_score: int = 0
    review_attempts: List[ReviewResult] = field(default_factory=list)
    total_attempts: int = 0
    split_count: int = 1
    error_message: str = ""

    @property
    def passed_qa(self) -> bool:
        return self.final_score >= 80


class AgenticTranslator:
    """
    Translator V3.0 với workflow agentic bất đồng bộ tuyến tính tuyệt đối
    """

    MAX_REVISION_ATTEMPTS = 3
    PASS_THRESHOLD = 80

    def __init__(
        self,
        config: TranslatorConfig,
        glossary_manager: GlossaryManager,
        memory_manager: MemoryManager,
        translator: ChapterTranslator
    ):
        self.config = config
        self.glossary = glossary_manager
        self.memory = memory_manager
        self.translator = translator
        self.prompt_builder = translator.prompt_builder
        self.director = translator.director
        self.qa = translator.qa
        self.character_tracker = translator.character_tracker
        self.world_manager = None
        self.expansion_engine = translator.expansion_engine

        self.split_tracker: Dict[int, int] = {}
        self.total_output_chapters = 0
        self.quarantine_log_file = os.path.join(config.output_dir, "quarantine_chapters.log")

    def _get_architecture_context(self, chapter: ChapterData) -> str:
        """[ARCHITECT] Lấy tất cả context cần thiết"""
        context_parts = []

        # 1. Memory context (Dựa trên chỉ mục vật lý)
        memory_ctx = self.memory.get_latest_memory(chapter.index)
        if memory_ctx:
            context_parts.append(f"[MEMORY CONTEXT]\n{memory_ctx}")

        # 2. Direction từ Director (nếu có, dựa trên chỉ mục vật lý)
        if self.director:
            direction = self.director.get_direction_for_translation(chapter.index)
            if direction:
                context_parts.append(f"[CHAPTER DIRECTION]\n{direction}")

        # 3. World context
        if self.world_manager:
            world_ctx = self.world_manager.get_full_context(chapter.index)
            if world_ctx:
                context_parts.append(f"[WORLD CONTEXT]\n{world_ctx}")

        # 4. Tiền ngữ cảnh gối đầu từ chương trước (Sliding Token Window vật lý tuyệt đối)
        if getattr(chapter, 'previous_context', ''):
            context_parts.append(f"[TIỀN NGỮ CẢNH - 500 TỪ CUỐI CỦA CHƯƠNG TRƯỚC]\n{chapter.previous_context}")

        return "\n\n".join(context_parts)

    async def _translate_with_context(
        self,
        chapter: ChapterData,
        architecture_context: str,
        revision_feedback: str = "",
        is_enforcement_pass: bool = False
    ) -> Tuple[str, str]:
        """
        [WRITER] Dịch chương với context đầy đủ (bất đồng bộ)
        """
        # Build character context cho Psychological Rationalization
        character_context = ""
        if self.character_tracker:
            try:
                character_context = self.character_tracker.get_character_context(
                    0 if chapter.is_extra else chapter.index
                )
            except Exception:
                pass

        # Build style guide từ StyleLearner
        style_guide = ""
        if hasattr(self.translator, 'style_learner') and self.translator.style_learner:
            try:
                style_guide = self.translator.style_learner.get_prompt_instruction()
            except Exception:
                pass

        # Build genre prompt từ GenreMixer
        genre_prompt = ""
        if hasattr(self.translator, 'genre_mixer') and self.translator.genre_mixer:
            try:
                genre_prompt = self.translator.genre_mixer.get_prompt_section()
            except Exception:
                pass

        # Build system prompt
        expansion_types = None
        if self.expansion_engine and not is_enforcement_pass:
            target = self.expansion_engine.calculate_expansion_target(
                chapter.index, len(chapter.content)
            )
            expansion_types = target.expansion_types
        system_prompt = self.prompt_builder.build_system_prompt(
            memory_context=architecture_context,
            is_extra=chapter.is_extra,
            chapter_num=0 if chapter.is_extra else chapter.num,
            enable_world_building=self.config.enable_world_building,
            enable_character_depth=self.config.enable_character_depth,
            enable_map_exploration=self.config.enable_map_exploration,
            character_context=character_context,
            style_guide=style_guide,
            genre_prompt=genre_prompt,
            expansion_types=expansion_types
        )

        # Áp dụng siết chặt kỷ luật ở Enforcement Pass (Lượt cuối)
        if is_enforcement_pass:
            system_prompt += """
    \n╔══════════════════════════════════════════════════════════════════╗
    ║  ⚠️ CƯƠNG CHẾ TUYỆT ĐỐI - ĐÂY LÀ LƯỢT DỊCH CUỐI CÙNG               ║
    ╚══════════════════════════════════════════════════════════════════╝
    CẤM tự ý mở rộng tình tiết. CẤM đẻ thêm hội thoại.
    Hãy tập trung 100% vào việc chuyển ngữ sát nghĩa, thoát ý Convert sang tiếng Việt thuần túy, đặt tính chính xác lên tối cao.
    Nếu bản dịch còn sót từ convert thô hoặc ngữ pháp cứng nhắc, hệ thống sẽ bị lỗi nghiêm trọng!
    """

        if self.expansion_engine and not is_enforcement_pass:
            raw_length = len(chapter.content)
            target = self.expansion_engine.calculate_expansion_target(chapter.index, raw_length)
            rate = self.expansion_engine.min_rate
            target_chars = int(raw_length * rate)
            min_output_chars = int(target_chars * 0.9)

            expansion_prompt = f"""
    \n╔══════════════════════════════════════════════════════════════════╗
    ║  🔥 BẮT BUỘC: MỞ RỘNG NỘI DUNG - KHÔNG ĐƯỢC VIẾT NGẮN HƠN TARGET ║
    ╚══════════════════════════════════════════════════════════════════╝
    📊 THỐNG KÊ BẮT BUỘC:
       • Input gốc: ~{raw_length:,} ký tự
       • Target output: {target_chars:,} ký tự (x{rate:.1f})
       • TỐI THIỂU: {min_output_chars:,} ký tự (KHÔNG ĐƯỢC ÍT HƠN!)

    📝 KỸ THUẬT MỞ RỘNG BẮT BUỘC ÁP DỤNG:
    1. Đào sâu nội tâm nhân vật sâu sắc, suy nghĩ nội tâm, flashback hợp lý.
    2. Thêm mô tả môi trường chi tiết (âm thanh, mùi vị, ánh sáng).
    3. Mở rộng hội thoại tự nhiên với action beats, mô tả giọng nói, cảm xúc.
    4. WORLD-BUILDING: Xây dựng bối cảnh thế giới bám sát sườn truyện.

    ⚠️ TUYỆT ĐỐI CẤM: Không viết lan man, lặp từ, lê thê vô nghĩa. Phải bám sát sườn cốt truyện gốc!
    """
            system_prompt += expansion_prompt

        if revision_feedback:
            system_prompt += f"""
    \n[⚠️ REVISION REQUIRED - CHỈ DẪN SỬA LỖI TỪ CRITIC]
    {revision_feedback}
    QUAN TRỌNG: Đây là bản viết lại. Hãy sửa triệt để các lỗi được chỉ ra ở trên.
    """

        model = self.config.model_writer
        temp = 0.0 if is_enforcement_pass else 0.3

        user_content = f"Tiêu đề gốc (Tiếng Trung/Convert): {chapter.title_raw}\n\nNội dung chương:\n{chapter.content}"
        try:
            translated = await self.translator.call_api(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=temp
            )
            return translated, ""
        except Exception as e:
            return "", str(e)

    def _review_translation(
        self,
        chapter: ChapterData,
        translated_text: str,
        architecture_context: str,
        attempt: int = 1
    ) -> ReviewResult:
        """[CRITIC] Review và chấm điểm translation"""
        self.qa.previous_summary = architecture_context
        self.qa.system_instruction = """
    Bạn là một kiểm duyệt viên chất lượng dịch thuật khắt khe.
    Hãy chấm điểm bản dịch trên thang điểm 0-100.
    Đặc biệt lưu ý:
    1. Trừ điểm cực nặng nếu phát hiện mâu thuẫn cốt truyện, nhân vật chết đột ngột sống lại, hoặc quên tình tiết quan trọng.
    2. Trừ điểm nặng nếu bản dịch viết lan man lê thê, lặp từ vô nghĩa hoặc mang mùi convert thô cứng nhắc.
    """
        return self.qa.review(
            content=translated_text,
            chapter_num=chapter.index,  # Sử dụng chỉ mục vật lý để QA
            attempt=attempt
        )

    def _log_to_quarantine(self, chapter_index: int, score: int, feedback: str):
        """Ghi vết lỗi cách ly xuống quarantine_chapters.log"""
        os.makedirs(os.path.dirname(self.quarantine_log_file), exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Vị trí vật lý: {chapter_index:04d} | Điểm tốt nhất: {score}/100 | LỖI: {feedback}\n"
        try:
            with open(self.quarantine_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"⚠️ Lỗi ghi file quarantine log: {e}")

    async def _architect_supreme_review_async(
        self,
        chapter: ChapterData,
        translated_text: str,
        architecture_context: str,
        critic_feedback: str
    ) -> Tuple[int, str]:
        """
        [ARCHITECT SUPREME REVIEW] Phúc khảo chất lượng dịch thuật của chương
        Sử dụng Architect Model để đánh giá lại nhằm tránh Critic Agent máy móc báo lỗi QA giả.
        """
        system_prompt = """
Bạn là Tổng Biên Tập kiêm Trọng Tài Chất Lượng Dịch Thuật cấp cao.
Nhiệm vụ của bạn là đánh giá bản dịch của một chương tiểu thuyết dựa trên văn bản gốc, kịch bản bối cảnh cốt truyện (framework), và phản hồi/khiếu nại của kiểm duyệt viên cấp dưới (Critic QA).

Hãy đánh giá xem phản hồi của kiểm duyệt viên Critic QA là ĐÚNG hay SAI (Lỗi giả - False Positive).
Ví dụ về lỗi giả: Critic QA phàn nàn bản dịch bị cắt cụt ở cuối chương do chương kết thúc bằng một câu hệ thống máy móc, trong khi văn bản gốc thực tế cũng kết thúc y hệt như vậy.

Hãy đọc kỹ 4 thông tin sau:
1. Kịch bản bối cảnh (Framework):
{architecture_context}

2. Lời phê bình của Critic QA:
{critic_feedback}

Hãy trả về kết quả dưới dạng JSON duy nhất với cấu trúc sau (không thêm văn bản ngoài JSON):
{{
  "is_critic_wrong": true,
  "reasoning": "Giải thích chi tiết tại sao Critic đúng hoặc sai, so sánh phần kết và nội dung của bản dịch so với bản gốc",
  "score": 90
}}
"""
        
        user_content = f"""
--- VĂN BẢN GỐC (RAW) ---
{chapter.content}

--- BẢN DỊCH (TRANSLATION) ---
{translated_text}
"""
        try:
            # Format prompts
            formatted_system = system_prompt.format(
                architecture_context=architecture_context,
                critic_feedback=critic_feedback
            )
            
            response = await self.translator.call_api(
                model=self.config.model_architect,
                system_prompt=formatted_system,
                user_content=user_content,
                temperature=0.0
            )
            
            import json
            # Tìm kiếm JSON block
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                score = int(data.get("score", 50))
                reasoning = data.get("reasoning", "Không có lý do chi tiết.")
                return score, reasoning
            else:
                print(f"   ⚠️ Lỗi parse JSON từ Supreme Review, phản hồi thô: {response}")
                return 50, "Lỗi định dạng phản hồi từ mô hình."
        except Exception as e:
            print(f"   ⚠️ Lỗi trong quá trình Supreme Review: {e}")
            return 50, f"Exception: {e}"

    async def process_chapter_with_qa_async(self, chapter: ChapterData) -> TranslationResult:
        """
        Main workflow bất đồng bộ: Architect → Writer → Critic → Fail-safe Loop
        """
        result = TranslationResult(
            chapter_index=chapter.index,
            status="PENDING"
        )

        # Lưu tên file theo chỉ mục vật lý tuyệt đối trong thư mục con translated/
        translated_dir = os.path.join(self.config.temp_folder, "translated")
        os.makedirs(translated_dir, exist_ok=True)
        temp_file = os.path.join(translated_dir, f"chap_{chapter.index:04d}.txt")
        display = f"Chương {chapter.index:04d} (Tiêu đề gốc: {chapter.title_raw})"

        # Skip if already translated
        if os.path.exists(temp_file):
            try:
                with open(temp_file, 'r', encoding='utf-8') as f:
                    existing = f.read()
                    if len(existing) > 50 and not "[QA_STATUS: FAILED" in existing:
                        result.status = "SKIPPED"
                        result.translated_text = existing
                        print(f"⏭️  [{display}] Đã dịch xong trước đó (Bỏ qua).")
                        return result
            except Exception:
                pass

        # === [ARCHITECT] Get context ===
        print(f"⏳ [{display}] Đang bắt đầu xử lý (Architect & Writer)...")
        # Đảm bảo framework cho batch chứa chương này đã sẵn sàng (on-demand)
        await self.translator.ensure_batch_framework_async(self.translator.director.get_batch_id(chapter.index))
        architecture_context = self._get_architecture_context(chapter)

        # === [WRITER] → [CRITIC] Loop ===
        attempts_history = []
        best_translation = ""
        best_score = -1
        best_feedback = ""
        revision_feedback = ""

        is_lite_critic = getattr(self.config, 'lite_critic', True)
        max_attempts = 1 if is_lite_critic else self.MAX_REVISION_ATTEMPTS

        for attempt in range(1, max_attempts + 1):
            is_enforcement_pass = (attempt == max_attempts) and not is_lite_critic

            if is_enforcement_pass:
                print(f"   ⚠️  [KÍCH HOẠT ĐIỀU PHỐI CƯỠNG CHẾ: TEMPERATURE = 0.0] {display}")

            # === [WRITER] Translate ===
            translated, error = await self._translate_with_context(
                chapter, architecture_context, revision_feedback, is_enforcement_pass
            )

            if error:
                print(f"   ❌ [{display} - WRITER Lượt {attempt}] Lỗi: {error}")
                if attempt < max_attempts:
                    await asyncio.sleep(2)
                    continue
                else:
                    result.status = "FAILED"
                    result.error_message = error
                    return result

            # === [CRITIC] Review ===
            review = self._review_translation(chapter, translated, architecture_context, attempt)
            attempts_history.append(review)
            score = review.score.total_score

            print(f"   ✍️  [{display} - Writer Lượt {attempt}]: Score {score} " + ("(PASS)" if score >= self.PASS_THRESHOLD else "(FAIL)"))

            if score > best_score:
                best_score = score
                best_translation = translated
                best_feedback = review.feedback

            # Pass?
            if score >= self.PASS_THRESHOLD:
                break

            revision_feedback = review.feedback

        # === Xử lý kết quả sau vòng lặp ===
        if best_score < self.PASS_THRESHOLD and not is_lite_critic:
            print(f"   🏛️  [SUPREME REVIEW] Bản dịch chưa đạt điểm chuẩn QA ({best_score}/{self.PASS_THRESHOLD}).")
            print(f"       Kích hoạt Architect ({self.config.model_architect}) phúc khảo toàn diện để tránh lỗi QA giả (False Positives)...")
            try:
                supreme_score, supreme_reason = await self._architect_supreme_review_async(
                    chapter, best_translation, architecture_context, best_feedback
                )
                print(f"   🏛️  [SUPREME REVIEW KẾT QUẢ]: Điểm phúc khảo: {supreme_score}/100. Lý do: {supreme_reason}")
                if supreme_score >= self.PASS_THRESHOLD:
                    print(f"   ✅ [SUPREME REVIEW] Quyết định của Critic được hủy bỏ! Bản dịch được CHẤP THUẬN với điểm phúc khảo: {supreme_score}")
                    best_score = supreme_score
            except Exception as e:
                print(f"   ⚠️ Lỗi trong quá trình Supreme Review: {e}")

        result.final_score = best_score
        result.review_attempts = attempts_history
        result.total_attempts = len(attempts_history)

        # Cương chế chuẩn hóa định dạng tiêu đề chương ở dòng đầu tiên của bản dịch
        lines = best_translation.split('\n')
        title_idx = -1
        for i, line in enumerate(lines):
            if line.strip():
                title_idx = i
                break
        if title_idx != -1:
            title_line = lines[title_idx]
            # Loại bỏ ### ở đầu/cuối và các từ khóa prefix thô
            core_title = re.sub(r'^###\s*|\s*###$', '', title_line).strip()
            core_title = re.sub(r'^(Chương\s*\d+|Ngoại\s*truyện|Phiên\s*ngoại|Spinoff|Vĩ\s*thanh)\s*:\s*', '', core_title, flags=re.IGNORECASE).strip()
            
            if chapter.is_extra:
                new_title = f"### Ngoại truyện: {core_title} ###"
            else:
                new_title = f"### Chương {chapter.num}: {core_title} ###"
            lines[title_idx] = new_title
            best_translation = '\n'.join(lines)

        if best_score >= self.PASS_THRESHOLD or is_lite_critic:
            result.status = "SUCCESS"
            result.translated_text = best_translation
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(best_translation)
            print(f"✅ [{display}] Hoàn thành dịch thuật thành công! Điểm QA: {best_score}")
        else:
            result.status = "SUCCESS"
            result.translated_text = f"# [QA_STATUS: FAILED | BEST_SCORE: {best_score}]\n\n{best_translation}"

            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(result.translated_text)

            self._log_to_quarantine(chapter.index, best_score, best_feedback)
            print(f"⚠️  [{display}] CẢNH BÁO: Không đạt chuẩn QA sau {max_attempts} lượt sửa. Fallback lấy bản dịch {best_score} điểm. Đã cách ly/ghi vết vào quarantine_chapters.log")

        # Cập nhật bộ nhớ, bối cảnh và từ điển động (nếu thành công)
        if best_score >= 60:
            try:
                self.memory.save_chapter_summary(chapter.index, best_translation)
            except Exception as e:
                print(f"   ⚠️ Lỗi cập nhật bộ nhớ/thế giới: {e}")

        return result


class WorkflowV3Runner:
    """Main runner điều phối workflow Tam Quyền Phân Lập bất đồng bộ tuyến tính"""

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.glossary = GlossaryManager(config)

        self.memory = MemoryManager(config)
        self.translator = ChapterTranslator(config, self.glossary, self.memory)
        self.agentic_translator = AgenticTranslator(config, self.glossary, self.memory, self.translator)

    async def run_async(self, tasks: List[ChapterData], on_progress=None) -> Tuple[int, int]:
        """Chạy dịch thuật bất đồng bộ sử dụng Semaphore để kiểm soát số luồng"""
        total = len(tasks)
        if not total:
            print("❌ Không có chương nào để dịch!")
            return 0, 0

        # Lập kế hoạch frameworks cho 10 chương trước
        print("🎬 [DIRECTOR] Chuẩn bị batch frameworks...")
        await self.translator.prepare_batch_framework_async(tasks)
        print("-" * 70)

        print(f"🚀 Bắt đầu dịch {total} chương với {self.config.max_threads} luồng song song...")
        print("-" * 70)

        semaphore = asyncio.Semaphore(self.config.max_threads)
        success_count = 0
        start_time = time.time()

        async def worker(task: ChapterData):
            async with semaphore:
                try:
                    res = await self.agentic_translator.process_chapter_with_qa_async(task)
                    if on_progress:
                        try:
                            on_progress(task, res)
                        except Exception:
                            pass
                    return task, res
                except Exception as e:
                    print(f"❌ Lỗi xử lý Chương {task.index}: {e}")
                    if on_progress:
                        try:
                            on_progress(task, None)
                        except Exception:
                            pass
                    return task, None

        futures = [worker(task) for task in tasks]
        results = await asyncio.gather(*futures)

        for task, res in results:
            if res and res.status in ["SUCCESS", "SKIPPED"]:
                success_count += 1

        elapsed = time.time() - start_time
        print("-" * 70)
        print(f"🎉 Hoàn thành dịch thuật: {success_count}/{total} chương thành công trong {elapsed:.1f} giây.")
        return success_count, total

    def run(self, tasks: List[ChapterData]) -> Tuple[int, int]:
        """Wrapper đồng bộ để chạy run_async"""
        return asyncio.run(self.run_async(tasks))
