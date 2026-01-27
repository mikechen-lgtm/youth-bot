"""
从 fb_activities 资料表导出活动数据供 RAG 使用
可以输出为文本或直接返回格式化字符串
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import text

# 载入环境变数
load_dotenv()
load_dotenv(".env.local")

from json_to_database import create_engine_instance


def get_activities_from_db(
    days_ahead: int = 90,
    include_past: bool = False,
    source_filter: Optional[str] = None
) -> list:
    """从资料表获取活动数据

    Args:
        days_ahead: 查询未来多少天的活动（预设 90 天）
        include_past: 是否包含过去的活动
        source_filter: 来源过滤（可选）

    Returns:
        活动列表
    """
    engine = create_engine_instance()

    # 构建查询条件
    conditions = []
    params = {"days_ahead": days_ahead}

    if not include_past:
        conditions.append("event_date >= CURDATE()")

    if include_past and not days_ahead:
        # 如果要包含过去且不限制未来，则不加时间限制
        pass
    else:
        conditions.append("event_date <= DATE_ADD(CURDATE(), INTERVAL :days_ahead DAY)")

    if source_filter:
        conditions.append("source = :source")
        params["source"] = source_filter

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
    SELECT
        id, source, title, content,
        event_date, event_time, deadline,
        location, location_address, target,
        url, registration_url, info_url,
        tags, focus_areas, categories
    FROM fb_activities
    {where_clause}
    ORDER BY event_date ASC
    """

    with engine.begin() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result.fetchall()]


def format_activity_as_markdown(activity: dict) -> str:
    """将单个活动格式化为 Markdown"""
    lines = []

    # 标题
    lines.append(f"## {activity['title']}\n")

    # 元数据
    lines.append(f"**来源**：{activity['source']}")
    lines.append(f"**活动日期**：{activity['event_date']}")

    if activity.get('event_time'):
        lines.append(f"**活动时间**：{activity['event_time']}")

    if activity.get('deadline'):
        lines.append(f"**报名截止**：{activity['deadline']}")

    if activity.get('location'):
        location = activity['location']
        if activity.get('location_address'):
            location += f" ({activity['location_address']})"
        lines.append(f"**地点**：{location}")

    if activity.get('target'):
        lines.append(f"**适用对象**：{activity['target']}")

    lines.append("")  # 空行

    # 内容
    if activity.get('content'):
        lines.append(activity['content'])
        lines.append("")

    # 连结
    if activity.get('registration_url'):
        lines.append(f"[报名连结]({activity['registration_url']})")

    if activity.get('info_url'):
        lines.append(f"[详细资讯]({activity['info_url']})")

    if activity.get('url'):
        lines.append(f"[原文连结]({activity['url']})")

    lines.append("\n---\n")

    return "\n".join(lines)


def export_activities_text(
    days_ahead: int = 90,
    include_past: bool = False,
    output_file: Optional[str] = None
) -> str:
    """导出活动为文本格式"""

    activities = get_activities_from_db(
        days_ahead=days_ahead,
        include_past=include_past
    )

    if not activities:
        return "# 活动资讯\n\n目前没有查询到相关活动。\n"

    # 生成标题
    now = datetime.now()
    if include_past:
        title = f"# 桃园市政府青年事务局 - 所有活动\n\n"
    else:
        future_date = now + timedelta(days=days_ahead)
        title = f"# 桃园市政府青年事务局 - 近期活动\n\n"
        title += f"**资料更新时间**：{now.strftime('%Y/%m/%d %H:%M')}\n"
        title += f"**活动数量**：{len(activities)} 个\n"
        title += f"**时间范围**：{now.strftime('%Y/%m/%d')} ~ {future_date.strftime('%Y/%m/%d')}\n\n"
        title += "---\n\n"

    # 格式化所有活动
    content = title
    for activity in activities:
        content += format_activity_as_markdown(activity)

    # 写入文件（如果指定）
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ 已导出到：{output_file}")
        print(f"  活动数量：{len(activities)}")

    return content


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从资料表导出活动数据供 RAG 使用"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="查询未来多少天的活动（预设：90）"
    )
    parser.add_argument(
        "--include-past",
        action="store_true",
        help="包含过去的活动"
    )
    parser.add_argument(
        "--output",
        help="输出档案路径（选填，不指定则输出到标准输出）"
    )
    parser.add_argument(
        "--source",
        help="过滤特定来源（选填）"
    )

    args = parser.parse_args()

    try:
        content = export_activities_text(
            days_ahead=args.days,
            include_past=args.include_past,
            output_file=args.output
        )

        # 如果没有指定输出档案，则输出到标准输出
        if not args.output:
            print(content)

        return 0

    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
