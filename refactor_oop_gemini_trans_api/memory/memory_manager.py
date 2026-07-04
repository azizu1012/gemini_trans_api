"""
Memory Manager Module - Quản lý bộ nhớ AI (Block và Cumulative)
"""
import os
import re
import glob
import threading
from typing import Optional, List
from dataclasses import dataclass

try:
    from ..config.config import TranslatorConfig
except ImportError:
    from ..config.config import TranslatorConfig


@dataclass
class MemoryBlock:
    """Một block memory (10 chương)"""
    start_chapter: int
    end_chapter: int
    content: str
    file_path: str


class MemoryManager:
    """
    Quản lý Memory với:
    - Block memory (mỗi 10 chương)
    - Cumulative memory (mỗi 50/100 chương)
    - Thread-safe operations
    """
    
    def __init__(self, config: TranslatorConfig):
        self.config = config
        self._lock = threading.Lock()
        self._generation_lock = threading.Lock()
        self._background_threads: List[threading.Thread] = []
        
        # Ensure folder exists
        os.makedirs(self.config.memory_folder, exist_ok=True)
    
    def get_latest_memory(self, current_chapter: int) -> str:
        """Lấy memory context cho chapter hiện tại"""
        context_parts = []
        
        # 1. Lấy Cumulative gần nhất
        cumulative_files = sorted(glob.glob(
            os.path.join(self.config.memory_folder, "cumulative_*.txt")
        ))
        
        if cumulative_files:
            valid_files = [
                f for f in cumulative_files 
                if int(re.findall(r'\d+', os.path.basename(f))[0]) < current_chapter
            ]
            if valid_files:
                try:
                    latest = valid_files[-1]
                    milestone = re.findall(r'\d+', os.path.basename(latest))[0]
                    with open(latest, 'r', encoding='utf-8') as f:
                        content = f.read()
                    context_parts.append(
                        f"[TÓM TẮT ĐẠI CƯƠNG (Chap 1 -> {milestone})]:\n{content}"
                    )
                except Exception:
                    pass
        
        # 2. Lấy Block Memory gần nhất
        prev_block_end = (current_chapter - 1) // 10 * 10
        prev_block_start = prev_block_end - 9
        
        if prev_block_end > 0 and prev_block_start > 0:
            block_file = os.path.join(
                self.config.memory_folder,
                f"memory_block_{prev_block_start:04d}_{prev_block_end:04d}.txt"
            )
            if os.path.exists(block_file):
                try:
                    with open(block_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    context_parts.append(
                        f"[DIỄN BIẾN MỚI NHẤT ({prev_block_start}-{prev_block_end})]:\n{content}"
                    )
                except Exception:
                    pass
        
        return '\n\n'.join(context_parts) if context_parts else "(Chưa có dữ liệu ký ức)"
    
    def check_and_trigger_memory(self, completed_chapter: int, api_manager, model_name: str):
        """
        Kiểm tra và tạo memory block nếu đủ 10 chương.
        Được gọi sau mỗi chương dịch xong.
        """
        if not self.config.enable_memory:
            return
        
        # Tính block
        block_idx = (completed_chapter - 1) // 10
        start_chap = block_idx * 10 + 1
        end_chap = start_chap + 9
        
        # Kiểm tra file memory đã tồn tại chưa
        mem_file = os.path.join(
            self.config.memory_folder,
            f"memory_block_{start_chap:04d}_{end_chap:04d}.txt"
        )
        
        if os.path.exists(mem_file):
            return
        
        # Kiểm tra đủ 10 file chưa
        all_exist = True
        for i in range(start_chap, end_chap + 1):
            chap_file = os.path.join(self.config.temp_folder, "translated", f"chap_{i:04d}.txt")
            if not os.path.exists(chap_file):
                all_exist = False
                break
        
        if all_exist:
            # Tạo memory trong background thread
            thread = threading.Thread(
                target=self._generate_block_memory,
                args=(start_chap, end_chap, api_manager, model_name),
                daemon=True
            )
            thread.start()
            self._background_threads.append(thread)
    
    def _generate_block_memory(
        self, 
        start_chap: int, 
        end_chap: int,
        api_manager,
        model_name: str
    ):
        """Tạo memory block cho 10 chương"""
        mem_file = os.path.join(
            self.config.memory_folder,
            f"memory_block_{start_chap:04d}_{end_chap:04d}.txt"
        )
        
        with self._generation_lock:
            if os.path.exists(mem_file):
                return
            
            print(f"   🧠 [Memory] Tổng hợp Chap {start_chap}-{end_chap}...")
            
            # Đọc nội dung các chương
            full_text = ""
            for i in range(start_chap, end_chap + 1):
                path = os.path.join(self.config.temp_folder, "translated", f"chap_{i:04d}.txt")
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if len(content) > 20:
                                full_text += f"\n--- Chap {i} ---\n{content[:2500]}"
                    except Exception:
                        pass
            
            if not full_text:
                print(f"   ⚠️ [Memory] Không có nội dung cho block {start_chap}-{end_chap}")
                return
            
            prompt = f"""
Bạn là Thư Ký Ghi Chép. Hãy đọc tóm tắt nội dung các chương ({start_chap}-{end_chap}) và thực hiện:
1. Tóm tắt ngắn gọn các sự kiện chính.
2. Ghi chú về các Nhân vật mới xuất hiện.
3. Ghi chú về Địa danh mới.
4. Lưu ý quan trọng cho AI dịch các chương tiếp theo.

Nội dung truyện:
{full_text}
"""
            config = {
                "system_instruction": f"Tóm tắt cốt truyện {start_chap}-{end_chap}:",
                "safety_settings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
            }
            
            if hasattr(api_manager, 'call_api_sync'):
                try:
                    text = api_manager.call_api_sync(
                        model=model_name or self.config.summary_model,
                        system_prompt="Tổng hợp cốt truyện chương tiểu thuyết ngắn gọn.",
                        user_content=prompt,
                        temperature=0.2
                    )
                    if text:
                        with open(mem_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                        print(f"   💾 [Memory] Đã lưu: memory_block_{start_chap:04d}_{end_chap:04d}.txt")
                        
                        # Trigger cumulative nếu đạt mốc
                        if end_chap % 50 == 0:
                            self._trigger_cumulative(end_chap, api_manager, model_name)
                        return
                except Exception as e:
                    print(f"   ❌ [Memory] Thất bại block {start_chap}-{end_chap}: {e}")
                    return
            else:
                for attempt in range(self.config.retry_limit):
                    try:
                        key_obj, model_used = api_manager.get_next_key(for_memory=True)
                        if not key_obj:
                            print(f"   ❌ [Memory] Hết key cho block {start_chap}-{end_chap}")
                            return
                        
                        response = api_manager.make_throttled_call(
                            key_obj,
                            model_used or self.config.summary_model,
                            [prompt],
                            config
                        )
                        
                        if response.text:
                            with open(mem_file, 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            print(f"   💾 [Memory] Đã lưu: memory_block_{start_chap:04d}_{end_chap:04d}.txt")
                            
                            # Trigger cumulative nếu đạt mốc
                            if end_chap % 50 == 0:
                                self._trigger_cumulative(end_chap, api_manager, model_name)
                            return
                    
                    except Exception as e:
                        if attempt < self.config.retry_limit - 1:
                            import time
                            time.sleep(5)
                        else:
                            print(f"   ❌ [Memory] Thất bại block {start_chap}-{end_chap}: {e}")
    
    def _trigger_cumulative(self, milestone: int, api_manager, model_name: str):
        """Tạo cumulative memory (tóm tắt đại cương)"""
        target_file = os.path.join(
            self.config.memory_folder,
            f"cumulative_{milestone:04d}.txt"
        )
        
        if os.path.exists(target_file):
            return
        
        thread = threading.Thread(
            target=self._generate_cumulative,
            args=(milestone, api_manager, model_name),
            daemon=True
        )
        thread.start()
        self._background_threads.append(thread)
    
    def _generate_cumulative(self, milestone: int, api_manager, model_name: str):
        """Tổng hợp cumulative memory"""
        target_file = os.path.join(
            self.config.memory_folder,
            f"cumulative_{milestone:04d}.txt"
        )
        
        with self._generation_lock:
            if os.path.exists(target_file):
                return
            
            print(f"   ⭐ [Memory] Tổng hợp đại cương mốc {milestone}...")
            
            # Tìm cumulative trước
            existing = sorted(glob.glob(
                os.path.join(self.config.memory_folder, "cumulative_*.txt")
            ))
            
            previous_summary = ""
            last_milestone = 0
            
            if existing:
                valid = [f for f in existing 
                        if int(re.findall(r'\d+', os.path.basename(f))[0]) < milestone]
                if valid:
                    last_file = valid[-1]
                    last_milestone = int(re.findall(r'\d+', os.path.basename(last_file))[0])
                    with open(last_file, 'r', encoding='utf-8') as f:
                        previous_summary = f.read()
            
            # Gom memory blocks mới
            new_events = ""
            first_block = (last_milestone // 10) * 10 + 1
            if first_block <= last_milestone:
                first_block += 10
            
            for i in range(first_block, milestone + 1, 10):
                block_end = i + 9
                block_path = os.path.join(
                    self.config.memory_folder,
                    f"memory_block_{i:04d}_{block_end:04d}.txt"
                )
                if os.path.exists(block_path):
                    with open(block_path, 'r', encoding='utf-8') as f:
                        new_events += f"\n--- Diễn biến {i}-{block_end} ---\n{f.read()}\n"
            
            if not previous_summary and not new_events:
                return
            
            prompt = f"""
Nhiệm vụ: Cập nhật "Đại Cương Cốt Truyện" đến chương {milestone}.
DỮ LIỆU:
1. [CỐT TRUYỆN NỀN (Đến chương {last_milestone})]:
{previous_summary if previous_summary else "(Mở đầu)"}
2. [DIỄN BIẾN MỚI (Chương {last_milestone + 1} - {milestone})]:
{new_events}
YÊU CẦU:
Viết lại bản tóm tắt đại cương mới, bao trùm từ đầu đến chương {milestone}.
"""
            
            config = {
                "system_instruction": "Tổng hợp đại cương cốt truyện:",
                "safety_settings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
            }
            
            try:
                if hasattr(api_manager, 'call_api_sync'):
                    text = api_manager.call_api_sync(
                        model=model_name or self.config.summary_model,
                        system_prompt="Tổng hợp đại cương cốt truyện:",
                        user_content=prompt,
                        temperature=0.2
                    )
                    if text:
                        with open(target_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                        print(f"   🏆 [Memory] Đã lưu cumulative_{milestone:04d}.txt")
                else:
                    key_obj, model_used = api_manager.get_next_key(for_memory=True)
                    if not key_obj:
                        return
                    
                    response = api_manager.make_throttled_call(
                        key_obj,
                        model_used or self.config.summary_model,
                        [prompt],
                        config
                    )
                    
                    if response.text:
                        with open(target_file, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f"   🏆 [Memory] Đã lưu cumulative_{milestone:04d}.txt")
            
            except Exception as e:
                print(f"   ❌ [Memory] Lỗi cumulative {milestone}: {e}")
    
    def recover_missing_memories(self, max_chapter: int, api_manager, model_name: str):
        """
        Khôi phục các memory block bị thiếu - chạy BACKGROUND không blocking
        """
        print("\n🕵️ Rà soát memory...")
        
        total_blocks = (max_chapter - 1) // 10
        existing_blocks = 0
        missing_blocks = 0
        to_recover = []
        
        for b in range(total_blocks + 1):
            start = b * 10 + 1
            end = start + 9
            
            mem_path = os.path.join(
                self.config.memory_folder,
                f"memory_block_{start:04d}_{end:04d}.txt"
            )
            
            if os.path.exists(mem_path):
                existing_blocks += 1
                continue
            
            # Kiểm tra đủ 10 file chưa
            all_exist = all(
                os.path.exists(os.path.join(self.config.temp_folder, "translated", f"chap_{i:04d}.txt"))
                for i in range(start, end + 1)
            )
            
            if all_exist:
                to_recover.append((start, end))
            else:
                missing_blocks += 1
        
        # Chạy recovery BACKGROUND - không blocking main thread
        if to_recover:
            print(f"   ⚠️ Phát hiện {len(to_recover)} block thiếu memory")
            print(f"   🔄 Đang tạo background... (dịch tiếp không cần chờ)")
            
            def _background_recover():
                for start, end in to_recover:
                    try:
                        self._generate_block_memory(start, end, api_manager, model_name)
                    except Exception as e:
                        print(f"   ❌ [Memory] Lỗi tạo block {start}-{end}: {e}")
            
            thread = threading.Thread(target=_background_recover, daemon=True)
            thread.start()
            self._background_threads.append(thread)
        elif total_blocks == 0:
            print("   📭 Chưa có memory (dịch từ đầu)")
        else:
            print(f"   📦 Memory: {existing_blocks} blocks có sẵn, {missing_blocks} chờ dịch thêm")
    
    def wait_for_background_tasks(self):
        """Chờ tất cả background tasks hoàn thành"""
        if self._background_threads:
            print("\n⏳ Đang chờ memory tasks hoàn tất...")
            for thread in self._background_threads:
                thread.join()
            print("✅ Memory tasks hoàn tất")
    
    def save_chapter_summary(self, chapter_index: int, translated_text: str):
        """Lưu tóm tắt chương (placeholder/hỗ trợ tương thích)"""
        pass

