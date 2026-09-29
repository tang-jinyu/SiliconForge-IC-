# Digital IC Agent 原理解析说明书

这份文档不是用户操作手册，而是给想系统学习这个项目的人看的。重点回答：

1. 这个 agent 现在由哪些层组成。
2. 为什么选现在这套框架和架构。
3. 如果你以后要继续扩到侧信道、更多任务类型或更强的 UI/API，这套结构是否扛得住。

## 一句话理解当前架构

当前项目不是“一个会调模型的网页”，而是：

1. 以 `task_service.py` 为中轴的任务执行平台。
2. 以 `workflow.py` 为核心的数字 IC 闭环工作流。
3. 以 `task_queue.py`、`api.py`、`web/app.js` 为外壳的可操作产品骨架。

## 当前分层

可以把它理解成 6 层：

1. 入口层：CLI、HTTP API、Web UI。
2. 服务层：`task_service.py`，负责统一的任务生命周期、取消、重试、落盘。
3. 队列层：`task_queue.py`，当前是本地文件队列。
4. 工作流层：`workflow.py`，负责多阶段数字 IC 任务链路。
5. 能力层：`llm.py`、`prechecks.py`、`eda.py`。
6. 展示层：`task_views.py` 和静态前端，负责把内部状态转成用户可看、可操作的 detail/summary。

## 为什么用 LangGraph

当前工作流编排选的是 LangGraph。

### 选它的原因

1. 这个项目天然是多阶段状态机，不是一次 prompt 调用。
2. 数字 IC 任务存在明显节点边界：需求分析、架构、规格、RTL、TB、EDA、repair、review。
3. 任务中间态需要可恢复、可检查点化、可插 repair 回路。
4. 后面如果要扩 tool call、人工审批、失败分支、策略分支，图结构比线性脚本更自然。

### LangGraph 在这里的优点

1. 节点和边清晰，适合多阶段 agent。
2. 状态对象集中，便于落盘和调试。
3. repair / review 这类回环比普通函数链更自然。
4. 后续要插更多任务节点时成本较低。

### LangGraph 在这里的代价

1. 对简单任务来说会显得重。
2. 调试成本高于一层普通函数调用。
3. 如果节点拆得太碎，状态管理会变复杂。

## 为什么不是直接用“一个大 Prompt + 一个大函数”

那条路一开始写起来快，但会很快失控。

缺点主要有：

1. 中间产物不清楚。
2. 失败后不知道该从哪里 repair。
3. 没法做有边界的取消、重试和日志定位。
4. 很难把 UI/API/队列接上。

这个项目现在已经有 running cancel、retry diff、task detail、provider cancel 这些需求，如果还是“大函数式 agent”，后面维护会非常痛。

## 为什么要有 task_service 这一层

`workflow.py` 只解决“如何跑一条任务链”。

但真正产品化时，你还需要解决：

1. 任务如何进入系统。
2. 任务如何排队。
3. 任务如何取消。
4. 任务失败后如何 retry。
5. 中间产物和最终产物如何统一落盘。
6. UI/API 如何不碰内部 workflow 细节。

这些都属于服务层职责，不属于工作流本身。所以当前结构把 `task_service.py` 单独拉出来，是对的。

## 为什么任务状态要单独建模

项目现在有：

1. `AgentTaskRequest`
2. `AgentTaskRecord`
3. `AgentTaskExecution`

这样做的意义，是把“用户提交的内容”“运行中的生命周期”“执行完成后的结果”拆开。

优点：

1. CLI / API / UI 都能复用同一套模型。
2. pending / running / cancel_requested / canceled / failed / succeeded 这些状态能统一处理。
3. 后续扩优先级、资源标签、侧信道任务类型时有明确落点。

## 为什么 LLM 层要单独封装

`llm.py` 现在不只是“调一下模型”。它已经承担：

1. OpenAI-compatible transport 选择。
2. OpenAI Responses background transport 与 chat fallback。
3. in-flight timeout。
4. cancel 协作与 provider-side cancel。
5. structured output 和 JSON fallback。
6. capability probe。
7. LLM trace 记录。

如果这些逻辑分散在 workflow 各节点里，后面几乎没法维护。

## 现在这套 transport 设计为什么合理

当前不是把所有 provider 强行绑成一种协议，而是两层策略：

1. 原生 OpenAI 或支持 Responses background 的兼容 provider：优先走 `responses_background`。
2. 只支持 chat 的兼容 provider：回退到 `chat`。

这样做的好处是：

1. 能吃到 provider-side request id cancel 的能力。
2. 不会因为追求最强能力把兼容 provider 全部打废。
3. transport 能继续扩，比如以后加 streaming、async、tool-call specialized transport。

## 启动期 capability probe 的意义

以前的 auto transport 只能靠域名判断是不是 OpenAI 原生端点，这不够。

现在的 probe 逻辑解决的是：

1. 某个 custom base URL 到底支不支持 Responses background。
2. transport 该选 `responses_background` 还是 `chat`。
3. 这个判断应该在进程启动时尽量先做，而不是等任务跑到一半才发现 transport 选错。

这就是一个典型的“平台工程问题”，不是纯 prompt 工程问题。

## 还有哪些常见 agent 架构可选

除了当前这套，常见还有几种。

### 架构 A：单 agent + 单函数链

优点：

1. 起步快。
2. 文件少。
3. demo 容易出结果。

缺点：

1. 状态不可控。
2. 失败回路难做。
3. 很难产品化。

### 架构 B：Planner / Executor 双代理

优点：

1. 复杂任务拆解更强。
2. 任务计划可以单独优化。

缺点：

1. token 成本更高。
2. 不一定适合当前这种强流程、强产物约束的数字 IC 闭环。

### 架构 C：多 agent 协作

例如分析 agent、RTL agent、验证 agent、EDA agent 各自独立。

优点：

1. 模块职责清晰。
2. 方便给不同模型分工。

缺点：

1. 协调复杂度高。
2. 中间协议和共享状态很快变成真正难点。

### 架构 D：工具中心型 agent

模型只负责决策，主要工作靠工具执行。

优点：

1. 可控性更高。
2. 更适合工程化。

缺点：

1. 前期工具设计工作量大。
2. 没有足够工具时，模型能力发挥不出来。

当前这个项目最接近的是“工作流骨架 + 工具中心型能力层”的折中方案。

## 可维护性怎么样

结论先说：当前版本的可维护性已经明显好于 prompt 脚本阶段，适合继续迭代，但还没到“大团队长期协作几乎不需要重构”的程度。

### 现在的维护优势

1. 入口层和核心执行层已经拆开。
2. 任务生命周期已经统一建模。
3. LLM transport / cancel / timeout 已经被隔离进 `llm.py`。
4. detail 视图由 `task_views.py` 统一生成，前端不直接读 workflow。
5. API 回归和浏览器回归都已经有了。

### 现在的维护风险

1. 任务类型虽然已有框架，但还不够多，很多规则仍主要围绕现有数字 IC 闭环生长。
2. 队列仍是本地文件队列，不适合真正高并发。
3. 目前 UI 仍是静态前端，不是组件化前端工程。
4. 侧信道、更多 EDA 模块、更多模式接入后，workflow 状态字段会继续膨胀，需要进一步模块化。

## 以后要加“侧信道”等功能，怎么接最合理

如果你以后想加侧信道分析、功耗、时序、可测性或别的数字 IC 任务，当前结构是能接的，但建议按下面方式扩：

1. 不要直接把侧信道逻辑硬塞进现有 workflow 节点。
2. 先把侧信道定义成新的 task kind。
3. 把专用 precheck、专用 EDA/tool、专用 review 规则拆成独立能力模块。
4. 如果侧信道流程和现有闭环差异很大，就为它建立新的 execution strategy。

也就是说，优先扩“任务模型和能力层”，而不是先把一个巨型 workflow 越堆越大。

## 什么时候适合认真做 UI

现在已经可以做，而且不是“等核心全做完再说”。

原因很直接：

1. 现在已经有稳定的任务模型。
2. 已经有 summary/detail API。
3. 已经有 cancel/retry/SSE/detail/diff/waveform/asset 这些可交互对象。

也就是说，UI 现在已经有稳定后端契约，不再是空壳阶段。

如果后面要继续做更正式的 UI，我建议顺序是：

1. 先把 detail 信息结构继续稳定。
2. 再决定是否把静态前端升级成 React/Vue 之类的工程化前端。
3. 最后再做更强的多任务过滤、图表、任务模板和报告面板。

## 学这个项目时最值得盯的 6 个文件

1. `digital_ic_agent/workflow.py`
2. `digital_ic_agent/task_service.py`
3. `digital_ic_agent/llm.py`
4. `digital_ic_agent/prechecks.py`
5. `digital_ic_agent/task_views.py`
6. `digital_ic_agent/api.py`

你可以按这个顺序读：

1. 先看 `task_service.py` 理解平台中轴。
2. 再看 `workflow.py` 理解 agent 主链路。
3. 再看 `llm.py` 理解 transport、timeout、cancel、probe。
4. 最后看 `api.py` 和 `task_views.py` 理解产品化接口是怎么接上的。