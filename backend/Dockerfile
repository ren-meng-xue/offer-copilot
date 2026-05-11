FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

# 将后端项目放到 /app/backend，保留仓库里的 backend 包层级，
# 这样容器内仍然可以使用 `backend.app...` 这类绝对导入。
COPY pyproject.toml uv.lock README.md /app/backend/
RUN uv sync --frozen --no-dev --project /app/backend

COPY . /app/backend

EXPOSE 8000

CMD ["uv", "run", "--project", "/app/backend", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
