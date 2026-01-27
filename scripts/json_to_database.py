"""
将 RAG 资料夹中的 JSON 档案汇入 MySQL 资料表
资料表栏位直接对应 JSON 字段，不进行额外解析

使用方法：
    python scripts/json_to_database.py --rag-dir rag_data
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from zoneinfo import ZoneInfo

# 载入环境变数
load_dotenv()
load_dotenv(".env.local")

# 设定日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _build_mysql_url() -> str:
    """建立 MySQL 连接 URL"""
    if os.getenv("MYSQL_URL"):
        return os.getenv("MYSQL_URL")

    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "youth-chat")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


def create_engine_instance() -> Engine:
    """创建 SQLAlchemy engine"""
    mysql_url = _build_mysql_url()
    return create_engine(
        mysql_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        connect_args={"charset": "utf8mb4"},
    )


def ensure_activities_table(engine: Engine) -> None:
    """确保 fb_activities 资料表存在（简化版，只包含 JSON 实际字段）"""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS fb_activities (
        id INT AUTO_INCREMENT PRIMARY KEY COMMENT '资料表主键',
        source VARCHAR(100) NOT NULL COMMENT '来源（从档名提取）',
        post_id INT COMMENT 'JSON 中的 post ID',
        title VARCHAR(500) NOT NULL COMMENT '标题',
        content TEXT COMMENT '内容',
        publish_date DATETIME COMMENT '发布日期',
        url VARCHAR(1000) COMMENT '原文连结',
        tags JSON COMMENT '标签（JSON 阵列）',
        retrieval_time DATETIME COMMENT '爬取时间',
        raw_data JSON COMMENT '完整原始资料（JSON）',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_source (source),
        INDEX idx_title (title(100)),
        INDEX idx_publish_date (publish_date),
        UNIQUE KEY unique_post (source, post_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='Facebook 贴文资料表（对应 JSON 字段）'
    """

    with engine.begin() as conn:
        conn.execute(text(create_table_sql))

    logger.info("✓ 资料表 'fb_activities' 已确保存在")


def parse_datetime(date_str: str) -> Optional[datetime]:
    """解析日期时间字串"""
    if not date_str:
        return None

    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.astimezone(TAIPEI_TZ)
    except (ValueError, TypeError):
        pass

    return None


def prepare_activity_data(post: dict, source: str) -> Dict[str, Any]:
    """准备要插入资料表的活动资料（直接对应 JSON 字段）"""
    # 解析日期时间
    publish_date = parse_datetime(post.get("publish_date"))
    retrieval_time = parse_datetime(post.get("retrieval_time"))

    # 准备 JSON 栏位
    tags = json.dumps(post.get("tags"), ensure_ascii=False) if post.get("tags") else None
    raw_data = json.dumps(post, ensure_ascii=False)

    return {
        "source": source,
        "post_id": post.get("id"),
        "title": post.get("title", "无标题")[:500],
        "content": (post.get("content") or "").strip(),
        "publish_date": publish_date,
        "url": post.get("url"),
        "tags": tags,
        "retrieval_time": retrieval_time,
        "raw_data": raw_data,
    }


def insert_activity(engine: Engine, activity_data: Dict[str, Any]) -> bool:
    """插入或更新活动资料"""
    insert_sql = """
    INSERT INTO fb_activities (
        source, post_id, title, content, publish_date, url, tags, retrieval_time, raw_data
    ) VALUES (
        :source, :post_id, :title, :content, :publish_date, :url, :tags, :retrieval_time, :raw_data
    )
    ON DUPLICATE KEY UPDATE
        title = VALUES(title),
        content = VALUES(content),
        publish_date = VALUES(publish_date),
        url = VALUES(url),
        tags = VALUES(tags),
        retrieval_time = VALUES(retrieval_time),
        raw_data = VALUES(raw_data),
        updated_at = CURRENT_TIMESTAMP
    """

    try:
        with engine.begin() as conn:
            conn.execute(text(insert_sql), activity_data)
        return True
    except Exception as e:
        logger.error(f"插入活动失败: {activity_data.get('title')[:50]} - {e}")
        return False


def process_json_files(rag_dir: Path, engine: Engine) -> Dict[str, int]:
    """处理所有 JSON 档案"""
    json_files = list(rag_dir.glob("FB-POST-*.json"))

    stats = {
        "total_files": len(json_files),
        "total_posts": 0,
        "imported": 0,
        "failed": 0,
    }

    logger.info(f"📂 找到 {len(json_files)} 个 JSON 档案")

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "posts" not in data:
                logger.info(f"  ⏭️  跳过 {json_path.name}（不包含 posts）")
                continue

            source = data.get("source", json_path.stem)
            posts = data.get("posts", [])
            stats["total_posts"] += len(posts)

            logger.info(f"\n处理来源：{source}（{len(posts)} 个贴文）")

            for post in posts:
                title = post.get("title", "无标题")[:50]

                # 准备活动资料
                activity_data = prepare_activity_data(post, source)

                # 插入资料库
                if insert_activity(engine, activity_data):
                    stats["imported"] += 1
                    post_id = post.get("id", "N/A")
                    logger.info(f"  ✓ [{post_id}] {title}")
                else:
                    stats["failed"] += 1

        except json.JSONDecodeError as e:
            logger.error(f"  ❌ JSON 解析错误 {json_path.name}: {e}")
            stats["failed"] += 1
        except Exception as e:
            logger.error(f"  ❌ 处理错误 {json_path.name}: {e}")
            stats["failed"] += 1

    return stats


def print_statistics(stats: Dict[str, int]) -> None:
    """列印统计资讯"""
    print("\n" + "="*60)
    print("📊 汇入统计")
    print("="*60)
    print(f"处理档案数：{stats['total_files']}")
    print(f"贴文总数：{stats['total_posts']}")
    print(f"✅ 成功汇入：{stats['imported']}")
    print(f"❌ 失败：{stats['failed']}")
    print("="*60)


def query_activities_summary(engine: Engine) -> None:
    """查询并显示活动资料摘要"""
    summary_sql = """
    SELECT
        source,
        COUNT(*) as total,
        MIN(publish_date) as earliest,
        MAX(publish_date) as latest
    FROM fb_activities
    GROUP BY source
    ORDER BY source
    """

    print("\n" + "="*80)
    print("📋 资料表摘要")
    print("="*80)

    with engine.begin() as conn:
        result = conn.execute(text(summary_sql))
        rows = result.fetchall()

        if not rows:
            print("资料表为空")
            return

        print(f"{'来源':<40} {'总数':>10} {'最早发布':>20} {'最晚发布':>20}")
        print("-"*80)

        total_all = 0

        for row in rows:
            source, total, earliest, latest = row
            total_all += total

            earliest_str = earliest.strftime("%Y-%m-%d") if earliest else "N/A"
            latest_str = latest.strftime("%Y-%m-%d") if latest else "N/A"

            print(f"{source:<40} {total:>10} {earliest_str:>20} {latest_str:>20}")

        print("-"*80)
        print(f"{'总计':<40} {total_all:>10}")

    print("="*80)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将 JSON 贴文资料汇入 MySQL 资料表（对应 JSON 字段）"
    )
    parser.add_argument(
        "--rag-dir",
        default="rag_data",
        help="RAG 资料目录（预设: rag_data）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式（不实际写入资料库）",
    )

    args = parser.parse_args()

    rag_dir = Path(args.rag_dir)
    if not rag_dir.exists():
        logger.error(f"❌ 错误：找不到 RAG 目录：{rag_dir}")
        return 1

    if args.dry_run:
        logger.info("🔍 试运行模式（不会写入资料库）")
        return 0

    try:
        # 创建资料库连线
        logger.info("🔗 连接资料库...")
        engine = create_engine_instance()

        # 确保资料表存在
        ensure_activities_table(engine)

        # 处理 JSON 档案
        logger.info(f"\n🚀 开始处理...")
        logger.info(f"   输入目录：{rag_dir}\n")

        stats = process_json_files(rag_dir, engine)

        # 列印统计
        print_statistics(stats)

        # 显示资料表摘要
        query_activities_summary(engine)

        logger.info("\n✨ 完成！")
        return 0

    except Exception as e:
        logger.error(f"\n❌ 执行失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
