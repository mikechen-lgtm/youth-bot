#!/usr/bin/env python3
"""驗證所有優化項目的腳本"""

import sys
import os

print("=" * 70)
print("🔍 驗證聊天機器人優化項目")
print("=" * 70)
print()

# 測試1: 驗證時間工具模組
print("1️⃣ 測試時間工具模組...")
try:
    from time_tools import (
        get_current_time_info,
        calculate_date_range,
        TIME_TOOLS_DEFINITIONS,
        TAIPEI_TZ
    )
    print("   ✅ time_tools 模組導入成功")

    # 測試函數
    current_time = get_current_time_info()
    print(f"   ✅ get_current_time_info(): {current_time['current_date']}")

    date_range = calculate_date_range("today", 0, 90)
    print(f"   ✅ calculate_date_range(): {date_range['start_date']} 到 {date_range['end_date']}")

    print(f"   ✅ TIME_TOOLS_DEFINITIONS: {len(TIME_TOOLS_DEFINITIONS)} 個工具")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    sys.exit(1)

print()

# 測試2: 驗證 OpenAI Service
print("2️⃣ 測試 OpenAI Service 整合...")
try:
    from openai_service import (
        TIME_TOOLS_AVAILABLE,
        _process_function_calls,
        _stream_rag_response
    )

    if TIME_TOOLS_AVAILABLE:
        print("   ✅ 時間工具在 openai_service 中可用")
    else:
        print("   ⚠️  時間工具在 openai_service 中不可用")

    print("   ✅ _process_function_calls 函數存在")
    print("   ✅ _stream_rag_response 函數存在")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print()

# 測試3: 驗證 RAG 數據結構
print("3️⃣ 測試 RAG 數據結構...")
try:
    from scripts.convert_json_to_markdown import (
        extract_event_date_from_content,
        calculate_activity_status,
        DATE_PATTERNS,
        STATUS_CONFIG
    )

    print("   ✅ 日期提取函數存在")
    print(f"   ✅ 支援 {len(DATE_PATTERNS)} 種日期格式")
    print(f"   ✅ 定義了 {len(STATUS_CONFIG)} 個活動狀態")

    # 測試日期提取
    test_content = "活動日期：2026/01/27"
    date, source = extract_event_date_from_content(test_content)
    print(f"   ✅ 日期提取測試: '{test_content}' → {date}")

    # 測試狀態計算
    status, days, desc = calculate_activity_status("2026/02/15")
    print(f"   ✅ 狀態計算測試: 2026/02/15 → {desc}")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print()

# 測試4: 驗證環境配置
print("4️⃣ 檢查環境配置...")
try:
    from dotenv import load_dotenv
    load_dotenv()

    enable_fc = os.getenv("ENABLE_FUNCTION_CALLING", "false").lower()
    print(f"   {'✅' if enable_fc == 'true' else '⚠️ '} ENABLE_FUNCTION_CALLING={enable_fc}")

    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    print(f"   ✅ OPENAI_MODEL={openai_model}")

    rag_store = os.getenv("RAG_VECTOR_STORE_ID", "未設定")
    print(f"   {'✅' if rag_store != '未設定' else '⚠️ '} RAG_VECTOR_STORE_ID={'已設定' if rag_store != '未設定' else '未設定'}")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print()

# 測試5: 檢查 RAG 數據文件
print("5️⃣ 檢查 RAG 數據文件...")
try:
    from pathlib import Path

    rag_dir = Path("rag_data")
    if rag_dir.exists():
        md_files = list(rag_dir.glob("*.md"))
        json_files = list(rag_dir.glob("*.json"))

        print(f"   ✅ Markdown 文件: {len(md_files)} 個")
        print(f"   ✅ JSON 文件: {len(json_files)} 個")

        # 檢查一個 Markdown 文件的結構
        if md_files:
            sample_md = md_files[0]
            content = sample_md.read_text(encoding="utf-8")

            has_date = "活動日期：" in content
            has_status = "活動狀態：" in content
            has_standard_format = "2026/" in content or "2025/" in content

            print(f"   {'✅' if has_date else '❌'} 包含活動日期標記")
            print(f"   {'✅' if has_status else '❌'} 包含活動狀態標記")
            print(f"   {'✅' if has_standard_format else '❌'} 使用標準日期格式")
    else:
        print("   ⚠️  rag_data 目錄不存在")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print()
print("=" * 70)
print("✅ 驗證完成")
print("=" * 70)
