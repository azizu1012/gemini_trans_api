#!/usr/bin/env python3
"""
Rescan Locations Tool
=====================
Xóa world data cũ và quét lại tất cả chương đã dịch để rebuild location database.

Usage:
  python rescan_locations.py          # Quét lại tất cả
  python rescan_locations.py --reset  # Xóa sạch trước khi quét
  python rescan_locations.py --dry    # Chỉ xem, không lưu
"""

import os
import sys
import glob
import argparse
import re

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trackers.world_builder import DynamicWorldBuilder


def get_chapter_files(temp_folder: str) -> list:
    """Lấy danh sách file chương đã dịch, sắp xếp theo số chương"""
    pattern = os.path.join(temp_folder, "chap_*.txt")
    files = glob.glob(pattern)
    
    # Sort by chapter number
    def extract_num(f):
        match = re.search(r'chap_(\d+)', os.path.basename(f))
        return int(match.group(1)) if match else 0
    
    return sorted(files, key=extract_num)


def reset_world_data(world_data_dir: str, output_dir: str):
    """Xóa sạch world data cũ"""
    files_to_delete = [
        os.path.join(world_data_dir, "discovered_locations.json"),
        os.path.join(world_data_dir, "discovered_arcs.json"),
        os.path.join(output_dir, "world_config.json"),
    ]
    
    for f in files_to_delete:
        if os.path.exists(f):
            os.remove(f)
            print(f"🗑️  Đã xóa: {os.path.basename(f)}")


def rescan_all_chapters(temp_folder: str, world_builder: DynamicWorldBuilder, dry_run: bool = False):
    """Quét lại tất cả chương đã dịch"""
    chapter_files = get_chapter_files(temp_folder)
    
    if not chapter_files:
        print("❌ Không tìm thấy file chương nào trong", temp_folder)
        return
    
    print(f"\n📚 Tìm thấy {len(chapter_files)} chương đã dịch")
    print("=" * 60)
    
    all_locations = set()
    
    for i, chap_file in enumerate(chapter_files, 1):
        # Extract chapter number
        match = re.search(r'chap_(\d+)', os.path.basename(chap_file))
        if not match:
            continue
        chap_num = int(match.group(1))
        
        # Read content
        try:
            with open(chap_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"⚠️  Lỗi đọc chương {chap_num}: {e}")
            continue
        
        # Extract locations
        new_locs = world_builder.extract_locations(content, chap_num)
        
        if new_locs:
            all_locations.update(new_locs)
            print(f"✅ Chương {chap_num:4d}: {', '.join(new_locs[:3])}{'...' if len(new_locs) > 3 else ''}")
        
        # Progress
        if i % 50 == 0:
            print(f"   ... Đã quét {i}/{len(chapter_files)} chương ...")
    
    print("=" * 60)
    print(f"\n📍 TỔNG KẾT: {len(all_locations)} địa danh được phát hiện")
    print("-" * 40)
    
    for loc in sorted(all_locations):
        print(f"  • {loc}")
    
    if not dry_run:
        # Force save
        world_builder.save_state()
        print(f"\n💾 Đã lưu vào world_config.json")
    else:
        print(f"\n⚠️  DRY RUN - Không lưu file")


def main():
    parser = argparse.ArgumentParser(description="Rescan locations từ các chương đã dịch")
    parser.add_argument('--reset', action='store_true', help='Xóa sạch data cũ trước khi quét')
    parser.add_argument('--dry', action='store_true', help='Chỉ xem, không lưu file')
    args = parser.parse_args()
    
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    temp_folder = os.path.join(output_dir, "temp_chapters")
    world_data_dir = os.path.join(output_dir, "memory_store", "world_data")
    
    print("🔍 RESCAN LOCATIONS TOOL")
    print("=" * 60)
    print(f"📁 Temp folder: {temp_folder}")
    print(f"📁 World data: {world_data_dir}")
    
    # Reset if requested
    if args.reset:
        print("\n🗑️  RESET MODE - Xóa data cũ...")
        reset_world_data(world_data_dir, output_dir)
    
    # Create world builder
    os.makedirs(world_data_dir, exist_ok=True)
    world_builder = DynamicWorldBuilder(save_dir=world_data_dir)
    
    # If reset, clear in-memory too
    if args.reset:
        world_builder.locations.clear()
        world_builder.arcs.clear()
    
    # Rescan
    rescan_all_chapters(temp_folder, world_builder, dry_run=args.dry)


if __name__ == "__main__":
    main()
