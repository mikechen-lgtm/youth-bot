"""
資料庫查詢工具模組 - 提供活動資料查詢功能供 AI 調用

此模組實現 OpenAI Function Calling 工具，用於從 MySQL 資料表查詢活動資料。
使用台北時區 (Asia/Taipei) 確保時間計算準確性。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# 台北時區
TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# 載入環境變數
load_dotenv()


def _build_mysql_url() -> str:
    """建立 MySQL 連接 URL"""
    if os.getenv("MYSQL_URL"):
        return os.getenv("MYSQL_URL")

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "youth-chat")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


_engine: Optional[Engine] = None


def _get_engine() -> Engine:
    """取得全域 SQLAlchemy engine（singleton）"""
    global _engine
    if _engine is None:
        mysql_url = _build_mysql_url()
        _engine = create_engine(
            mysql_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            connect_args={"charset": "utf8mb4"},
        )
    return _engine


def _today_start() -> datetime:
    """取得今天 00:00（台北時區），作為過去/未來活動的分界點"""
    now = datetime.now(TAIPEI_TZ)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _format_activity_result(row) -> Dict[str, Any]:
    """格式化單筆活動資料"""
    # 優先使用 event_date，若無則使用 publish_date
    effective_date = row[4] if row[4] else row[3]

    return {
        "source": row[0],
        "title": row[1],
        "content": row[2][:500] + "..." if row[2] and len(row[2]) > 500 else row[2],
        "publish_date": effective_date.strftime("%Y/%m/%d %H:%M") if effective_date else None,
        "url": row[5],
        "tags": json.loads(row[6]) if row[6] else [],
    }


def get_past_activities(days_back: int = 30, limit: int = 20) -> Dict[str, Any]:
    """
    獲取過去的活動（發布時間在今天之前）

    Args:
        days_back: 往前查詢的天數（預設 30 天）
        limit: 最多返回幾筆（預設 20 筆）

    Returns:
        包含活動列表、統計資訊的字典
    """
    try:
        engine = _get_engine()
        today = _today_start()
        start_date = today - timedelta(days=days_back)

        query = text("""
            SELECT
                source,
                title,
                content,
                publish_date,
                event_date,
                url,
                tags
            FROM fb_activities
            WHERE COALESCE(event_date, publish_date) < :today_start
              AND COALESCE(event_date, publish_date) >= :start_date
            ORDER BY COALESCE(event_date, publish_date) DESC
            LIMIT :limit
        """)

        with engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "today_start": today,
                    "start_date": start_date,
                    "limit": limit,
                }
            )
            rows = result.fetchall()

        activities = [_format_activity_result(row) for row in rows]

        return {
            "success": True,
            "query_type": "past_activities",
            "time_range": {
                "from": start_date.strftime("%Y/%m/%d"),
                "to": today.strftime("%Y/%m/%d"),
                "description": f"{start_date.strftime('%Y/%m/%d')} 到 {today.strftime('%Y/%m/%d')}（過去 {days_back} 天）"
            },
            "total_count": len(activities),
            "activities": activities,
        }

    except Exception as e:
        logger.error("查詢過去活動失敗: %s", e)
        return {
            "success": False,
            "error": str(e),
            "query_type": "past_activities",
        }


def get_recent_activities(days_ahead: int = 90, limit: int = 20) -> Dict[str, Any]:
    """
    獲取近期活動（發布時間在今天到未來 N 天內）

    Args:
        days_ahead: 往後查詢的天數（預設 90 天，約 3 個月）
        limit: 最多返回幾筆（預設 20 筆）

    Returns:
        包含活動列表、統計資訊的字典
    """
    try:
        engine = _get_engine()
        today = _today_start()
        end_date = today + timedelta(days=days_ahead)

        query = text("""
            SELECT
                source,
                title,
                content,
                publish_date,
                event_date,
                url,
                tags
            FROM fb_activities
            WHERE COALESCE(event_date, publish_date) >= :today_start
              AND COALESCE(event_date, publish_date) <= :end_date
            ORDER BY COALESCE(event_date, publish_date) ASC
            LIMIT :limit
        """)

        with engine.begin() as conn:
            result = conn.execute(
                query,
                {
                    "today_start": today,
                    "end_date": end_date,
                    "limit": limit,
                }
            )
            rows = result.fetchall()

        activities = [_format_activity_result(row) for row in rows]

        return {
            "success": True,
            "query_type": "recent_activities",
            "time_range": {
                "from": today.strftime("%Y/%m/%d"),
                "to": end_date.strftime("%Y/%m/%d"),
                "description": f"{today.strftime('%Y/%m/%d')} 到 {end_date.strftime('%Y/%m/%d')}（未來 {days_ahead} 天）"
            },
            "total_count": len(activities),
            "activities": activities,
        }

    except Exception as e:
        logger.error("查詢近期活動失敗: %s", e)
        return {
            "success": False,
            "error": str(e),
            "query_type": "recent_activities",
        }


def execute_database_tool(function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    統一的資料庫工具執行介面

    Args:
        function_name: 工具函數名稱
        arguments: 函數參數字典

    Returns:
        函數執行結果或錯誤資訊
    """
    tool_map = {
        "get_past_activities": lambda: get_past_activities(**arguments),
        "get_recent_activities": lambda: get_recent_activities(**arguments),
    }

    if function_name not in tool_map:
        return {
            "success": False,
            "error": f"未知的工具函數: {function_name}",
            "function_name": function_name,
            "arguments": arguments,
        }

    try:
        result = tool_map[function_name]()
        logger.info("執行資料庫工具成功: %s", function_name)
        return result
    except Exception as e:
        logger.error("執行資料庫工具失敗: %s, 錯誤: %s", function_name, e)
        return {
            "success": False,
            "error": str(e),
            "function_name": function_name,
            "arguments": arguments,
        }


# OpenAI Function Calling 工具定義
DATABASE_TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_past_activities",
            "description": (
                "查詢過去的活動（活動日期在今天之前）。"
                "用於回答「過去有什麼活動」「之前辦過什麼」等問題。"
                "優先使用活動日期（event_date），若無則使用發布日期（publish_date）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "往前查詢的天數，例如 30 表示過去 30 天",
                        "default": 30,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回幾筆活動",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_activities",
            "description": (
                "查詢近期活動（活動日期在今天到未來 N 天內）。"
                "用於回答「最近有什麼活動」「近期活動」「接下來有什麼」等問題。"
                "🔴 重要：這是查詢「未來活動」的主要工具，當用戶問近期/最近活動時必須使用。"
                "優先使用活動日期（event_date），若無則使用發布日期（publish_date）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "往後查詢的天數，例如 90 表示未來 3 個月",
                        "default": 90,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回幾筆活動",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
]

__all__ = [
    "get_past_activities",
    "get_recent_activities",
    "execute_database_tool",
    "DATABASE_TOOLS_DEFINITIONS",
]
