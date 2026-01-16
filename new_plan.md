# RAG 資料自動同步方案

## 需求確認
- **資料來源**: GCS Bucket
- **觸發方式**: Cloud Scheduler（每日定時）

| 模式 | 觸發場景 | 行為 |
|------|----------|------|
| **增量更新** `--update` | 每日爬蟲新增檔案、手動新增檔案 | 保留現有 store，只上傳新增檔案 |
| **完全重建** `--rebuild` | 修改原有檔案內容、刪除檔案 | 刪除舊 store，建立新的，重新上傳所有檔案，更新 .env |

## 架構設計

```
GCS Bucket (rag-data/)
    │
    ├── 爬蟲每日新增檔案
    │
    ▼
sync_rag_from_bucket.py
    │
    ├── --update  → 增量更新（比對後只上傳新檔案）
    └── --rebuild → 完全重建（刪除舊 store，重建）
    │
    ▼
OpenAI Vector Store
    │
    ▼
.env (RAG_VECTOR_STORE_ID)
```

## 實作計畫

### 1. 建立 GCS 同步腳本
**檔案**: `scripts/sync_rag_from_bucket.py`

功能：
- 從 GCS bucket 下載檔案到本地 `rag_data/`
- 呼叫現有的 `bootstrap_vector_store.py` 進行更新

參數：
```bash
# 增量更新（每日爬蟲後執行）
python scripts/sync_rag_from_bucket.py --update

# 完全重建（清空重來）
python scripts/sync_rag_from_bucket.py --rebuild

# 指定 bucket
python scripts/sync_rag_from_bucket.py --update --bucket gs://your-bucket/rag-data
```

### 2. 環境變數配置
新增到 `.env`：
```
RAG_GCS_BUCKET=gs://your-project-bucket/rag-data
```

### 3. Cloud Scheduler 定時任務配置

建立 Cloud Run Job 執行同步：
```bash
# 建立 Cloud Run Job
gcloud run jobs create rag-sync-job \
  --image=gcr.io/PROJECT_ID/rag-sync \
  --region=asia-east1 \
  --set-env-vars="RAG_GCS_BUCKET=gs://xxx/rag-data" \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest"

# 建立 Cloud Scheduler（每日凌晨 3 點執行增量更新）
gcloud scheduler jobs create http rag-daily-sync \
  --location=asia-east1 \
  --schedule="0 3 * * *" \
  --uri="https://asia-east1-run.googleapis.com/apis/run.googleapis.com/v1/..." \
  --http-method=POST
```

## 修改檔案清單

| 檔案 | 動作 |
|------|------|
| `scripts/sync_rag_from_bucket.py` | 新增 - GCS 同步腳本 |
| `scripts/bootstrap_vector_store.py` | 已完成 - 支援 --rebuild/--update |
| `.env.example` | 更新 - 新增 RAG_GCS_BUCKET |
| `requirements.txt` | 更新 - 新增 google-cloud-storage |

## 驗證步驟

1. 手動測試增量更新：
   ```bash
   python scripts/sync_rag_from_bucket.py --update --bucket gs://xxx
   python scripts/bootstrap_vector_store.py --list
   ```

2. 手動測試完全重建：
   ```bash
   python scripts/sync_rag_from_bucket.py --rebuild --bucket gs://xxx
   grep RAG_VECTOR_STORE_ID .env
   ```

3. 重啟服務測試聊天功能
