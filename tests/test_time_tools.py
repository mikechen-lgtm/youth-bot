"""
時間工具模組測試

測試 time_tools.py 中的所有功能，包括：
- 基本功能測試
- 邊界條件測試（跨年、閏年、時區）
- 錯誤處理測試

運行方式：
    python tests/test_time_tools.py
    或
    pytest tests/test_time_tools.py -v
"""

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
import os

# 添加項目根目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from time_tools import (
    get_current_time_info,
    calculate_date_range,
    parse_date_string,
    execute_time_tool,
    TIME_TOOLS_DEFINITIONS,
    TAIPEI_TZ,
)


class TestGetCurrentTimeInfo(unittest.TestCase):
    """測試 get_current_time_info 函數"""

    def test_basic_functionality(self):
        """測試基本功能"""
        result = get_current_time_info()

        # 檢查必要的鍵
        required_keys = [
            "current_date",
            "current_datetime",
            "yesterday",
            "tomorrow",
            "one_week_later",
            "one_month_later",
            "three_months_later",
            "weekday",
            "timezone",
        ]
        for key in required_keys:
            self.assertIn(key, result)

        # 檢查日期格式
        self.assertRegex(result["current_date"], r"^\d{4}/\d{2}/\d{2}$")
        self.assertRegex(result["current_datetime"], r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}$")

        # 檢查時區
        self.assertEqual(result["timezone"], "Asia/Taipei")

        # 檢查星期
        self.assertIn("星期", result["weekday"])

    def test_date_consistency(self):
        """測試日期一致性"""
        result = get_current_time_info()

        # 解析日期
        current = datetime.strptime(result["current_date"], "%Y/%m/%d")
        yesterday = datetime.strptime(result["yesterday"], "%Y/%m/%d")
        tomorrow = datetime.strptime(result["tomorrow"], "%Y/%m/%d")

        # 檢查日期關係
        self.assertEqual((current - yesterday).days, 1)
        self.assertEqual((tomorrow - current).days, 1)


class TestCalculateDateRange(unittest.TestCase):
    """測試 calculate_date_range 函數"""

    def test_future_range(self):
        """測試未來時間範圍"""
        result = calculate_date_range("today", 0, 90)

        self.assertIn("start_date", result)
        self.assertIn("end_date", result)
        self.assertEqual(result["days_in_range"], 91)  # 包含起始和結束日

        # 檢查描述
        self.assertIn("今天起90天內", result["description"])

    def test_past_range(self):
        """測試過去時間範圍"""
        result = calculate_date_range("today", -7, 0)

        self.assertEqual(result["days_in_range"], 8)
        self.assertIn("過去7天", result["description"])

    def test_specific_date_base(self):
        """測試指定基準日期"""
        result = calculate_date_range("2026/01/15", 0, 30)

        self.assertEqual(result["base_date"], "2026/01/15")
        self.assertEqual(result["start_date"], "2026/01/15")
        self.assertEqual(result["end_date"], "2026/02/14")

    def test_yesterday_base(self):
        """測試以昨天為基準"""
        result = calculate_date_range("yesterday", 0, 7)

        now = datetime.now(TAIPEI_TZ)
        yesterday = (now - timedelta(days=1)).strftime("%Y/%m/%d")

        self.assertEqual(result["base_date"], yesterday)

    def test_cross_year_boundary(self):
        """測試跨年邊界"""
        result = calculate_date_range("2025/12/31", 0, 7)

        self.assertEqual(result["start_date"], "2025/12/31")
        self.assertEqual(result["end_date"], "2026/01/07")

    def test_leap_year(self):
        """測試閏年處理"""
        # 2024 是閏年
        result = calculate_date_range("2024/02/28", 0, 2)

        self.assertEqual(result["start_date"], "2024/02/28")
        self.assertEqual(result["end_date"], "2024/03/01")  # 跨越 2/29

    def test_negative_range_swap(self):
        """測試負數範圍自動交換"""
        result = calculate_date_range("today", 7, -7)

        # 應該自動交換，使起始日期早於結束日期
        start = datetime.strptime(result["start_date"], "%Y/%m/%d")
        end = datetime.strptime(result["end_date"], "%Y/%m/%d")

        self.assertLess(start, end)

    def test_invalid_date_format(self):
        """測試無效日期格式"""
        with self.assertRaises(ValueError):
            calculate_date_range("invalid-date", 0, 7)


class TestParseDateString(unittest.TestCase):
    """測試 parse_date_string 函數"""

    def test_standard_format(self):
        """測試標準格式 YYYY/MM/DD"""
        result = parse_date_string("2026/01/27")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 27)

    def test_hyphen_format(self):
        """測試連字符格式 YYYY-MM-DD"""
        result = parse_date_string("2026-01-27")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_roc_year_format(self):
        """測試民國年格式"""
        result = parse_date_string("115年1月27日")

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)  # 115 + 1911 = 2026
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 27)

    def test_month_day_format(self):
        """測試月日格式（推斷年份）"""
        result = parse_date_string("1月27日")

        self.assertIsNotNone(result)
        self.assertIn(result.year, [2026, 2027])  # 可能是今年或明年

    def test_embedded_in_text(self):
        """測試從文本中提取日期"""
        text = "活動日期：2026/01/27，地點：桃園"
        result = parse_date_string(text)

        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_invalid_format(self):
        """測試無效格式"""
        result = parse_date_string("無效的日期")

        self.assertIsNone(result)


class TestExecuteTimeTool(unittest.TestCase):
    """測試 execute_time_tool 函數"""

    def test_execute_get_current_time_info(self):
        """測試執行 get_current_time_info"""
        result = execute_time_tool("get_current_time_info", {})

        self.assertIn("current_date", result)
        self.assertNotIn("error", result)

    def test_execute_calculate_date_range(self):
        """測試執行 calculate_date_range"""
        result = execute_time_tool(
            "calculate_date_range",
            {
                "base_date": "today",
                "start_offset_days": 0,
                "end_offset_days": 30,
            }
        )

        self.assertIn("start_date", result)
        self.assertNotIn("error", result)

    def test_execute_unknown_function(self):
        """測試執行未知函數"""
        result = execute_time_tool("unknown_function", {})

        self.assertIn("error", result)
        self.assertEqual(result["function_name"], "unknown_function")

    def test_execute_with_invalid_arguments(self):
        """測試使用無效參數"""
        result = execute_time_tool(
            "calculate_date_range",
            {"base_date": "invalid-date", "start_offset_days": 0, "end_offset_days": 7}
        )

        self.assertIn("error", result)


class TestToolDefinitions(unittest.TestCase):
    """測試工具定義"""

    def test_definitions_structure(self):
        """測試定義結構"""
        self.assertEqual(len(TIME_TOOLS_DEFINITIONS), 2)

        for tool in TIME_TOOLS_DEFINITIONS:
            self.assertEqual(tool["type"], "function")
            self.assertIn("function", tool)
            self.assertIn("name", tool["function"])
            self.assertIn("description", tool["function"])
            self.assertIn("parameters", tool["function"])

    def test_get_current_time_info_definition(self):
        """測試 get_current_time_info 定義"""
        tool = TIME_TOOLS_DEFINITIONS[0]

        self.assertEqual(tool["function"]["name"], "get_current_time_info")
        self.assertIn("Taipei", tool["function"]["description"])
        self.assertEqual(tool["function"]["parameters"]["type"], "object")

    def test_calculate_date_range_definition(self):
        """測試 calculate_date_range 定義"""
        tool = TIME_TOOLS_DEFINITIONS[1]

        self.assertEqual(tool["function"]["name"], "calculate_date_range")
        self.assertIn("base_date", tool["function"]["parameters"]["properties"])
        self.assertIn("start_offset_days", tool["function"]["parameters"]["properties"])
        self.assertIn("end_offset_days", tool["function"]["parameters"]["properties"])


class TestIntegration(unittest.TestCase):
    """集成測試"""

    def test_complete_workflow(self):
        """測試完整工作流程"""
        # 步驟1：獲取當前時間
        current_time = get_current_time_info()
        self.assertIn("current_date", current_time)

        # 步驟2：基於當前時間計算未來3個月
        date_range = calculate_date_range("today", 0, 90)
        self.assertIn("start_date", date_range)
        self.assertIn("end_date", date_range)

        # 步驟3：驗證日期一致性
        self.assertEqual(date_range["start_date"], current_time["current_date"])

    def test_past_month_query(self):
        """測試「上個月的活動」查詢邏輯"""
        # 模擬查詢上個月（過去30-60天）
        result = calculate_date_range("today", -60, -30)

        start = datetime.strptime(result["start_date"], "%Y/%m/%d").replace(tzinfo=TAIPEI_TZ)
        end = datetime.strptime(result["end_date"], "%Y/%m/%d").replace(tzinfo=TAIPEI_TZ)
        now = datetime.now(TAIPEI_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

        # 驗證都是過去的日期
        self.assertLess(end, now)


def run_tests():
    """運行所有測試"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    suite.addTests(loader.loadTestsFromTestCase(TestGetCurrentTimeInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestCalculateDateRange))
    suite.addTests(loader.loadTestsFromTestCase(TestParseDateString))
    suite.addTests(loader.loadTestsFromTestCase(TestExecuteTimeTool))
    suite.addTests(loader.loadTestsFromTestCase(TestToolDefinitions))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
