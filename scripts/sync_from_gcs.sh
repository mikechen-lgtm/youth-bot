#!/bin/bash
# 從 GCS 同步 RAG 資料到本地
# inotifywait 會自動偵測變化並更新 Vector Store

PROJECT_DIR="/home/creative_design/youth-bot"
LOG_FILE="$PROJECT_DIR/logs/gcs_sync.log"

mkdir -p "$PROJECT_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Syncing from GCS..." >> "$LOG_FILE"
/snap/bin/gsutil -m rsync -r gs://youth-crawler-bucket "$PROJECT_DIR/rag_data" >> "$LOG_FILE" 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync complete" >> "$LOG_FILE"
