#!/bin/bash
# RAG 資料自動監控腳本
# 使用 inotifywait 監控 rag_data 目錄變化，自動觸發 Vector Store 更新
#
# 用法:
#   ./scripts/watch_rag_data.sh           # 前台運行
#   ./scripts/watch_rag_data.sh &         # 後台運行
#   nohup ./scripts/watch_rag_data.sh &   # 持久後台運行
#
# 需要安裝: sudo apt install inotify-tools

set -e

PROJECT_DIR="/home/creative_design/youth-bot"
RAG_DATA_DIR="$PROJECT_DIR/rag_data"
LOG_FILE="$PROJECT_DIR/logs/rag_watch.log"
CONDA_DIR="/home/creative_design/miniconda3"

# 防止重複觸發的冷卻時間（秒）
COOLDOWN=5
LAST_RUN=0

# 確保 logs 目錄存在
mkdir -p "$PROJECT_DIR/logs"

# 初始化 conda
source "$CONDA_DIR/etc/profile.d/conda.sh"
conda activate base

cd "$PROJECT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

run_update() {
    local now=$(date +%s)
    local elapsed=$((now - LAST_RUN))

    # 冷卻時間內跳過
    if [ $elapsed -lt $COOLDOWN ]; then
        log "Skipping update (cooldown: ${elapsed}s < ${COOLDOWN}s)"
        return
    fi

    LAST_RUN=$now
    log "Detected changes, updating Vector Store..."

    # 執行更新（只執行 JSON 轉換和 Vector Store 更新，不從 GCS 同步）
    if python "$PROJECT_DIR/scripts/convert_json_to_markdown.py" --rag-dir "$RAG_DATA_DIR" --in-place >> "$LOG_FILE" 2>&1; then
        log "JSON to Markdown conversion complete"
    else
        log "Warning: JSON conversion failed or no JSON files"
    fi

    if python "$PROJECT_DIR/scripts/bootstrap_vector_store.py" --update >> "$LOG_FILE" 2>&1; then
        log "Vector Store update complete"
    else
        log "ERROR: Vector Store update failed"
    fi
}

# 檢查 inotifywait 是否安裝
if ! command -v inotifywait &> /dev/null; then
    echo "Error: inotifywait not found. Install with: sudo apt install inotify-tools"
    exit 1
fi

log "=========================================="
log "RAG Data Watcher Started"
log "Watching: $RAG_DATA_DIR"
log "Cooldown: ${COOLDOWN}s"
log "=========================================="

# 監控 rag_data 目錄
# -m: 持續監控（不退出）
# -r: 遞迴監控子目錄
# -e: 監控的事件類型
#   - modify: 檔案內容被修改
#   - create: 新檔案建立
#   - delete: 檔案被刪除
#   - moved_to: 檔案移入目錄
inotifywait -m -r -e modify,create,delete,moved_to "$RAG_DATA_DIR" --format '%w%f %e' |
while read FILE EVENT; do
    # 只處理支援的檔案類型
    if [[ "$FILE" =~ \.(md|txt|pdf|html|json)$ ]]; then
        log "Event: $EVENT on $FILE"
        run_update
    fi
done
