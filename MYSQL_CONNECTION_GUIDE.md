# MySQL 連線問題解決指南

## 已實施的改進措施

### 1. 連線池優化 (`app.py:80-93`)

新增了完整的連線池配置：

```python
mysql_engine: Engine = create_engine(
    MYSQL_URL,
    future=True,
    pool_pre_ping=True,          # 確保連線有效性
    pool_size=10,                # 連線池大小（同時保持的連線數）
    max_overflow=20,             # 超過 pool_size 時可額外建立的連線數
    pool_recycle=3600,           # 連線回收時間（秒），避免 MySQL 的 wait_timeout 問題
    pool_timeout=30,             # 取得連線的等待時間（秒）
    echo_pool=False,             # 生產環境關閉連線池日誌
    connect_args={
        "connect_timeout": 10,   # MySQL 連線超時（秒）
        "charset": "utf8mb4",    # 使用 UTF-8 編碼
    }
)
```

**改進說明：**
- `pool_size=10`: 維持 10 個持久連線，適合中等流量
- `max_overflow=20`: 高峰期最多可增加 20 個臨時連線（總計 30 個）
- `pool_recycle=3600`: 每小時回收連線，避免 MySQL 預設的 8 小時 `wait_timeout` 問題
- `pool_timeout=30`: 等待連線最多 30 秒，避免無限期卡住
- `connect_timeout=10`: MySQL 連線建立逾時 10 秒

### 2. 啟動重試機制 (`app.py:488-515`)

新增了資料庫初始化重試邏輯：

```python
def ensure_mysql_schema_with_retry(max_retries: int = 3, retry_delay: int = 5) -> None:
    """Ensure MySQL schema with retry mechanism for startup resilience."""
    for attempt in range(1, max_retries + 1):
        try:
            ensure_mysql_schema()
            return
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise
```

**改進說明：**
- 啟動時會重試 3 次，每次間隔 5 秒
- 防止因 MySQL 暫時性無法連線導致應用程式啟動失敗
- 適合容器環境（Docker, Kubernetes）中的服務依賴啟動順序問題

### 3. 健康檢查端點 (`app.py:1791-1811`)

改進了 `/health` 端點，新增資料庫連線測試：

```python
@app.get("/health")
def health() -> tuple[dict, int]:
    """Health check endpoint with database connection test."""
    health_status = {
        "status": "healthy",
        "database": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Test MySQL connection
    try:
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        return health_status, 503

    return health_status, 200
```

**使用方式：**
```bash
curl http://localhost:8300/health
```

**正常回應（HTTP 200）：**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-01-27T10:30:00.000Z"
}
```

**異常回應（HTTP 503）：**
```json
{
  "status": "unhealthy",
  "database": "disconnected",
  "error": "Connection refused",
  "timestamp": "2026-01-27T10:30:00.000Z"
}
```

## 常見連線問題診斷

### 問題 1：應用程式啟動失敗

**症狀：**
```
ERROR: Failed to create MySQL schema: Can't connect to MySQL server on 'localhost'
```

**可能原因：**
1. MySQL 服務未啟動
2. 連線參數錯誤（主機、埠、用戶名、密碼）
3. 防火牆阻擋

**診斷步驟：**

```bash
# 1. 檢查 MySQL 是否執行
sudo systemctl status mysql
# 或
docker ps | grep mysql

# 2. 測試連線
mysql -h localhost -P 3306 -u root -p

# 3. 檢查環境變數
echo $MYSQL_HOST
echo $MYSQL_PORT
echo $MYSQL_USER
echo $MYSQL_DATABASE

# 4. 查看應用程式日誌
tail -f logs/backend.log
```

**解決方案：**
```bash
# 啟動 MySQL
sudo systemctl start mysql

# 或使用 Docker
docker-compose up -d mysql

# 確認資料庫存在
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS \`youth-chat\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 問題 2：執行期間連線中斷

**症狀：**
```
產生回覆時發生問題，請稍後再試或聯繫我們的服務人員。
```

**可能原因：**
1. MySQL `wait_timeout` 導致閒置連線被關閉
2. 網路不穩定
3. 連線池耗盡

**診斷步驟：**

```bash
# 1. 檢查 MySQL wait_timeout 設定
mysql -u root -p -e "SHOW VARIABLES LIKE 'wait_timeout';"

# 2. 檢查連線池狀態（需要啟用 echo_pool）
# 修改 app.py: echo_pool=True，重新啟動後觀察日誌

# 3. 監控當前連線數
mysql -u root -p -e "SHOW PROCESSLIST;"
```

**解決方案：**

調整 MySQL 設定（`/etc/mysql/my.cnf` 或 `/etc/my.cnf`）：
```ini
[mysqld]
wait_timeout = 28800        # 8 小時
max_connections = 200       # 最大連線數
```

重啟 MySQL：
```bash
sudo systemctl restart mysql
```

### 問題 3：高流量時連線失敗

**症狀：**
```
QueuePool limit of size 10 overflow 20 reached, connection timed out
```

**可能原因：**
連線池設定太小，無法應對高並發請求

**解決方案：**

調整 `app.py` 中的連線池參數：
```python
pool_size=20,           # 增加基礎連線數
max_overflow=40,        # 增加溢位連線數
pool_timeout=60,        # 增加等待時間
```

### 問題 4：Docker 環境啟動順序問題

**症狀：**
```
Application failed to start: MySQL connection refused
```

**可能原因：**
應用程式在 MySQL 完全啟動前就嘗試連線

**解決方案：**

使用 `docker-compose.yml` 的 `depends_on` 和健康檢查：

```yaml
services:
  mysql:
    image: mysql:8.0
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: .
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
```

或使用等待腳本：
```bash
#!/bin/bash
# wait-for-mysql.sh

set -e

host="$1"
shift
cmd="$@"

until mysql -h "$host" -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1"; do
  >&2 echo "MySQL is unavailable - sleeping"
  sleep 2
done

>&2 echo "MySQL is up - executing command"
exec $cmd
```

## 環境變數設定

### 方式 1：使用完整連線字串

```bash
export MYSQL_URL="mysql+pymysql://username:password@localhost:3306/youth-chat?charset=utf8mb4"
```

### 方式 2：分開設定（推薦）

```bash
export MYSQL_HOST="localhost"
export MYSQL_PORT="3306"
export MYSQL_USER="root"
export MYSQL_PASSWORD="your_password"
export MYSQL_DATABASE="youth-chat"
```

### 生產環境建議

使用 `.env` 檔案（不要提交到 Git）：

```bash
# .env
MYSQL_HOST=mysql-server.example.com
MYSQL_PORT=3306
MYSQL_USER=youth_bot_user
MYSQL_PASSWORD=***secure_password***
MYSQL_DATABASE=youth_chat_prod
```

載入方式：
```bash
# 使用 python-dotenv（已在 requirements.txt）
from dotenv import load_dotenv
load_dotenv()

# 或使用 export
set -a
source .env
set +a
```

## 效能監控

### 1. 使用健康檢查端點

設定監控系統定期檢查：
```bash
# Prometheus 設定範例
- job_name: 'youth-bot'
  metrics_path: '/health'
  scrape_interval: 30s
  static_configs:
    - targets: ['localhost:8300']
```

### 2. 啟用連線池日誌（除錯用）

修改 `app.py`：
```python
mysql_engine: Engine = create_engine(
    MYSQL_URL,
    echo_pool="debug",  # 啟用詳細日誌
    ...
)
```

### 3. 監控 MySQL 效能

```sql
-- 查看連線狀態
SHOW PROCESSLIST;

-- 查看連線統計
SHOW STATUS LIKE 'Threads%';
SHOW STATUS LIKE 'Connections';

-- 查看慢查詢
SHOW VARIABLES LIKE 'slow_query%';
```

## 疑難排解檢查清單

- [ ] MySQL 服務是否執行？
- [ ] 環境變數是否正確設定？
- [ ] 資料庫 `youth-chat` 是否存在？
- [ ] 用戶是否有足夠權限？
- [ ] 防火牆是否允許 3306 埠？
- [ ] `/health` 端點是否返回 200？
- [ ] 應用程式日誌是否有錯誤訊息？
- [ ] MySQL 日誌是否有連線拒絕記錄？
- [ ] 連線池設定是否適合當前流量？
- [ ] MySQL `wait_timeout` 是否小於 `pool_recycle`？

## 相關檔案

- `app.py:80-93` - MySQL 連線引擎配置
- `app.py:332-486` - 資料庫 schema 初始化
- `app.py:488-515` - 重試機制
- `app.py:1791-1811` - 健康檢查端點
- `requirements.txt` - Python 依賴（PyMySQL, SQLAlchemy）

## 進一步改進建議

### 1. 新增連線池監控

```python
@app.get("/api/admin/db-pool-status")
def db_pool_status():
    """Return database connection pool statistics."""
    pool = mysql_engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "timeout": pool.timeout()
    }
```

### 2. 實作斷路器模式

使用 `pybreaker` 套件防止級聯失敗：

```python
from pybreaker import CircuitBreaker

db_breaker = CircuitBreaker(fail_max=5, timeout_duration=60)

@db_breaker
def execute_query(query):
    with mysql_engine.connect() as conn:
        return conn.execute(query)
```

### 3. 新增告警機制

```python
def send_alert(message: str):
    """Send alert via email/Slack when database issues occur."""
    # 實作告警邏輯
    pass

try:
    ensure_mysql_schema()
except Exception as e:
    send_alert(f"Database initialization failed: {e}")
    raise
```

---

**最後更新：** 2026-01-27
**維護者：** Youth Bot 團隊
