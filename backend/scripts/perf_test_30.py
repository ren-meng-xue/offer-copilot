import asyncio
import time
import httpx
import sys

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzgwMDQ1MjA2fQ.BkdTX95apaDvLwVeIpEo299tJ8Dabi3dJem1xcrolEg"
BASE_URL = "http://127.0.0.1:8080"
KB_ID = 4  # 使用 FastAPI 中文教程知识库

async def run_single_request(client, conv_id, idx):
    ttft = None
    total_time = None
    success = False
    start_time = time.perf_counter()
    
    try:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/v1/qa/conversations/{conv_id}/ask",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"question": f"第 {idx} 次压测：请问 FastAPI 中的依赖注入是如何工作的？"},
            timeout=30.0
        ) as response:
            if response.status_code != 200:
                print(f"❌ 请求 {idx} 失败，HTTP {response.status_code}")
                return None
                
            async for line in response.aiter_lines():
                if not line:
                    continue
                # 记录 TTFT (第一个收到数据的行)
                if ttft is None:
                    ttft = (time.perf_counter() - start_time) * 1000  # ms
                
                if '"type": "done"' in line:
                    success = True
                    break
            
            total_time = (time.perf_counter() - start_time) * 1000  # ms
    except Exception as e:
        print(f"❌ 请求 {idx} 发生异常: {e}")
        return None
        
    return {
        "idx": idx,
        "ttft": ttft,
        "total_time": total_time,
        "success": success
    }

async def main():
    print("🚀 正在初始化压测会话...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        # 1. 创建 conversation
        resp = await client.post(
            f"{BASE_URL}/api/v1/qa/conversations",
            headers=headers,
            json={"knowledge_base_id": KB_ID}
        )
        if not (200 <= resp.status_code < 300):
            print(f"❌ 初始化会话失败，HTTP {resp.status_code}: {resp.text}")
            print("请确认后端已在 8080 端口启动且 Token 有效！")
            return
            
        data = resp.json()["data"]
        conv_id = data.get("conv_id") or data.get("id")
        print(f"✅ 成功创建测试会话 ID: {conv_id}")
        
        # 2. 并发运行 30 次请求
        print("⚡️ 开始执行 30 次 RAG 流式请求压测（模拟并发数=3，总量=30）...")
        results = []
        sem = asyncio.Semaphore(3)  # 限制并发数为 3
        
        async def worker(idx):
            async with sem:
                res = await run_single_request(client, conv_id, idx)
                if res:
                    print(f"  [请求 {idx:02d}] 成功! TTFT: {res['ttft']:.1f}ms | 总耗时: {res['total_time']:.1f}ms")
                    results.append(res)
                else:
                    results.append({"idx": idx, "success": False})

        tasks = [worker(i) for i in range(1, 31)]
        await asyncio.gather(*tasks)
        
        # 3. 统计指标
        successful_runs = [r for r in results if r.get("success")]
        total_runs = len(results)
        success_count = len(successful_runs)
        
        if success_count == 0:
            print("❌ 压测完成，但全部请求失败。")
            return
            
        ttfts = sorted([r["ttft"] for r in successful_runs])
        total_times = sorted([r["total_time"] for r in successful_runs])
        
        avg_ttft = sum(ttfts) / success_count
        p95_ttft = ttfts[int(success_count * 0.95)]
        p99_ttft = ttfts[int(success_count * 0.99)] if success_count > 1 else p95_ttft
        
        avg_total = sum(total_times) / success_count
        p95_total = total_times[int(success_count * 0.95)]
        p99_total = total_times[int(success_count * 0.99)] if success_count > 1 else p95_total
        
        print("\n================== 📊 压测性能统计结果 ==================")
        print(f"🔹 成功率: {success_count}/{total_runs} ({(success_count/total_runs)*100:.1f}%)")
        print(f"🔹 TTFT (首字延迟)  - 平均值: {avg_ttft:.1f}ms | p95: {p95_ttft:.1f}ms | p99: {p99_ttft:.1f}ms")
        print(f"🔹 总耗时 (流式完成) - 平均值: {avg_total:.1f}ms | p95: {p95_total:.1f}ms | p99: {p99_total:.1f}ms")
        print("========================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
