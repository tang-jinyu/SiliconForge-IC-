# 参与 SiliconForge 开发

感谢你愿意一起完善面向数字 IC 的可验证 Agent。SiliconForge 采用 **Fork + Pull Request** 的开放协作方式：每位开发者可以在自己的 Fork 中安全实验，再把成熟改动提交回上游仓库统一评审、测试和发布。

## 推荐协作流程

1. 在 GitHub Fork 本仓库，然后克隆自己的 Fork。
2. 添加上游仓库为 `upstream`，定期同步主分支。
3. 为每项功能创建独立分支，不直接在 `main` 上开发。
4. 新功能同时补充测试、中文文档和必要的示例。
5. 运行相关测试与 EDA 回归后，向上游仓库提交 Pull Request。

```bash
git clone https://github.com/<your-name>/<repo>.git
cd <repo>
git remote add upstream https://github.com/<upstream-owner>/<repo>.git
git fetch upstream
git switch -c feature/short-description upstream/main
```

## 开发环境

### Windows / 本地 API 模式

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
Copy-Item .env.example .env
python -m digital_ic_agent serve --host 127.0.0.1 --port 8000
```

开发者无需 H100。使用阶跃星辰等远程模型时，应在自己的 `.env` 或 GUI 会话中填写个人 API 配置；Icarus Verilog 与 Yosys 可在 CPU 上完成主要仿真和综合验证。

### Docker / 双 H100 模式

参见 [部署说明](docs/DEPLOYMENT.md)。双 H100 用于本地 vLLM 推理，不是运行 GUI 或参与代码贡献的前提。

## 适合贡献的方向

- 新的参数化 RTL/TB 模板和独立 oracle
- 组合运算、FSM、FIFO、协议、修复任务之外的新 benchmark
- Icarus、Yosys、Vivado、Verilator 等工具适配
- Prompt、Verified Skills、失败指纹和修复策略
- 处理器前端、AI 加速器、片上互连与安全芯片场景
- GUI、国际化、任务可视化和工程编辑体验
- 双 H100/vLLM 性能优化、部署与可观测性
- 文档、教程、演示案例和可复现实验

## Pull Request 要求

- 一个 PR 聚焦一个明确问题，说明动机、实现方式和影响范围。
- 行为变化必须给出验证证据；RTL 变化应附仿真/综合结果。
- 不提交 `.env`、API Key、Tunnel Token、模型权重、运行目录或个人数据。
- 保持现有中文 GUI 和结构化交付目录兼容；改变接口时同步更新文档。
- PR 描述应关联对应 Issue；大型设计先开 Discussion/Issue 对齐方案。

## 测试

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m digital_ic_agent benchmark-run `
  --suite-dir benchmarks/blind_v1 `
  --output-dir runs/blind_v1
```

根据改动范围，可以补充更小的定向测试，但 PR 中应写明实际执行了哪些验证。

## 贡献者署名

被合并的功能会在发布记录和贡献者名单中保留作者署名。重要模块的长期贡献者可加入维护者评审，并参与路线图与版本规划。我们鼓励公开实验过程、失败证据和复现方法，让改进优先沉淀到共同上游，而不是形成彼此隔离的实现。

