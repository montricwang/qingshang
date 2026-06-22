# 清商当前设计取舍审计

> 审计日期：2026-06-22  
> 审计对象：当前工作区代码与文档，不修改业务代码  
> 配套登记：`docs/decisions/decision_register.md`

## 1. 审计方法与边界

本次逐项核对了以下实现，而不是只依据项目简介：

- 文本链路：`scripts/clean_zhoubangyan_working_text.py`、`scripts/import_zhoubangyan_poems.py`、`app/models/poem.py`。
- API 链路：`app/api/routes/poems.py`、`app/api/routes/cnkgraph.py`、`app/api/routes/__init__.py`。
- 外部工具链路：`CNKGraphClient._request_json()` 与 `cnkgraph_tools.py` 的五个 `build_*` 适配函数。
- LLM 链路：`poem_analyzer.py`、`allusion_candidate_extractor.py`、`llm_client.py`。
- Reader 链路：`apps/reader_app.py` 的四种阅读模式、候选选择、reading-aids 表单、缓存与 session state。
- 验证链路：`tests/` 五个测试文件、`scripts/probes/` 和 `docs/sync/latest.md` 的真实冒烟记录。

仓库中不存在 `app/prompts/*.md`，本轮开始前也不存在 `docs/decisions/decision_register.md`。前者说明 prompt 仍属于 Python 服务实现，后者说明过去的理由主要散落在同步文档和代码边界中。

## 2. 结论先行

当前架构最值得保留的不是某个框架，而是三条已经形成的边界：

1. Reader 只通过 FastAPI 访问数据，正文阅读不依赖 CNKGraph 或 LLM 成功。
2. LLM 只产生待查锚点与查询变体；后端可自动请求证据，但不会让 LLM 评价证据或生成解释。
3. CNKGraph 原始字段先经过工具适配，再由 Reader 读取清商字段。

当前最需要重审的也不是功能数量，而是六个会阻碍正式发布的问题：

| 优先级 | 问题 | 直接证据 | 判断 |
|---|---|---|---|
| P0 | 文本底本缺少可核验来源、版本、许可与校勘记录 | `clean_zhoubangyan_working_text.py:SOURCE` 只有一条来源字符串 | D-001，high |
| P0 | LLM 与 CNKGraph 没有后端缓存、认证、限流和成本保护 | `chat_completion()` 与 `build_poem_reading_aids()` 每次实时调用 | D-004/D-014，high |
| P0 | `/analyze` 无证据直接生成完整赏析，与新主线不一致 | `poem_analyzer.build_analysis_prompt()` 不读取任何 Evidence | D-009，high |
| P0 | 数据库没有迁移版本链 | `create_all()` 加独立 `drop_redundant_indexes.sql` | D-017，high |
| P1 | 自动测试不覆盖真实数据库和 ASGI 生命周期 | `tests/` 以纯函数、mock 与 OpenAPI 存在性为主 | D-018，high |
| P1 | 没有语料快照和典故候选质量集 | 清洗规则与 prompt 改动没有 corpus/eval 门禁 | D-019，high |

## 3. 分类审计

### 3.1 数据源与文本底本

**当前判断：结构化链路可保留，来源治理必须补。**

- `INPUT_PATH = data/working/zhoubangyan.txt` 到 `OUTPUT_JSON_PATH` 再到 PostgreSQL 的链路清楚，且导入前后都经过 `PoemCore`；这是工程上的稳定收益，对应 D-002。
- `SOURCE = "国学典籍网《全宋词·周邦彦》工作整理文本"` 只说明网站与集合，不说明具体页面、获取日期、整理者改动、繁简转换、标点来源和许可。Reader 的 `render_poem()` 原样展示该字符串，会让用户误以为它已经是充分的书目出处。
- `PoemModel.source` 位于作品层，无法表达某句异文、某处人工改字或多个底本。现在不要改表，但在正式版前至少应先建立独立的来源说明文档和数据清洗 manifest。
- `import_zhoubangyan_poems.py` 对作者做 delete 后全量导入，适合当前只读语料；未来若候选、注释或用户数据引用数据库自增 `id`，该策略会破坏引用。当前外部定位使用稳定 `poem_id` 与 `global_line_no`，暂时避免了这个问题。

**建议**：保留清洗/JSON/导入三级链路；把“来源 manifest + 语料哈希 + 许可结论”设为正式发布门槛，不要先扩充更多作者。

### 3.2 外部 API / 工具选择

**当前判断：工具范围克制，但供应方风险尚未被产品边界吸收。**

- 不接 labelize 是有实测支持的正确决定。`integration_v0_1.md` 把两个 404 接口排除，避免把不可用聚合能力伪装成主线，D-003 应保留。
- `/api/cnkgraph/*` 直接把供应方名称写进清商公开路径。Swagger 调试很方便，但若将来切换来源，前端或第三方调用者会感知供应方变化。reading-aids 路径更接近清商领域语言，应优先作为产品接口。
- `CNKGraphClient._request_json()` 每次调用都新建 `httpx.AsyncClient`。`build_poem_reading_aids()` 查询多字时又逐字串行调用 `build_char_evidence()` 和 `build_rhyme_evidence()`；这既没有连接池复用，也让长短语延迟随字符数增长。
- `_unique_lookup_chars()` 使用 `char.isalpha()`，不仅会选汉字，也会选拉丁字母。当前 Reader 提示用户输入中文短语，所以问题不突出；一旦允许混合文本，应明确“字典工具字符集”而不是依赖 Python 的字母定义。
- 真实 probe 证明“某日可访问”，尚未证明调用许可、限流、SLA 和长期稳定性。当前不能把 69/71 的成功率解释为可生产依赖。

**建议**：近期继续使用现有五类工具，但产品代码应面向 provider-neutral 的 reading-aids；连接复用、并发上限和供应方许可在公网部署前重审。

### 3.3 适配层与字段窄化

**当前判断：分层方向正确，公开 `raw` 与静默丢字段削弱了边界。**

- `CNKGraphClient` 不解释领域字段、`cnkgraph_tools.py` 不处理 HTTP，这一分工明确，应保留 D-005。
- `build_char_evidence()` 只取第一本 `ModernDictionary`、第一条 Usage、第一条 Explain；`build_allusion_candidates()` 只取第一条 Explain 和 Quote。这是可接受的 v0.1 摘要策略，但代码和响应没有告诉调用者“还有其他释义被省略”。
- `EvidenceItem.raw`、CNKGraph `AllusionCandidate.raw`、`ProsodyAid.raw` 会被 FastAPI 序列化。Reader 虽然不展示 raw，但“前端不用”不等于“API 没公开”。正式 API 应把调试原文移到受控日志、内部模型或显式 debug 开关。
- LLM `AllusionCandidateItem` 与 CNKGraph `AllusionCandidate` 都叫候选，却处于不同阶段。Reader 上方“AI 候选”和下方 Tab“典故候选”靠位置区分，不是靠概念命名区分。

**建议**：保留 adapter；在 v0.2 契约设计时把 `raw` 从默认公开响应移除，并将两个候选阶段命名为“检索锚点”和“证据候选”一类可区分术语。

### 3.4 LLM 职责边界

**当前判断：新候选提取符合主线，旧整首赏析仍是最大的语义冲突。**

- `filter_allusion_candidates()` 校验 anchor 位于对应 line、每句最多 2 个、全词最多 10 个，并使用 `REASON_TEMPLATES` 覆盖模型自由理由。这是明确的“模型提议、程序守边界”。
- `query` 没有像 `reason` 一样归一化。真实《兰陵王·柳》输出中 query 曾包含“唐代制度”等具体限定；它不会直接展示为证据，但未来自动接 reading-aids 时可能把模型假设带入检索。
- `PoemAnalysis` 对 JSON 形状做校验，但 `analyze_poem()` 的事实来源仍只有原文与模型。结构正确不能替代证据正确。
- 两套 prompt 都内嵌 Python，模型名来自全局 settings，响应没有返回 model、prompt version 或生成时间。即使以后缓存，也无法可靠解释结果差异。
- `chat_completion()` 在 HTTP 错误中拼接 `response.text`。这有助调试，但正式日志或 API detail 需要避免暴露供应方响应中的敏感信息。

**建议**：保留 allusion-candidates 的有限职责；在有证据组合方案前，不把 `/analyze` 接入 Reader，并把它标为实验性。prompt 外置不是为了“文件更整齐”，而是为了版本化和质量评测。

### 3.5 Workflow / Agent 边界

**当前判断：采用固定自动查证 workflow，仍不进入 Agent。**

当前页面的实际流程是：

```text
整首 LLM 候选 + query_variants
  -> 固定调用 CNKGraph allusion/reference
  -> 每个 query/source 返回 hit/no_result/error
  -> 用户仍可选择 anchor
  -> selected_text + line_no
  -> 用户可继续提交 reading-aids
```

- `/allusion-candidates/with-evidence` 使用固定的候选、查询变体和两类工具矩阵，不做自主规划；它是可枚举 workflow，不是 Agent。
- `choose_allusion_candidate()` 仍只调用 `choose_line()`；query_variants 不进入 selected_text，也不被当成解释。
- `_collect_or_error()` 让每个工具独立降级，Reader 只在全部所选工具硬失败时显示整次失败，符合“正文永远先可读”。
- 自动查证最多产生 60 次外部调用，当前没有缓存、限流、workflow ID、步骤日志或可恢复状态；这使 D-011 风险由 low 调整为 medium。
- “AI 综合解释”仍是占位区。未定义证据选择、引用格式、冲突处理前，不应以 Agent 名义把现有函数自动串起来。

**建议**：D-011 保留。下一阶段优先补缓存/限流和 evidence bundle 评测，不优先选择 Agent 框架。

### 3.6 前端框架与交互

**当前判断：Streamlit 适合当前学习型原型，但单文件和内部 CSS 选择器已到重审阈值附近。**

- `main()` 只负责装配目录、正文和工具列，且所有数据来自 FastAPI，说明 Streamlit 没有侵入数据库层。
- `st.session_state` 已管理 poem、选句、候选、证据、阅读模式、播放索引与速度；状态间清理依赖 `choose_poem()` 和 `choose_line()` 的手工约定。新增状态时容易漏清理。
- `install_styles()` 大量使用 `data-testid`、`st-key-*` 和 BaseWeb DOM 结构。升级 Streamlit 可能在 Python 测试仍通过时破坏样式或交互。
- 通读/慢读/转轮/领读共享原始 line 数据，慢读只在 `display_text` 加全角空格，未污染 selected_text，这是值得保留的展示层边界。
- `fetch_opening_lines()` 为当前页无标题作品并发请求详情，缓存 300 秒。它避免修改列表 API，却制造了最多 24 个额外请求；这是典型的“短期保持后端不动，前端承担 N+1”。

**建议**：暂不换前端框架。先把 API client、纯展示函数、主题 CSS 和页面装配拆开；当出现第二页面或多用户需求时，再比较 Streamlit 与正式 Web 前端，而不是现在重写。

### 3.7 缓存与持久化

**当前判断：本地读缓存够原型使用，外部调用无缓存不适合公开服务。**

- 30 秒目录/详情缓存解决的是 Streamlit rerun，不是数据库查询缓存；300 秒 opening-line 缓存解决的是目录 N+1 的重复部分。
- allusion-candidates、reading-aids 和 `/analyze` 均不缓存。相同 poem、anchor、include、模型和 prompt 会重复发起远端请求。
- 没有缓存 key 设计，也没有记录 CNKGraph 响应时间、模型版本或 prompt 版本。现在直接加 Redis 只会把不稳定语义缓存得更久。
- 不持久化结果是合理暂缓，但因此没有人工确认、纠错和回归样本的自然来源。

**建议**：先定义可审计 key：`poem_id + text/line_no + tools + provider/model + prompt/schema version`，再选择内存、数据库或 Redis。公网前至少需要短期去重、超时、限流和成本上限。

### 3.8 数据库结构

**当前判断：三层正文结构暂时不要动；迁移能力必须先于下一次 schema 变更。**

- `poem_id` 与 `(author, author_order)` 唯一约束、section/line 双层编号和 relationship `order_by` 已被 API、prompt、Reader 与测试共同依赖。
- `full_text` 是派生冗余字段，当前由清洗/导入流程维护；数据库本身没有约束证明它等于 lines 拼接。
- `PoemLineModel` 同时持有 `poem_db_id` 与 `section_db_id`，方便约束全词行号，但数据库没有复合约束证明 line 的 poem 与 section 的 poem 相同。现有导入器会正确写入，任意其他写入路径需要小心。
- 没有 Alembic 时，不应新增候选、缓存或注释表。D-017 的重审条件已经满足于“任何下一次 schema 变更之前”。

**建议**：保留 D-016；把 Alembic 基线作为所有持久化新功能的前置任务。

### 3.9 测试与验证

**当前判断：单元测试方向合理，但“34 passed”不能覆盖当前主要风险。**

- `test_allusion_candidates.py` 覆盖 anchor、类型、每句/全词上限和 mock JSON；它不能评价“月榭”是否应该成为候选。
- `test_cnkgraph_tools.py` 可保护已知样本的字段适配，但没有保存正式契约 fixture 来检测供应方字段漂移。
- `test_reader_app.py` 保护纯函数和文本安全，不运行真实 Streamlit 事件循环；领读自动推进此前只做到局部浏览器验证。
- `test_core.py` 检查 OpenAPI path 存在，不发送 ASGI 请求，也不验证 Depends(get_db)、404、500 或 response_model。
- 真实 probe 与《兰陵王·柳》冒烟很有价值，但结果是时间点证据，尚未转成可重复的领域评测集。

**建议**：按风险补测试，而不是先追覆盖率数字：

1. PostgreSQL + FastAPI 集成测试：列表、详情、404、reading-aids 局部失败、候选接口 response_model。
2. 188 首语料快照：作品数、片数、句数、关键 poem_id、稳定哈希。
3. 典故候选评测集：至少记录应选、不可选、可接受 uncertain，并按模型/prompt 版本运行。
4. Playwright 冒烟：四阅读模式、候选回填、深浅主题、局部错误显示。
5. CI：compileall、pytest、基础 lint/format；真实 CNKGraph/LLM 保持手动或定时非阻断任务。

### 3.10 当前版本范围控制

**当前判断：功能边界文字清楚，但版本定义没有形成发布门。**

- 多轮任务都明确写了“不改数据库、不做 Agent、不接 labelize、不自动解释”，说明范围控制是有效的。
- Reader 从 v0.1.5 到 v0.1.11 已包含目录、主题、证据工具、四种阅读模式、整首候选识别和自动证据预览；“v0.1”现在同时表达 API 原型和较丰富 UI，缺少统一完成定义。
- `integration_v0_1.md` 说“下一轮可增加缓存和契约样本”，但当前已经新增 LLM 候选，而缓存与契约治理仍未补上，说明功能推进快于基础约束。
- `/analyze` 属于早期能力，Reader 的“AI 综合解释”却仍未接入。保留接口没有问题，但不应让它自动代表未来综合解释方案。

**建议**：把下一版本定义为一组验收门，而不是更多按钮：来源说明、Alembic 基线、API 集成测试、候选评测、外部调用成本保护。完成前继续暂缓 Agent、持久化注评和自动综合解释。

## 4. 建议动作总表

| 顺序 | 动作 | 关联决策 | 完成标准 |
|---|---|---|---|
| 1 | 建立文本来源与语料 manifest | D-001/D-002 | 有来源 URL/获取日期/许可结论/整理规则/JSON 哈希，不改正文也可完成 |
| 2 | 明确 `/analyze` 的实验状态 | D-009 | 文档和产品均不把无证据赏析称为正式综合解释 |
| 3 | 为外部调用设计成本保护 | D-004/D-014 | 有请求去重、限流、超时、调用日志和缓存 key 规范 |
| 4 | 建立 Alembic 基线 | D-017 | 当前三表与索引可从迁移重建，下一次 schema 变化不再依赖零散 SQL |
| 5 | 补数据库/API 集成测试 | D-018 | 真实 ASGI + 测试数据库覆盖主要成功与错误路径 |
| 6 | 建立语料与典故候选评测集 | D-019 | 清洗变更和 prompt/model 变更都有可比较报告 |
| 7 | 收紧公开 CNKGraph 契约 | D-006/D-007 | 默认响应不暴露 raw，两类候选命名可区分 |
| 8 | 拆分 Reader 内部模块 | D-013 | 不改变页面行为，API/CSS/纯函数/页面装配边界清楚 |

## 5. 当前建议暂时不要动

- 不重构 poems/sections/lines 三层结构，也不改变 `poem_id`、`global_line_no` 和原文数据。
- 不接 labelize，不用新的自动笺注接口替代当前人工 workflow。
- 不引入 Agent 框架；当前没有需要自主规划的任务，只有明确的候选、查询和展示步骤。
- 不为“可能以后会用”而新增人物、地理、古籍或注释表；先完成来源、迁移和评测基础。
- 不立即更换 Streamlit；当前问题主要是单文件耦合与测试方式，不是框架已经无法承载功能。
- 不把 CNKGraph probe 成功率或 26 项单元测试解释为生产就绪。

## 6. 本轮文件范围

本轮只新增/更新设计文档及其 Git 跟踪规则：

- `docs/decisions/decision_register.md`
- `docs/audits/current_decision_audit.md`
- `docs/sync/latest.md`
- `.gitignore`：只放行上述两份新治理文档，其他 `docs/*` 仍保持忽略。

没有修改 `app/`、`apps/`、`scripts/`、数据库结构、API 或运行配置。
