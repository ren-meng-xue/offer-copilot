FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    haveged \
    && rm -rf /var/lib/apt/lists/*


# 将后端项目放到 /app/backend，保留仓库里的 backend 包层级，
# 这样容器内仍然可以使用 `backend.app...` 这类绝对导入。
COPY pyproject.toml uv.lock README.md /app/backend/
RUN uv sync --frozen --no-dev --project /app/backend

COPY . /app/backend

RUN chmod +x /app/backend/start-combined.sh

EXPOSE 8080

CMD ["sh", "/app/backend/start-combined.sh"]
