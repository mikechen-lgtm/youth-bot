"""
將 RAG 資料夾中的 JSON 檔案轉換為 Markdown 格式
按活動日期自動分類為「過去活動」和「近期活動」

版本 v3.0:
- 收集所有 JSON 檔案的活動
- 按活動日期過濾分類
- 只生成兩個檔案：過去活動.md、近期活動.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# 日期解析正則表達式
DATE_PATTERNS = {
    "iso": re.compile(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})'),
    "roc": re.compile(r'(\d{3})年(\d{1,2})月(\d{1,2})日'),
    "month_day": re.compile(r'(\d{1,2})月(\d{1,2})日'),
}


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


def extract_event_date_from_content(content: str, publish_date: str = None) -> Tuple[Optional[datetime], str]:
    """
    從內容中提取活動日期

    Returns:
        (event_datetime, event_date_source)
    """
    if not content:
        return None, ""

    # ISO 格式: YYYY/MM/DD 或 YYYY-MM-DD
    match = DATE_PATTERNS["iso"].search(content)
    if match:
        year, month, day = map(int, match.groups())
        date = _try_parse_date(year, month, day)
        if date:
            return date, "extracted_from_content"

    # 民國年: 115年1月23日
    match = DATE_PATTERNS["roc"].search(content)
    if match:
        roc_year, month, day = map(int, match.groups())
        date = _try_parse_date(roc_year + 1911, month, day)
        if date:
            return date, "extracted_from_content"

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
                    return next_year_date, "inferred_from_content"
            return date, "inferred_from_content"

    return None, ""


def extract_post_content(post: dict) -> str:
    """從貼文資料提取主要內容"""
    return (post.get("content") or post.get("raw_content") or "").strip()


def get_event_date(post: dict) -> Optional[datetime]:
    """
    提取貼文的活動日期

    Returns:
        活動日期的 datetime 物件，如果無法提取則返回 None
    """
    # 優先使用結構化的活動時間
    time_data = post.get("time", {})
    if isinstance(time_data, dict):
        event_time = time_data.get("event")
    else:
        event_time = post.get("event_time")

    if event_time:
        try:
            if "T" in event_time:
                return datetime.fromisoformat(event_time.replace("Z", "+00:00")).replace(tzinfo=TAIPEI_TZ)
            # 嘗試解析 YYYY/MM/DD 或 YYYY-MM-DD 格式
            for fmt in ["%Y/%m/%d", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(event_time.split()[0], fmt).replace(tzinfo=TAIPEI_TZ)
                except ValueError:
                    continue
        except (ValueError, TypeError):
            pass

    # 從內容提取日期
    content = extract_post_content(post)
    publish_date = post.get("publish_date")
    event_datetime, _ = extract_event_date_from_content(content, publish_date)
    return event_datetime


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


def format_post_to_markdown(post: dict, source: str, event_date: datetime) -> str:
    """將單一貼文轉換為 Markdown 格式"""
    lines = []

    # 標題
    title = post.get("title", "無標題活動")
    lines.extend([f"# {title}", ""])

    # 元數據區塊
    publish_date = post.get("publish_date")
    if publish_date:
        lines.append(f"**發布日期：** {format_date(publish_date)}")

    # 活動日期
    lines.append(f"**活動日期：** {event_date.strftime('%Y/%m/%d')}")

    # 來源
    lines.append(f"**來源：** {source}")
    lines.extend(["", "---", ""])

    # 詳細時間資訊
    time_data = post.get("time", {})
    event_time = time_data.get("event") if isinstance(time_data, dict) else post.get("event_time")
    if event_time:
        lines.append(f"**活動時間：** {format_date(event_time)}")

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


def collect_all_posts(rag_dir: Path) -> List[Tuple[dict, str, Optional[datetime]]]:
    """
    收集所有 JSON 檔案中的活動

    Returns:
        List of (post, source, event_date)
    """
    all_posts = []
    json_files = list(rag_dir.glob("*.json"))

    print(f"📂 找到 {len(json_files)} 個 JSON 檔案")

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "posts" not in data:
                print(f"  ⏭️  跳過 {json_path.name}（不包含 posts）")
                continue

            source = data.get("source", json_path.stem)
            posts = data.get("posts", [])

            for post in posts:
                event_date = get_event_date(post)
                if event_date:
                    all_posts.append((post, source, event_date))
                    print(f"  ✓ {source}: {post.get('title', '無標題')[:30]} - {event_date.strftime('%Y/%m/%d')}")
                else:
                    print(f"  ⚠️  無法提取日期: {post.get('title', '無標題')[:30]}")

        except json.JSONDecodeError as e:
            print(f"  ❌ JSON 解析錯誤 {json_path.name}: {e}")
        except Exception as e:
            print(f"  ❌ 處理錯誤 {json_path.name}: {e}")

    return all_posts


def generate_categorized_markdown(rag_dir: Path, output_dir: Path) -> Tuple[Path, Path]:
    """
    生成按時間分類的 Markdown 檔案

    Returns:
        (過去活動檔案路徑, 近期活動檔案路徑)
    """
    # 收集所有活動
    all_posts = collect_all_posts(rag_dir)

    if not all_posts:
        print("\n⚠️  未找到任何包含日期的活動")
        return None, None

    # 計算時間範圍
    now = datetime.now(TAIPEI_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    three_months_later = now + timedelta(days=90)

    # 分類活動
    past_posts = []
    upcoming_posts = []

    for post, source, event_date in all_posts:
        if event_date < now:
            past_posts.append((post, source, event_date))
        elif event_date <= three_months_later:
            upcoming_posts.append((post, source, event_date))

    print(f"\n📊 分類結果：")
    print(f"  過去活動：{len(past_posts)} 個")
    print(f"  近期活動（今天到未來3個月）：{len(upcoming_posts)} 個")

    # 排序：過去活動按日期降序，近期活動按日期升序
    past_posts.sort(key=lambda x: x[2], reverse=True)
    upcoming_posts.sort(key=lambda x: x[2])

    output_dir.mkdir(exist_ok=True)

    # 生成「過去活動.md」
    past_file = output_dir / "過去活動.md"
    if past_posts:
        lines = [
            "# 桃園市政府青年事務局 - 過去活動",
            "",
            f"**資料更新時間：** {now.strftime('%Y/%m/%d %H:%M')}",
            f"**活動數量：** {len(past_posts)} 個",
            "",
            "---",
            ""
        ]

        for post, source, event_date in past_posts:
            lines.extend([
                format_post_to_markdown(post, source, event_date),
                "---",
                ""
            ])

        with open(past_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"\n✅ 已生成：{past_file}")
    else:
        print(f"\n⏭️  無過去活動，跳過生成 {past_file}")

    # 生成「近期活動.md」
    upcoming_file = output_dir / "近期活動.md"
    if upcoming_posts:
        lines = [
            "# 桃園市政府青年事務局 - 近期活動",
            "",
            f"**資料更新時間：** {now.strftime('%Y/%m/%d %H:%M')}",
            f"**活動數量：** {len(upcoming_posts)} 個",
            f"**時間範圍：** {now.strftime('%Y/%m/%d')} ~ {three_months_later.strftime('%Y/%m/%d')}（未來3個月）",
            "",
            "---",
            ""
        ]

        for post, source, event_date in upcoming_posts:
            days_until = (event_date - now).days
            if days_until == 0:
                time_desc = "**🔥 今天舉辦！**"
            elif days_until <= 7:
                time_desc = f"**⏰ 本週活動（還有 {days_until} 天）**"
            else:
                time_desc = f"還有 {days_until} 天"

            lines.extend([
                format_post_to_markdown(post, source, event_date),
                time_desc,
                "",
                "---",
                ""
            ])

        with open(upcoming_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"✅ 已生成：{upcoming_file}")
    else:
        print(f"\n⏭️  無近期活動，跳過生成 {upcoming_file}")

    return past_file if past_posts else None, upcoming_file if upcoming_posts else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="將 JSON 貼文資料按時間分類轉換為 Markdown（過去活動、近期活動）"
    )
    parser.add_argument(
        "--rag-dir",
        default="rag_data",
        help="RAG 資料目錄 (預設: rag_data)",
    )
    parser.add_argument(
        "--output-dir",
        help="輸出目錄 (預設: rag_data)",
    )

    args = parser.parse_args()

    rag_dir = Path(args.rag_dir)
    if not rag_dir.exists():
        print(f"❌ 錯誤：找不到 RAG 目錄：{rag_dir}")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else rag_dir

    print(f"\n🚀 開始處理...")
    print(f"   輸入目錄：{rag_dir}")
    print(f"   輸出目錄：{output_dir}\n")

    past_file, upcoming_file = generate_categorized_markdown(rag_dir, output_dir)

    if past_file or upcoming_file:
        print(f"\n✨ 完成！檔案已儲存至 {output_dir}")
        return 0
    else:
        print(f"\n⚠️  未生成任何檔案")
        return 1


if __name__ == "__main__":
    sys.exit(main())
