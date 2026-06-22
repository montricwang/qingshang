# 清商项目决策登记表

> 建立日期：2026-06-22  
> 审计基线：Reader v0.1.10、CNKGraph Tool Layer v0.1、Allusion Candidate Extractor  
> 状态说明：本表记录当前代码已经形成的设计取舍；“当时理由”若没有原始 ADR，依据代码、同步文档和提交结果反推，并明确标为“推定”。

## 使用规则

- 决策编号保持稳定；后续改变结论时更新状态和复审日期，不复用旧编号。
- 风险等级表示“维持当前方案而不重审”的风险，不表示实现质量。
- `保留` 表示当前方案适合继续使用；`扩展` 表示保留边界后补能力；`重构` 表示行为目标保留但实现需要调整；`删除` 表示应退出主线；`暂缓` 表示现在不要投入。

## 1. 数据源与文本底本

### D-001 单一工作整理文本作为当前周邦彦底本

- **决策内容**：以 `data/working/zhoubangyan.txt` 为输入，统一标记来源为“国学典籍网《全宋词·周邦彦》工作整理文本”，当前 Reader 只展示该批 188 首周邦彦词作。
- **当时理由**：推定为先建立一套可清洗、可分句、可导入的稳定语料，优先完成单作者阅读闭环；见 `scripts/clean_zhoubangyan_working_text.py` 的 `INPUT_PATH`、`SOURCE` 和 `parse_working_text()`。
- **当前收益**：文本格式统一，清洗规则、数据库导入和 Reader 展示可以围绕同一批数据迭代；`PoemCore` 在写入 JSON 前提供结构校验。
- **当前代价**：`source` 只有一条笼统字符串，没有版本日期、抓取位置、校勘说明、许可证、异文或逐句来源；“工作整理文本”不能回答底本可靠性问题。
- **风险等级**：high
- **重审条件**：公开发布、引入第二底本、出现异文争议、需要引用原始页码/卷次，或开始导入其他作者。
- **建议动作**：扩展
- **证据位置**：`scripts/clean_zhoubangyan_working_text.py:INPUT_PATH/SOURCE`、`app/models/poem.py:PoemModel.source`、`apps/reader_app.py:render_poem()`。

### D-002 生成 JSON 作为数据库导入中间产物

- **决策内容**：清洗脚本生成 `data/generated/zhoubangyan_poems.json`，导入脚本使用 `PoemCore` 再校验，并在一个事务中删除该作者旧数据后全量重建。
- **当时理由**：推定为让人工整理、结构验证和数据库写入解耦，并保证失败时不会留下半批数据；见 `load_poems()` 与 `main()` 中的 delete/commit 流程。
- **当前收益**：导入可重复，JSON 可人工复核，删除和新增在同一事务提交。
- **当前代价**：JSON 究竟是受版本控制的 seed 还是随时重建的构建产物尚未定性；全量替换不保留修订历史，也不适合未来的人工注释外键。
- **风险等级**：medium
- **重审条件**：生成 JSON 进入发布包、需要增量修订、开始保存用户注释，或同一作品需要多版本共存。
- **建议动作**：保留
- **证据位置**：`scripts/clean_zhoubangyan_working_text.py:OUTPUT_JSON_PATH`、`scripts/import_zhoubangyan_poems.py:load_poems()/main()`。

## 2. 外部 API / 工具选择

### D-003 近期只接 CNKGraph 的五类阅读工具

- **决策内容**：近期主线只使用字典、典故、出处/化用、词谱和平水韵能力；labelize、人物、地理、年历、古籍、类书和曲谱不进入 Reader 主链路。
- **当时理由**：已对 Postman 集合做真实 probe；labelize 专项复测 31 次均无 2xx，而五类工具能支撑单首词的手动阅读闭环。
- **当前收益**：外部依赖范围有限，失败行为和 UI 分区清楚，没有被不可用的自动笺注接口卡住。
- **当前代价**：部分中远期能力需要多次小工具调用拼装；人物、地理和文献实体暂时无法统一消歧。
- **风险等级**：low
- **重审条件**：CNKGraph 发布正式开放文档/鉴权方案、labelize 恢复且有稳定契约，或产品进入跨作品知识关联阶段。
- **建议动作**：保留
- **证据位置**：`docs/cnkgraph/integration_v0_1.md` 第 2、3 节，`app/services/cnkgraph_client.py:CNKGraphClient`。

### D-004 CNKGraph 作为当前唯一外部知识工具提供方

- **决策内容**：所有外部字词、典故、出处、词谱和韵书证据均来自 `CNKGRAPH_BASE_URL`，直接工具接口也以 `/api/cnkgraph/*` 命名。
- **当时理由**：推定为复用搜韵正在使用的统一古典文献 API，减少初期多数据源对齐成本。
- **当前收益**：客户端异常、配置和适配逻辑集中，工具层实现速度快。
- **当前代价**：形成单一供应方依赖；授权许可、限流、SLA、字段稳定性和长期可用性没有被确认，供应方语义还进入了公开路径命名。
- **风险等级**：high
- **重审条件**：公网发布、日调用量明显增长、出现第二证据源、连续上游故障，或需要替换 CNKGraph 而保持清商 API 不变。
- **建议动作**：重构
- **证据位置**：`app/core/config.py:cnkgraph_base_url`、`app/api/routes/cnkgraph.py` 的 `/api/cnkgraph/*` 路由、`docs/cnkgraph/cnkgraph_api_test_report.md`。

## 3. 适配层与字段窄化

### D-005 客户端与领域适配器分层

- **决策内容**：`CNKGraphClient` 只处理 HTTP 和原始 JSON，`cnkgraph_tools.py` 再转换为 `EvidenceItem`、CNKGraph `AllusionCandidate` 与 `ProsodyAid`。
- **当时理由**：外部字段变化应局限在适配层，Reader 不直接理解 CNKGraph 的 `Explains`、`Quotes`、`Sentences`、`References` 等结构。
- **当前收益**：网络错误统一为 `CNKGraphClientError`；前端主要读取清商字段，测试可以分别 mock transport 和工具方法。
- **当前代价**：适配逻辑依赖大量 `.get()` 和“取第一条”规则，字段缺失时经常静默变成空值，缺少契约漂移告警。
- **风险等级**：medium
- **重审条件**：上游字段变更、空结果率异常、增加第二数据源，或 Evidence schema 需要表达多义项与匹配分数。
- **建议动作**：保留
- **证据位置**：`app/services/cnkgraph_client.py:_request_json()`、`app/services/cnkgraph_tools.py:_as_items()/build_*`。

### D-006 窄字段为主，但公开响应仍携带 raw

- **决策内容**：`EvidenceItem`、CNKGraph `AllusionCandidate` 和 `ProsodyAid` 都保留 `raw`；Reader 的 `_card_html()` 和 `render_reading_results()` 不展示它。
- **当时理由**：`raw` 用于调试、溯源和后续适配，同时通过主要字段避免前端直接依赖第三方结构。
- **当前收益**：出现解析问题时可以检查上游原始样本，不必立即增加所有字段。
- **当前代价**：`raw` 已成为公开 FastAPI 响应的一部分，会增加载荷、泄露供应方结构并削弱“外部变化不影响清商契约”的承诺；客户端可能绕过窄字段开始依赖它。
- **风险等级**：medium
- **重审条件**：出现第二前端、公开 API、响应体明显增大、上游包含敏感字段，或开始做契约版本管理。
- **建议动作**：重构
- **证据位置**：`app/schemas/cnkgraph.py:RawCNKGraphData/EvidenceItem/ProsodyAid`、`docs/cnkgraph/integration_v0_1.md` 第 4 节。

### D-007 “典故候选”存在两个不同领域模型

- **决策内容**：CNKGraph 检索结果使用 `app.schemas.cnkgraph.AllusionCandidate`；LLM 整首识别使用 `app.schemas.allusion.AllusionCandidateItem`，Reader 都以“典故候选”呈现。
- **当时理由**：两者分别表示“外部证据候选”和“待查询原文锚点”，独立开发可避免强行共享不兼容字段。
- **当前收益**：LLM 候选可保留 `line_no/query/confidence`，CNKGraph 候选可保留 `source_text/source_ref`，没有为了统一而丢字段。
- **当前代价**：接口、函数和 UI 文案容易混淆“识别候选”与“证据候选”；`read_allusion_candidates` 在两个路由模块中同名，学习与日志检索成本上升。
- **风险等级**：medium
- **重审条件**：增加综合解释、候选状态流转、埋点，或前端需要同时展示两类候选。
- **建议动作**：重构
- **证据位置**：`app/schemas/allusion.py`、`app/schemas/cnkgraph.py:AllusionCandidate`、`app/api/routes/poems.py` 与 `cnkgraph.py`。

## 4. LLM 职责边界

### D-008 LLM 只生成整首典故检索候选，不生成证据

- **决策内容**：`extract_allusion_candidates()` 让 LLM 输出锚点、类型、query 和置信度；服务端验证原文包含关系、每句/全词上限，并把自由 reason 归一为固定模板。
- **当时理由**：模型适合发现疑似检索点，但不应在没有工具证据时编造出处、书名或人物故事。
- **当前收益**：候选可审计、可手动选择，真实《兰陵王·柳》测试中的越界理由被本地模板阻断。
- **当前代价**：候选召回和误报仍依赖模型；`query` 仍可能夹带未经证实的具体判断；每次点击都产生实时成本且结果不持久化。
- **风险等级**：medium
- **重审条件**：建立候选质量评测集、增加自动查证、需要结果复现，或 query 被发现持续污染后续检索。
- **建议动作**：保留
- **证据位置**：`app/services/allusion_candidate_extractor.py:build_allusion_candidate_prompt()/filter_allusion_candidates()`、`POST /api/poems/{poem_id}/allusion-candidates`。

### D-009 保留无证据的整首 LLM 赏析接口

- **决策内容**：`POST /api/poems/{poem_id}/analyze` 直接把完整词作交给 LLM，返回摘要、情感、风格、意象和逐句解释，不读取 CNKGraph 证据。
- **当时理由**：推定为早期先验证结构化赏析链路，使用 `PoemAnalysis` 约束 JSON 输出。
- **当前收益**：已有完整赏析能力，路由和 Schema 简单，适合内部原型。
- **当前代价**：与新形成的“候选 -> 外部证据 -> 再解释”方向不一致；提示词只能要求“不编造”，不能证明事实依据，接口名称 `analyze` 容易被理解为可靠成品。
- **风险等级**：high
- **重审条件**：Reader 接入 AI 综合解释、对外展示赏析、需要引用证据，或出现典故/背景幻觉。
- **建议动作**：暂缓
- **证据位置**：`app/api/routes/poems.py:analyze_poem_detail()`、`app/services/poem_analyzer.py:build_analysis_prompt()/analyze_poem()`。

### D-010 LLM 提示词内嵌在 Python 服务

- **决策内容**：分析与候选识别提示词都由 Python f-string 构造；当前不存在 `app/prompts/*.md`，也没有 prompt version/hash。
- **当时理由**：推定为原型期保持调用代码与输出 Schema 同处，减少文件和加载机制。
- **当前收益**：定位调用关系直接，改动无需模板引擎。
- **当前代价**：提示词难以单独评审、版本化和做 golden test；线上结果无法回答“由哪一版 prompt 生成”。
- **风险等级**：medium
- **重审条件**：同一任务出现第二版 prompt、做 A/B 评测、缓存 LLM 结果、保存分析结果，或多人协作审校提示词。
- **建议动作**：重构
- **证据位置**：`app/services/poem_analyzer.py:build_analysis_prompt()`、`app/services/allusion_candidate_extractor.py:build_allusion_candidate_prompt()`。

## 5. Workflow / Agent 边界

### D-011 候选识别后自动查证并受控审阅，但不开放检索

- **决策内容**：`/allusion-candidates/with-evidence` 继续提供未审阅的候选证据；v0.2.0 新增 `/allusion-candidates/with-review`，在同一固定 CNKGraph 证据集合上逐候选调用受控 Evidence Reviewer。用户仍可点击 anchor 回填 selected_text，并用 reading-aids 进一步手动查询；系统不做开放搜索、知人论世扩展或 Agent 编排。
- **当时理由**：v0.1.10 的候选 pills 仍要求用户逐项复制/查询，无法直接判断候选是否有外部证据；固定的两工具查询矩阵可以补齐闭环，同时不把 query_variants 当成结论。
- **当前收益**：候选、查询变体和 `hit/no_result/error` 仍可追溯；Reviewer 可区分前代来源、自命中、后代沿用和弱/误命中，并只依据合格最佳证据生成一至两句“审阅短注”。检索命中和短注都不被表述为最终人工确认。
- **当前代价**：除每首最多 60 次 CNKGraph 调用外，还可能增加最多 10 次逐候选 LLM Review；当前仍无缓存、限流、并发控制或持久化，重复点击会重复请求。
- **风险等级**：medium
- **重审条件**：出现明显延迟、限流或成本问题；准备公网开放；增加新数据源；或计划让审阅结果自动持久化、发布或替代人工确认。
- **建议动作**：保留
- **证据位置**：`app/services/allusion_evidence.py:build_allusion_evidence_preview()`、`app/services/allusion_evidence_reviewer.py:build_allusion_evidence_review()`、`app/api/routes/poems.py`、`apps/reader_app.py:render_allusion_evidence_preview()/render_tools()`。

## 6. 前端框架与交互

### D-012 Streamlit 作为 FastAPI 的薄客户端

- **决策内容**：Reader 只通过 HTTP 调用 `/api/poems`、详情、allusion-candidates 和 reading-aids，不导入 ORM 或直接连接 PostgreSQL。
- **当时理由**：快速形成可操作阅读器，同时保留后端契约作为唯一业务入口。
- **当前收益**：数据库和外部工具错误集中在 FastAPI；Reader 可独立重启，前后端职责基本清楚。
- **当前代价**：本机需要同时运行两个进程；同步 `httpx` 调用会阻塞 Streamlit rerun；部署与错误排查对初学者不够直观。
- **风险等级**：low
- **重审条件**：需要多用户并发、SEO、复杂路由、移动端应用、细粒度前端测试，或部署运维成本超过开发速度收益。
- **建议动作**：保留
- **证据位置**：`apps/reader_app.py:_api_url()/fetch_*()/main()`、`.streamlit/config.toml`。

### D-013 Reader 单文件承载样式、API、状态与四种阅读模式

- **决策内容**：约 43KB 的 `apps/reader_app.py` 同时包含 CSS、HTTP 适配、目录、四种阅读模式、候选 UI、证据卡片和 session state。
- **当时理由**：推定为按 v0.1.x 快速迭代，避免过早组件化；Streamlit 本身鼓励脚本式页面。
- **当前收益**：功能位置集中，原型修改速度快；通读、慢读、转轮、领读共享同一状态。
- **当前代价**：CSS 依赖 Streamlit 内部 `data-testid` 和 key 生成类名；任何局部改动都要理解整页 rerun 与大量状态键，浏览器自动化曾在重渲染后超时。
- **风险等级**：medium
- **重审条件**：文件超过 50KB、增加第二页面、再增加一种工具工作流、Streamlit 升级导致选择器失效，或 UI 回归频率上升。
- **建议动作**：重构
- **证据位置**：`apps/reader_app.py:install_styles()/render_poem()/render_tools()/initialize_state()`。

## 7. 缓存与持久化

### D-014 只缓存 Reader 的目录与详情读取

- **决策内容**：`fetch_poems()` 和 `fetch_poem()` 使用 30 秒 `st.cache_data`；无标题起句并发读取使用 300 秒缓存；CNKGraph 与 LLM 结果不缓存。
- **当时理由**：减少 Streamlit rerun 对本地 API 的重复读取，同时避免在外部接口许可、稳定性和结果语义未确定前引入服务端缓存。
- **当前收益**：目录浏览较顺畅，缓存失效简单，不需要新基础设施。
- **当前代价**：同一 LLM 候选或 CNKGraph 查询会重复付费/请求；缓存属于单个 Streamlit 进程，不能跨实例共享；目录页为补起句最多额外请求 24 个详情。
- **风险等级**：high
- **重审条件**：公网部署、并发用户出现、外部 API 有配额、LLM 成本可见、响应延迟影响阅读，或多实例运行。
- **建议动作**：扩展
- **证据位置**：`apps/reader_app.py:fetch_poems()/fetch_poem()/fetch_opening_lines()`、`docs/cnkgraph/integration_v0_1.md` 第 6 节。

### D-015 不持久化候选、证据和 LLM 分析

- **决策内容**：外部证据和 LLM 输出只存在于 HTTP 响应与 `st.session_state`，数据库仍只有 poems/sections/lines。
- **当时理由**：结果 Schema、来源许可和用户价值尚未稳定，避免过早新增表和迁移负担。
- **当前收益**：核心文本数据保持干净，重新请求即可试验新适配策略。
- **当前代价**：结果不可复现、不能审校、无法比较 prompt/模型版本，也无法建立人工纠错闭环。
- **风险等级**：medium
- **重审条件**：需要人工审核、分享链接、结果复用、成本控制、质量评测，或正式提供“清商注释”。
- **建议动作**：暂缓
- **证据位置**：`app/models/poem.py` 仅三类模型、`apps/reader_app.py:initialize_state()`。

## 8. 数据库结构

### D-016 三层 poem / section / line 作为核心稳定契约

- **决策内容**：PostgreSQL 使用 poems、poem_sections、poem_lines；`poem_id` 是稳定业务 ID，line 同时保存全词和片内编号，关系有级联删除与唯一约束。
- **当时理由**：支持完整展示、片段排序、逐句定位、LLM 上下文和 reading-aids 的 `line_no` 校验。
- **当前收益**：Reader 四种模式、候选 anchor 校验和完整词作 prompt 都复用同一结构；外部 ID 没有污染核心表。
- **当前代价**：`full_text` 与 lines 是重复数据，需要导入流程保证一致；行号和断句一旦变化会影响候选定位及未来引用。
- **风险等级**：low
- **重审条件**：支持异文/版本、多层注释、跨句锚点、重新断句，或开始保存依赖 line_no 的持久结果。
- **建议动作**：保留
- **证据位置**：`app/models/poem.py`、`app/crud/poem.py:get_poem_by_poem_id()`、`app/schemas/poem.py`。

### D-017 暂无 Alembic，结构变更依赖 create_all 与独立 SQL

- **决策内容**：数据库初始化只创建缺失表；历史索引调整使用 `scripts/drop_redundant_indexes.sql`，没有迁移版本链。
- **当时理由**：推定为早期只有三张表，先降低环境搭建复杂度。
- **当前收益**：新环境初始化简单，当前 schema 小。
- **当前代价**：无法可靠升级已有数据库、回滚或证明环境结构一致；任何新表/字段都会放大手工操作风险。
- **风险等级**：high
- **重审条件**：下一次数据库 schema 变更、首次部署共享环境、保存候选/注释，或多人维护数据库。
- **建议动作**：扩展
- **证据位置**：`app/db/init_db.py`、`scripts/drop_redundant_indexes.sql`、`docs/sync/latest.md` 已知问题。

## 9. 测试与验证

### D-018 单元测试使用 mock，真实外部服务使用独立 probe

- **决策内容**：自动测试不访问真实 CNKGraph/LLM，使用 `httpx.MockTransport`、`AsyncMock` 和纯函数测试；真实 API 验证由 `scripts/probes` 与人工冒烟承担。
- **当时理由**：避免网络不稳定、配额和第三方变化破坏本地测试，同时保留真实可用性证据。
- **当前收益**：26 项测试运行快，能稳定覆盖适配、候选过滤、Reader 纯函数和路由存在性。
- **当前代价**：没有测试 PostgreSQL、FastAPI 请求生命周期、真实序列化、Streamlit 完整交互或 LLM 供应方契约；probe 结果不会自动阻止回归。
- **风险等级**：high
- **重审条件**：首次 CI、首次公网部署、增加迁移、修改依赖注入/路由、升级 Streamlit，或外部契约变更。
- **建议动作**：扩展
- **证据位置**：`tests/test_cnkgraph_tools.py`、`tests/test_allusion_candidates.py`、`tests/test_reader_app.py`、`scripts/probes/`。

### D-019 尚无语料快照、候选质量集和 CI 门禁

- **决策内容**：当前没有完整 188 首清洗结果的稳定哈希/统计快照，没有典故候选 precision/recall 样例集，也没有 GitHub Actions、覆盖率、lint 或类型检查。
- **当时理由**：推定为优先验证业务闭环，工程门禁与领域评测尚未排入 v0.1。
- **当前收益**：初期迭代阻力低。
- **当前代价**：解析规则、prompt 或依赖升级可能在“测试全绿”时改变大量语料或候选质量；真实《兰陵王·柳》验证仍是人工记录。
- **风险等级**：high
- **重审条件**：修改清洗规则、prompt、模型、依赖版本，开始接受外部贡献，或准备发布可复现版本。
- **建议动作**：扩展
- **证据位置**：`tests/` 当前五个文件、`docs/sync/latest.md` 第 7、9 节。

## 10. 当前版本范围控制

### D-020 v0.1 主线坚持“本地阅读 + 手动证据 + 有限 LLM 候选”

- **决策内容**：当前明确不做 labelize、复杂 Agent、自动查证、自动综合解释、音频同步、逐字高亮、新数据库表或中远期实体库；Reader 版本已推进到 v0.1.10。
- **当时理由**：先完成可阅读、可选择、可手动求证的最小闭环，把高幻觉和高耦合能力留在边界之外。
- **当前收益**：多数新增功能能在不改数据库和 poems 主链路的情况下落地，失败不会阻断正文阅读。
- **当前代价**：v0.1.x 同时覆盖四种阅读模式、CNKGraph 工具层和 LLM 候选识别，版本号没有对应正式验收清单；旧 `/analyze` 又超出 evidence-first 边界。
- **风险等级**：medium
- **重审条件**：宣布 v0.2、准备发布、Reader 再增加主要工作流，或决定接入 AI 综合解释。
- **建议动作**：保留
- **证据位置**：`apps/reader_app.py:READING_MODES/render_tools()`、`docs/cnkgraph/integration_v0_1.md`、`docs/sync/latest.md` 各 v0.1.x 记录。

### D-021 v0.2 只对封闭证据集做 LLM Review，仍保留人工确认

- **决策内容**：v0.2.0 的 Evidence Reviewer 只能读取当前候选已有的 CNKGraph 窄证据，按稳定 ID 分类并生成最多一至两句审阅短注；不允许调用 Web Search、本地 Poetry RAG、知人论世资料或其他工具。Review 结果不是最终定论，也不自动持久化或发布。
- **当时理由**：v0.1.12 已能展示候选证据，但用户仍需自行区分前代来源、当前作品自命中、后代沿用和误命中；这一判断适合受控审阅，却不需要开放式 Agent 或新增数据源。
- **当前收益**：Reader 可直接展示 `reviewed/insufficient_evidence/ambiguous/error`、最佳/降级/拒绝证据和审阅短注；程序会过滤不存在于输入证据的引用，并禁止自命中与后代用例进入最佳证据。
- **当前代价**：每首最多增加 10 次 LLM 调用；Reviewer 仍可能对现有证据相关性判断失误，且 CNKGraph 本身的漏检无法由封闭审阅补足。当前没有缓存、评测集或人工确认持久化。
- **风险等级**：high
- **重审条件**：短注准备面向公开用户发布、需要保存人工确认、Reviewer 质量无法由固定样例约束、需要引入第二证据源，或成本/延迟超过原型可接受范围。
- **建议动作**：暂缓扩展
- **证据位置**：`app/services/allusion_evidence_reviewer.py`、`app/schemas/allusion.py:EvidenceReviewResult`、`app/api/routes/poems.py:read_allusion_candidates_with_review()`、`tests/test_evidence_reviewer.py`。
