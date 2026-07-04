import os
import re
import time
import threading
import glob
import random
from concurrent.futures import ThreadPoolExecutor
from google import genai
from google.genai.errors import APIError
import dotenv

dotenv.load_dotenv()

# --- CẤU HÌNH ---
BASE_DIR = r"C:\Users\Azuree\Documents\Code-make-novel\Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật"
RATE_LIMIT_FILE = os.path.join(BASE_DIR, "rate-limit-api.txt") # File chứa các key bị rate limit
INPUT_FILE_PATH = os.path.join(BASE_DIR, "Truyen_Hoan_Chinh_Fixed.txt")
OUTPUT_FILE_PATH = os.path.join(BASE_DIR, "Truyen_Dich_Hoan_Chinh.txt")
TITLES_FILE_PATH = os.path.join(BASE_DIR, "Danh_sach_ten_chuong.txt")
TEMP_FOLDER = os.path.join(BASE_DIR, "temp_chapters")
MEMORY_FOLDER = os.path.join(BASE_DIR, "memory_store")
MODEL_NAME = os.getenv("MODEL_NAME")
SUMMARY_MODEL_NAME = "gemini-2.5-flash"
MAX_THREADS = 3
RETRY_LIMIT = 6 # Tăng giới hạn thử lại
RETRY_INITIAL_DELAY = 4  # Khởi đầu với 2s delay
RETRY_MAX_DELAY = 30     # Tối đa 30s delay (exponential backoff)

# --- TỪ ĐIỂN CỐ ĐỊNH (GLOSSARY) ---
GLOSSARY = {
    # ... (Giữ nguyên toàn bộ từ điển cố định của bạn) ...
    "Lâm Nhất": "Lâm Nhất (Nam chính - Xưng Ta/Tao)",
    "Anna": "Anna (Nữ chính/phụ)",
    "Chu Vân": "Chu Vân (Em gái Chu Khải)",
    "Chu Khải": "Chu Khải (Anh trai Chu Vân, kẻ cuồng chủ nghĩa kiểm soát cực đoan muốn Chu Vân luôn dưới sự kiểm soát của mình)",
    "Tinh Thành Đạo": "Tinh Thành Đạo",
    "Lục Lâm Hải": "Lục Lâm Hải",
    "Trương Thành": "Trương Thành",
    
    # --- ĐỊA DANH / TỔ CHỨC ---
    "Tư Đức Farrell": "Tư Đức Farrell (Tên Thành phố/Tổ chức - KHÔNG dịch là tên người)",
    "Thành phố Pease": "Thành phố Pease",
    "Pease": "Thành phố Pease",
    "KTV": "Karaoke",
    "Miền Đất Hứa": "Miền Đất Hứa (Địa danh)",
    "Khu Tái Sinh": "Khu Tái Sinh (Địa danh)",
    "Đào Nguyên": "Đào Nguyên (Chốn đào nguyên)",
    "Thành Phố Hy Vọng": "Thành Phố Hy Vọng",
    "Dãy núi phía Tây": "Dãy núi phía Tây",
    
    # --- THUẬT NGỮ ---
    "Dị loại": "Dị loại (Quái vật)",
    "Mạt thế": "Mạt thế",
    "Dị năng": "Dị năng",
    "Sờ lang": "Sờ lang (Tên một loài dị loại, tuyệt đối KHÔNG đổi thành 'mò lang' hay tên khác)",
    "Giác tỉnh": "Thức tỉnh (Dị năng)",
    
    # --- ĐẠI TỪ (Update Style Mạt Thế) ---
    "Ta": "Ta / Tao (Xưng hô mặc định - Cấm dùng Tôi trừ khi giả vờ yếu đuối)",
    "Hắn": "Hắn (ngôi thứ 3 nam)",
    "Nàng/Cô ấy": "Cô ấy (ngôi thứ 3 nữ)",
    "Bọn họ": "Bọn họ (Dùng cho nhóm người hoặc tổ chức)",

    # --- THUẬT NGỮ THÔNG DỤNG (VIỆT HÓA) ---
    "ba ba mụ mụ": "ba mẹ",
    "tiểu tử": "thằng nhóc / gã trai trẻ",
    "cô nương": "cô gái",
}

# --- API KEYS ---
# 1. Định nghĩa các nguồn key
API_KEY_SOURCES = {
    'main': [
        "GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "GEMINI_API_KEY_5", "GEMINI_API_KEY_6", "GEMINI_API_KEY_7", "GEMINI_API_KEY_8", "GEMINI_API_KEY_9"
    ],

    'summary': [
        "GEMINI_API_KEY_Tomtat", "GEMINI_API_KEY_Tomtat_2", "GEMINI_API_KEY_Tomtat_3", 
        "GEMINI_API_KEY_Tomtat_4", "GEMINI_API_KEY_Tomtat_5"
    ]
}

# 2. Tải tất cả các key từ .env, tạo bản đồ key -> name
all_loaded_keys = {}
KEY_VALUE_TO_NAME_MAP = {}
for pool, names in API_KEY_SOURCES.items():
    all_loaded_keys[pool] = []
    for name in names:
        key_value = os.getenv(name)
        if key_value:
            all_loaded_keys[pool].append(key_value)
            KEY_VALUE_TO_NAME_MAP[key_value] = name

# 4. Gán vào các biến chính để sử dụng và khởi tạo pool với thời gian sử dụng
def initialize_key_pool(keys):
    """Chuyển danh sách key chuỗi thành danh sách các đối tượng để theo dõi."""
    return [{'key': k, 'last_used': 0.0} for k in keys]

API_KEYS_POOL = initialize_key_pool(all_loaded_keys.get('main', []))
SUMMARY_API_KEYS_POOL = initialize_key_pool(all_loaded_keys.get('summary', []))

# Thông báo trạng thái
print("--- QUẢN LÝ API KEY ---")
print(f"✅ Key chính hoạt động: {len(API_KEYS_POOL)}/{len(all_loaded_keys.get('main', []))}")
print(f"✅ Key tóm tắt hoạt động: {len(SUMMARY_API_KEYS_POOL)}/{len(all_loaded_keys.get('summary', []))}")
print("-----------------------")


if not API_KEYS_POOL:
    print("❌ LỖI: Không còn API Key chính nào để hoạt động. Kiểm tra file .env và rate-limit-api.txt!")
    exit()

# Khóa để quản lý việc cập nhật pool key trong lúc chạy đa luồng
active_pools_lock = threading.Lock()
memory_generation_lock = threading.Lock() # Khóa riêng cho việc tạo memory
BACKGROUND_THREADS = []
background_threads_lock = threading.Lock()

# 429 HANDLING: Cooldown Window 30 phút (1800s)
COOLDOWN_WINDOW = 1800  # 30 phút (giây)
MAX_REQUESTS_PER_WINDOW = 20  # 20 request/30 phút

# Theo dõi thời gian request của mỗi key
key_request_history = {}  # {key_string: [timestamp1, timestamp2, ...]} (tối đa 20 entry)
key_request_history_lock = threading.Lock()

delayed_keys_pool = {}  # {key_string: release_time} - khi vượt quá giới hạn
delayed_keys_lock = threading.Lock()

# LOGGING: Theo dõi sử dụng key
key_usage_log = {}  # {key_string: {'type': 'main/summary', 'usage_count': int, 'frozen_by_429': bool, 'frozen_time': float, 'in_cooldown': bool}}
key_log_lock = threading.Lock()

# --- CÁC HÀM TIỆN ÍCH API (MỚI) ---
MIN_REQUEST_INTERVAL = 2.8 # Giây - Thời gian chờ tối thiểu giữa các request (giảm từ 1.2)
last_request_time = 0.0
request_lock = threading.Lock()

def check_key_rate_limit(key_string):
    """
    Kiểm tra xem key có vượt quá giới hạn 20 request/30 phút không.
    Return: (is_available, time_to_wait_seconds)
    - is_available=True: key có thể dùng
    - is_available=False: key cần chờ (cooldown), time_to_wait_seconds là thời gian cần chờ
    """
    with key_request_history_lock:
        now = time.time()
        
        # Lấy lịch sử request của key này
        history = key_request_history.get(key_string, [])
        
        # Xóa các request cũ hơn 30 phút
        history = [ts for ts in history if now - ts < COOLDOWN_WINDOW]
        key_request_history[key_string] = history
        
        # Nếu chưa đạt 20 request trong 30 phút -> có thể dùng
        if len(history) < MAX_REQUESTS_PER_WINDOW:
            return True, 0
        
        # Nếu đã 20 request trong 30 phút -> cần chờ
        # Thời gian chờ = (request #1 + 30 phút) - now
        oldest_request = history[0]
        wait_time = (oldest_request + COOLDOWN_WINDOW) - now
        return False, max(0, wait_time)

def restore_delayed_keys():
    """Khôi phục các key từ delayed_keys_pool về main pool nếu đã hết thời gian delay."""
    with delayed_keys_lock:
        now = time.time()
        ready_keys = [k for k, release_time in delayed_keys_pool.items() if now >= release_time]
        
        if ready_keys:
            with active_pools_lock:
                for key_string in ready_keys:
                    # Tìm key_obj trong API_KEYS_POOL theo giá trị key
                    key_obj = next((k for k in API_KEYS_POOL if k['key'] == key_string), None)
                    if not key_obj:
                        # Khôi phục lại key_obj từ dictionary
                        key_obj = {'key': key_string, 'last_used': 0.0}
                        API_KEYS_POOL.append(key_obj)
                    del delayed_keys_pool[key_string]
                    with key_log_lock:
                        if key_string in key_usage_log:
                            key_usage_log[key_string]['frozen_by_429'] = False
                            key_usage_log[key_string]['in_cooldown'] = False

def calculate_exponential_backoff(attempt):
    """Tính delay exponential backoff cho retry (2s, 4s, 8s, 16s, 30s)."""
    delay = min(RETRY_INITIAL_DELAY * (2 ** attempt), RETRY_MAX_DELAY)
    return delay + random.uniform(0, 1)  # Thêm jitter

def get_next_api_key(key_type='main'):
    """
    Lấy một API key ngẫu nhiên từ pool, đảm bảo key không vượt quá giới hạn cooldown 30 phút.
    Trả về một đối tượng key và tên pool của nó.
    Nếu tất cả key đều trong cooldown, sẽ chờ key soonest-to-be-available.
    """
    # Trước tiên, khôi phục delayed keys nếu đã sẵn sàng
    restore_delayed_keys()
    
    with active_pools_lock:
        target_pool = None
        pool_name = key_type

        # Xác định pool mục tiêu
        if key_type == 'summary' and SUMMARY_API_KEYS_POOL:
            target_pool = SUMMARY_API_KEYS_POOL
            pool_name = 'summary'
        else: # Mặc định hoặc 'main'
            target_pool = API_KEYS_POOL
            pool_name = 'main'

        # Fallback về pool chính nếu pool mục tiêu rỗng
        if not target_pool:
            if API_KEYS_POOL:
                target_pool = API_KEYS_POOL
                pool_name = 'main (fallback)'
            else:
                return None, None # Hết sạch key

        while True:  # Vòng lặp để chộ key có sẵn
            now = time.time()
            available_keys = []
            
            # Tìm các key không trong cooldown 30 phút
            for key_obj in target_pool:
                is_avail, wait_time = check_key_rate_limit(key_obj['key'])
                if is_avail:
                    available_keys.append((key_obj, wait_time))
            
            if available_keys:
                # Chọn ngẫu nhiên từ các key có sẵn
                chosen_key_obj, _ = random.choice(available_keys)
                
                # Cập nhật thời điểm sử dụng và ghi vào lịch sử
                with key_request_history_lock:
                    key_str = chosen_key_obj['key']
                    if key_str not in key_request_history:
                        key_request_history[key_str] = []
                    key_request_history[key_str].append(now)
                
                # Log tracking
                with key_log_lock:
                    if key_str not in key_usage_log:
                        key_usage_log[key_str] = {
                            'type': pool_name, 
                            'usage_count': 0, 
                            'frozen_by_429': False, 
                            'frozen_time': 0,
                            'in_cooldown': False
                        }
                    key_usage_log[key_str]['usage_count'] += 1
                
                return chosen_key_obj, pool_name
            
            # Không có key sẵn sàng -> tìm key soonest-to-be-available và chờ
            min_wait = float('inf')
            for key_obj in target_pool:
                is_avail, wait_time = check_key_rate_limit(key_obj['key'])
                if not is_avail and wait_time < min_wait:
                    min_wait = wait_time
            
            if min_wait < float('inf'):
                # Chờ key soonest để sẵn sàng
                wait_duration = min(min_wait + 1, 5)  # Chờ tối đa 5s
                print(f"   ⏳ [COOLDOWN] Tất cả key đang trong cooldown. Chờ {wait_duration:.1f}s...")
                
                # Update log
                with key_log_lock:
                    for key_obj in target_pool:
                        is_avail, _ = check_key_rate_limit(key_obj['key'])
                        if not is_avail and key_obj['key'] in key_usage_log:
                            key_usage_log[key_obj['key']]['in_cooldown'] = True
                
                time.sleep(wait_duration)
            else:
                # Không có key nào -> fallback sleep 0.5s
                time.sleep(0.5)
def make_throttled_api_call(client, model_name, contents, config):
    """
    Thực hiện một lệnh gọi API duy nhất với throttling toàn cục.
    """
    global last_request_time
    with request_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_duration = MIN_REQUEST_INTERVAL - time_since_last
            time.sleep(sleep_duration)
        last_request_time = time.time()

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config
    )
    
    return response








def get_ai_config(prompt):
    """Trả về cấu hình cho Gemini API, bao gồm cả việc tắt Safety Filters."""
    return {
        "system_instruction": prompt,
        "safety_settings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    }


def get_system_prompt(memory_context="", is_extra=False):
    # Lấy text glossary tĩnh
    static_glossary_text = "\n".join([f"- {k}: {v}" for k, v in GLOSSARY.items()])

    extra_instruction = "Đây là phiên ngoại (Extra/Side Story). Hãy dịch với giọng văn thoải mái hơn nhưng vẫn giữ chất Mạt thế." if is_extra else ""

    prompt = f"""
[VAI TRÒ]
Bạn là một dịch giả tiểu thuyết chuyên nghiệp, chuyên dòng Mạt thế/Khoa huyễn u tối (Lovecraftian/Post-Apocalyptic).
Nhiệm vụ: Dịch văn bản từ tiếng Trung (Convert/Thô) sang tiếng Việt.

PHẦN 1: BỘ NHỚ (MEMORY) - TÓM TẮT TRƯỚC ĐÓ
{memory_context}

PHẦN 2: TỪ ĐIỂN BẮT BUỘC (GLOSSARY)
{static_glossary_text}

PHẦN 2.5: HỌC THUẬT NGỮ MỚI (DYNAMIC TERMINOLOGY)
- Trong quá trình dịch, nếu gặp tên riêng, thuật ngữ, địa danh mới (ví dụ: "Sờ lang") không có trong Từ điển, **TUYỆT ĐỐI GIỮ NGUYÊN**, không tự ý dịch hay thay đổi.
- Coi các thuật ngữ mới này là một phần của thế giới truyện và sử dụng nhất quán.

PHẦN 3: QUY TẮC DỊCH (NGHIÊM NGẶT)
1. **XƯNG HÔ (QUAN TRỌNG NHẤT):**
   - Bối cảnh Mạt thế tàn khốc, không có chỗ cho sự khách sáo.
   - Ngôi thứ nhất: **Ta / Tao** (Tuyệt đối **KHÔNG dùng 'Tôi'** trừ khi nhân vật đang diễn kịch, nói chuyện với cấp trên hoặc tình huống cực kỳ trang trọng).
   - Ngôi thứ hai: **Ngươi / Mày / Cậu / Cô**.
   - Kẻ thù/Người lạ: Ta - Ngươi.
   - Bạn bè thân thiết/Đồng đội: Tao - Mày hoặc Tôi - Cậu (tùy độ thân).

2. **Xử lý nội dung:**
   - **Tư Đức Farrell** = Tên địa danh/tổ chức (Ví dụ: "Phe Tư Đức Farrell", "Tại Tư Đức Farrell").
   - Tuyệt đối không để lại chữ Hán.
   - **Xử lý thành ngữ/tiếng lóng:** Nếu gặp câu như `"Trương Thành là ai? Ta có thể không biết cái gì Trương Thành Lý Thành Vương Nhị tê dại thành."`, phải hiểu ý nghĩa là "Tôi không biết Trương Thành là ai cả". Dịch lại thành câu tự nhiên, thể hiện sự phủ nhận, ví dụ: `"Trương Thành là thằng nào? Tao không biết thằng Trương Thành, Lý Thành hay Vương Thành chó má nào hết."`
   - **TUÂN THỦ TỪ ĐIỂN:** Các từ trong mục "TỪ ĐIỂN BẮT BUỘC" phải được giữ nguyên 100%. Ví dụ: "Sờ lang" phải luôn là "Sờ lang", không được tự ý sửa thành "mò lang". Đây là lỗi nghiêm trọng.
   - Văn phong: Ngắn gọn, lạnh lùng, dứt khoát.

3. **Tiêu đề & Định dạng (QUAN TRỌNG):**
   - **TỰ ĐỘNG TẠO TÊN CHƯƠNG MỚI:** Dựa vào nội dung chương đã dịch, hãy sáng tạo một tên chương mới súc tích, hấp dẫn và phù hợp với không khí truyện (Lạnh lùng, Mạt thế).
   - **TRẢ VỀ KẾT QUẢ:** Bắt đầu câu trả lời của bạn **TRỰC TIẾP** bằng dòng tiêu đề đã được tối ưu.
   - **ĐỊNH DẠNG TIÊU ĐỀ:** `### Chương X: [Tên chương mới] ###` hoặc `### Ngoại truyện: [Tên ngoại truyện mới] ###`.
   - **TUYỆT ĐỐI KHÔNG** thêm bất kỳ lời dẫn hay ghi chú nào trước dòng tiêu đề.

[BỐI CẢNH BỔ SUNG]
{extra_instruction}
"""
    return prompt.strip()



def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}p {s}s" if h > 0 else f"{m}p {s}s"

def normalize_string(s):
    s = re.sub(r'[^\w\s]', '', s).lower()
    return re.sub(r'\s+', ' ', s).strip()

def load_titles_and_extras(file_path):
    main_chapters = []
    extra_chapters = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        extra_counter = 1
        for line in lines:
            line = line.strip()
            if not line: continue
            match = re.search(r'Chương\s*(\d+)', line, re.IGNORECASE)
            if match:
                chap_num = int(match.group(1))
                main_chapters.append({
                    "num": chap_num,
                    "title_raw": line,
                    "clean_title": f"### {line} ###"
                })
            else:
                extra_chapters.append({
                    "extra_index": extra_counter,
                    "title_raw": line,
                    "clean_title": f"### {line} ###"
                })
                extra_counter += 1
    except FileNotFoundError:
        print(f"❌ Không tìm thấy file danh sách: {file_path}")
        return [], []
    return main_chapters, extra_chapters

def load_raw_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError: return []
    
    # Split by chapter headers: ### ... ###
    # Pattern: ###<space><content><space>### (on single line)
    parts = re.split(r'(### .+? ###)', content, flags=re.MULTILINE)
    
    content_blocks = []
    current_header = None
    current_content = []
    
    for part in parts:
        part_stripped = part.strip()
        if not part_stripped: 
            continue
        
        # Check if this is a header (starts with ### and ends with ###)
        if re.match(r'^### .+? ###$', part_stripped):
            # Lưu header + content trước đó nếu có
            if current_header and current_content:
                full_content = "\n".join(current_content)
                if "[LỖI" not in full_content:
                    content_blocks.append({
                        "header": current_header,
                        "content": full_content,
                        "header_norm": normalize_string(current_header)
                    })
            # Bắt đầu header mới
            current_header = part_stripped
            current_content = []
        elif current_header:
            # Gom tất cả content cho header hiện tại
            current_content.append(part_stripped)
    
    # Xử lý header cuối cùng
    if current_header and current_content:
        full_content = "\n".join(current_content)
        if "[LỖI" not in full_content:
            content_blocks.append({
                "header": current_header,
                "content": full_content,
                "header_norm": normalize_string(current_header)
            })
    
    return content_blocks

# --- MEMORY LOGIC (UPDATED: Robust Check) ---

def get_latest_memory(current_chap_num):
    context = ""
    # 1. Lấy Đại Cương (Cumulative) gần nhất
    mem_files_cumulative = sorted(glob.glob(os.path.join(MEMORY_FOLDER, "cumulative_*.txt")))
    if mem_files_cumulative:
        valid_cumulative = [f for f in mem_files_cumulative if int(re.findall(r'\d+', os.path.basename(f))[0]) < current_chap_num]
        if valid_cumulative:
            try:
                latest_valid = valid_cumulative[-1]
                with open(latest_valid, 'r', encoding='utf-8') as f:
                    context += f"\n[TÓM TẮT ĐẠI CƯƠNG (Chap 1 -> {re.findall(r'\d+', os.path.basename(latest_valid))[0]})]:\n{f.read()}\n"
            except: pass

    # 2. Lấy Block Memory 10 chương gần nhất
    prev_block_end = (current_chap_num - 1) // 10 * 10
    prev_block_start = prev_block_end - 9

    if prev_block_end > 0:
        target_file = os.path.join(MEMORY_FOLDER, f"memory_block_{prev_block_start:04d}_{prev_block_end:04d}.txt")
        if os.path.exists(target_file):
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    context += f"\n[DIỄN BIẾN MỚI NHẤT ({prev_block_start}-{prev_block_end})]:\n{f.read()}\n"
            except: pass

    return context if context else "(Chưa có dữ liệu ký ức)"

def consolidate_memory(current_milestone):
    """Tổng hợp memory khi đạt mốc 50 hoặc 100 (Snowball)."""
    target_file = os.path.join(MEMORY_FOLDER, f"cumulative_{current_milestone:04d}.txt")
    if os.path.exists(target_file): return

    print(f"   ⭐ [Memory] Đang tổng hợp sự kiện lớn mốc {current_milestone} (Snowball Mode)...")

    # 1. Tìm Cumulative cũ gần nhất
    existing_cumulatives = sorted(glob.glob(os.path.join(MEMORY_FOLDER, "cumulative_*.txt")))
    previous_summary = ""
    last_milestone = 0

    if existing_cumulatives:
        valid_prev = [f for f in existing_cumulatives if int(re.findall(r'\d+', os.path.basename(f))[0]) < current_milestone]
        if valid_prev:
            last_file = valid_prev[-1]
            last_milestone = int(re.findall(r'\d+', os.path.basename(last_file))[0])
            with open(last_file, 'r', encoding='utf-8') as f:
                previous_summary = f.read()

    # 2. Gom các memory block mới
    new_events_text = ""
    first_block_start = (last_milestone // 10) * 10 + 1
    if first_block_start <= last_milestone: first_block_start += 10

    for i in range(first_block_start, current_milestone + 1, 10):
        block_end = i + 9
        block_start = i
        block_path = os.path.join(MEMORY_FOLDER, f"memory_block_{block_start:04d}_{block_end:04d}.txt")
        if os.path.exists(block_path):
            with open(block_path, 'r', encoding='utf-8') as f:
                new_events_text += f"\n--- Diễn biến {block_start}-{block_end} ---\n{f.read()}\n"

    if not previous_summary and not new_events_text:
        print(f"   ⚠️ [Memory] Không có nội dung để tổng hợp cho mốc {current_milestone}.")
        return

    # 3. Tạo Prompt
    prompt = f"""
Nhiệm vụ: Cập nhật "Đại Cương Cốt Truyện" đến chương {current_milestone}.
DỮ LIỆU:
1. [CỐT TRUYỆN NỀN (Đến chương {last_milestone})]:
{previous_summary if previous_summary else "(Mở đầu)"}
2. [DIỄN BIẾN MỚI (Chương {last_milestone + 1} - {current_milestone})]:
{new_events_text}
YÊU CẦU:
Viết lại một bản tóm tắt đại cương mới, bao trùm từ đầu đến chương {current_milestone}, lồng ghép các diễn biến mới vào.
"""
    config = get_ai_config("Tổng hợp đại cương cốt truyện (Snowball):")

    api_key_obj = None # Khởi tạo để có thể truy cập trong khối except
    for attempt in range(RETRY_LIMIT):
        try:
            api_key_obj, pool_name = get_next_api_key('summary')
            if not api_key_obj:
                print(f"   ❌ [FAILED] Không thể tạo cumulative memory cho mốc {current_milestone} vì đã hết key.")
                return

            api_key = api_key_obj['key']
            key_name = KEY_VALUE_TO_NAME_MAP.get(api_key, "Unknown")
            model_to_use = SUMMARY_MODEL_NAME if pool_name == 'summary' else MODEL_NAME
            
            print(f"      - [CUMULATIVE MEMORY] Attempt {attempt + 1}, using key '{key_name}' from '{pool_name}' pool...")
            client = genai.Client(api_key=api_key)

            resp = make_throttled_api_call(client, model_to_use, [prompt], config)

            if resp.text:
                with open(target_file, 'w', encoding='utf-8') as f:
                    f.write(resp.text)
                print(f"   🏆 [Memory] Đã cập nhật Cumulative Memory: Mốc {current_milestone}")
                return
        except Exception as e:
            error_str = str(e)
            # 429 sẽ được xử lý bởi get_next_api_key -> restore_delayed_keys
            if not ("429" in error_str or "Resource" in error_str):
                print(f"   ⚠️ [Memory Error] Lỗi tạo cumulative memory lần {attempt+1}: {e}")

            if attempt == RETRY_LIMIT - 1:
                print(f"   ❌ [FAILED] Không thể tạo cumulative memory cho mốc {current_milestone}.")
            else:
                time.sleep(5)

def generate_block_memory(start_chap, end_chap):
    """Hàm tạo memory - Được gọi khi ĐÃ ĐỦ file"""
    target_mem_file = os.path.join(MEMORY_FOLDER, f"memory_block_{start_chap:04d}_{end_chap:04d}.txt")
    
    with memory_generation_lock:
        if os.path.exists(target_mem_file):
            return 

        print(f"   🧠 [Memory] Bắt đầu tổng hợp Chap {start_chap}-{end_chap}...")
        full_text = ""
        for i in range(start_chap, end_chap + 1):
            path = os.path.join(TEMP_FOLDER, f"chap_{i:04d}.txt")
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if len(content) > 20:
                            full_text += f"\n--- Chap {i} ---\n" + content[:2500] 
                except: pass
        
        if not full_text:
            print(f"   ⚠️ [Memory] Không có nội dung để tổng hợp cho block {start_chap}-{end_chap}.")
            return

        prompt = f"""
        Bạn là Thư Ký Ghi Chép. Hãy đọc tóm tắt nội dung các chương vừa qua ({start_chap}-{end_chap}) và thực hiện:
        1. Tóm tắt ngắn gọn các sự kiện chính.
        2. Ghi chú về các Nhân vật mới xuất hiện (Phe phái, tên gọi, đặc điểm).
        3. Ghi chú về Địa danh mới.
        4. Rút ra lưu ý quan trọng cho AI dịch các chương tiếp theo.
        
        Nội dung truyện:
        {full_text}
        """
        config = get_ai_config(f"Tóm tắt cốt truyện {start_chap}-{end_chap}:")

        api_key_obj = None # Khởi tạo để có thể truy cập trong khối except
        for attempt in range(RETRY_LIMIT):
            try:
                api_key_obj, pool_name = get_next_api_key('summary')
                if not api_key_obj:
                    print(f"   ❌ [FAILED] Không thể tạo memory cho block {start_chap}-{end_chap} vì đã hết key.")
                    return
    
                api_key = api_key_obj['key']
                key_name = KEY_VALUE_TO_NAME_MAP.get(api_key, "Unknown")
                model_to_use = SUMMARY_MODEL_NAME if pool_name == 'summary' else MODEL_NAME
                
                print(f"      - [MEMORY GEN] Attempt {attempt + 1}, using key '{key_name}' from '{pool_name}' pool...")
                client = genai.Client(api_key=api_key)
    
                resp = make_throttled_api_call(client, model_to_use, [prompt], config)
    
                if resp.text:
                    with open(target_mem_file, 'w', encoding='utf-8') as f:
                        f.write(resp.text)
                    print(f"   💾 [Memory] Đã lưu: memory_block_{start_chap:04d}_{end_chap:04d}.txt")
                    
                    if end_chap % 50 == 0:
                        thread = threading.Thread(target=consolidate_memory, args=(end_chap,), daemon=True)
                        thread.start()
                        with background_threads_lock:
                            BACKGROUND_THREADS.append(thread)
                    return # Thành công
            except Exception as e:
                error_str = str(e)
                # 429 sẽ được xử lý bởi get_next_api_key -> restore_delayed_keys
                if not ("429" in error_str or "Resource" in error_str):
                    print(f"   ⚠️ [Memory Error] Lỗi tạo block lần {attempt+1}: {e}")
    
                if attempt == RETRY_LIMIT - 1:
                    print(f"   ❌ [FAILED] Không thể tạo memory cho block {start_chap}-{end_chap}.")
                else:
                    time.sleep(5)
def check_and_trigger_memory(completed_chap_num):
    """
    Hàm này được gọi MỖI KHI xong 1 chương.
    Nó sẽ tính toán xem chương này thuộc Block nào (ví dụ Chap 5 thuộc Block 1-10).
    Sau đó nó kiểm tra xem CẢ BLOCK đó đã đủ file chưa.
    Nếu đủ -> Gọi generate_block_memory.
    """
    # Tính toán Block
    # Block 1: 1-10, Block 2: 11-20...
    # Công thức: block_idx = (num - 1) // 10
    block_idx = (completed_chap_num - 1) // 10
    start_chap = block_idx * 10 + 1
    end_chap = start_chap + 9
    
    # Kiểm tra xem file memory của block này đã có chưa (đỡ tốn công check file)
    target_mem_file = os.path.join(MEMORY_FOLDER, f"memory_block_{start_chap:04d}_{end_chap:04d}.txt")
    if os.path.exists(target_mem_file):
        return # Đã xong rồi, không cần check nữa

    # Kiểm tra xem đủ 10 file chưa
    all_files_exist = True
    for i in range(start_chap, end_chap + 1):
        file_path = os.path.join(TEMP_FOLDER, f"chap_{i:04d}.txt")
        if not os.path.exists(file_path):
            all_files_exist = False
            break

    if all_files_exist:
        # Nếu đủ cả 10 file, thì tạo memory.
        # Dùng thread riêng (daemon) để không chặn luồng dịch hiện tại
        thread = threading.Thread(target=generate_block_memory, args=(start_chap, end_chap), daemon=True)
        thread.start()
        with background_threads_lock:
            BACKGROUND_THREADS.append(thread)

def recover_missing_memories(all_tasks):
    """Quét và tạo lại memory bị thiếu từ các file đã dịch."""
    main_chapters = [t for t in all_tasks if not t.get('is_extra', False)]
    if not main_chapters: return
    max_chap = max(c['num'] for c in main_chapters)

    print("\n🕵️ Đang rà soát file cũ để khôi phục Memory (Catch-up Mode)...")
    total_blocks = (max_chap - 1) // 10

    for b in range(total_blocks + 1):
        start = b * 10 + 1
        end = start + 9
        mem_path = os.path.join(MEMORY_FOLDER, f"memory_block_{start:04d}_{end:04d}.txt")
        if os.path.exists(mem_path):
            continue

        if all(os.path.exists(os.path.join(TEMP_FOLDER, f"chap_{i:04d}.txt")) for i in range(start, end + 1)):
            print(f"⚠️ Phát hiện Block {start}-{end} đủ file nhưng thiếu Memory. Đang tạo bù...")
            generate_block_memory(start, end) # Gọi trực tiếp để đảm bảo xong
    print("✅ Rà soát hoàn tất.\n")





# --- XỬ LÝ CHƯƠNG ---

def process_item(item_data):
    num = item_data.get("num", 0)
    is_extra = item_data.get('is_extra', False)
    original_title = item_data["title_raw"]
    content = item_data["content"]
    all_raw_blocks_ref = item_data.get("all_raw_blocks", [])

    if is_extra:
        idx = item_data["extra_index"]
        temp_file = os.path.join(TEMP_FOLDER, f"extra_{idx:03d}.txt")
        chap_display = f"Ngoại truyện {idx}"
    else:
        temp_file = os.path.join(TEMP_FOLDER, f"chap_{num:04d}.txt")
        chap_display = f"Chap {num:03d}"

    if os.path.exists(temp_file):
        with open(temp_file, 'r', encoding='utf-8') as f:
            if len(f.read()) > 50:
                if not is_extra:
                    check_and_trigger_memory(num)
                return chap_display, "SKIPPED", ""

    memory_context = get_latest_memory(num) if not is_extra else ""
    system_prompt = get_system_prompt(memory_context, is_extra)
    prompt_with_title_context = f"{system_prompt}\n\n[TIÊU ĐỀ GỐC ĐỂ THAM KHẢO]:\n{original_title}"
    full_input = content
    ai_config = get_ai_config(prompt_with_title_context)

    print(f"   📤 [QUEUE] Thêm chương {num} vào hàng chờ dịch...")
    for attempt in range(RETRY_LIMIT):
        try:
            current_key_obj, key_pool_name = get_next_api_key('main')
            if not current_key_obj:
                return chap_display, "FAILED", "All API keys are exhausted."

            current_key = current_key_obj['key']

            client = genai.Client(api_key=current_key)
            response = make_throttled_api_call(
                client,
                model_name=MODEL_NAME,
                contents=[full_input],
                config=ai_config
            )

            raw_text = response.text.strip()
            header_start_index = raw_text.find("###")
            if not raw_text or header_start_index == -1:
                error_detail = raw_text
                raise ValueError(f"Empty or invalid response format (Header '###' not found). Raw response: '{error_detail[:500]}'")

            # Slice the text from the header onwards to trim any preamble
            translated_text = raw_text[header_start_index:]

            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(translated_text)

            if not is_extra:
                check_and_trigger_memory(num)

            # Extract chapter title from first line: ### Chapter Name ###
            first_line = translated_text.splitlines()[0] if translated_text.splitlines() else ""
            new_title_match = re.match(r'^###\s+(.+?)\s+###$', first_line.strip())
            new_title_display = new_title_match.group(1).strip() if new_title_match else "[Không lấy được tên mới]"

            print(f"   ✔️  [DONE] Chap {num}: '{new_title_display}'")
            return chap_display, "SUCCESS", ""

        except Exception as e:
            error_str = str(e)
            # 429: Key đã vượt quá giới hạn 20 req/30 phút -> đưa vào delayed pool
            if "429" in error_str or "Resource" in error_str:
                key_string = current_key_obj['key']
                key_name = KEY_VALUE_TO_NAME_MAP.get(key_string, "Unknown")
                
                # Tính toán thời gian chờ dựa trên cooldown window
                is_avail, wait_time = check_key_rate_limit(key_string)
                if not is_avail:
                    release_time = time.time() + wait_time + 2  # Thêm 2s buffer
                    
                    # Log freeze event
                    with key_log_lock:
                        if key_string not in key_usage_log:
                            key_usage_log[key_string] = {
                                'type': key_pool_name, 
                                'usage_count': 0, 
                                'frozen_by_429': False, 
                                'frozen_time': 0,
                                'in_cooldown': False
                            }
                        key_usage_log[key_string]['frozen_by_429'] = True
                        key_usage_log[key_string]['frozen_time'] = wait_time
                    
                    print(f"   ❌ [429 LIMIT] {key_name} vượt quá 20 req/30 phút. Freeze {wait_time:.1f}s")
                    
                    with delayed_keys_lock:
                        delayed_keys_pool[key_string] = release_time
                    with active_pools_lock:
                        if current_key_obj in API_KEYS_POOL:
                            API_KEYS_POOL.remove(current_key_obj)
                
                # Retry ngay với key khác
                if attempt < RETRY_LIMIT - 1:
                    time.sleep(0.5)  # Pause ngắn trước retry
                else:
                    print(f"   ❌ [FAILED] Chap {num} (429 after {RETRY_LIMIT} retries)")
                    return chap_display, "FAILED", error_str
            else:
                # Lỗi khác: retry với exponential backoff
                if attempt < RETRY_LIMIT - 1:
                    retry_delay = calculate_exponential_backoff(attempt)
                    print(f"   ⏳ [RETRY {attempt + 1}] Chờ {retry_delay:.1f}s trước lần thử tiếp theo...")
                    time.sleep(retry_delay)
                else:
                    print(f"   ❌ [FAILED] Chap {num}")
                    return chap_display, "FAILED", error_str

def merge_chapters():
    main_files = sorted(glob.glob(os.path.join(TEMP_FOLDER, "chap_*.txt")))
    extra_files = sorted(glob.glob(os.path.join(TEMP_FOLDER, "extra_*.txt")))
    if not main_files and not extra_files: return

    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as outfile:
        outfile.write(f"--- ĐỪNG CHẠY, NƠI NÀY KHẮP NƠI LÀ QUÁI VẬT ---\n\n")
        if main_files:
            outfile.write(f"\n\n{'='*20} CHÍNH VĂN {'='*20}\n\n")
            for file_path in main_files:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read() + "\n\n" + "-"*10 + "\n\n")
        if extra_files:
            outfile.write(f"\n\n{'='*20} NGOẠI TRUYỆN {'='*20}\n\n")
            for file_path in extra_files:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read() + "\n\n" + "-"*10 + "\n\n")

def main_translator():
    if not os.path.exists(TEMP_FOLDER): os.makedirs(TEMP_FOLDER)
    if not os.path.exists(MEMORY_FOLDER): os.makedirs(MEMORY_FOLDER)

    print("📋 Đang phân loại danh sách...")
    main_chapters, extra_chapters = load_titles_and_extras(TITLES_FILE_PATH)
    print("📖 Đang đọc nội dung gốc...")
    raw_blocks = load_raw_content(INPUT_FILE_PATH)
    
    all_tasks = []
    print("🔗 Đang khớp nối...")
    for item in main_chapters:
        target_num = item["num"]
        for block in raw_blocks:
            match = re.search(r'Chương\s*(\d+)', block["header"], re.IGNORECASE)
            if match and int(match.group(1)) == target_num:
                all_tasks.append({
                    "is_extra": False, "num": target_num,
                    "clean_title": item["clean_title"], "content": block["content"],
                    "title_raw": item["title_raw"],
                    "all_raw_blocks": raw_blocks # Cung cấp tham chiếu đến nội dung thô
                })
                break
    
    for item in extra_chapters:
        target_title_norm = normalize_string(item["title_raw"])
        found_block = None
        for block in raw_blocks:
            block_header_norm = normalize_string(block["header"])
            if re.search(r'chuong \d+', block_header_norm): continue
            core_target = target_title_norm.replace("phien ngoai", "").strip()
            core_block = block_header_norm.replace("phien ngoai", "").strip()
            if len(core_target) > 5 and core_target in core_block:
                found_block = block["content"]
                break
            if len(core_block) > 5 and core_block in core_target:
                found_block = block["content"]
                break
        if found_block:
            all_tasks.append({
                "is_extra": True, "extra_index": item["extra_index"],
                "clean_title": item["clean_title"], "content": found_block,
                "title_raw": item["title_raw"] # Thêm tên chương gốc
            })

    all_tasks.sort(key=lambda x: x["num"] if not x["is_extra"] else 10000 + x["extra_index"])
    
    # --- QUAN TRỌNG: CHẠY RECOVER MEMORY TRƯỚC ---
    recover_missing_memories(all_tasks)
    # --------------------------------------------------

    total = len(all_tasks)
    print(f"🚀 Bắt đầu dịch {total} chương.")
    print("-" * 70)

    count = 0
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Sử dụng executor.map để đảm bảo các chương được xử lý và ghi lại theo đúng thứ tự
        # Điều này sẽ ngăn chặn tình trạng "nhảy cóc" chương khi chạy lại script
        results = executor.map(process_item, all_tasks)
        for result in results:
            try:
                chap_display, status, error_msg = result
                count += 1
                elapsed = time.time() - start_time
                avg = elapsed / count
                eta = format_time(avg * (total - count))
                if status == "SUCCESS": print(f"✅ {chap_display:<10} | {count/total*100:5.1f}% | ETA: {eta}")
                elif status == "SKIPPED": print(f"⏩ {chap_display:<10} | {count/total*100:5.1f}% | ETA: {eta}")
                else: print(f"❌ {chap_display:<10} | {count/total*100:5.1f}% | LỖI: {error_msg[:30]}...")
            except Exception as e: print(f"❌ Lỗi hệ thống: {e}")

    # --- CHỜ CÁC TÁC VỤ NỀN HOÀN TẤT ---
    if BACKGROUND_THREADS:
        print("\n⏳ Đang chờ các tác vụ nền (glossary, memory) hoàn tất...")
        for thread in BACKGROUND_THREADS:
            thread.join() # Chờ từng thread xong
        print("✅ Tất cả tác vụ nền đã hoàn tất.")

    # --- BÁOCÁO SỬ DỤNG KEY ---
    print("\n" + "="*70)
    print("📊 BÁO CÁO SỬ DỤNG API KEYS (Cooldown: 20 req/30 phút):")
    print("="*70)
    with key_log_lock:
        for key_string, info in sorted(key_usage_log.items(), key=lambda x: -x[1]['usage_count']):
            key_name = KEY_VALUE_TO_NAME_MAP.get(key_string, "Unknown")
            
            # Kiểm tra trạng thái hiện tại
            is_avail, wait_time = check_key_rate_limit(key_string)
            if is_avail:
                status = "✅ READY"
                extra_info = ""
            elif info['frozen_by_429']:
                status = "❌ FROZEN"
                extra_info = f" | Frozen: {info['frozen_time']:.1f}s"
            else:
                status = "⏳ COOLDOWN"
                extra_info = f" | Chờ: {wait_time:.1f}s"
            
            print(f"{status:<12} | {key_name:<25} | Pool: {info['type']:<8} | Dùng: {info['usage_count']:3d} lần{extra_info}")
    print("="*70 + "\n")

    merge_chapters()

if __name__ == "__main__":
    # ... (code khởi tạo)
    main_translator()