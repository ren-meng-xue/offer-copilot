"""Locust 压测脚本：模拟问答请求。

启动：
  cd backend
  uv run locust -f scripts/load_test/locustfile.py \
    --host=http://localhost:8080 \
    --headless -u 50 -r 5 -t 5m \
    --html ../docs/specs/2026-05-27-measurement-and-fix/screenshots/baseline/locust-50.html

环境变量：
  LOCUST_TOKEN     - JWT token
  LOCUST_KB_IDS    - 逗号分隔的 KB ID（如 "1,2,3"）
  LOCUST_QUESTIONS - synthetic.jsonl 路径
"""

import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, events, task

TOKEN = os.environ.get("LOCUST_TOKEN", "")
KB_IDS = [int(x) for x in os.environ.get("LOCUST_KB_IDS", "1,2,3,4,5,6,7").split(",")]
QUESTIONS_PATH = os.environ.get(
    "LOCUST_QUESTIONS",
    str(Path(__file__).resolve().parents[3] / "eval" / "synthetic.jsonl"),
)


# 预加载问题
_QUESTIONS: list[dict] = []
if Path(QUESTIONS_PATH).exists():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                _QUESTIONS.append(json.loads(line))
            except json.JSONDecodeError:
                continue


class AskUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.conversations: dict[int, str] = {}
        for kb_id in KB_IDS:
            resp = self.client.post(
                "/api/v1/qa/conversations",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"knowledge_base_id": kb_id},
                name="POST /conversations (setup)",
            )
            if 200 <= resp.status_code < 300:
                try:
                    data = resp.json()["data"]
                    conv_id = data.get("conv_id") or data.get("id")
                    if conv_id:
                        self.conversations[kb_id] = conv_id
                except (KeyError, ValueError):
                    pass

    @task
    def ask(self):
        if not _QUESTIONS or not self.conversations:
            return
        sample = random.choice(_QUESTIONS)
        kb_id = sample["kb_id"]
        # 尝试匹配 KB ID 的 conversation，如果没有则随机取一个
        conv_id = self.conversations.get(kb_id)
        if not conv_id:
            conv_id = random.choice(list(self.conversations.values()))

        with self.client.post(
            f"/api/v1/qa/conversations/{conv_id}/ask",
            json={"question": sample["question"]},
            headers={"Authorization": f"Bearer {TOKEN}"},
            stream=True,
            name="POST /conversations/:id/ask",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"status={resp.status_code}")
                return

            # 简单消费 stream
            saw_done = False
            try:
                for line in resp.iter_lines():
                    if line:
                        if b'"type": "done"' in line:
                            saw_done = True
                            break
                if saw_done:
                    resp.success()
                else:
                    resp.failure("no done event in stream")
            except Exception as e:
                resp.failure(f"stream error: {e}")
