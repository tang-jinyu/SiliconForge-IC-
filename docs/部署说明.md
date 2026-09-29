# SiliconForge 部署说明

## 1. 部署拓扑

当前生产环境运行在双 NVIDIA H100 服务器上：

- `agent`：FastAPI、LangGraph、Web GUI、任务队列和 EDA 编排；
- `vllm`：在两张 H100 上执行本地大模型推理；
- `runs`：持久化任务源码、报告和 EDA 证据；
- `.agent_queue`：持久化任务状态；
- `model-cache`：持久化 Hugging Face 模型权重。

`compose.yaml` 定义 Agent 服务，`compose.h100.yaml` 叠加 GPU 推理服务并把 Agent 的 OpenAI-compatible 地址切换到 `http://vllm:8000/v1`。

## 2. Windows 开发部署

### 环境

- Windows 10/11
- Python 3.11 或更高版本
- 可选：OSS CAD Suite 或本机 Icarus Verilog、Yosys

### 安装与启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
python -m digital_ic_agent serve --host 127.0.0.1 --port 8000
```

也可以直接双击 `打开数字IC-Agent网页.cmd`。服务启动后访问 `http://127.0.0.1:8000/`。

`127.0.0.1` 是本机回环地址，其他电脑无法通过这个地址访问。局域网访问可把服务绑定到 `0.0.0.0` 并使用本机局域网 IP；互联网访问应使用双 H100 服务器的公网 IP/域名，或者由校园网出口、VPN、FRP/Cloudflare Tunnel 等方式建立公网入口。

### StepFun 配置

在本机 `.env` 中设置：

```dotenv
DIGITAL_IC_AGENT_BASE_URL=https://api.stepfun.com/v1
DIGITAL_IC_AGENT_API_KEY=你的密钥
DIGITAL_IC_AGENT_MODEL=step-5-preview
DIGITAL_IC_AGENT_LLM_TRANSPORT=chat
DIGITAL_IC_AGENT_LLM_TIMEOUT_SECONDS=600
DIGITAL_IC_AGENT_LLM_MAX_ATTEMPTS=3
```

## 3. 双 H100 服务器部署

### 服务器环境

- Linux x86_64
- NVIDIA Driver
- Docker Engine 与 Docker Compose Plugin
- NVIDIA Container Toolkit
- 两张 NVIDIA H100

验证 GPU 容器运行时：

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi
```

### 准备配置

```bash
git clone <你的仓库地址> siliconforge
cd siliconforge
cp .env.server.example .env.server
```

编辑 `.env.server`，设置访问口令、会话密钥和模型参数。双 H100 的默认核心配置为：

```dotenv
VLLM_MODEL=Qwen/Qwen3-32B-AWQ
VLLM_TENSOR_PARALLEL_SIZE=2
VLLM_MAX_MODEL_LEN=32768
VLLM_API_KEY=local-h100
HF_CACHE_DIR=./model-cache
```

### 模型额度策略

公开部署的默认策略是：登录用户没有保存个人模型配置时，不允许执行真实模型任务，即使服务器环境中存在项目所有者的远程 API Key，也不会自动回落使用。

```dotenv
DIGITAL_IC_AGENT_ALLOW_SHARED_LLM=false
```

双 H100 Compose 会显式设置 `DIGITAL_IC_AGENT_ALLOW_SHARED_LLM=true`，共享对象是容器内的本地 vLLM 服务，因此用户任务消耗服务器 GPU 资源，不消耗 StepFun API 额度。将 Agent 改接远程付费服务时，保持该值为 `false`，用户需在 GUI 的“模型与 API”中填写自己的 Key、Base URL 和模型名。

### 启动

```bash
docker compose -f compose.yaml -f compose.h100.yaml up -d --build
docker compose -f compose.yaml -f compose.h100.yaml ps
docker compose -f compose.yaml -f compose.h100.yaml logs -f vllm
```

vLLM 完成模型加载并通过健康检查后，Agent 自动连接本地推理端点。服务器本机访问：

```text
http://127.0.0.1:8000/
```

`compose.yaml` 默认只把端口绑定到服务器回环地址。需要局域网直连时，可在 `.env.server` 中设置 `DIGITAL_IC_AGENT_BIND_ADDRESS=0.0.0.0`，并使用防火墙限制访问来源。仅上传 GitHub 不会自动生成可运行网址。

### 无公网 IP：Cloudflare Tunnel + HTTPS 域名

实验室服务器没有公网 IP 时，推荐使用 Cloudflare Tunnel。`cloudflared` 容器会从服务器主动建立出站连接，因此不需要公网 IP、端口映射或对互联网开放 8000 端口；外部用户访问 Cloudflare 提供的 HTTPS 域名，流量再通过隧道进入同一 Compose 网络中的 `agent:8000`。

1. 将域名接入 Cloudflare，在 Zero Trust 控制台创建 Tunnel。
2. 为 Tunnel 添加 Public Hostname，例如 `agent.example.com`。
3. Service Type 选择 `HTTP`，Service URL 填写 `http://agent:8000`。这里必须使用 Compose 服务名 `agent`，不能填写 `127.0.0.1`。
4. 在 Tunnel 页面选择“Add a replica”，复制命令中的 `eyJ...` Token，只把它写入服务器本地 `.env.server`：

```dotenv
DIGITAL_IC_AGENT_BIND_ADDRESS=127.0.0.1
CLOUDFLARE_TUNNEL_TOKEN=eyJ...replace-with-real-token
```

5. 使用 H100 与 Tunnel 两个叠加配置启动：

```bash
docker compose --env-file .env.server \
  -f compose.yaml \
  -f compose.h100.yaml \
  -f compose.tunnel.yaml \
  up -d --build

docker compose --env-file .env.server \
  -f compose.yaml \
  -f compose.h100.yaml \
  -f compose.tunnel.yaml \
  ps
```

6. 检查隧道日志，然后在外地电脑打开配置的 HTTPS 域名：

```bash
docker compose --env-file .env.server \
  -f compose.yaml -f compose.h100.yaml -f compose.tunnel.yaml \
  logs -f cloudflared
```

Tunnel Token 等价于启动该隧道的凭据，不应发到聊天、截图或 GitHub。需要撤销访问时，可在 Cloudflare 控制台轮换 Token 或删除 Public Hostname。

### 状态检查

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/runtime
nvidia-smi
```

`/api/runtime` 用于确认模型配置、操作系统和 EDA 工具发现结果；`nvidia-smi` 用于查看两个 vLLM worker 的显存和利用率。

## 4. 数据持久化与升级

任务目录、队列和模型缓存均通过 Compose volume 映射到仓库目录。升级时保留这些目录：

```bash
git pull
docker compose -f compose.yaml -f compose.h100.yaml up -d --build
```

查看运行日志：

```bash
docker compose -f compose.yaml -f compose.h100.yaml logs -f agent
docker compose -f compose.yaml -f compose.h100.yaml logs -f vllm
```

## 5. 便携迁移包

Windows 端可生成包含源码、照片素材、提示词、Skills、模板、benchmark、文档和部署文件的迁移包：

```powershell
.\scripts\package_portable.ps1
```

脚本在 `dist/` 生成 ZIP 与 SHA256。解压到服务器后按双 H100 部署步骤启动即可。
