# 📁 Download Organizer

**智能下载文件夹整理工具** - 自动分类、智能识别、实时监控

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

---

## ✨ 功能特性

- **🗂️ 智能分类** - 根据文件扩展名自动归类（文档、图片、视频、安装包等）
- **🧠 语义识别** - 基于文件名关键词识别论文、发票、合同、简历等子类型
- **👀 实时监控** - 监控模式自动整理新下载的文件
- **⏪ 一键撤销** - 完整的操作历史记录，支持批量还原
- **📅 日期归档** - 可选按年月自动归档（如 `文档/2026-01/`）
- **🔄 递归整理** - 支持整理子文件夹中的文件
- **🔒 安全预览** - 默认预览模式，确认后再执行

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/download-organizer.git
cd download-organizer

# 安装依赖（监控模式需要）
pip install watchdog
```

## 🚀 快速开始

```bash
# 预览整理效果（不实际移动文件）
python organize_downloads.py

# 执行整理
python organize_downloads.py --execute

# 启动监控模式（自动整理新下载的文件）
python organize_downloads.py --watch

# 撤销上次操作
python organize_downloads.py --undo

# 查看操作历史
python organize_downloads.py --history
```

## 📖 使用指南

### 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--execute` | `-e` | 执行模式，实际移动文件 |
| `--watch` | `-w` | 监控模式，实时整理新文件 |
| `--undo` | `-u` | 撤销上一批操作 |
| `--history` | | 显示操作历史 |
| `--no-date` | | 不按日期归档 |
| `--path` | `-p` | 指定下载文件夹路径 |

### 默认分类规则

| 分类 | 文件类型 |
|------|----------|
| 文档 | `.pdf` `.doc` `.docx` `.txt` `.xlsx` `.pptx` 等 |
| 图片 | `.jpg` `.png` `.gif` `.webp` `.heic` 等 |
| 视频 | `.mp4` `.mov` `.avi` `.mkv` 等 |
| 音频 | `.mp3` `.wav` `.flac` `.m4a` 等 |
| 安装包 | `.dmg` `.exe` `.pkg` `.zip` `.rar` 等 |
| 代码 | `.py` `.js` `.ts` `.html` `.css` 等 |
| 数据分析 | `.csv` `.dta` `.do` `.sav` 等 |

### 智能子分类

脚本会根据文件名关键词自动识别更细的分类：

| 主分类 | 子分类 | 识别关键词 |
|--------|--------|------------|
| 文档 | 论文 | `paper`, `research`, `arxiv`, `1-s2.0-` 等 |
| 文档 | 发票 | `发票`, `invoice`, `receipt` 等 |
| 文档 | 合同 | `合同`, `contract`, `agreement` 等 |
| 图片 | 照片 | `photo`, `IMG_`, `DSC_` 等 |
| 图片 | 截图 | `screenshot`, `截图` 等 |

## ⚙️ 自定义配置

编辑 `organize_downloads.py` 文件顶部的配置区域：

```python
# 分类规则
CATEGORIES = {
    "文档": [".pdf", ".doc", ".docx", ...],
    "图片": [".jpg", ".png", ...],
    # 添加你的自定义分类
}

# 智能识别规则
SMART_RULES = {
    "文档": [
        (["论文", "paper"], "论文"),
        (["发票", "invoice"], "发票"),
        # 添加你的自定义规则
    ],
}

# 是否按日期归档
ARCHIVE_BY_DATE = True
```

## 📂 整理效果示例

**整理前：**
```
Downloads/
├── paper_v2_final.pdf
├── IMG_1234.jpg
├── 发票_2026.pdf
├── Cursor.dmg
└── data.csv
```

**整理后：**
```
Downloads/
├── 文档/
│   ├── 论文/
│   │   └── paper_v2_final.pdf
│   └── 发票/
│       └── 发票_2026.pdf
├── 图片/
│   └── 照片/
│       └── IMG_1234.jpg
├── 安装包/
│   └── Cursor.dmg
└── 数据分析/
    └── data.csv
```

## 🔧 进阶用法

### 创建可双击运行的快捷方式 (macOS)

```bash
# 创建预览快捷方式
echo '#!/bin/bash
python3 ~/path/to/organize_downloads.py
read -p "按回车键退出..."' > ~/Desktop/整理下载.command
chmod +x ~/Desktop/整理下载.command
```

### 设置定时任务 (macOS/Linux)

```bash
# 每天凌晨 2 点自动整理
crontab -e
# 添加: 0 2 * * * python3 /path/to/organize_downloads.py -e --no-date
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

## 🙏 致谢

- [watchdog](https://github.com/gorakhargosh/watchdog) - 文件系统监控库

---

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**
