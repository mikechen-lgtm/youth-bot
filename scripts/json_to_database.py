"""
将 RAG 资料夹中的 JSON 档案汇入 MySQL 资料表
资料表栏位直接对应 JSON 字段，不进行额外解析

使用方法：
    python scripts/json_to_database.py --rag-dir rag_data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
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


def extract_facebook_id(url: str) -> Optional[str]:
    """
    從 Facebook URL 提取真實的 Post ID

    支援的格式：
    1. pfbid 格式：https://www.facebook.com/.../posts/pfbid0abc123...
    2. reel 格式：https://www.facebook.com/reel/123456789/
    3. posts 數字格式：https://www.facebook.com/.../posts/123456789
    """
    if not url:
        return None

    match = re.search(r'pfbid[0-9a-zA-Z]+', url)
    if match:
        return match.group(0)

    match = re.search(r'/reel/(\d+)', url)
    if match:
        return f"reel_{match.group(1)}"

    match = re.search(r'/posts/(\d+)', url)
    if match:
        return f"post_{match.group(1)}"

    return None


def resolve_post_id(post: dict, source: str) -> str:
    """
    決定貼文的唯一 post_id

    優先順序：
    1. JSON id 已經是 pfbid/reel_/post_ 字串 → 直接使用
    2. 從 URL 提取 Facebook ID
    3. Fallback: 用 source + url 產生確定性 hash
    """
    json_id = post.get("id")

    if isinstance(json_id, str) and (
        json_id.startswith("pfbid")
        or json_id.startswith("reel_")
        or json_id.startswith("post_")
    ):
        return json_id

    url = post.get("url", "")
    fb_id = extract_facebook_id(url)
    if fb_id:
        return fb_id

    hash_input = f"{source}:{url or post.get('title', '')}"
    short_hash = hashlib.md5(hash_input.encode("utf-8")).hexdigest()[:16]
    logger.warning(
        f"無法從 URL 提取 Facebook ID: '{post.get('title', '?')[:40]}', "
        f"使用 fallback hash: fallback_{short_hash}"
    )
    return f"fallback_{short_hash}"


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
        post_id VARCHAR(200) COMMENT 'Facebook 贴文 ID（pfbid 或数字字串）',
        title VARCHAR(500) NOT NULL COMMENT '标题',
        content TEXT COMMENT '内容',
        publish_date DATETIME COMMENT '发布日期',
        event_date DATETIME COMMENT '活動日期（從內容提取）',
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

    # 迁移：如果 post_id 仍是 INT 类型，改为 VARCHAR(200)
    migrate_sql = """
    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'fb_activities'
      AND COLUMN_NAME = 'post_id'
    """
    with engine.begin() as conn:
        result = conn.execute(text(migrate_sql))
        row = result.fetchone()
        if row and row[0].lower() == "int":
            logger.info("⚡ 检测到 post_id 为 INT，正在迁移为 VARCHAR(200)...")
            conn.execute(text("ALTER TABLE fb_activities DROP INDEX unique_post"))
            conn.execute(text(
                "ALTER TABLE fb_activities MODIFY COLUMN post_id VARCHAR(200) "
                "COMMENT 'Facebook 贴文 ID（pfbid 或数字字串）'"
            ))
            conn.execute(text(
                "ALTER TABLE fb_activities ADD UNIQUE KEY unique_post (source, post_id)"
            ))
            logger.info("✓ post_id 已迁移为 VARCHAR(200)")

    # 迁移：新增 event_date 欄位（如果不存在）
    check_event_date_sql = """
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'fb_activities'
      AND COLUMN_NAME = 'event_date'
    """
    with engine.begin() as conn:
        result = conn.execute(text(check_event_date_sql))
        row = result.fetchone()
        if row and row[0] == 0:
            logger.info("⚡ 新增 event_date 欄位...")
            conn.execute(text(
                "ALTER TABLE fb_activities ADD COLUMN event_date DATETIME "
                "COMMENT '活動日期（從內容提取）' AFTER publish_date"
            ))
            conn.execute(text(
                "CREATE INDEX idx_event_date ON fb_activities (event_date)"
            ))
            logger.info("✓ event_date 欄位與索引已新增")

    logger.info("✓ 资料表 'fb_activities' 已确保存在")


def clear_activities_table(engine: Engine) -> None:
    """清空 fb_activities 资料表（用于完全重建）"""
    truncate_sql = "TRUNCATE TABLE fb_activities"

    with engine.begin() as conn:
        conn.execute(text(truncate_sql))

    logger.info("✓ 资料表 'fb_activities' 已清空")


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


def extract_event_date(content: str, publish_date: Optional[datetime] = None) -> Optional[datetime]:
    """
    從貼文內容中提取活動日期

    使用 regex 解析常見的中文日期格式，回傳最早且 >= publish_date 的日期。
    若無未來日期，回傳所有候選中最早的日期。無法提取時回傳 None。

    支援格式：
    - 民國年全稱：115年02月11日
    - 民國年斜線：115/03/01
    - 西元年：2026/02/11
    - 中文月日：2月11日（從 publish_date 推斷年份）
    - MM/DD(星期)：02/11(三)（從 publish_date 推斷年份）
    """
    if not content:
        return None

    candidates = []
    ref_year = publish_date.year if publish_date else datetime.now(TAIPEI_TZ).year

    # Pattern 1: 民國年全稱 — 115年02月11日 or 115年2月11日
    for m in re.finditer(r'(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', content):
        try:
            year = int(m.group(1)) + 1911
            month = int(m.group(2))
            day = int(m.group(3))
            if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                candidates.append(datetime(year, month, day, tzinfo=TAIPEI_TZ))
        except (ValueError, OverflowError):
            continue

    # Pattern 2: 民國年斜線 — 115/03/01（首段 100~200 才視為民國年）
    for m in re.finditer(r'(?<!\d)(\d{3})/(\d{1,2})/(\d{1,2})(?!\d)', content):
        try:
            roc_year = int(m.group(1))
            if 100 <= roc_year <= 200:
                year = roc_year + 1911
                month = int(m.group(2))
                day = int(m.group(3))
                if 1 <= month <= 12 and 1 <= day <= 31:
                    candidates.append(datetime(year, month, day, tzinfo=TAIPEI_TZ))
        except (ValueError, OverflowError):
            continue

    # Pattern 3: 西元年 — 2026/02/11 or 2026/2/11
    for m in re.finditer(r'(?<!\d)(20\d{2})/(\d{1,2})/(\d{1,2})(?!\d)', content):
        try:
            year = int(m.group(1))
            month = int(m.group(2))
            day = int(m.group(3))
            if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                candidates.append(datetime(year, month, day, tzinfo=TAIPEI_TZ))
        except (ValueError, OverflowError):
            continue

    # Pattern 4: 中文月日（無年份）— 2月11日 or 11月15日
    # 排除已被 Pattern 1 匹配的（前面有「年」字）
    for m in re.finditer(r'(?<!\d)(?<!年)(\d{1,2})\s*月\s*(\d{1,2})\s*日', content):
        try:
            month = int(m.group(1))
            day = int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                dt = datetime(ref_year, month, day, tzinfo=TAIPEI_TZ)
                # 若比 publish_date 早超過 60 天，可能是跨年，試 +1 年
                if publish_date and (publish_date - dt).days > 60:
                    dt = datetime(ref_year + 1, month, day, tzinfo=TAIPEI_TZ)
                candidates.append(dt)
        except (ValueError, OverflowError):
            continue

    # Pattern 5: MM/DD(星期) — 02/11(三) or 6/3(二)
    for m in re.finditer(r'(?<!\d)(\d{1,2})/(\d{1,2})\s*[\(（][一二三四五六日][\)）]', content):
        try:
            month = int(m.group(1))
            day = int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                dt = datetime(ref_year, month, day, tzinfo=TAIPEI_TZ)
                if publish_date and (publish_date - dt).days > 60:
                    dt = datetime(ref_year + 1, month, day, tzinfo=TAIPEI_TZ)
                candidates.append(dt)
        except (ValueError, OverflowError):
            continue

    if not candidates:
        return None

    # 去重
    candidates = list(set(candidates))

    # 優先選取 >= publish_date 的最早日期
    if publish_date:
        pub_date_naive = publish_date.replace(hour=0, minute=0, second=0, microsecond=0)
        future_dates = [d for d in candidates if d >= pub_date_naive]
        if future_dates:
            return min(future_dates)

    # 沒有未來日期，回傳最早的日期
    return min(candidates)


def prepare_activity_data(post: dict, source: str) -> Dict[str, Any]:
    """准备要插入资料表的活动资料（直接对应 JSON 字段）"""
    # 解析日期时间
    publish_date = parse_datetime(post.get("publish_date"))
    retrieval_time = parse_datetime(post.get("retrieval_time"))

    # 從內容提取活動日期
    content = (post.get("content") or "").strip()
    event_date = extract_event_date(content, publish_date)

    # 准备 JSON 栏位
    tags = json.dumps(post.get("tags"), ensure_ascii=False) if post.get("tags") else None
    raw_data = json.dumps(post, ensure_ascii=False)

    # 使用 resolve_post_id 取得正确的 Facebook 贴文 ID
    post_id = resolve_post_id(post, source)

    return {
        "source": source,
        "post_id": post_id,
        "title": post.get("title", "无标题")[:500],
        "content": content,
        "publish_date": publish_date,
        "event_date": event_date,
        "url": post.get("url"),
        "tags": tags,
        "retrieval_time": retrieval_time,
        "raw_data": raw_data,
    }


def insert_activity(engine: Engine, activity_data: Dict[str, Any]) -> bool:
    """插入或更新活动资料"""
    insert_sql = """
    INSERT INTO fb_activities (
        source, post_id, title, content, publish_date, event_date, url, tags, retrieval_time, raw_data
    ) VALUES (
        :source, :post_id, :title, :content, :publish_date, :event_date, :url, :tags, :retrieval_time, :raw_data
    )
    ON DUPLICATE KEY UPDATE
        title = VALUES(title),
        content = VALUES(content),
        publish_date = VALUES(publish_date),
        event_date = VALUES(event_date),
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

    # 按照档名正序排序，确保较新的档案后处理（避免旧资料覆盖新资料）
    # 档名格式：FB-POST-来源-YYYYMMDD.json（统一使用西元年）
    # - 20260121 < 20260129（字母顺序 = 时间顺序）
    # 正序后：20260121 档案先处理，20260129 档案后处理（新资料覆盖旧资料）
    json_files.sort(key=lambda x: x.name)

    stats = {
        "total_files": len(json_files),
        "total_posts": 0,
        "imported": 0,
        "failed": 0,
    }

    logger.info(f"📂 找到 {len(json_files)} 个 JSON 档案")
    logger.info(f"📋 处理顺序（按档名正序排列，确保新档案后处理）：")
    for i, f in enumerate(json_files, 1):
        logger.info(f"  {i}. {f.name}")

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
                title = (post.get("title") or "").strip()
                content = (post.get("content") or "").strip()

                # 跳過標題和內容都為空的貼文
                if not title and not content:
                    logger.info(f"  ⏭️  跳過空貼文 (id={post.get('id', 'N/A')})")
                    continue

                title_display = title[:50] or content[:50]

                # 准备活动资料
                activity_data = prepare_activity_data(post, source)

                # 插入资料库
                if insert_activity(engine, activity_data):
                    stats["imported"] += 1
                    post_id = post.get("id", "N/A")
                    logger.info(f"  ✓ [{post_id}] {title_display}")
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
        MAX(publish_date) as latest,
        SUM(CASE WHEN event_date IS NOT NULL THEN 1 ELSE 0 END) as with_event_date
    FROM fb_activities
    GROUP BY source
    ORDER BY source
    """

    print("\n" + "="*100)
    print("📋 资料表摘要")
    print("="*100)

    with engine.begin() as conn:
        result = conn.execute(text(summary_sql))
        rows = result.fetchall()

        if not rows:
            print("资料表为空")
            return

        print(f"{'来源':<40} {'总数':>6} {'有活動日期':>10} {'最早发布':>14} {'最晚发布':>14}")
        print("-"*100)

        total_all = 0
        total_event_date = 0

        for row in rows:
            source, total, earliest, latest, with_event_date = row
            total_all += total
            total_event_date += with_event_date

            earliest_str = earliest.strftime("%Y-%m-%d") if earliest else "N/A"
            latest_str = latest.strftime("%Y-%m-%d") if latest else "N/A"

            print(f"{source:<40} {total:>6} {with_event_date:>10} {earliest_str:>14} {latest_str:>14}")

        print("-"*100)
        print(f"{'总计':<40} {total_all:>6} {total_event_date:>10}")

    print("="*100)


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
    parser.add_argument(
        "--clear-table",
        action="store_true",
        help="清空资料表后再汇入（用于完全重建）",
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

        # 如果需要清空表
        if args.clear_table:
            logger.info("🗑️  清空现有资料...")
            clear_activities_table(engine)

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
