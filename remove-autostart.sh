#!/bin/bash

# Youth Chatbot - Ubuntu 移除開機自動啟動

echo "=========================================="
echo "  移除 Youth Chatbot 開機自動啟動 (Ubuntu)"
echo "=========================================="
echo ""

# 檢查是否為 root
if [ "$EUID" -ne 0 ]; then
    echo "[錯誤] 請使用 sudo 執行此腳本"
    echo ""
    echo "使用方式: sudo ./remove-autostart.sh"
    exit 1
fi

# 停止服務
echo "停止服務..."
systemctl stop youth-chatbot-frontend.service 2>/dev/null
systemctl stop youth-chatbot-backend.service 2>/dev/null

# 停用服務
echo "停用開機自動啟動..."
systemctl disable youth-chatbot-frontend.service 2>/dev/null
systemctl disable youth-chatbot-backend.service 2>/dev/null

# 刪除服務檔案
echo "刪除服務檔案..."
rm -f /etc/systemd/system/youth-chatbot-backend.service
rm -f /etc/systemd/system/youth-chatbot-frontend.service

# 重新載入 systemd
systemctl daemon-reload

echo ""
echo "=========================================="
echo "  已成功移除開機自動啟動設定"
echo "=========================================="
