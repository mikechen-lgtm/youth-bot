# 多阶段构建 Dockerfile
# Stage 1: 构建前端
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# 复制前端依赖文件
COPY package.json package-lock.json ./

# 安装前端依赖
RUN npm ci

# 复制前端源代码
COPY . .

# 构建前端（输出到 dist/）
RUN npm run build

# Stage 2: Python Flask 应用
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 从构建阶段复制前端构建产物
COPY --from=frontend-builder /app/dist ./dist

# 复制后端源代码
COPY app.py openai_service.py ./
COPY rag_data ./rag_data/
COPY public ./public/

# 设置环境变量
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# 暴露端口（Cloud Run 会自动设置 PORT 环境变量）
EXPOSE 8080

# 启动 Flask 应用
CMD ["python", "app.py"]
