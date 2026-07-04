import re
import hashlib
import os
from collections import defaultdict
import tkinter as tk
from tkinter import scrolledtext, messagebox

# --- CẤU HÌNH ---
INPUT_FILE_PATH = r"C:\Users\Azuree\Documents\Truyen-chu\Truyen_Hoan_Chinh_DRAFT.txt"
# File đầu ra sẽ chứa các chapter đã sửa lỗi
OUTPUT_FILE_PATH = r"C:\Users\Azuree\Documents\Truyen-chu\Truyen_Dich_Hoan_Chinh_DRAFT_FINAL.txt" 

# Mẫu Regex để tìm và tách chương
HEADER_PATTERN = re.compile(r'(\n\n\n###.*?###\n\n)', re.DOTALL)

# Biến toàn cục lưu trữ dữ liệu sau khi phân tích
ALL_CHAPTER_DATA = {} # Lưu trữ tất cả các chapter (header, content)
TITLE_HEADER = ""     # Lưu trữ phần tiêu đề file
ERROR_LIST = []       # Danh sách các chương cần sửa
CURRENT_ERROR_INDEX = 0

def parse_chapters(file_path):
    """Đọc file và chia nội dung thành dictionary {index: chap_data}"""
    global ALL_CHAPTER_DATA, TITLE_HEADER
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        messagebox.showerror("Lỗi File", f"Không tìm thấy file tại đường dẫn: {file_path}")
        return False

    parts = HEADER_PATTERN.split(content)
    chapters_map = {}
    
    TITLE_HEADER = parts[0]
    
    # parts[1] là header 1, parts[2] là content 1, ...
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        content = parts[i+1].strip()
        
        match = re.search(r'CHƯƠNG (\d+)', header, re.IGNORECASE) 
        chapter_num = int(match.group(1)) if match else 0
        
        # Key là Index thứ tự trong file (1, 2, 3...)
        chapters_map[i // 2] = { 
            'number': chapter_num,
            'header': header,
            'content': content,
            'index_in_file': i // 2, # Chỉ mục thứ tự trong file
            'is_fixed': False
        }
    
    ALL_CHAPTER_DATA = chapters_map
    return True

def find_errors():
    """Xác định các chương cần được đánh dấu lại (refill) và trả về danh sách lỗi."""
    global ERROR_LIST
    
    # 1. Kiểm tra Trùng Lặp Tên/Số Chương
    num_to_index = defaultdict(list)
    for index, chap in ALL_CHAPTER_DATA.items():
        num_to_index[chap['number']].append(index)
    
    for num, indices in num_to_index.items():
        if len(indices) > 1:
            # Xử lý các chương bị lặp (ví dụ: 557 lặp 2 lần)
            # Chỉ đánh dấu chương lặp sau chương đầu tiên để người dùng dán lại
            for index in indices[1:]: # Bắt đầu từ bản lặp thứ 2
                chap = ALL_CHAPTER_DATA[index]
                ERROR_LIST.append({
                    'type': 'Trùng Tên Chương',
                    'number_to_fix': chap['number'],
                    'index_to_fix': index,
                    'header_to_fix': chap['header'],
                    'context': f"Đã tìm thấy bản lặp của {chap['header']} tại vị trí này. Vui lòng dán lại nội dung chính xác của chương này hoặc xóa nếu là chương thừa."
                })
    
    # 2. Kiểm tra Lệch Thứ Tự (Thiếu Chương)
    actual_numbers = sorted(list(set(chap['number'] for chap in ALL_CHAPTER_DATA.values())))
    
    for i in range(len(actual_numbers) - 1):
        current = actual_numbers[i]
        next_chap = actual_numbers[i+1]
        
        if next_chap > current + 1:
            # Bị thiếu (missing_num)
            for missing_num in range(current + 1, next_chap):
                # Tìm index của chương liền sau chương bị thiếu
                index_next = next(index for index, chap in ALL_CHAPTER_DATA.items() if chap['number'] == next_chap)
                
                ERROR_LIST.append({
                    'type': 'Thiếu Chương',
                    'number_to_fix': missing_num,
                    'index_to_fix': index_next, # Sẽ chèn chương bị thiếu vào VỊ TRÍ này
                    'header_to_fix': f"### CHƯƠNG {missing_num}: [CẦN TÌM TÊN CHƯƠNG CHÍNH XÁC] ###",
                    'context': f"Phát hiện THIẾU CHƯƠNG {missing_num} (nằm giữa Chương {current} và Chương {next_chap}). Bạn cần tìm và dán nội dung cho Chương {missing_num}."
                })

    # Gộp các lỗi có cùng chương/index để tránh xử lý nhiều lần
    # Đây là logic phức tạp, tạm thời ưu tiên Trùng Tên và Thiếu Chương vì chúng gây lỗi cấu trúc
    
    print(f"Đã phát hiện tổng cộng {len(ERROR_LIST)} lỗi cần xử lý thủ công.")
    
    # Sắp xếp theo index trong file để sửa tuần tự
    ERROR_LIST.sort(key=lambda x: x['index_to_fix'])

# --- GIAO DIỆN TKINTER ---

class ChapterFixerApp:
    def __init__(self, master):
        self.master = master
        master.title("Tự Động Sửa Lỗi Chương Truyện")
        
        if not parse_chapters(INPUT_FILE_PATH):
            master.destroy()
            return
            
        find_errors()
        
        if not ERROR_LIST:
            messagebox.showinfo("Hoàn tất", "Không tìm thấy lỗi cần sửa chữa. File đã sạch!")
            self.save_all()
            master.destroy()
            return

        self.setup_gui()
        self.load_error()

    def setup_gui(self):
        # Khung trạng thái
        self.status_label = tk.Label(self.master, text="", font=("Arial", 12, "bold"))
        self.status_label.pack(pady=10)

        # Khung hiển thị Context (Read-only)
        tk.Label(self.master, text="NGỮ CẢNH LỖI / NỘI DUNG GỐC (Chỉ đọc):").pack(pady=5)
        self.context_text = scrolledtext.ScrolledText(self.master, height=10, wrap=tk.WORD, bg="#f0f0f0", font=("Consolas", 10))
        self.context_text.pack(padx=10, fill="x")
        
        # Khung nhập liệu (Editable)
        tk.Label(self.master, text="DÁN NỘI DUNG ĐÃ SỬA CHỮA HOẶC NỘI DUNG CHƯƠNG BỊ THIẾU VÀO ĐÂY:").pack(pady=5)
        self.refill_text = scrolledtext.ScrolledText(self.master, height=15, wrap=tk.WORD, font=("Consolas", 10))
        self.refill_text.pack(padx=10, fill="both", expand=True)

        # Khung nút bấm
        button_frame = tk.Frame(self.master)
        button_frame.pack(pady=10)
        
        self.save_button = tk.Button(button_frame, text="✅ Lưu & Chuyển Lỗi Tiếp Theo", command=self.save_and_next, bg="#4CAF50", fg="white", font=("Arial", 11, "bold"))
        self.save_button.pack(side=tk.LEFT, padx=10)

        self.skip_button = tk.Button(button_frame, text="➡️ Bỏ Qua Lỗi Này (Không sửa)", command=self.skip_error, bg="#ff9800", fg="white")
        self.skip_button.pack(side=tk.LEFT, padx=10)

        self.finish_button = tk.Button(button_frame, text="💾 Hoàn Tất & Ghi File Cuối", command=self.finish_fixing, bg="#2196F3", fg="white")
        self.finish_button.pack(side=tk.LEFT, padx=10)

    def load_error(self):
        """Tải thông tin lỗi hiện tại lên GUI"""
        global CURRENT_ERROR_INDEX
        if CURRENT_ERROR_INDEX >= len(ERROR_LIST):
            self.finish_fixing()
            return

        error = ERROR_LIST[CURRENT_ERROR_INDEX]
        
        # Cập nhật trạng thái
        self.status_label.config(text=f"🚨 LỖI {CURRENT_ERROR_INDEX + 1} / {len(ERROR_LIST)}: {error['type']} - Chương {error['number_to_fix']}")
        
        # Xóa nội dung cũ
        self.context_text.delete('1.0', tk.END)
        self.refill_text.delete('1.0', tk.END)
        
        # Hiển thị Context
        self.context_text.insert(tk.END, error['context'] + "\n\n" + "-"*50 + "\n\n")

        # Đối với lỗi Trùng Tên Chương, hiển thị nội dung gốc để người dùng sửa lại
        if error['type'] == 'Trùng Tên Chương' and error['index_to_fix'] in ALL_CHAPTER_DATA:
            original_content = ALL_CHAPTER_DATA[error['index_to_fix']]['content']
            self.context_text.insert(tk.END, f"NỘI DUNG CŨ CỦA {error['header_to_fix']}:\n\n{original_content}")
        
        # Đặt tiêu đề cho phần dán lại
        self.refill_text.insert(tk.END, f"{error['header_to_fix']}\n\n[DÁN NỘI DUNG CHÍNH XÁC CỦA CHƯƠNG {error['number_to_fix']} VÀO ĐÂY]")


    def save_and_next(self):
        """Lưu nội dung đã sửa và chuyển sang lỗi tiếp theo."""
        global CURRENT_ERROR_INDEX
        
        error = ERROR_LIST[CURRENT_ERROR_INDEX]
        new_content_raw = self.refill_text.get('1.0', tk.END).strip()
        
        if not new_content_raw or "[DÁN NỘI DUNG CHÍNH XÁC" in new_content_raw:
            messagebox.showwarning("Thiếu nội dung", "Vui lòng dán nội dung chương chính xác trước khi lưu.")
            return

        # Tách header và content mới
        parts = new_content_raw.split('\n\n', 1)
        new_header = parts[0].strip()
        new_content = parts[1].strip() if len(parts) > 1 else ""

        # LƯU DỮ LIỆU ĐÃ SỬA VÀO ALL_CHAPTER_DATA
        if error['type'] == 'Thiếu Chương':
            # Nếu là chương bị thiếu, tạo một bản ghi mới trong ALL_CHAPTER_DATA
            new_index = max(ALL_CHAPTER_DATA.keys()) + 1 
            ALL_CHAPTER_DATA[new_index] = {
                'number': error['number_to_fix'],
                'header': new_header,
                'content': new_content,
                'index_in_file': error['index_to_fix'], # Dùng index để biết vị trí chèn
                'is_fixed': True,
                'is_missing': True # Đánh dấu là chương mới được chèn
            }
            # Cập nhật index của các chương sau đó (rất phức tạp, tạm thời dùng logic ghi lại file để sắp xếp)
            
        else: # Lỗi Trùng Tên Chương (Chương cần dán đè)
            index = error['index_to_fix']
            ALL_CHAPTER_DATA[index]['header'] = new_header
            ALL_CHAPTER_DATA[index]['content'] = new_content
            ALL_CHAPTER_DATA[index]['is_fixed'] = True

        CURRENT_ERROR_INDEX += 1
        self.load_error()

    def skip_error(self):
        """Bỏ qua lỗi hiện tại (tức là xóa bản lặp đó đi)."""
        global CURRENT_ERROR_INDEX
        
        error = ERROR_LIST[CURRENT_ERROR_INDEX]
        
        if error['type'] == 'Trùng Tên Chương':
            # Xóa bản lặp khỏi danh sách để nó không được ghi ra file
            if error['index_to_fix'] in ALL_CHAPTER_DATA:
                del ALL_CHAPTER_DATA[error['index_to_fix']]
                messagebox.showinfo("Đã Xóa", f"Đã xóa bản lặp của {error['header_to_fix']} (Vị trí {error['index_to_fix']}).")
        
        # Lỗi Thiếu Chương không thể bỏ qua, phải dán lại hoặc dùng nút Hoàn Tất để kết thúc
        
        CURRENT_ERROR_INDEX += 1
        self.load_error()

    def finish_fixing(self):
        """Hoàn tất quá trình sửa chữa và ghi tất cả dữ liệu ra file."""
        if not messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn kết thúc và ghi file?"):
            return
            
        self.save_all()
        messagebox.showinfo("Thành công!", f"Đã ghi file hoàn tất tại:\n{os.path.abspath(OUTPUT_FILE_PATH)}")
        self.master.destroy()
        
    def save_all(self):
        """Logic ghi lại file cuối cùng."""
        with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f:
            # 1. Ghi lại tiêu đề file gốc
            f.write(TITLE_HEADER.strip() + "\n\n")
            
            # 2. Tạo danh sách cuối cùng cần ghi, ưu tiên chèn các chương bị thiếu vào đúng vị trí
            final_chapters = []
            
            # Chuyển đổi từ dict sang list để sắp xếp theo số chương/index chèn
            all_data_list = list(ALL_CHAPTER_DATA.values())
            
            # Sắp xếp để giữ thứ tự logic: Sắp xếp theo số chương, sau đó ưu tiên chương được chèn
            all_data_list.sort(key=lambda x: x['number'])

            # Logic chèn chương bị thiếu (đã được đánh dấu is_missing=True) vào đúng vị trí
            i = 0
            while i < len(all_data_list):
                chap = all_data_list[i]
                final_chapters.append(chap)
                
                # Kiểm tra nếu chương tiếp theo bị thiếu trong danh sách hiện tại
                # (Logic này rất phức tạp để viết lại, nên tạm thời chỉ sắp xếp theo số chương)
                
                i += 1
            
            # LƯU Ý: Do việc chèn chương bị thiếu cần logic sắp xếp phức tạp, 
            # chúng ta sẽ đơn giản hóa: chỉ sắp xếp theo số chương và ghi ra.
            
            # Sắp xếp theo số chương để đảm bảo thứ tự cuối cùng là đúng
            sorted_chapters = sorted(ALL_CHAPTER_DATA.values(), key=lambda x: x['number'])
            
            for chap in sorted_chapters:
                header = chap['header']
                content = chap['content']
                
                # Định dạng đầu ra
                formatted_output = f"\n\n\n{header}\n\n{content}"
                f.write(formatted_output)

            # Ghi lại chương cuối nếu bị thiếu/chèn thủ công

# --- CHẠY ỨNG DỤNG ---
if __name__ == "__main__":
    print(f"Bắt đầu phân tích file: {os.path.abspath(INPUT_FILE_PATH)}")
    
    root = tk.Tk()
    app = ChapterFixerApp(root)
    root.mainloop()