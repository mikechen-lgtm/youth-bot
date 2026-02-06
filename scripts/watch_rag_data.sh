#!/bin/bash
# RAG 资料自动监控脚本 v2.0
# 分离 .md 和 .json 文件处理逻辑

set -e

PROJECT_DIR="/home/creative_design/youth-bot"
RAG_DATA_DIR="$PROJECT_DIR/rag_data"
LOG_FILE="$PROJECT_DIR/logs/rag_watch.log"
CONDA_DIR="/home/creative_design/miniconda3"

# 冷却时间设置
COOLDOWN_MD=15          # .md 文件冷却（秒）
COOLDOWN_JSON=30        # .json 文件冷却（秒）
LAST_MD_RUN=0
LAST_JSON_RUN=0

# 初始化环境
mkdir -p "$PROJECT_DIR/logs"
source "$CONDA_DIR/etc/profile.d/conda.sh"
conda activate base
cd "$PROJECT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# === .md 文件处理 ===

handle_md_create() {
    local file=$1
    log "📄 .md 新增: $(basename "$file")"

    # 检查冷却
    local now=$(date +%s)
    local elapsed=$((now - LAST_MD_RUN))
    if [ $elapsed -lt $COOLDOWN_MD ]; then
        log "  ⏭️  冷却中 (${elapsed}s < ${COOLDOWN_MD}s)"
        return
    fi
    LAST_MD_RUN=$now

    # 增量添加到 Vector Store
    log "  → 增量添加到 Vector Store"
    if python "$PROJECT_DIR/scripts/add_to_vector_store.py" --file "$file" >> "$LOG_FILE" 2>&1; then
        log "  ✓ 添加成功"
    else
        log "  ❌ 添加失败"
    fi
}

handle_md_modify() {
    local file=$1
    log "✏️  .md 修改: $(basename "$file")"

    # 检查冷却
    local now=$(date +%s)
    local elapsed=$((now - LAST_MD_RUN))
    if [ $elapsed -lt $COOLDOWN_MD ]; then
        log "  ⏭️  冷却中 (${elapsed}s < ${COOLDOWN_MD}s)"
        return
    fi
    LAST_MD_RUN=$now

    # 重建整个 Vector Store
    log "  → 重建整个 Vector Store"
    if python "$PROJECT_DIR/scripts/bootstrap_vector_store.py" --rebuild >> "$LOG_FILE" 2>&1; then
        log "  ✓ 重建成功"
    else
        log "  ❌ 重建失败"
    fi
}

handle_md_delete() {
    local file=$1
    log "🗑️  .md 删除: $(basename "$file")"

    # 检查冷却
    local now=$(date +%s)
    local elapsed=$((now - LAST_MD_RUN))
    if [ $elapsed -lt $COOLDOWN_MD ]; then
        log "  ⏭️  冷却中 (${elapsed}s < ${COOLDOWN_MD}s)"
        return
    fi
    LAST_MD_RUN=$now

    # 使用 --update 模式（会自动检测并删除远程孤立文件）
    log "  → 更新 Vector Store（自动删除远程文件）"
    if python "$PROJECT_DIR/scripts/bootstrap_vector_store.py" --update >> "$LOG_FILE" 2>&1; then
        log "  ✓ 更新成功"
    else
        log "  ❌ 更新失败"
    fi
}

# === .json 文件处理 ===

handle_json_change() {
    local file=$1
    local event=$2
    log "📋 .json 变化 [$event]: $(basename "$file")"

    # 检查冷却
    local now=$(date +%s)
    local elapsed=$((now - LAST_JSON_RUN))
    if [ $elapsed -lt $COOLDOWN_JSON ]; then
        log "  ⏭️  冷却中 (${elapsed}s < ${COOLDOWN_JSON}s)"
        return
    fi
    LAST_JSON_RUN=$now

    # 清空并重建 MySQL
    log "  → 清空 MySQL 表并重新导入所有 JSON"
    if python "$PROJECT_DIR/scripts/json_to_database.py" --rag-dir "$RAG_DATA_DIR" --clear-table >> "$LOG_FILE" 2>&1; then
        log "  ✓ MySQL 重建成功"
    else
        log "  ❌ MySQL 重建失败"
    fi
}

# === 事件路由器 ===

process_event() {
    local file=$1
    local event=$2

    # 获取文件扩展名（转小写）
    local ext="${file##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    # 路由到对应处理函数
    case "$ext" in
        md)
            case "$event" in
                CREATE|MOVED_TO)
                    handle_md_create "$file"
                    ;;
                MODIFY)
                    handle_md_modify "$file"
                    ;;
                DELETE)
                    handle_md_delete "$file"
                    ;;
            esac
            ;;
        json)
            # 任何 JSON 变化都触发重建
            handle_json_change "$file" "$event"
            ;;
        *)
            # 忽略其他文件类型
            ;;
    esac
}

# === 主监控循环 ===

if ! command -v inotifywait &> /dev/null; then
    echo "Error: inotifywait not found. Install with: sudo apt install inotify-tools"
    exit 1
fi

log "=========================================="
log "RAG Data Watcher v2.0 Started"
log "Watching: $RAG_DATA_DIR"
log "Cooldown: MD=${COOLDOWN_MD}s, JSON=${COOLDOWN_JSON}s"
log "=========================================="

# 监控事件
inotifywait -m -r -e modify,create,delete,moved_to "$RAG_DATA_DIR" --format '%w%f %e' |
while read FILE EVENT; do
    # 只处理 .md 和 .json 文件
    if [[ "$FILE" =~ \.(md|json)$ ]]; then
        process_event "$FILE" "$EVENT"
    fi
done
