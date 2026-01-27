"""
將 RAG 資料夾中的 JSON 檔案轉換為 Markdown 格式
以提升 OpenAI File Search 的語意檢索效果

優化版本 v2.1:
- 自動提取活動日期
- 標註活動狀態（未來/過去/進行中）
- 計算距今天數
- 統一日期格式為 yyyy/mm/dd
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# 日期解析正則表達式
DATE_PATTERNS = {
    "iso": re.compile(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'),
    "roc": re.compile(r'(\d{3})年(\d{1,2})月(\d{1,2})日'),
    "month_day": re.compile(r'(\d{1,2})月(\d{1,2})日'),
}

# 活動狀態定義
STATUS_CONFIG = [
    (0, "today", "今天舉辦"),
    (7, "this_week", "本週活動（還有 {days} 天）"),
    (30, "this_month", "本月活動（還有 {days} 天）"),
    (90, "next_3_months", "未來 3 個月內（還有 {days} 天）"),
]


def format_date(date_str: str) -> str:
    """將 ISO 日期格式轉換為 yyyy/mm/dd 格式"""
    if not date_str:
        return ""
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y/%m/%d %H:%M")
        return date_str
    except (ValueError, TypeError):
        return date_str


def _try_parse_date(year: int, month: int, day: int) -> Optional[datetime]:
    """嘗試創建 datetime 物件，失敗返回 None"""
    try:
        return datetime(year, month, day, tzinfo=TAIPEI_TZ)
    except ValueError:
        return None


def extract_event_date_from_content(content: str, publish_date: str = None) -> Tuple[str, str]:
    """
    從內容中提取活動日期

    Returns:
        (event_date, event_date_source)
    """
    if not content:
        return "", ""

    # ISO 格式: YYYY/MM/DD 或 YYYY-MM-DD
    match = DATE_PATTERNS["iso"].search(content)
    if match:
        year, month, day = map(int, match.groups())
        date = _try_parse_date(year, month, day)
        if date:
            return date.strftime("%Y/%m/%d"), "extracted_from_content"

    # 民國年: 115年1月23日
    match = DATE_PATTERNS["roc"].search(content)
    if match:
        roc_year, month, day = map(int, match.groups())
        date = _try_parse_date(roc_year + 1911, month, day)
        if date:
            return date.strftime("%Y/%m/%d"), "extracted_from_content"

    # 月日: 1月24日（推斷年份）
    match = DATE_PATTERNS["month_day"].search(content)
    if match:
        month, day = map(int, match.groups())
        now = datetime.now(TAIPEI_TZ)

        date = _try_parse_date(now.year, month, day)
        if date:
            # 如果日期已過且有 publish_date，使用明年
            if publish_date and date < now:
                next_year_date = _try_parse_date(now.year + 1, month, day)
                if next_year_date:
                    return next_year_date.strftime("%Y/%m/%d"), "inferred_from_content"
            return date.strftime("%Y/%m/%d"), "inferred_from_content"

    return "", ""


def calculate_activity_status(event_date_str: str) -> Tuple[str, int, str]:
    """
    計算活動狀態

    Returns:
        (status, days_diff, status_desc)
    """
    if not event_date_str:
        return "unknown", 0, "日期未知"

    try:
        event_date = datetime.strptime(event_date_str, "%Y/%m/%d").replace(tzinfo=TAIPEI_TZ)
        now = datetime.now(TAIPEI_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        days_diff = (event_date - now).days

        # 已過期
        if days_diff < 0:
            return "past", days_diff, f"已過期 {abs(days_diff)} 天"

        # 根據配置判斷狀態
        for threshold, status, desc_template in STATUS_CONFIG:
            if days_diff <= threshold:
                return status, days_diff, desc_template.format(days=days_diff)

        return "future", days_diff, f"未來活動（還有 {days_diff} 天）"

    except (ValueError, TypeError):
        return "unknown", 0, "日期格式錯誤"


def extract_post_content(post: dict) -> str:
    """從貼文資料提取主要內容"""
    return (post.get("content") or post.get("raw_content") or "").strip()


def _format_metadata(post: dict, publish_date: str) -> Tuple[list, str]:
    """提取並格式化元數據"""
    metadata_lines = []
    publish_date_formatted = format_date(publish_date) if publish_date else "未知"
    metadata_lines.append(f"**發布日期：** {publish_date_formatted}")

    # 處理不同的時間格式
    time_data = post.get("time", {})
    if isinstance(time_data, dict):
        event_time = time_data.get("event")
        deadline = time_data.get("deadline")
    else:
        event_time = post.get("event_time")
        deadline = post.get("deadline")

    # 優先使用結構化的活動時間，否則從內容提取
    if event_time:
        event_date = format_date(event_time).split()[0]
    else:
        content = extract_post_content(post)
        event_date, _ = extract_event_date_from_content(content, publish_date)

    # 計算活動狀態
    if event_date:
        status, _, status_desc = calculate_activity_status(event_date)
        metadata_lines.append(f"**活動日期：** {event_date}")
        metadata_lines.append(f"**活動狀態：** {status_desc}")

        # 視覺化標記
        status_markers = {
            "past": "**此活動已過期**",
            "today": "**即將開始！**",
            "this_week": "**即將開始！**",
            "this_month": "**本月活動**",
        }
        if status in status_markers:
            metadata_lines.append(status_markers[status])
    else:
        metadata_lines.append("**活動日期：** 未知")
        metadata_lines.append("**活動狀態：** 日期資訊不明確")

    post_type = post.get("type")
    if post_type:
        metadata_lines.append(f"**類型：** {post_type}")

    return metadata_lines, event_time


def _format_location(location) -> Optional[str]:
    """格式化地點資訊"""
    if not location:
        return None

    if isinstance(location, dict):
        loc_name = location.get("name", "")
        loc_addr = location.get("address", "")
        if loc_name or loc_addr:
            return f"{loc_name}" + (f"（{loc_addr}）" if loc_addr else "")
    elif isinstance(location, str) and location:
        return location

    return None


def _format_links(links: dict) -> list:
    """格式化連結區塊"""
    if not links or not isinstance(links, dict):
        return []

    valid_links = {k: v for k, v in links.items() if v}
    if not valid_links:
        return []

    link_names = {
        "registration": "報名連結",
        "info": "詳細資訊",
        "apply": "線上申請",
        "url": "原文連結",
    }

    lines = ["## 相關連結"]
    for key, url in valid_links.items():
        name = link_names.get(key, key)
        lines.append(f"- {name}：{url}")
    lines.append("")

    return lines


def format_post_to_markdown(post: dict, index: int) -> str:
    """將單一貼文轉換為 Markdown 格式（含活動狀態元數據）"""
    lines = []

    # 標題
    title = post.get("title", f"貼文 {index}")
    lines.extend([f"# {title}", ""])

    # 元數據區塊
    publish_date = post.get("publish_date")
    metadata_lines, event_time = _format_metadata(post, publish_date)
    lines.extend(metadata_lines)
    lines.extend(["", "---", ""])

    # 詳細時間資訊
    if event_time:
        lines.append(f"**活動時間：** {format_date(event_time)}")

    time_data = post.get("time", {})
    deadline = time_data.get("deadline") if isinstance(time_data, dict) else post.get("deadline")
    if deadline:
        lines.append(f"**報名截止：** {format_date(deadline)}")

    # 地點資訊
    location_str = _format_location(post.get("location"))
    if location_str:
        lines.append(f"**地點：** {location_str}")

    # 適用對象
    target = post.get("target")
    if target:
        lines.append(f"**適用對象：** {target}")

    # 補助金額
    subsidy = post.get("subsidy")
    if subsidy and isinstance(subsidy, dict):
        subsidy_str = ", ".join(f"{k}：{v}" for k, v in subsidy.items())
        lines.append(f"**補助金額：** {subsidy_str}")

    lines.append("")

    # 主要內容
    content = extract_post_content(post)
    if content:
        lines.extend(["## 內容", "", content, ""])

    # 聚焦領域
    focus_areas = post.get("focus_areas")
    if focus_areas:
        lines.append("## 聚焦領域")
        lines.extend(f"- {area}" for area in focus_areas)
        lines.append("")

    # 提案類別
    categories = post.get("categories")
    if categories:
        lines.append("## 提案類別")
        lines.extend(f"- {cat}" for cat in categories)
        lines.append("")

    # 相關連結
    lines.extend(_format_links(post.get("links")))

    # 原文連結
    url = post.get("url")
    if url:
        lines.extend([f"**原文連結：** {url}", ""])

    # 標籤
    tags = post.get("tags")
    if tags:
        lines.extend([f"**標籤：** {', '.join(tags)}", ""])

    return "\n".join(lines)


def convert_json_to_markdown(json_path: Path) -> str:
    """將 JSON 檔案轉換為 Markdown 內容"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []

    # 檔案標題與來源資訊
    source = data.get("source", "未知來源")
    page_url = data.get("page_url", "")
    scraped_at = data.get("scraped_at", "")

    lines.extend([f"# {source} - 最新消息", ""])
    if page_url:
        lines.append(f"**來源：** {page_url}")
    if scraped_at:
        lines.append(f"**資料更新日期：** {format_date(scraped_at)}")
    lines.extend(["", "---", ""])

    # 處理貼文
    posts = data.get("posts", [])
    for i, post in enumerate(posts, 1):
        lines.extend([format_post_to_markdown(post, i), "---", ""])

    return "\n".join(lines)


def process_rag_directory(rag_dir: Path, output_dir: Path = None) -> list:
    """處理 RAG 資料夾中的所有 JSON 檔案"""
    if output_dir is None:
        output_dir = rag_dir / "converted"

    output_dir.mkdir(exist_ok=True)

    converted_files = []
    json_files = list(rag_dir.glob("*.json"))

    print(f"Found {len(json_files)} JSON files in {rag_dir}")

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "posts" not in data:
                print(f"  Skipping {json_path.name} (not a posts file)")
                continue

            markdown_content = convert_json_to_markdown(json_path)
            output_path = output_dir / f"{json_path.stem}.md"

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            converted_files.append(output_path)
            print(f"  Converted: {json_path.name} -> {output_path.name}")

        except json.JSONDecodeError as e:
            print(f"  Error parsing {json_path.name}: {e}")
        except Exception as e:
            print(f"  Error processing {json_path.name}: {e}")

    print(f"\nConverted {len(converted_files)} files to {output_dir}")
    return converted_files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="將 JSON 貼文資料轉換為 Markdown 格式以提升 RAG 檢索效果"
    )
    parser.add_argument(
        "--rag-dir",
        default="rag_data",
        help="RAG 資料目錄 (預設: rag_data)",
    )
    parser.add_argument(
        "--output-dir",
        help="輸出目錄 (預設: rag_data/converted)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="直接輸出到 rag_data 目錄（取代 converted 子目錄）",
    )

    args = parser.parse_args()

    rag_dir = Path(args.rag_dir)
    if not rag_dir.exists():
        print(f"Error: RAG directory not found: {rag_dir}")
        return 1

    if args.in_place:
        output_dir = rag_dir
    elif args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = rag_dir / "converted"

    process_rag_directory(rag_dir, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
