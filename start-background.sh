#!/bin/bash

# Youth Chatbot - Ubuntu 背景啟動腳本

echo "=========================================="
echo "  Youth Chatbot 背景啟動腳本 (Ubuntu)"
echo "=========================================="

# 取得腳本所在目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 建立 logs 資料夾
mkdir -p logs

# 檢查是否已在運行
if pgrep -f "python.*app.py" > /dev/null; then
    echo "[警告] 後端服務已在運行中"
else
    echo ""
    echo "[後端] 啟動 Flask 服務 (背景運行)..."
    nohup python3 app.py > logs/backend.log 2>&1 &
    echo "[後端] PID: $!"
fi

# 等待後端啟動
sleep 2

if pgrep -f "vite" > /dev/null; then
    echo "[警告] 前端服務已在運行中"
else
    echo "[前端] 啟動 Vite 開發伺服器 (背景運行)..."
    nohup npm run dev > logs/frontend.log 2>&1 &
    echo "[前端] PID: $!"
fi

echo ""
echo "=========================================="
echo "  服務已在背景啟動！"
echo "  前端: http://35.212.208.67:3000"
echo "  後端: http://localhost:8300"
echo ""
echo "  日誌檔案:"
echo "  - logs/backend.log"
echo "  - logs/frontend.log"
echo ""
echo "  停止服務: ./stop.sh"
echo "=========================================="
