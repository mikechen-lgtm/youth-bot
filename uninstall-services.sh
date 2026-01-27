#!/bin/bash

# Youth Bot - 移除 systemd 服務腳本

echo "=========================================="
echo "  Youth Bot - 移除開機自動啟動服務"
echo "=========================================="

echo ""
echo "步驟 1: 停止服務"
sudo systemctl stop youth-bot-backend.service
sudo systemctl stop youth-bot-frontend.service

echo ""
echo "步驟 2: 停用服務"
sudo systemctl disable youth-bot-backend.service
sudo systemctl disable youth-bot-frontend.service

echo ""
echo "步驟 3: 刪除服務文件"
sudo rm -f /etc/systemd/system/youth-bot-backend.service
sudo rm -f /etc/systemd/system/youth-bot-frontend.service

echo ""
echo "步驟 4: 重新載入 systemd"
sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo "  移除完成！"
echo "=========================================="
