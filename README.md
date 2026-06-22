# 清商 Qingshang

清商是一个面向宋词阅读场景的**垂直领域、证据驱动 AI 工作流应用**（vertical-domain, evidence-grounded AI workflow application）。

它不是一个开放式聊天机器人，而是把“文学解释”拆成可观察、可调试、可约束的多步 AI 工作流：从用户选择词句开始，系统依次进行**意图识别**、**任务路由**、**候选识别**、**外部证据检索**、**证据审阅**和**受控短注生成**，并保留每一步的输入摘要、输出摘要、耗时和局部错误。

当前版本：**Reader v0.2.0-preview（阅读器 0.2.0 预览版）**

---

## 项目定位

传统大语言模型（LLM）在解释古典文学文本时容易出现两个问题：

1. **解释不可追溯**：模型能生成流畅回答，但很难说明典故、出处、化用判断来自哪里。
2. **幻觉风险较高**：文学解释常涉及典故、历史人物、前代诗文、词牌、评注，模型容易把合理联想写成确定事实。

清商的目标不是让大语言模型直接“自由赏析”，而是建立一个**证据优先的 AI 工作流**（evidence-first AI workflow）：

```text
用户输入 / 选句
→ 意图路由（Intent Router）
→ 任务路由（Task Router）
→ 候选识别（Candidate Extraction）
→ 证据检索（Evidence Retrieval）
→ 证据审阅（Evidence Review）
→ 最终回答（Final Answer）
→ 工作流追踪（Workflow Trace）
```

解释不是一次生成，而是一个可以被审计和复盘的流程。

---

## 当前已实现能力

### 1. 意图识别（Intent Recognition）

系统会根据用户选择的词句、上下文和操作入口，判断当前任务类型，例如：

- 典故 / 用事解释
- 文献化用候选分析
- 字词或名物解释
- 证据检索与短注生成

当前版本采用轻量规则路由，后续可升级为大语言模型意图分类器（LLM intent classifier）。

### 2. 任务路由（Task Routing）

不同任务进入不同处理链路：

```text
典故/化用类问题
→ 候选识别
→ CNKGraph 证据检索
→ 证据审阅
→ 短注生成
```

该设计避免把所有问题都直接交给大语言模型生成，便于后续扩展更多工具，例如本地 Poetry RAG、网页搜索兜底（Web Search fallback）、词谱分析、格律校验等。

### 3. 候选识别（Candidate Extraction）

系统使用大语言模型从当前词句或整首词中识别疑似解释锚点，例如：

- 典故
- 前代文献语词
- 诗句化用
- 节令礼俗
- 历史地名
- 惯用文学母题

候选识别不是最终解释，只负责提出“值得查证的对象”。

### 4. 查询变体生成（Query Variants）

对于典故和化用，系统不会机械截取最短关键词，而是生成更适合检索的查询变体。

例如：

```text
燕台句
→ 燕台句
→ 燕台诗
→ 李商隐 燕台诗
```

这样可以减少“燕台”被误检为黄金台求贤一类结果的概率。

### 5. 外部证据检索（Evidence Retrieval）

当前外部知识源使用 CNKGraph，主要用于：

- 典故候选检索
- 出处与化用检索
- 前代诗文片段召回
- 词句相关外部证据获取

系统不会把检索命中直接当成结论，而是统一标记为**候选证据**。

### 6. 证据审阅（Evidence Review）

系统通过受控的大语言模型审阅器（LLM reviewer）审阅已检索到的证据，判断其与当前词句的关系：

- `prior_source`：前代来源候选
- `current_work_self_hit`：当前作品自命中
- `later_reuse`：后代沿用
- `weak_related`：弱相关
- `irrelevant`：无关或误命中
- `unknown`：无法判断

审阅器只能基于输入证据判断，不允许凭空补充出处、人物或故事。

### 7. 受控短注生成（Final Answer / Controlled Synthesis）

系统根据证据审阅结果生成 1–2 句谨慎短注。

短注会区分：

- 有较强证据支持的解释
- 需要人工确认的候选判断
- 证据不足或存在歧义的情况

例如系统不会把“查到结果”直接写成“已经确定为典故”。

### 8. 工作流追踪（Workflow Trace）

每次运行工作流都会展示：

- 步骤名称
- 工具名称
- 运行状态
- 耗时
- 输入摘要
- 输出摘要
- 局部错误

示例：

```text
意图路由 · 完成 · 0 ms
候选识别 · 完成 · 6088 ms
证据检索 · 完成 · 4448 ms
证据审阅 · 完成 · 5954 ms
最终回答 · 完成 · 0 ms
```

这使系统具备基础可观测性，便于后续做性能优化、缓存命中率统计、失败归因和成本控制。

---

## 轻量状态与记忆机制

当前版本没有实现复杂长期记忆系统，但已经保留了面向工作流的轻量状态设计：

- 当前作品 `poem_id`
- 当前句号 `line_no`
- 用户选中文本 `selected_text`
- 候选锚点 `anchor`
- 查询变体 `query variants`
- 证据结果 `evidence results`
- 审阅结果 `review result`
- 工作流追踪 `workflow trace`

这些状态保证系统可以把模型输出、外部证据和前端交互绑定回稳定的本地文本锚点。

后续可扩展为：

- 用户阅读历史
- 人工确认注释
- 证据快照缓存
- 提示词版本 / 模型版本追踪（prompt version / model version）
- 对话记忆（conversation memory）
- 已审阅注释记忆（reviewed annotation memory）

---

## 当前系统流程

```text
Reader 选句
  → 意图路由（规则）
  → 任务路由（固定工作流）
  → 候选识别（LLM）
  → CNKGraph 证据检索（典故与出处工具）
  → 证据审阅（只审阅已检索证据）
  → 最终回答（确定性聚合）
  → 工作流追踪（可视化执行过程）
```

---

## 技术栈

### 后端（Backend）

- FastAPI
- PostgreSQL
- SQLAlchemy 异步 ORM
- Pydantic
- 异步服务层（async service layer）
- REST API

### 前端（Frontend）

- Streamlit Reader
- 逐句阅读与选句交互
- 候选证据侧栏
- 工作流追踪展示

### AI 与工具层（AI / Tooling）

- 大语言模型候选识别（LLM candidate extraction）
- 大语言模型证据审阅（LLM evidence review）
- CNKGraph API 集成
- 确定性聚合（deterministic aggregation）
- 工作流结果结构化数据模型（structured schemas）

---

## 为什么不是普通 RAG

普通检索增强生成（RAG）通常是：

```text
query → retrieval → LLM answer
查询 → 检索 → 大语言模型回答
```

清商当前工作流是：

```text
文本锚点
→ 意图识别
→ 任务路由
→ 候选识别
→ 证据检索
→ 证据审阅
→ 受控生成
→ 工作流追踪
```

差异在于：

1. 检索对象不是普通 query，而是经过候选识别的解释锚点。
2. 检索结果不会直接进入最终回答，而是先经过证据审阅。
3. 系统会区分前代来源、当前作品自命中、后代沿用和弱相关。
4. 每一步都有结构化追踪，方便调试、评估和后续优化。

---

## 与企业 AI 应用场景的相似性

虽然当前领域是宋词阅读，但系统设计对应的是通用的垂直领域 AI 应用问题。

在企业合规、税务、审计、知识库问答等场景中，也常见类似需求：

- 专业文本密集
- 术语和上下文依赖强
- 回答必须可追溯
- 需要引用依据
- 不能让模型直接给出不可审计结论
- 需要人工复核
- 需要日志、权限、缓存和版本管理

因此清商的工作流可以类比迁移到：

```text
法规条文 / 客户材料 / 申报记录
→ 意图识别
→ 任务路由
→ 文档检索
→ 证据审阅
→ 风险提示或解释生成
→ 审计日志
```

---

## 当前边界

Reader v0.2.0-preview 不是完整开放式智能体（Agent）系统。

当前尚未接入：

- 网页搜索（Web Search）
- Poetry RAG
- CCPoem-Bert 向量检索
- LangGraph
- 长期用户记忆
- 权限系统
- 生产级监控
- 云端正式部署

这些能力已在架构中预留，但尚未作为当前版本能力宣称。

---

## Public Demo Mode（公开演示模式）

为方便在线展示，系统支持公开演示模式（Public Demo Mode）：

```text
PUBLIC_DEMO_MODE = true
```

该模式使用内置样例数据，不依赖：

- PostgreSQL
- LLM API key
- CNKGraph API key

页面会明确标记为 sample data（样例数据），用于：

- Streamlit Cloud demo（Streamlit 云端演示）
- 面试展示
- 离线演示
- 工作流结构说明

配置模板见：

```text
.streamlit/secrets.toml.example
```

真实密钥不应提交到 Git。

---

## 本地运行

复制 `.env.example` 为 `.env`，填写本地 PostgreSQL 和 LLM 配置。

启动 FastAPI：

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

启动 Reader：

```bash
.venv\Scripts\python.exe -m streamlit run apps/reader_app.py --server.port 8501
```

访问：

```text
Reader: http://127.0.0.1:8501/
API Docs: http://127.0.0.1:8000/docs
```

---

## 验证

```bash
.venv\Scripts\python.exe -m compileall app apps scripts tests
.venv\Scripts\python.exe -m pytest -q
```

---

## 部署方向

当前 demo 可使用 Streamlit Community Cloud（Streamlit 社区云）展示前端。

正式部署可逐步迁移到 Azure：

- FastAPI → Azure App Service / Azure Container Apps
- PostgreSQL → Azure Database for PostgreSQL
- 密钥管理 → Azure Key Vault
- 日志与指标 → Application Insights
- 未来检索层 → Azure AI Search
- 未来模型层 → Azure OpenAI / Azure AI Foundry
- 后台任务 → Azure Functions / Container Apps Jobs

迁移目标不是改变当前工作流，而是提升可部署性、权限治理、可观测性和扩展能力。

---

## 未来计划

### v0.2.x

- 完善证据审阅
- 增强短注稳定性
- 改进候选证据排序
- 增加缓存与错误恢复

### v0.3.x

- 本地 Poetry RAG
- BM25 / n-gram / CCPoem-Bert 混合检索（hybrid retrieval）
- 变形诗句化用召回

### v0.4.x

- 知人论世扩展
- 作者画像
- 典故人物背景
- 文学史语境解释

### v0.5.x

- 缓存策略
- 延迟统计（latency）
- 缓存命中率（cache hit ratio）
- DeepSeek / LLM 使用量追踪
- P50 / P95 性能分析

### v0.6.x

- LangGraph / 智能体工作流（Agentic workflow）
- 网页搜索兜底（Web Search fallback）
- 多工具任务编排
- 长期记忆与人工确认注释沉淀

---

## 当前状态

清商目前处于 **v0.2.0-preview（预览版）**。

它的重点不是“让 LLM 写一篇漂亮赏析”，而是证明：

> 一个垂直领域 AI 应用可以通过意图识别、任务路由、证据检索、证据审阅和工作流追踪，把模型生成能力约束在可追溯、可调试、可复核的系统流程中。
