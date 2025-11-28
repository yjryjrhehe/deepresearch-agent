import subprocess
import sys
import os
import time
import socket
from dotenv import load_dotenv

# ================= 配置区域 =================
FRONTEND_DIR = "src/frontend"  # 前端目录
# ===========================================

def wait_for_port(port, host='127.0.0.1', timeout=120, service_name="Service"):
    """
    检测端口是否开启（TCP Socket 探测）
    """
    start_time = time.time()
    print(f"⏳ 等待 {service_name} (Port {port}) 就绪...", end="", flush=True)
    
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                print(f" ✅ 就绪！")
                return True
        except (OSError, ConnectionRefusedError):
            if time.time() - start_time > timeout:
                print(f" ❌ 超时！")
                return False
            time.sleep(0.5) # 每0.5秒检测一次
            print(".", end="", flush=True)

def run_services():
    print("🚀 [DeepResearch Agent] 严格顺序启动脚本")
    print("--------------------------------------------------")

    # 1. 加载环境变量
    print("📂 [Init] 正在加载 .env 环境变量...")
    load_dotenv(override=True)
    os.environ["PYTHONUTF8"] = "1"

    processes = []

    try:
        # ========================================================
        # 阶段 1: 启动 LiteLLM Proxy (Port 4000)
        # ========================================================
        print("\n🤖 [1/3] 正在启动 LiteLLM Proxy...")
        litellm_process = subprocess.Popen(
            ["litellm", "--config", "config.yaml"],
            shell=True,
            env=os.environ
        )
        processes.append(litellm_process)

        # ⛔️ 阻塞等待：直到 LiteLLM 的 4000 端口通了，才继续
        if not wait_for_port(4000, service_name="LiteLLM"):
            raise RuntimeError("LiteLLM 启动失败，端口未响应。")

        # ========================================================
        # 阶段 2: 启动 FastAPI Backend (Port 8002)
        # ========================================================
        print("\n🔌 [2/3] 正在启动 FastAPI (Backend)...")
        uvicorn_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.backend.api.server:app", "--port", "8002", "--reload"],
            env=os.environ,
            shell=False
        )
        processes.append(uvicorn_process)

        # ⛔️ 阻塞等待：直到 Backend 的 8002 端口通了，才继续
        if not wait_for_port(8002, service_name="FastAPI"):
            raise RuntimeError("FastAPI 启动失败，端口未响应。")

        # ========================================================
        # 阶段 3: 启动 Frontend (Port 5173 - 默认 Vite 端口)
        # ========================================================
        print(f"\n💻 [3/3] 正在启动前端 (npm run dev)...")
        npm_cmd = "npm run dev -- --host 127.0.0.1 -- port 5173"
        npm_process = subprocess.Popen(
            npm_cmd,
            cwd=FRONTEND_DIR,
            shell=True,
            env=os.environ
        )
        processes.append(npm_process)
        
        # 可选：也等待前端端口就绪，为了完美的“全部启动”提示
        # 注意：Vite 可能会用 ipv6 (::1) 或 ipv4 (127.0.0.1)，这里简单检测 ipv4
        if not wait_for_port(5173, service_name="Frontend"):
            raise RuntimeError("Frontend 启动失败，端口未响应。")

        print("\n--------------------------------------------------")
        print("✨ 完美！所有服务已按顺序启动完毕。")
        print("   1. LiteLLM Proxy: http://localhost:4000 (Ready)")
        print("   2. API Backend:   http://localhost:8002 (Ready)")
        print("   3. Frontend:      http://localhost:5173 (Running)")
        print("--------------------------------------------------")
        print("👉 按 Ctrl+C 可以一次性停止所有服务")

        # 挂起主进程
        uvicorn_process.wait()
        npm_process.wait()

    except KeyboardInterrupt:
        print("\n\n🛑 正在停止所有服务...")
    except RuntimeError as e:
        print(f"\n❌ 错误: {e}")
    finally:
        # 清理逻辑
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
            
            if p.poll() is None:
                subprocess.run(f"taskkill /F /T /PID {p.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
        print("✅ 所有服务已清理。")

if __name__ == "__main__":
    run_services()