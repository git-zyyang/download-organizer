#!/usr/bin/env python3
"""
下载文件夹智能整理工具 v2.0

功能：
1. 按文件类型自动分类
2. 智能化分类（基于文件名语义识别论文、发票、合同等）
3. 按日期归档（文档/2026-01/）
4. 监控模式（实时自动整理新下载的文件）
5. 撤销功能（支持一键还原）

使用方法：
  预览模式：    python organize_downloads.py
  执行整理：    python organize_downloads.py --execute
  监控模式：    python organize_downloads.py --watch
  撤销操作：    python organize_downloads.py --undo
  查看历史：    python organize_downloads.py --history
"""

import os
import sys
import json
import shutil
import argparse
import re
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional, Dict, List, Tuple

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # 定义空基类以避免语法错误
    class FileSystemEventHandler:
        pass
    Observer = None

# ============ 配置 ============

# 下载文件夹路径
DOWNLOADS_PATH = Path.home() / "Downloads"

# 历史记录文件
HISTORY_FILE = DOWNLOADS_PATH / ".organize_history.json"

# 是否按日期归档（True: 文档/2026-01/file.pdf, False: 文档/file.pdf）
ARCHIVE_BY_DATE = True

# ============ 分类规则 ============

CATEGORIES = {
    "文档": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xlsx", ".xls", ".pptx", ".ppt"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg", ".tiff"],
    "安装包": [".dmg", ".pkg", ".app", ".exe", ".msi", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "视频": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv"],
    "音频": [".mp3", ".wav", ".flac", ".aac", ".m4a"],
    "代码": [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml"],
    "数据分析": [".do", ".csv", ".dta", ".sav", ".rdata", ".sqlite", ".db"],
}

# ============ 智能分类规则（基于文件名关键词） ============
# 格式: (关键词列表, 子分类名)
# 优先级从上到下，匹配到第一个就停止

SMART_RULES = {
    "文档": [
        # 学术论文特征
        (["论文", "paper", "research", "study", "journal", "review"], "论文"),
        (["arxiv", "ieee", "acm", "springer", "elsevier", "s2.0-", "1-s2.0"], "论文"),
        (["摘要", "abstract", "introduction", "conclusion"], "论文"),
        # 发票
        (["发票", "invoice", "receipt", "账单", "bill"], "发票"),
        # 合同
        (["合同", "contract", "agreement", "协议"], "合同"),
        # 简历
        (["简历", "resume", "cv", "curriculum"], "简历"),
        # 报告
        (["报告", "report", "汇报", "总结"], "报告"),
        # 手册/文档
        (["手册", "manual", "guide", "教程", "tutorial"], "手册"),
    ],
    "图片": [
        # 截图
        (["screenshot", "截图", "屏幕", "screen"], "截图"),
        # 照片
        (["photo", "img_", "dsc_", "dcim", "9b6b"], "照片"),
        # 设计稿
        (["design", "设计", "ui", "mockup"], "设计"),
    ],
}

# 要跳过的文件
SKIP_FILES = {
    ".DS_Store",
    ".localized",
    "organize_downloads.py",
    ".organize_history.json",
}

SKIP_PATTERNS = [
    ".uploading",
    ".download",
    ".crdownload",
    ".part",
    ".tmp",
]

# ============ 核心逻辑 ============

def get_category(filename: str) -> str:
    """根据文件扩展名获取基础分类"""
    ext = Path(filename).suffix.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return "其他"


def get_smart_subcategory(filename: str, category: str) -> Optional[str]:
    """基于文件名关键词进行智能子分类"""
    if category not in SMART_RULES:
        return None

    filename_lower = filename.lower()

    for keywords, subcategory in SMART_RULES[category]:
        for keyword in keywords:
            if keyword.lower() in filename_lower:
                return subcategory

    return None


def get_date_folder(file_path: Path) -> str:
    """获取文件的日期文件夹名（如 2026-01）"""
    try:
        mtime = file_path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return dt.strftime("%Y-%m")
    except:
        return datetime.now().strftime("%Y-%m")


def should_skip(filename: str) -> bool:
    """判断是否应该跳过该文件"""
    if filename in SKIP_FILES:
        return True
    if filename.startswith("."):
        return True
    for pattern in SKIP_PATTERNS:
        if pattern in filename:
            return True
    return False


def get_unique_path(dest_path: Path) -> Path:
    """处理重名文件，返回唯一路径"""
    if not dest_path.exists():
        return dest_path

    base = dest_path.stem
    ext = dest_path.suffix
    parent = dest_path.parent
    counter = 1

    while True:
        new_name = f"{base}_{counter}{ext}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# ============ 历史记录管理 ============

def load_history() -> List[Dict]:
    """加载移动历史"""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def save_history(history: List[Dict]):
    """保存移动历史"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def record_move(source: Path, dest: Path):
    """记录一次移动操作"""
    history = load_history()

    # 获取最新的批次ID
    batch_id = history[-1]["batch_id"] if history and "batch_id" in history[-1] else 0
    current_batch = history[-1] if history and history[-1].get("batch_id") == batch_id else None

    if current_batch and (datetime.now() - datetime.fromisoformat(current_batch["timestamp"])).seconds < 60:
        # 同一批次（60秒内）
        current_batch["moves"].append({
            "source": str(source),
            "dest": str(dest)
        })
    else:
        # 新批次
        history.append({
            "batch_id": batch_id + 1,
            "timestamp": datetime.now().isoformat(),
            "moves": [{
                "source": str(source),
                "dest": str(dest)
            }]
        })

    save_history(history)


def start_new_batch():
    """开始新的操作批次"""
    history = load_history()
    batch_id = history[-1]["batch_id"] + 1 if history else 1
    history.append({
        "batch_id": batch_id,
        "timestamp": datetime.now().isoformat(),
        "moves": []
    })
    save_history(history)
    return batch_id


def add_to_batch(source: Path, dest: Path):
    """添加移动记录到当前批次"""
    history = load_history()
    if history:
        history[-1]["moves"].append({
            "source": str(source),
            "dest": str(dest)
        })
        save_history(history)


# ============ 主要功能 ============

def calculate_moves(downloads_path: Path, recursive: bool = True) -> Tuple[Dict, List]:
    """计算需要移动的文件

    Args:
        downloads_path: 下载文件夹路径
        recursive: 是否递归整理子文件夹
    """
    stats = defaultdict(list)
    skipped = []

    # 获取所有分类文件夹名称（避免重复整理已分类的文件）
    category_names = set(CATEGORIES.keys()) | {"其他"}

    def process_file(file_path: Path, base_path: Path):
        """处理单个文件"""
        filename = file_path.name

        if should_skip(filename):
            skipped.append(filename)
            return

        # 获取基础分类
        category = get_category(filename)

        # 智能子分类
        subcategory = get_smart_subcategory(filename, category)

        # 日期文件夹
        date_folder = get_date_folder(file_path) if ARCHIVE_BY_DATE else None

        # 构建目标路径
        if subcategory and date_folder:
            dest_folder = base_path / category / subcategory / date_folder
        elif subcategory:
            dest_folder = base_path / category / subcategory
        elif date_folder:
            dest_folder = base_path / category / date_folder
        else:
            dest_folder = base_path / category

        dest_path = dest_folder / filename

        # 如果文件已经在正确位置，跳过
        if file_path.parent == dest_folder:
            return

        dest_path = get_unique_path(dest_path)

        # 构建分类键用于显示
        if subcategory:
            display_category = f"{category}/{subcategory}"
        else:
            display_category = category

        stats[display_category].append({
            "source": file_path,
            "dest": dest_path,
            "size": file_path.stat().st_size,
            "date_folder": date_folder
        })

    def scan_directory(dir_path: Path, base_path: Path, depth: int = 0):
        """递归扫描目录"""
        for item in dir_path.iterdir():
            if item.is_file():
                process_file(item, base_path)
            elif item.is_dir() and recursive:
                # 跳过隐藏文件夹和.app包
                if item.name.startswith(".") or item.name.endswith(".app"):
                    continue
                # 递归扫描子文件夹（但都归类到顶层分类文件夹）
                scan_directory(item, base_path, depth + 1)

    scan_directory(downloads_path, downloads_path)
    return stats, skipped


def print_preview(stats: Dict, skipped: List, dry_run: bool = True):
    """打印预览信息"""
    print("\n" + "="*60)
    print(f"{'📋 预览模式' if dry_run else '🚀 执行模式'}")
    if ARCHIVE_BY_DATE:
        print(f"📅 按日期归档已启用")
    print("="*60)

    total_files = 0
    total_size = 0

    for category, files in sorted(stats.items()):
        count = len(files)
        size = sum(f["size"] for f in files)
        total_files += count
        total_size += size

        print(f"\n📁 {category}/ ({count}个文件, {format_size(size)})")

        # 按日期分组显示
        if ARCHIVE_BY_DATE:
            by_date = defaultdict(list)
            for f in files:
                by_date[f["date_folder"]].append(f)

            for date_folder in sorted(by_date.keys(), reverse=True):
                date_files = by_date[date_folder]
                print(f"   📆 {date_folder}/ ({len(date_files)}个)")
                for f in date_files[:3]:
                    print(f"      └─ {f['source'].name}")
                if len(date_files) > 3:
                    print(f"      └─ ... 还有{len(date_files)-3}个文件")
        else:
            for f in files[:5]:
                print(f"   └─ {f['source'].name}")
            if len(files) > 5:
                print(f"   └─ ... 还有{len(files)-5}个文件")

    print(f"\n" + "-"*60)
    print(f"总计: {total_files}个文件, {format_size(total_size)}")

    if skipped:
        print(f"跳过: {len(skipped)}个文件 (隐藏文件/正在下载)")


def organize_downloads(downloads_path: Path, dry_run: bool = True):
    """整理下载文件夹"""
    if not downloads_path.exists():
        print(f"错误：路径不存在 {downloads_path}")
        return

    stats, skipped = calculate_moves(downloads_path)
    print_preview(stats, skipped, dry_run)

    if dry_run:
        print(f"\n💡 这是预览模式，未做任何更改")
        print(f"   执行整理请运行: python {Path(__file__).name} --execute")
        print(f"   启动监控模式: python {Path(__file__).name} --watch")
        return

    # 开始新批次
    batch_id = start_new_batch()
    print(f"\n正在整理文件... (批次 #{batch_id})")

    moved_count = 0
    total_files = sum(len(files) for files in stats.values())

    for category, files in stats.items():
        for f in files:
            try:
                f["dest"].parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f["source"]), str(f["dest"]))
                add_to_batch(f["source"], f["dest"])
                moved_count += 1
            except Exception as e:
                print(f"   ❌ 移动失败: {f['source'].name} - {e}")

    print(f"\n✅ 完成！成功移动 {moved_count}/{total_files} 个文件")
    print(f"   如需撤销，运行: python {Path(__file__).name} --undo")


def undo_last_batch():
    """撤销最后一批移动操作"""
    history = load_history()

    if not history:
        print("没有可撤销的操作")
        return

    # 找到最后一个有效批次
    last_batch = None
    for batch in reversed(history):
        if batch["moves"]:
            last_batch = batch
            break

    if not last_batch:
        print("没有可撤销的操作")
        return

    print(f"\n撤销批次 #{last_batch['batch_id']} ({last_batch['timestamp']})")
    print(f"共 {len(last_batch['moves'])} 个文件")
    print("-" * 40)

    restored = 0
    for move in last_batch["moves"]:
        source = Path(move["source"])
        dest = Path(move["dest"])

        if dest.exists():
            try:
                # 确保源目录存在
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(source))
                print(f"   ✅ 还原: {source.name}")
                restored += 1
            except Exception as e:
                print(f"   ❌ 还原失败: {dest.name} - {e}")
        else:
            print(f"   ⚠️ 文件不存在: {dest}")

    # 从历史中移除该批次
    history = [b for b in history if b["batch_id"] != last_batch["batch_id"]]
    save_history(history)

    print(f"\n✅ 已还原 {restored}/{len(last_batch['moves'])} 个文件")

    # 清理空文件夹
    cleanup_empty_folders(DOWNLOADS_PATH)


def cleanup_empty_folders(path: Path):
    """清理空文件夹"""
    for folder in path.iterdir():
        if folder.is_dir() and folder.name not in SKIP_FILES:
            cleanup_empty_folders(folder)
            try:
                # 检查是否为空（忽略.DS_Store）
                contents = [f for f in folder.iterdir() if f.name != ".DS_Store"]
                if not contents:
                    # 删除.DS_Store和文件夹
                    for f in folder.iterdir():
                        f.unlink()
                    folder.rmdir()
            except:
                pass


def show_history():
    """显示移动历史"""
    history = load_history()

    if not history:
        print("没有操作历史")
        return

    print("\n📜 操作历史")
    print("=" * 60)

    for batch in reversed(history[-10:]):  # 只显示最近10批
        timestamp = datetime.fromisoformat(batch["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        count = len(batch["moves"])
        print(f"\n批次 #{batch['batch_id']} | {timestamp} | {count}个文件")

        for move in batch["moves"][:3]:
            source_name = Path(move["source"]).name
            dest_folder = Path(move["dest"]).parent.relative_to(DOWNLOADS_PATH)
            print(f"   {source_name} → {dest_folder}/")

        if count > 3:
            print(f"   ... 还有{count-3}个文件")


# ============ 监控模式 ============

class DownloadHandler(FileSystemEventHandler):
    """文件系统事件处理器"""

    def __init__(self, downloads_path: Path):
        self.downloads_path = downloads_path
        self.pending_files = {}  # 等待处理的文件
        self.process_delay = 2  # 等待文件下载完成的延迟（秒）

    def on_created(self, event):
        if event.is_directory:
            return
        self._schedule_process(Path(event.src_path))

    def on_moved(self, event):
        if event.is_directory:
            return
        # 文件移动到下载文件夹（如Chrome下载完成）
        dest_path = Path(event.dest_path)
        if dest_path.parent == self.downloads_path:
            self._schedule_process(dest_path)

    def _schedule_process(self, file_path: Path):
        """延迟处理文件（等待下载完成）"""
        if file_path.parent != self.downloads_path:
            return

        filename = file_path.name

        if should_skip(filename):
            return

        # 记录文件，稍后处理
        self.pending_files[str(file_path)] = time.time()

    def process_pending(self):
        """处理等待中的文件"""
        now = time.time()
        to_remove = []

        for file_path_str, timestamp in list(self.pending_files.items()):
            if now - timestamp < self.process_delay:
                continue

            file_path = Path(file_path_str)
            to_remove.append(file_path_str)

            if not file_path.exists():
                continue

            # 检查文件是否还在被写入
            try:
                size1 = file_path.stat().st_size
                time.sleep(0.5)
                size2 = file_path.stat().st_size
                if size1 != size2:
                    # 文件还在下载，重新加入队列
                    self.pending_files[file_path_str] = now
                    to_remove.remove(file_path_str)
                    continue
            except:
                continue

            # 处理文件
            self._process_file(file_path)

        for path in to_remove:
            self.pending_files.pop(path, None)

    def _process_file(self, file_path: Path):
        """整理单个文件"""
        filename = file_path.name

        # 获取分类
        category = get_category(filename)
        subcategory = get_smart_subcategory(filename, category)
        date_folder = get_date_folder(file_path) if ARCHIVE_BY_DATE else None

        # 构建目标路径
        if subcategory and date_folder:
            dest_folder = self.downloads_path / category / subcategory / date_folder
        elif subcategory:
            dest_folder = self.downloads_path / category / subcategory
        elif date_folder:
            dest_folder = self.downloads_path / category / date_folder
        else:
            dest_folder = self.downloads_path / category

        dest_path = dest_folder / filename
        dest_path = get_unique_path(dest_path)

        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(dest_path))
            record_move(file_path, dest_path)

            # 显示分类信息
            display_category = f"{category}/{subcategory}" if subcategory else category
            print(f"   ✅ {filename} → {display_category}/{date_folder or ''}")
        except Exception as e:
            print(f"   ❌ 移动失败: {filename} - {e}")


def watch_downloads(downloads_path: Path):
    """监控模式"""
    if not WATCHDOG_AVAILABLE:
        print("❌ 监控模式需要安装 watchdog 库")
        print("   运行: pip install watchdog")
        return

    print("\n" + "="*60)
    print("👀 监控模式已启动")
    print("="*60)
    print(f"监控路径: {downloads_path}")
    print(f"按日期归档: {'是' if ARCHIVE_BY_DATE else '否'}")
    print(f"按 Ctrl+C 停止监控")
    print("-"*60 + "\n")

    handler = DownloadHandler(downloads_path)
    observer = Observer()
    observer.schedule(handler, str(downloads_path), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
            handler.process_pending()
    except KeyboardInterrupt:
        print("\n\n停止监控...")
        observer.stop()

    observer.join()
    print("✅ 监控已停止")


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(
        description="下载文件夹智能整理工具 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python organize_downloads.py           # 预览模式
  python organize_downloads.py -e        # 执行整理
  python organize_downloads.py -w        # 监控模式
  python organize_downloads.py --undo    # 撤销上次操作
  python organize_downloads.py --no-date # 不按日期归档
        """
    )
    parser.add_argument(
        "--execute", "-e",
        action="store_true",
        help="执行模式，实际移动文件"
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="监控模式，实时整理新下载的文件"
    )
    parser.add_argument(
        "--undo", "-u",
        action="store_true",
        help="撤销上一批移动操作"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="显示操作历史"
    )
    parser.add_argument(
        "--no-date",
        action="store_true",
        help="不按日期归档"
    )
    parser.add_argument(
        "--path", "-p",
        default=str(DOWNLOADS_PATH),
        help=f"下载文件夹路径（默认 {DOWNLOADS_PATH}）"
    )

    args = parser.parse_args()

    # 设置日期归档选��
    global ARCHIVE_BY_DATE
    if args.no_date:
        ARCHIVE_BY_DATE = False

    downloads_path = Path(args.path).expanduser()

    if args.undo:
        undo_last_batch()
    elif args.history:
        show_history()
    elif args.watch:
        watch_downloads(downloads_path)
    else:
        dry_run = not args.execute
        organize_downloads(downloads_path, dry_run=dry_run)


if __name__ == "__main__":
    main()
