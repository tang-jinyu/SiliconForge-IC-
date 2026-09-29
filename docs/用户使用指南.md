# Digital IC Agent 用户说明书

这份说明书是给使用当前版本 agent 的用户看的。它不讲内部实现细节，重点回答三件事：

1. 现在这个 agent 已经能做什么。
2. 你应该怎么安装、运行和查看页面。
3. 你该怎么把它交给别的数字 IC 工程师使用。

## 这版已经能做什么

当前版本已经不是单纯整理 prompt 的脚本，而是一个可运行的数字 IC 自动化工作流内核。

它现在已经能完成这些事：

1. 从需求文本出发，自动跑完整数字 IC 闭环：需求分析、架构设计、规格生成、RTL 生成、TB 生成、EDA 检查、repair、review。
2. 支持多种任务类型，而不只是一个“大闭环”入口。
3. 通过 OpenAI-compatible API 调用大模型，而不是只支持单一厂商。
4. 通过 Icarus Verilog、vvp、Yosys 跑真实仿真和综合检查。
5. 提供 CLI、本地任务队列、HTTP API 和静态 Web UI。
6. 支持 running task 的取消、失败后 retry、详情查看、日志预览、产物预览、retry diff、波形缩略卡。
7. 在原生 OpenAI transport 下，任务取消不仅会在本地停止等待，还会发 provider-side request id cancel。

## 当前支持的任务类型

当前内置 5 类任务：

1. `digital_ic_workflow`：完整数字 IC 闭环。
2. `rtl_module_generation`：模块生成。
3. `tb_repair`：TB 修复。
4. `eda_triage`：对既有 RTL/TB 做预检、仿真和综合检查。
5. `interface_contract_check`：检查 RTL 与接口契约是否一致。

如果你只是第一次上手，建议先用 `rtl_module_generation` 或 `digital_ic_workflow`。

## 安装

推荐环境：

1. Python 3.11+
2. Windows PowerShell 或等价终端
3. 可选的 OSS CAD Suite

最简单的安装方式：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

如果你要跑浏览器回归测试，再额外执行：

```powershell
python -m pip install -e .[test]
```

## 模型配置

复制 `.env.example` 为 `.env`，填写这些环境变量：

1. `DIGITAL_IC_AGENT_API_KEY`
2. `DIGITAL_IC_AGENT_BASE_URL`
3. `DIGITAL_IC_AGENT_MODEL`
4. `DIGITAL_IC_AGENT_TEMPERATURE`
5. `DIGITAL_IC_AGENT_LLM_TIMEOUT_SECONDS`
6. `DIGITAL_IC_AGENT_LLM_TRANSPORT`

### 模型和 API 只能用 GPT / DeepSeek 吗？

不是。

当前接入方式是 OpenAI-compatible API，所以可以分成两类：

1. 原生 OpenAI：直接填 OpenAI 的 key、base URL 和模型名。
2. 兼容 OpenAI 协议的 provider：例如某些 DeepSeek、代理网关、自建兼容服务，只要它暴露 OpenAI-compatible 接口，就可以接。

这意味着它不是“写死只能用 GPT 和 DeepSeek”。更准确地说，它能接“任何足够兼容 OpenAI API 的模型服务”。

但要注意：

1. 如果 provider 支持 OpenAI Responses background API，那么 agent 可以用 provider-side request id cancel。
2. 如果 provider 只支持 chat/completions 风格接口，agent 会自动退回 chat transport。
3. 如果你把 `DIGITAL_IC_AGENT_LLM_TRANSPORT` 设成 `auto`，当前版本会优先探测 custom base URL 是否支持 Responses background，再决定走哪条 transport。

## 最常用的运行方式

### 1. 单次同步运行

适合先验证工作流能不能跑通。

```powershell
python -m digital_ic_agent run --task-file examples/hqc_single_fpga_case.md --output-dir runs/demo_run
```

### 2. 提交到本地队列

适合把任务先排进去，再由 worker 拉起执行。

```powershell
python -m digital_ic_agent queue-submit --task-file examples/hqc_single_fpga_case.md --output-dir runs/demo_queue
python -m digital_ic_agent queue-list
python -m digital_ic_agent queue-run-next
```

### 3. 打开 Web UI

如果你现在看不到页面，通常原因只有一个：服务没有启动。

启动命令：

```powershell
python -m digital_ic_agent serve --host 127.0.0.1 --port 8000
```

或者：

```powershell
digital-ic-agent-api
```

然后在浏览器打开：

`http://127.0.0.1:8000/`

### 如果你还是看不到页面，按这个顺序检查

1. 服务进程是否真的在运行。
2. 浏览器访问的是不是 `127.0.0.1:8000`。
3. 端口 8000 有没有被别的程序占掉。
4. 你是不是只执行了测试，没有真的启动 server。

## 第一次实操，建议按这个顺序来

如果你准备拿一个真实小项目来跑，不建议一上来就用最大闭环硬冲。

更稳的路径是：

1. 先跑一次 dry-run，确认安装、目录写入和 UI 都是通的。
2. 再拿一个小模块跑 `rtl_module_generation`，确认生成链路和输出目录结构。
3. 然后拿你现有的 RTL/TB 跑 `eda_triage`，确认仿真、综合和问题摘要链路。
4. 最后再把范围放大到 `digital_ic_workflow`。

推荐的第一条命令：

```powershell
python -m digital_ic_agent run --task-file examples/hqc_single_fpga_case.md --output-dir runs/first_smoke --dry-run
```

这一步主要验证三件事：

1. Python 环境和依赖没问题。
2. agent 能正常创建输出目录和中间结果。
3. 你本机的 `.env`、命令入口和路径都没有配错。

如果这一步还没过，不要直接上真实项目。

## 五类任务怎么选

第一次实操时，最常见的判断不是“能不能跑”，而是“该选哪类任务”。

可以按下面这个规则选：

1. 你只有需求，还没有 RTL/TB：选 `rtl_module_generation` 或 `digital_ic_workflow`。
2. 你已经有 RTL 和 testbench，想看问题出在哪：选 `eda_triage`。
3. 你怀疑主要是 testbench 有问题：选 `tb_repair`。
4. 你已经有 RTL 和接口规范，想先做一致性检查：选 `interface_contract_check`。
5. 你想从需求一路跑到规格、RTL、TB、EDA 和 repair：选 `digital_ic_workflow`。

如果你只是第一次试跑，推荐优先顺序：

1. `rtl_module_generation`
2. `eda_triage`
3. `digital_ic_workflow`

## Web UI 实操流程

如果你准备在页面里直接跑一个项目，建议按这个流程。

### 1. 先启动服务

```powershell
python -m digital_ic_agent serve --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`。

### 2. 先选任务类型，再填标题和需求文本

推荐做法：

1. 从顶部导航进入对应流程页。
2. 先选任务类型，再填任务标题。
3. 需求文本尽量写清楚接口、时序、复位、吞吐和验证目标。

一个适合第一次试跑的需求文本模板可以直接照着改：

```text
请生成一个可综合的 FPGA 模块，模块名为 gpio_debounce。
输入包括 clk、rst_n、gpio_in，输出为 gpio_out。
要求对输入做去抖，延迟窗口为 16 个时钟周期。
请同时生成最小可运行的 self-checking testbench。
RTL 风格要求同步时序、单时钟域、避免不可综合写法。
```

### 3. 如果你有现成 RTL / TB / 契约，打开“高级输入”

页面里的“高级输入”不是装饰，它直接对应任务 `metadata`。

当前支持这些字段：

1. `metadata.rtl_code`
2. `metadata.testbench_code`
3. `metadata.interface_contract`
4. `metadata.rtl_path`
5. `metadata.testbench_path`
6. `metadata.contract_path`

也就是说：

1. 你可以直接把 RTL/TB 文本贴进页面。
2. 也可以只填文件路径，让 agent 读本地文件。
3. 接口契约既可以直接贴文本，也可以填路径。

### 4. 三种最常见的真实项目输入方式

#### 场景 A：你要生成一个新模块

适合 `rtl_module_generation`。

你主要填：

1. 任务标题
2. 需求文本
3. 可选输出目录

这类任务通常不需要高级输入。

#### 场景 B：你已经有 RTL/TB，要做 triage

适合 `eda_triage`。

你有两种喂法：

1. 直接贴文本到 `rtl_code` 和 `testbench_code`
2. 在高级输入里填 `rtl_path` 和 `testbench_path`

如果你的 RTL/TB 已经在仓库里，第二种更省事。

#### 场景 C：你要检查接口契约

适合 `interface_contract_check`。

推荐至少准备这两样：

1. RTL 本体：`rtl_code` 或 `rtl_path`
2. 接口契约：`interface_contract` 或 `contract_path`

契约文本不必很长，但至少要写清楚端口、方向、位宽、时序约束和关键 handshake 语义。

### 5. 提交后重点看这三个区域

1. 左侧任务时间线：确认任务是否进入 `pending / running / succeeded / failed`。
2. 右侧详情舞台：看 LLM 诊断、任务资产、日志和生成产物预览。
3. 最近任务封面与个人照片：这是封面流，不是结果判定区，不要把它当作唯一状态来源。

### 6. 如果任务失败，优先这样排查

1. 先看详情页里的日志和 LLM 诊断。
2. 再看输出目录里的 `eda_result.json`、`simulation.log`、`yosys.log`。
3. 如果是输入不完整，直接修改需求文本或高级输入后重提，不要一开始就盲目 retry。
4. 如果是瞬时问题、模型输出跑偏或中间文件缺一块，再用 retry。

## 跑完后，输出目录里该重点看什么

不管你是 CLI 还是 Web UI，落盘结果通常都在 `runs/...` 或你手动指定的 `--output-dir`。

第一次实操时，建议重点盯这几个文件：

1. `specification.md`：需求是否被正确拆解。
2. `rtl_code.v`：RTL 风格是不是接近你能接受的工程写法。
3. `testbench.v`：testbench 是不是至少能自检。
4. `eda_result.json`：仿真和综合到底在哪一步出的问题。
5. `simulation.log`：波形/编译报错通常先在这里看。
6. `yosys.log`：综合问题先看这里。
7. `review.json`：最后的 review 和风险总结。
8. `run_manifest.json`：这一轮到底产出了哪些文件。

## 实际跑项目时最容易踩的坑

### 1. 服务没起来，但你以为页面问题

如果 `http://127.0.0.1:8000/` 打不开，先别看前端样式，先确认 serve 进程还活着。

### 2. 端口被旧进程占了

如果你刚跑过测试，或者之前开过一个旧 server，新的 `serve` 命令可能直接退出。

这时先停掉旧进程，再重新启动：

```powershell
python -m digital_ic_agent serve --host 127.0.0.1 --port 8000
```

### 3. 模型能调用，但 provider 行为和你预期不同

如果你使用的是 OpenAI-compatible provider，而不是原生 OpenAI：

1. `transport=auto` 可能会退回 chat 模式。
2. cancel 行为、超时和 provider-side cancel 的表现会因 provider 能力不同而不同。
3. 先看详情页的 LLM 诊断，不要只凭感觉判断。

### 4. 你想跑 triage，但没有把 RTL/TB 真正喂进去

`eda_triage` 不是只填一句“帮我检查一下”就行。

至少要满足下面二选一：

1. 贴入 `rtl_code` 和 `testbench_code`
2. 提供 `rtl_path` 和 `testbench_path`

### 5. 工具链问题被误判成 agent 问题

如果本机没有 Icarus Verilog / Yosys，或者路径没配对，EDA 相关结果会受影响。

这时优先检查：

1. `DIGITAL_IC_AGENT_IVERILOG_BIN`
2. `DIGITAL_IC_AGENT_VVP_BIN`
3. `DIGITAL_IC_AGENT_YOSYS_BIN`
4. `tools/oss-cad-suite/oss-cad-suite/bin`

## 推荐你第一次真实试跑的三步

如果你准备今天就拿一个项目实操，建议直接这样走：

1. 用 `--dry-run` 跑一个小样例，确认环境和目录没问题。
2. 用 Web UI 跑一个小模块生成任务，确认页面、详情和输出都能看懂。
3. 拿你现有项目里的一个最小 RTL/TB 组合跑 `eda_triage`，先验证 triage 闭环，再决定要不要上完整 workflow。

## 页面里现在能看到什么

当前 Web UI 已经能看和能操作，不只是演示图。

你可以在页面里做这些事：

1. 提交任务。
2. 看任务列表和实时状态。
3. 取消 running task。
4. 对终态任务 retry。
5. 展开 detail 查看产物、日志、retry diff、波形图。
6. 上传板卡图、波形图、日志快照和产物预览图。
7. 切换任务封面图。
8. 查看 LLM / provider 诊断信息，包括当前 transport、response id、provider cancel 是否命中。

## 怎么给别人使用

当前最现实的交付方式有两种。

### 方式 A：让别人直接在本机安装

适合小团队内部试用。

步骤：

1. 把仓库给对方。
2. 让对方按本说明创建虚拟环境并安装依赖。
3. 让对方配置 `.env`。
4. 让对方直接用 CLI 或启动 Web UI。

### 方式 B：你启动服务，让别人访问你的机器

适合先内部演示。

步骤：

1. 你在自己的机器上启动：

```powershell
python -m digital_ic_agent serve --host 0.0.0.0 --port 8000
```

2. 放开本机防火墙或公司内网访问策略。
3. 把你的机器 IP 和端口发给对方。
4. 对方在浏览器打开 `http://你的IP:8000/`。

通过 `DIGITAL_IC_AGENT_ACCESS_PASSWORD` 和 `DIGITAL_IC_AGENT_SESSION_SECRET` 启用登录与签名会话；通过反向代理配置 HTTPS、域名与访问策略。

## 适用场景

SiliconForge 适合：

1. 想用 agent 辅助做 RTL / TB / EDA 闭环的数字 IC 工程师。
2. 想快速生成模块骨架、补验证骨架、做 triage 的个人或小团队。
3. 希望把常用模块沉淀为个人参数化资产的工程团队。
4. 需要在 Windows 完成功能开发、再迁移到双 H100 服务器运行的参赛团队。

## 你接下来最常用的三个入口

1. CLI 同步执行：先验证 workflow。
2. 本地队列：先验证任务模型和取消/重试。
3. Web UI：先验证操作体验和详情页。

如果你只是想马上看到页面，最直接的命令还是：

```powershell
python -m digital_ic_agent serve --host 127.0.0.1 --port 8000
```
