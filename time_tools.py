"""
時間工具模組 - 提供精確的時間計算功能供 AI 調用

此模組實現 OpenAI Function Calling 工具，用於處理活動查詢中的時間相關邏輯。
使用台北時區 (Asia/Taipei) 確保時間計算準確性。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# 台北時區
TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# 中文星期對應
WEEKDAY_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

# 支援的日期格式
DATE_FORMATS = ("%Y/%m/%d", "%Y-%m-%d")


def get_current_time_info() -> Dict[str, Any]:
    """
    獲取當前時間資訊（台北時區）

    Returns:
        包含當前日期、昨天、明天及常用時間範圍的字典
    """
    now = datetime.now(TAIPEI_TZ)
    fmt = "%Y/%m/%d"

    return {
        "current_date": now.strftime(fmt),
        "current_datetime": now.strftime(f"{fmt} %H:%M:%S"),
        "yesterday": (now - timedelta(days=1)).strftime(fmt),
        "tomorrow": (now + timedelta(days=1)).strftime(fmt),
        "one_week_later": (now + timedelta(days=7)).strftime(fmt),
        "one_month_later": (now + timedelta(days=30)).strftime(fmt),
        "three_months_later": (now + timedelta(days=90)).strftime(fmt),
        "weekday": WEEKDAY_ZH[now.weekday()],
        "timezone": "Asia/Taipei",
    }


def _parse_base_date(base_date: str, now: datetime) -> datetime:
    """解析基準日期字串為 datetime 物件"""
    if base_date == "today":
        return now
    if base_date == "yesterday":
        return now - timedelta(days=1)

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(base_date, fmt).replace(tzinfo=TAIPEI_TZ)
        except ValueError:
            continue

    raise ValueError(f"無法解析日期格式: {base_date}")


def _generate_range_description(start_offset: int, end_offset: int, start_dt: datetime, end_dt: datetime) -> str:
    """生成日期範圍的中文描述"""
    if start_offset == 0 and end_offset > 0:
        return f"今天起{end_offset}天內"
    if start_offset < 0 and end_offset == 0:
        return f"過去{abs(start_offset)}天"
    if start_offset < 0 < end_offset:
        return f"過去{abs(start_offset)}天到未來{end_offset}天"
    return f"{start_dt.strftime('%Y/%m/%d')} 到 {end_dt.strftime('%Y/%m/%d')}"


def calculate_date_range(
    base_date: str = "today",
    start_offset_days: int = 0,
    end_offset_days: int = 0,
) -> Dict[str, Any]:
    """
    計算時間範圍

    Args:
        base_date: 基準日期 ("today", "yesterday", 或 "YYYY/MM/DD")
        start_offset_days: 起始偏移天數（負=過去，正=未來）
        end_offset_days: 結束偏移天數

    Returns:
        包含 base_date, start_date, end_date, description, days_in_range 的字典
    """
    now = datetime.now(TAIPEI_TZ)
    base_dt = _parse_base_date(base_date, now)

    start_dt = base_dt + timedelta(days=start_offset_days)
    end_dt = base_dt + timedelta(days=end_offset_days)

    # 確保起始日期早於結束日期
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    fmt = "%Y/%m/%d"
    return {
        "base_date": base_dt.strftime(fmt),
        "start_date": start_dt.strftime(fmt),
        "end_date": end_dt.strftime(fmt),
        "description": _generate_range_description(start_offset_days, end_offset_days, start_dt, end_dt),
        "days_in_range": (end_dt - start_dt).days + 1,
    }


def parse_date_string(date_str: str) -> Optional[datetime]:
    """
    解析日期字符串為 datetime 物件

    支援格式：
    - YYYY/MM/DD 或 YYYY-MM-DD
    - 民國年：115年1月23日
    - 月日：1月24日（自動推斷年份）
    """
    if not date_str:
        return None

    # 格式1: YYYY/MM/DD 或 YYYY-MM-DD
    match = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', date_str)
    if match:
        year, month, day = map(int, match.groups())
        try:
            return datetime(year, month, day, tzinfo=TAIPEI_TZ)
        except ValueError:
            pass

    # 格式2: 民國年 (115年1月23日)
    match = re.search(r'(\d{3})年(\d{1,2})月(\d{1,2})日', date_str)
    if match:
        roc_year, month, day = map(int, match.groups())
        try:
            return datetime(roc_year + 1911, month, day, tzinfo=TAIPEI_TZ)
        except ValueError:
            pass

    # 格式3: 月日 (1月24日)，推斷年份
    match = re.search(r'(\d{1,2})月(\d{1,2})日', date_str)
    if match:
        month, day = map(int, match.groups())
        now = datetime.now(TAIPEI_TZ)
        try:
            date = datetime(now.year, month, day, tzinfo=TAIPEI_TZ)
            # 如果日期已過，推斷為明年
            if date < now:
                date = datetime(now.year + 1, month, day, tzinfo=TAIPEI_TZ)
            return date
        except ValueError:
            pass

    return None


def execute_time_tool(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    統一的時間工具執行介面

    Args:
        function_name: 工具函數名稱
        arguments: 函數參數字典

    Returns:
        函數執行結果或錯誤資訊
    """
    tool_map = {
        "get_current_time_info": lambda: get_current_time_info(),
        "calculate_date_range": lambda: calculate_date_range(**arguments),
    }

    if function_name not in tool_map:
        return {
            "error": f"未知的工具函數: {function_name}",
            "function_name": function_name,
            "arguments": arguments,
        }

    try:
        result = tool_map[function_name]()
        logger.info("執行時間工具成功: %s", function_name)
        return result
    except Exception as e:
        logger.error("執行時間工具失敗: %s, 錯誤: %s", function_name, e)
        return {
            "error": str(e),
            "function_name": function_name,
            "arguments": arguments,
        }


# OpenAI Function Calling 工具定義
TIME_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time_info",
            "description": (
                "Get current time in Taipei timezone. Returns today, yesterday, tomorrow, "
                "and common date ranges. Use for 'now', 'recent', 'upcoming' queries."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_date_range",
            "description": (
                "Calculate date range from base date with day offsets. "
                "Examples: 'next 3 months' = (0, 90), 'past week' = (-7, 0)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "base_date": {
                        "type": "string",
                        "description": "Base date: 'today', 'yesterday', or 'YYYY/MM/DD'",
                        "default": "today",
                    },
                    "start_offset_days": {
                        "type": "integer",
                        "description": "Start offset in days (negative=past, positive=future)",
                        "default": 0,
                    },
                    "end_offset_days": {
                        "type": "integer",
                        "description": "End offset in days (same convention)",
                        "default": 0,
                    },
                },
                "required": [],
            },
        },
    },
]

__all__ = [
    "get_current_time_info",
    "calculate_date_range",
    "parse_date_string",
    "execute_time_tool",
    "TIME_TOOLS_DEFINITIONS",
    "TAIPEI_TZ",
]
