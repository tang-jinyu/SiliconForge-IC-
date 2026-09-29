# GitHub 上传清单

## 建议上传

从仓库根目录执行 `git add .` 时，当前 `.gitignore` 会自动筛选出应公开的工程文件。主要包括：

```text
.dockerignore
.env.example
.env.server.example
.gitignore
Dockerfile
compose.yaml
compose.h100.yaml
pyproject.toml
README.md
打开数字IC-Agent网页.cmd

digital_ic_agent/       Python、API、工作流、EDA 与 GUI
skills/                 Agent Skill Markdown 与参考说明
project_prompt/         工作流提示词
prompt/                 RTL/TB/repair 提示词资料
benchmarks/             五类盲测和 oracle
examples/               示例输入
picture/                默认人物照片与 3D 相册素材
docs/                   架构、部署、技术栈和使用文档
scripts/                安装、启动、打包与演示脚本
tests/                  自动化测试
```

`picture/` 中的七张照片会随公开仓库一同公开展示。如果仓库面向公众，先确认这些图片就是准备对外发布的版本。

## 自动排除

以下内容已由 `.gitignore` 排除，不会被 `git add .` 加入：

```text
.env
.env.stepfun
.env.server
.venv/
.agent_queue/
runs/
tmp/
dist/
model-cache/
tools/
论文参考/
video_assets/
fpai_demo_src_vivado/
*.egg-info/
__pycache__/
*.pyc
*.log
*.pb
*.zip
```

其中 `.env*` 本地配置保存模型 Key、访问口令和会话密钥；`runs/`、`.agent_queue/` 是用户任务和运行状态；`dist/`、`video_assets/` 是体积较大的生成成品与中间素材。

## 发布命令

```powershell
git status --short
git add .
git status --short
git commit -m "release: publish SiliconForge digital IC agent"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

第二次 `git status --short` 用于确认 `.env`、运行目录和大模型缓存没有进入暂存区。当前仓库公开候选文件均小于 GitHub 的单文件限制。
