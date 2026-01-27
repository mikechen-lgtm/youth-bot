#!/usr/bin/env python3
"""
端到端測試：聊天機器人時間處理功能

測試場景：
1. 未來活動查詢（「最近有什麼活動？」）
2. 過去活動查詢（「上個月辦了哪些活動？」）
3. 無活動回覆（「明年有什麼活動？」）
4. 非時間查詢（「青創基地在哪裡？」）
"""

import json
import requests
import time
from typing import Dict, List

# API 配置
API_BASE_URL = "http://localhost:8300"
API_ENDPOINT = f"{API_BASE_URL}/api/chat"

# 測試顏色輸出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test_header(test_name: str):
    """打印測試標題"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}測試：{test_name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    """打印錯誤消息"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message: str):
    """打印警告消息"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message: str):
    """打印信息"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def send_chat_request(query: str, session_id: str = "test-session") -> Dict:
    """發送聊天請求並返回完整回覆"""
    payload = {
        "message": query,
        "session_id": session_id
    }

    response = requests.post(
        API_ENDPOINT,
        json=payload,
        headers={"Content-Type": "application/json"},
        stream=True
    )

    if response.status_code != 200:
        return {
            "error": f"HTTP {response.status_code}",
            "text": "",
            "function_calls": [],
            "sources": []
        }

    # 解析 SSE 流
    full_text = ""
    function_calls = []
    sources = []

    for line in response.iter_lines():
        if not line:
            continue

        line = line.decode('utf-8')
        if not line.startswith('data: '):
            continue

        data_str = line[6:]  # 移除 "data: " 前綴

        if data_str.strip() == "[DONE]":
            break

        try:
            data = json.loads(data_str)

            if data.get("type") == "text":
                full_text += data.get("content", "")
            elif data.get("type") == "function_call":
                function_calls.append(data.get("content", {}))
            elif data.get("type") == "sources":
                sources = data.get("content", [])
        except json.JSONDecodeError:
            continue

    return {
        "text": full_text,
        "function_calls": function_calls,
        "sources": sources
    }

def test_future_activities():
    """測試1：未來活動查詢"""
    print_test_header("未來活動查詢")

    query = "最近有什麼活動？"
    print_info(f"查詢：{query}")

    start_time = time.time()
    result = send_chat_request(query)
    response_time = time.time() - start_time

    # 檢查回覆
    if "error" in result:
        print_error(f"API 錯誤：{result['error']}")
        return False

    print_info(f"響應時間：{response_time:.2f}秒")

    # 驗證 function calling
    if result["function_calls"]:
        print_success(f"偵測到 {len(result['function_calls'])} 個 function call")
        for fc in result["function_calls"]:
            func_name = fc.get("function", "unknown")
            print_info(f"  - 調用函數：{func_name}")
            print_info(f"  - 參數：{json.dumps(fc.get('arguments', {}), ensure_ascii=False)}")
            print_info(f"  - 結果：{json.dumps(fc.get('result', {}), ensure_ascii=False)[:200]}...")
    else:
        print_warning("未偵測到 function calling（可能未啟用）")

    # 檢查回覆內容
    response_text = result["text"]
    print_info(f"回覆長度：{len(response_text)} 字元")
    print_info(f"回覆前200字：{response_text[:200]}...")

    # 驗證日期格式
    import re
    date_pattern = r'\d{4}/\d{2}/\d{2}'
    dates_found = re.findall(date_pattern, response_text)
    if dates_found:
        print_success(f"找到日期格式 (yyyy/mm/dd)：{dates_found[:5]}")
    else:
        print_warning("未找到 yyyy/mm/dd 格式的日期")

    # 檢查是否有 RAG sources
    if result["sources"]:
        print_success(f"找到 {len(result['sources'])} 個來源")
    else:
        print_warning("未找到 RAG 來源")

    # 檢查性能
    if response_time < 3:
        print_success(f"響應時間合格（< 3秒）")
    elif response_time < 5:
        print_warning(f"響應時間較慢（< 5秒）")
    else:
        print_error(f"響應時間過長（> 5秒）")

    return True

def test_past_activities():
    """測試2：過去活動查詢"""
    print_test_header("過去活動查詢")

    query = "上個月辦了哪些活動？"
    print_info(f"查詢：{query}")

    start_time = time.time()
    result = send_chat_request(query)
    response_time = time.time() - start_time

    if "error" in result:
        print_error(f"API 錯誤：{result['error']}")
        return False

    print_info(f"響應時間：{response_time:.2f}秒")

    # 驗證 function calling
    if result["function_calls"]:
        print_success(f"偵測到 {len(result['function_calls'])} 個 function call")
        for fc in result["function_calls"]:
            func_name = fc.get("function", "unknown")
            print_info(f"  - 調用函數：{func_name}")
    else:
        print_warning("未偵測到 function calling")

    response_text = result["text"]
    print_info(f"回覆長度：{len(response_text)} 字元")
    print_info(f"回覆前200字：{response_text[:200]}...")

    return True

def test_no_activities():
    """測試3：無活動回覆"""
    print_test_header("無活動回覆")

    query = "明年有什麼活動？"
    print_info(f"查詢：{query}")

    start_time = time.time()
    result = send_chat_request(query)
    response_time = time.time() - start_time

    if "error" in result:
        print_error(f"API 錯誤：{result['error']}")
        return False

    print_info(f"響應時間：{response_time:.2f}秒")

    response_text = result["text"]
    print_info(f"回覆前200字：{response_text[:200]}...")

    # 檢查是否包含模板回覆的關鍵字
    template_keywords = ["粉專", "facebook", "1999", "青年事務局"]
    found_keywords = [kw for kw in template_keywords if kw in response_text.lower()]

    if found_keywords:
        print_success(f"包含模板回覆關鍵字：{found_keywords}")
    else:
        print_warning("未包含預期的模板回覆關鍵字")

    return True

def test_non_time_query():
    """測試4：非時間查詢"""
    print_test_header("非時間查詢（不應調用時間工具）")

    query = "青創基地在哪裡？"
    print_info(f"查詢：{query}")

    start_time = time.time()
    result = send_chat_request(query)
    response_time = time.time() - start_time

    if "error" in result:
        print_error(f"API 錯誤：{result['error']}")
        return False

    print_info(f"響應時間：{response_time:.2f}秒")

    # 驗證不應有時間相關的 function calling
    if result["function_calls"]:
        time_funcs = [fc for fc in result["function_calls"]
                     if fc.get("function", "").startswith(("get_current_time", "calculate_date"))]
        if time_funcs:
            print_warning(f"不應調用時間工具，但調用了：{[f.get('function') for f in time_funcs]}")
        else:
            print_info("調用了非時間工具（合理）")
    else:
        print_success("未調用時間工具（預期行為）")

    response_text = result["text"]
    print_info(f"回覆前200字：{response_text[:200]}...")

    return True

def main():
    """運行所有測試"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}桃園市政府青年事務局聊天機器人 - 端到端測試{Colors.END}")
    print(f"{Colors.BLUE}測試時間處理功能{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

    # 檢查服務是否運行
    try:
        # 嘗試訪問根路徑
        health_check = requests.get(API_BASE_URL, timeout=5)
        if health_check.status_code in [200, 404, 405]:  # 服務在運行
            print_success("後端服務運行正常")
        else:
            print_error(f"後端服務異常：HTTP {health_check.status_code}")
            return
    except Exception as e:
        print_error(f"無法連接到後端服務：{e}")
        print_info("請確保後端服務正在運行：./start.sh 或 python app.py")
        return

    # 運行測試
    tests = [
        ("未來活動查詢", test_future_activities),
        ("過去活動查詢", test_past_activities),
        ("無活動回覆", test_no_activities),
        ("非時間查詢", test_non_time_query),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print_error(f"測試異常：{e}")
            results.append((test_name, False))

        time.sleep(1)  # 避免請求過快

    # 匯總結果
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}測試結果匯總{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        if success:
            print_success(f"{test_name}：通過")
        else:
            print_error(f"{test_name}：失敗")

    print(f"\n{Colors.BLUE}總計：{passed}/{total} 測試通過{Colors.END}\n")

    if passed == total:
        print_success("✨ 所有測試通過！時間處理功能運作正常。")
    else:
        print_warning(f"⚠️  {total - passed} 個測試未通過，請檢查日誌。")

if __name__ == "__main__":
    main()
