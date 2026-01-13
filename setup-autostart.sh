#!/bin/bash

# Youth Chatbot - Ubuntu 設定開機自動啟動

echo "=========================================="
echo "  設定 Youth Chatbot 開機自動啟動 (Ubuntu)"
echo "=========================================="
echo ""

# 檢查是否為 root
if [ "$EUID" -ne 0 ]; then
    echo "[錯誤] 請使用 sudo 執行此腳本"
    echo ""
    echo "使用方式: sudo ./setup-autostart.sh"
    exit 1
fi

# 取得實際用戶
REAL_USER="${SUDO_USER:-$USER}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 檢查 Python 和 Node 路徑
PYTHON_PATH=$(which python3)
NPM_PATH=$(which npm)

if [ -z "$PYTHON_PATH" ]; then
    echo "[錯誤] 找不到 python3"
    exit 1
fi

if [ -z "$NPM_PATH" ]; then
    echo "[錯誤] 找不到 npm"
    exit 1
fi

echo "工作目錄: $SCRIPT_DIR"
echo "執行用戶: $REAL_USER"
echo "Python: $PYTHON_PATH"
echo "NPM: $NPM_PATH"
echo ""

# 建立後端 systemd 服務
cat > /etc/systemd/system/youth-chatbot-backend.service << EOF
[Unit]
Description=Youth Chatbot Backend (Flask)
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_PATH app.py
Restart=always
RestartSec=5
StandardOutput=append:$SCRIPT_DIR/logs/backend.log
StandardError=append:$SCRIPT_DIR/logs/backend.log

[Install]
WantedBy=multi-user.target
EOF

# 建立前端 systemd 服務
cat > /etc/systemd/system/youth-chatbot-frontend.service << EOF
[Unit]
Description=Youth Chatbot Frontend (Vite)
After=network.target youth-chatbot-backend.service

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$NPM_PATH run dev
Restart=always
RestartSec=5
StandardOutput=append:$SCRIPT_DIR/logs/frontend.log
StandardError=append:$SCRIPT_DIR/logs/frontend.log

[Install]
WantedBy=multi-user.target
EOF

# 建立 logs 資料夾
mkdir -p "$SCRIPT_DIR/logs"
chown "$REAL_USER:$REAL_USER" "$SCRIPT_DIR/logs"

# 重新載入 systemd
systemctl daemon-reload

# 啟用服務 (開機自動啟動)
systemctl enable youth-chatbot-backend.service
systemctl enable youth-chatbot-frontend.service

# 立即啟動服務
systemctl start youth-chatbot-backend.service
sleep 2
systemctl start youth-chatbot-frontend.service

echo ""
echo "=========================================="
echo "  設定成功！"
echo ""
echo "  服務狀態:"
systemctl is-active youth-chatbot-backend.service | xargs echo "  後端:"
systemctl is-active youth-chatbot-frontend.service | xargs echo "  前端:"
echo ""
echo "  常用指令:"
echo "  sudo systemctl status youth-chatbot-backend"
echo "  sudo systemctl status youth-chatbot-frontend"
echo "  sudo systemctl restart youth-chatbot-backend"
echo "  sudo systemctl restart youth-chatbot-frontend"
echo ""
echo "  前端: http://localhost:3000"
echo "  後端: http://localhost:8300"
echo "=========================================="
