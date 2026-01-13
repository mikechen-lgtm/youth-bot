# GCP Cloud Run ?¨ç½²?‡å?

?¬æ?æ¡?¯´?Žå?ä½•é?ç½?GitHub Actions ?ªåŠ¨?¨ç½²??GCP Cloud Run??
## ?ç½®è¦æ?

1. GCP é¡¹ç›®å·²å?å»?2. å·²å¯?¨ä»¥ä¸?APIï¼?   - Cloud Run API
   - Artifact Registry APIï¼ˆæ? Container Registry APIï¼?   - Cloud Build APIï¼ˆå¯?‰ï??¨ä??„å»ºï¼?
## ?ç½®æ­¥éª¤

### 1. ?›å»º?åŠ¡è´¦å·å¹¶èŽ·?–å???
```bash
# ?›å»º?åŠ¡è´¦å·
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions Service Account"

# ?ˆä?å¿…è??ƒé?
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# ?›å»ºå¯†é’¥?‡ä»¶
gcloud iam service-accounts keys create github-actions-key.json \
    --iam-account=github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 2. ?ç½® GitHub Secrets

??GitHub ä»“å???Settings ??Secrets and variables ??Actions ä¸­æ·»? ä»¥ä¸?secretsï¼?
**å¿…é?ï¼?*
- `GCP_PROJECT_ID`: ä½ ç? GCP é¡¹ç›® ID
- `GCP_SA_KEY`: ?åŠ¡è´¦å·å¯†é’¥?‡ä»¶?„å?å®¹ï??´ä¸ª JSON ?‡ä»¶?…å®¹ï¼?
**?¯é€‰ï?**
- `GCP_ARTIFACT_REPO`: Artifact Registry ä»“å??ç§°ï¼ˆå? `chatbot-poc-youth`ï¼‰ï??™ç©º?™ä½¿??GCR
- `OPENAI_API_KEY_SECRET_NAME`: GCP Secret Manager ä¸­ç? secret ?ç§°ï¼ˆç”¨äº?OpenAI API Keyï¼?- `POSTGRES_URL_SECRET_NAME`: GCP Secret Manager ä¸­ç? secret ?ç§°ï¼ˆç”¨äº?PostgreSQL è¿žæŽ¥å­—ç¬¦ä¸²ï?
- `FLASK_SECRET_KEY_SECRET_NAME`: GCP Secret Manager ä¸­ç? secret ?ç§°ï¼ˆç”¨äº?Flask session å¯†é’¥ï¼?
### 3. ?ç½® Secret Managerï¼ˆå¯?‰ä??¨è?ï¼?
??GCP Secret Manager ä¸­å?å»ºä»¥ä¸?secretsï¼?
```bash
# ?›å»º secrets
echo -n "your-openai-api-key" | gcloud secrets create OPENAI_API_KEY --data-file=-
echo -n "your-postgres-url" | gcloud secrets create POSTGRES_URL --data-file=-
echo -n "your-flask-secret-key" | gcloud secrets create FLASK_SECRET_KEY --data-file=-

# ?ˆä??åŠ¡è´¦å·è®¿é—®?ƒé?
gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
    --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 4. ?›å»º Artifact Registry ä»“å?ï¼ˆæŽ¨?ï?

```bash
# ?›å»º Docker ä»“å?
gcloud artifacts repositories create chatbot-poc-youth \
    --repository-format=docker \
    --location=asia-east1 \
    --description="Docker repository for chatbot-poc-youth"
```

### 5. ?ªå?ä¹‰éƒ¨ç½²é?ç½?
ç¼–è? `.github/workflows/deploy-cloud-run.yml`ï¼Œæ ¹?®é?è¦ä¿®?¹ï?

- `SERVICE_NAME`: Cloud Run ?åŠ¡?ç§°ï¼ˆé?è®¤ï?`chatbot-poc-youth`ï¼?- `REGION`: ?¨ç½²?ºå?ï¼ˆé?è®¤ï?`asia-east1`ï¼?- `memory`: ?…å??ç½®ï¼ˆé?è®¤ï?`1Gi`ï¼?- `cpu`: CPU ?ç½®ï¼ˆé?è®¤ï?`1`ï¼?- `min-instances`: ?€å°å?ä¾‹æ•°ï¼ˆé?è®¤ï?`0`ï¼Œå†·?¯åŠ¨ï¼?- `max-instances`: ?€å¤§å?ä¾‹æ•°ï¼ˆé?è®¤ï?`10`ï¼?
### 6. ?¯å??˜é??ç½®

??Cloud Run ?åŠ¡ä¸­é?ç½®çŽ¯å¢ƒå??ï??–é€šè? Secret Manager æ³¨å…¥ï¼?
**å¿…é??„çŽ¯å¢ƒå??ï?**
- `OPENAI_API_KEY`: OpenAI API å¯†é’¥
- `POSTGRES_URL` ??`POSTGRES_URL_NON_POOLING`: PostgreSQL è¿žæŽ¥å­—ç¬¦ä¸?- `FLASK_SECRET_KEY`: Flask session å¯†é’¥

**?¯é€‰ç??¯å??˜é?ï¼?*
- `FRONTEND_ORIGIN`: ?ç«¯?Ÿå?ï¼ˆCORS ?ç½®ï¼?- `SYSTEM_PROMPT`: ?ªå?ä¹‰ç³»ç»Ÿæ?ç¤ºè?
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google OAuth ?ç½®
- `LINE_CHANNEL_ID`, `LINE_CHANNEL_SECRET`: LINE OAuth ?ç½®
- `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`: Facebook OAuth ?ç½®

### 7. è§¦å??¨ç½²

?¨ç½²ä¼šåœ¨ä»¥ä??…å†µ?ªåŠ¨è§¦å?ï¼?- ?¨é€åˆ° `main` ??`master` ?†æ”¯
- ?‹åŠ¨è§¦å?ï¼ˆActions ??Deploy to Cloud Run ??Run workflowï¼?
## ?¬åœ°æµ‹è? Docker ?œå?

```bash
# ?„å»º?œå?
docker build -t chatbot-poc-youth:local .

# è¿è?å®¹å™¨
docker run -p 8080:8080 \
  -e PORT=8080 \
  -e OPENAI_API_KEY=your-key \
  -e POSTGRES_URL=your-postgres-url \
  chatbot-poc-youth:local
```

## ?…é??’é™¤

### ?„å»ºå¤±è´¥

1. æ£€??Dockerfile ?¯å¦æ­?¡®
2. ç¡®è®¤?€?‰ä?èµ–æ?ä»¶éƒ½å·²å???3. ?¥ç? GitHub Actions ?¥å?

### ?¨ç½²å¤±è´¥

1. æ£€??GCP ?åŠ¡è´¦å·?ƒé?
2. ç¡®è®¤ Artifact Registry ä»“å?å·²å?å»?3. éªŒè??¯å??˜é???secrets ?ç½®

### è¿è??¶é?è¯?
1. æ£€??Cloud Run ?¥å?ï¼š`gcloud run services logs read chatbot-poc-youth --region=asia-east1`
2. ç¡®è®¤?¯å??˜é?å·²æ­£ç¡®è®¾ç½?3. éªŒè??°æ®åº“è???
## æ³¨æ?äº‹é¡¹

1. **?°æ®åº?*: ?Ÿäº§?¯å?å»ºè®®ä½¿ç”¨ Cloud SQL PostgreSQLï¼Œè€Œä???SQLite
2. **?‡ä»¶å­˜å‚¨**: `uploads/` ?®å???Cloud Run ä¸­æ˜¯ä¸´æ—¶?„ï?å»ºè®®ä½¿ç”¨ Cloud Storage
3. **Session**: ?Ÿäº§?¯å?åº”ä½¿??Redis ?–æ•°?®å?å­˜å‚¨ session
4. **?æœ¬ä¼˜å?**: è®¾ç½® `min-instances=0` ?¯ä»¥?ä??æœ¬ï¼Œä?ä¼šæ??·å¯?¨å»¶è¿?
## ?¸å…³èµ„æ?

- [Cloud Run ?‡æ¡£](https://cloud.google.com/run/docs)
- [Artifact Registry ?‡æ¡£](https://cloud.google.com/artifact-registry/docs)
- [GitHub Actions ?‡æ¡£](https://docs.github.com/en/actions)



## OpenAI File Search ¦V¶q®w¡]Cloud Run¡^

### «Ø¥ß¦V¶q®w¡]¥»¾÷¡^
```bash
# ·|«Ø¥ß vector store¡B¤W¶Ç rag_data/¡A¨Ã¼g¦^ .env
python scripts/bootstrap_vector_store.py --write-env
```

### Cloud Run Àô¹ÒÅÜ¼Æ
¦b Cloud Run ³]©w¥H¤UÀô¹ÒÅÜ¼Æ¡G
- `OPENAI_API_KEY`
- `RAG_VECTOR_STORE_ID`¡]¤W­±²£¥Íªº vs_...¡^
- `RAG_AUTO_BOOTSTRAP=false`¡]¹w³]¤£¦Û°Ê¤W¶Ç¡^

### ¼W¶q·s¼WÀÉ®×¡]¤£»Ý­««Ø¡^
```bash
# ³æ¤@ÀÉ®×
python scripts/add_to_vector_store.py --store-id vs_XXXX --file rag_data/·s¼WÀÉ.md

# ¾ã­Ó¸ê®Æ§¨¡]¥u·|¤W¶Ç«ü©w°ÆÀÉ¦W¡^
python scripts/add_to_vector_store.py --store-id vs_XXXX --data-dir rag_data
```

> ¼W¶q·s¼W·|ª½±µ§ó·s OpenAI ªº¦V¶q®w¡A¤£»Ý­n­«·s³¡¸p Cloud Run¡C
