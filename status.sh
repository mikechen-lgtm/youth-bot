#!/bin/bash

# Youth Chatbot - Ubuntu 檢查服務狀態

echo "=========================================="
echo "  Youth Chatbot 服務狀態"
echo "=========================================="
echo ""

# 檢查後端
echo "[後端] Flask 服務:"
if pgrep -f "python.*app.py" > /dev/null; then
    PID=$(pgrep -f "python.*app.py")
    echo "  狀態: 運行中 (PID: $PID)"
else
    echo "  狀態: 未運行"
fi

# 檢查前端
echo ""
echo "[前端] Vite 服務:"
if pgrep -f "vite" > /dev/null; then
    PID=$(pgrep -f "vite")
    echo "  狀態: 運行中 (PID: $PID)"
else
    echo "  狀態: 未運行"
fi

# 檢查 systemd 服務 (如果已設定)
echo ""
echo "[Systemd 服務]"
if systemctl is-enabled youth-chatbot-backend.service &>/dev/null; then
    echo "  後端: $(systemctl is-active youth-chatbot-backend.service) (開機自動啟動: 已啟用)"
else
    echo "  後端: 未設定 systemd 服務"
fi

if systemctl is-enabled youth-chatbot-frontend.service &>/dev/null; then
    echo "  前端: $(systemctl is-active youth-chatbot-frontend.service) (開機自動啟動: 已啟用)"
else
    echo "  前端: 未設定 systemd 服務"
fi

echo ""
echo "=========================================="
echo "  前端: http://35.212.185.83:3000"
echo "  後端: http://localhost:8300"
echo "=========================================="
