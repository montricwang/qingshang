# Qingshang 项目现状同步

> 更新日期：2026-06-21
> 仓库基线：`main` / `c5e5160`
> 当前工作区：Reader v0.1.9 四模式阅读界面，后端与数据库结构未改动

## 1. 当前代码现状

当前仓库是一个异步 FastAPI 后端，数据存储使用 PostgreSQL + SQLAlchemy Async ORM，
LLM 调用使用兼容 OpenAI Chat Completions 协议的 HTTP 接口，默认配置指向 DeepSeek。

当前代码已经形成以下完整链路：

```text
HTTP 请求
  -> FastAPI 路由与参数校验
  -> Depends(get_db) 注入 AsyncSession
  -> CRUD 查询 SQLAlchemy ORM 对象
  -> Pydantic 响应序列化

诗词分析请求
  -> 查询完整诗词及 sections/lines
  -> 组装提示词
  -> httpx 调用 LLM
  -> 提取 JSON
  -> PoemAnalysis 校验
  -> JSON 响应
```

当前包含 FastAPI 后端、Reader v0.1.9 Streamlit 前端、数据清洗/导入脚本和单元测试。
当前没有用户系统、权限系统、Alembic 数据库迁移、Docker 配置或 CI。

### 2026-06-21 Reader v0.1.9

- 本轮只修改 Streamlit 前端；未修改后端 API、数据库、CNKGraph Tool Layer、LLM 或原文数据。
- 阅读区新增“通读、慢读、转轮、领读”四种模式，并使用 `reading_mode` 保存当前选择。
- 通读模式居中展示全部原始诗行；慢读模式继续使用按标点拆分、逐级缩进的句读排版。
- 转轮模式每次突出一条原始 poem_line，并以低透明度显示相邻诗行；支持“上一句 / 下一句”导航和当前位置计数。
- 领读模式在转轮视图上增加播放、暂停及自动推进；`current_line_index`、`is_playing`、`speed` 均保存在 `st.session_state`。
- 领读速度固定为快 2.5 秒、中 4 秒、慢 6 秒；使用 `st.fragment(run_every=0.5)` 检查推进时机，到达末句后自动停止。
- 切换词作或阅读模式会停止播放并重置计时；在末句重新播放时从首句开始。
- 通读、慢读分片和转轮/领读当前句均可点击，回填右侧 `selected_text` 时只使用干净原文。
- 当前没有音频同步、逐字高亮、按字数动态计时或真实 iOS wheel picker；这些不属于本版本范围。
- 浏览器已验证四模式控件与转轮首句视图正常渲染；自动化浏览器在 Streamlit 重渲染后的连续点击发生驱动超时，领读完整计时交互尚未由浏览器自动化跑通。
- `python -m compileall app apps scripts tests` 已通过；`python -m pytest -q` 已通过 22 项测试。

### 2026-06-21 Reader v0.1.8

- 本轮只修改 Streamlit 展示逻辑；未修改后端、数据库、poem_lines 原文或 API 请求契约。
- 正文行改为左对齐，并继续使用透明边框、浅色 hover 和浅赭选中状态。
- 新增纯函数 `build_breathing_fragments()`，在展示层把每条 poem_line 按 `，、。！？；：` 拆成可点击慢读分片。
- 每个 section 的缩进从 0 开始；软停顿后增加一级，硬停顿后归零，并支持同一句内多个逗号形成多级缩进。
- 每级缩进只加在 `display_text` 前，由两个全角空格表示；分片 `text`、`source_line_text`、poem_lines 原文均保持不变。
- 句末停顿后的闭合引号、书名号和括号保留在同一分片，避免闭合符号单独成行。
- 点击分片时使用无缩进的 `text` 回填 `selected_text`，同时继续携带原始 `line_no` 供 reading-aids 定位。
- 目录辅助标题移除“起句 ·”前缀，保留灰色并提高字号；末尾停顿标点清理规则保持不变。
- 正文仍不显示片名和行号，仅以片间留白与淡分隔表示分片。
- 新增跨行缩进、单行多逗号拆分、section 重置和闭合符号测试；`python -m compileall app apps scripts tests` 已通过，`python -m pytest -q` 已通过 20 项测试。

### 2026-06-21 Reader v0.1.7

- 本轮只修改 Streamlit 前端样式和展示细节；未修改后端 API、数据库、CNKGraph Tool Layer 或 LLM 功能。
- 深色模式完整覆盖检索输入框、placeholder、边框、focus、表单容器、pills 及 BaseWeb 弹出区域，避免白底回退。
- 工具选择由可删除 chip 的 `st.multiselect` 改为原生多选 `st.pills`。
- 左侧目录缩小按钮高度、条目间距、起句间距和分页按钮高度。
- 起句只移除末尾连续的 `，。！？；、：`，保留中间标点以及末尾书名号、引号和括号。
- 正文不再显示片段名称，片间仅保留极淡分隔；逐句继续可点击，但不再显示 `01`、`02` 等编号。
- 点击正文句子仍会把完整原句和内部 `line_no` 回填到阅读辅助表单。
- 新增起句尾标点测试；`python -m compileall app apps scripts tests` 已通过，`python -m pytest -q` 已通过 16 项测试。

### 2026-06-21 Reader v0.1.6

- 主色从高饱和红调整为低饱和赭色，并统一使用赭色、墨绿、米白和灰墨设计变量。
- 正文逐句按钮改为默认透明无边框、悬停显示边界、选中使用浅赭底色，减弱表单感。
- 新增浅色 / 深色外观切换；深色模式为背景、正文、表单、卡片和横幅分别设置配色。
- reading-aids 的局部错误按工具前缀放入对应 Tab；上游 404 显示为“暂无匹配结果”，不再使用总区域黄色警告。
- 只有全部已选工具因非 404 上游错误而不可用时，才显示整次查询失败提示。
- 选中文本下方新增短语查询建议，减少整句查询造成的误中与空结果。
- 目录使用 `series_label` 区分同词牌套词；无标题作品在按钮下以灰色“起句”展示第一句。
- 起句由前端并发读取当前目录页的词作详情并缓存 5 分钟，没有修改 `/api/poems` 返回结构。
- 新增 `tests/test_reader_app.py`，覆盖错误归组、套词标签和外部文本 HTML 转义。
- `python -m compileall app apps scripts tests` 已通过；`python -m pytest -q` 已通过 15 项测试。
- 浏览器实测“章台路”：典故候选正常显示，reference 404 仅在“出处与化用”Tab 内显示为暂无匹配；深色主题计算样式已生效。
- 未修改数据库、ORM、FastAPI 路由、poems 数据契约或 CNKGraph 工具层。

### 2026-06-21 Reader v0.1.5

- 新增 `apps/reader_app.py`，通过现有 FastAPI 读取本地周邦彦词作，不直接访问数据库。
- 左侧目录支持筛选和分页；正文区展示词牌、题名、题序、分片和逐句按钮，点击词句会填入右侧选中文本。
- 阅读辅助统一调用 `POST /api/poems/{poem_id}/reading-aids`，可手动选择典故、出处、字典、韵部和词谱工具。
- 结果按“字词释义、典故候选、出处与化用、韵部、词谱 / 平仄”分区，只展示清商窄模型中的证据字段，不展示 CNKGraph `raw`。
- 外部辅助失败时在右栏显示错误，词作正文仍保持可读；不做自动候选提取、LLM 综合解释或 Agent 调度。
- 新增 `apps/assets/reader-landscape.webp` 作为阅读器横幅，并新增 `.streamlit/config.toml` 固定轻量主题。
- `requirements.txt` 新增 `streamlit==1.41.1`；`.env.example` 新增 `QINGSHANG_API_BASE_URL`。
- AI 自动识别候选与 AI 综合解释目前均为下一版本占位区。

启动命令：

```bash
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
.venv\Scripts\python.exe -m streamlit run apps/reader_app.py
```

默认地址：FastAPI 为 `http://127.0.0.1:8000`，Reader 为 `http://127.0.0.1:8501`。

当前验证：Reader 能加载 188 首周邦彦词作、选择词作、点击词句回填查询框，并以“兔葵燕麦”真实获得 CNKGraph 字词证据。FastAPI 和 Streamlit 均可正常启动。尚未验证 CNKGraph 长期稳定性、并发负载或移动设备实机体验。

### 2026-06-20 CNKGraph Tool Layer v0.1

- 新增 `app/services/cnkgraph_client.py`：使用 `httpx.AsyncClient` 封装 11 个近期只读接口，统一处理超时、网络、非 2xx 和 JSON 错误。
- 新增 `app/services/cnkgraph_tools.py`：把典故、出处、字典、词谱和韵典原始响应适配为清商窄模型。
- 新增 `app/schemas/cnkgraph.py`：定义 `EvidenceItem`、`AllusionCandidate`、`ProsodyAid`、`ReadingAidRequest/Response` 等本地契约；第三方字段只保存在 `raw`。
- 新增 `app/api/routes/cnkgraph.py` 并注册到总路由；没有修改原 poems 查询与 analyze 实现。
- 新增直接工具接口：`GET /api/cnkgraph/char/{char}`、`GET /api/cnkgraph/allusions`、`POST /api/cnkgraph/reference`、`GET /api/cnkgraph/ci-tunes`、`POST /api/cnkgraph/rhyme`。
- 新增 `POST /api/poems/{poem_id}/reading-aids`：先读取本地词作并校验句号，再按 include 调用外部工具；单个工具失败只写入 `errors`，不让整次阅读请求返回 500。
- reading-aids 不调用 LLM，不做实体消歧或确定性典故判断；字典与韵典一次最多查询 30 个不重复文字。
- 配置新增 `CNKGRAPH_BASE_URL` 和 `CNKGRAPH_TIMEOUT_SECONDS`；新增完整 `.env.example`。
- 新增 `tests/test_cnkgraph_schemas.py` 和 `tests/test_cnkgraph_tools.py`，使用 MockTransport/AsyncMock，不真实访问 CNKGraph。
- 新增 `docs/cnkgraph/integration_v0_1.md`，记录接口范围、窄模型、raw、失败降级和后续边界。
- 明确不接两个 labelize 接口，也不接人物、地理、年历、古籍、类书和曲谱。
- 没有新增 ORM model、数据库迁移或数据库表，没有把 CNKGraph ID 写入 poems/sections/lines。
- `python -m compileall app scripts tests` 已通过；`python -m pytest -q` 已通过 12 项测试。
- 本地真实冒烟已通过：`GET /health`、`GET /api/poems?limit=1`、OpenAPI 路由、`GET /api/cnkgraph/allusions?key=前度刘郎` 和 `POST /api/poems/zhoubangyan-0001/reading-aids` 均成功。
- 真实典故请求返回 1 个清商 `AllusionCandidate`；reading-aids 使用 allusion/reference 返回 200 且 `errors=[]`。
- 使用不可达上游启动独立测试实例后，reading-aids 仍返回 200，并在 `errors` 中记录超时；直接 allusions 接口按设计返回 502。

### 2026-06-20 CNKGraph 自动笺注专项复测

- 新增 `scripts/probes/probe_cnkgraph_labelize.py`，硬性限制请求间隔至少 0.5 秒、总请求不超过 80 次。
- 最终实际请求 53 次，其中 31 次为 labelize 调用，0/31 返回 2xx；没有连接错误。
- 测试覆盖两种 host、常见路径和大小写变体、JSON/form/text 三种载荷、字段别名、四类文本以及 OPTIONS。
- 使用杜甫、苏轼、周邦彦、李白各 3 首真实作品交叉验证；12 个作品详情全部返回 200，对应 labelize 全部返回 404“作者不存在”。
- `POST /api/tool/labelize` 在所有变体下均为空 404，没有进入参数校验；没有出现 401、403 或认证提示。
- `OPTIONS /api/writing/10000/labelize` 返回 405 和 `Allow: GET`，但 `labels`、`annotations` 等同层路径也返回“作者不存在”，说明请求更可能被通用作品/作者路由误匹配，而非 labelize action 可用。
- 当前最符合证据的结论是公开 labelize 路径已移除、迁移或未暴露；不存在“参数格式错误”或“仅部分作品支持”的正向证据。
- 原始结果保存到 `data/generated/cnkgraph_labelize_probe_20260620_134704.json`，专项报告保存到 `docs/cnkgraph/labelize_probe_report.md`。
- 决策保持为“暂缓且不等待”：近期使用 glossary、reference、char、ciTune、tones、rhyme 组合清商自己的候选笺注链路。
- 本轮未修改 FastAPI 业务代码、数据库结构、poems 接口或数据契约。

### 2026-06-20 CNKGraph 全接口 probe

- 新增 `scripts/probe_cnkgraph_all.py`，直接读取 `docs/cnkgraph/postman/` 中 12 份 Postman collection，共展开 71 个请求。
- 使用 collection 自带变量和集合级回退参数，按顺序真实访问 `https://api.cnkgraph.com`；没有修改远端数据的请求。
- 最终结果为 69/71 返回 HTTP 2xx；12 个接口组均已覆盖。
- 两个失败接口均为自动笺注：`POST /api/tool/labelize` 返回 404 空响应，`GET /api/writing/10000/labelize` 返回 404“作者不存在”。
- 其余词汇典故、词谱、地理、古籍、类书、年历、曲谱、人物、诗文、韵典、字典和工具请求均按代表参数返回 200。
- 原始请求、状态、耗时、响应形态及受限响应样本保存到 `data/generated/cnkgraph_all_probe.json`。
- 完整测试与适用性报告保存到 `data/generated/cnkgraph_api_test_report.md`，包含 71 项明细和面向清商近中远期目标的论证。
- 近期建议优先评估诗文详情/平仄/出处、词汇典故、词谱、韵典、字典及出处与化用分析；两个自动笺注接口暂缓。
- 中期再接人物、地理、年历、古籍和类书，并先设计外部实体 ID、来源及人工消歧流程；曲谱和全库遍历放到远期。
- 当前只证明 2026-06-20 单次顺序请求的可访问性；未验证授权许可、限流、并发、SLA、长期稳定性和字段兼容性。
- 尚未把 CNKGraph 接入 FastAPI、Tool Layer、缓存或数据库；未修改 poems 接口和数据库结构。

### 2026-06-20 CNKGraph 词汇、典故 API probe

- 新增 `scripts/probe_cnkgraph_glossary.py`，请求定义来自 `docs/cnkgraph/postman/词汇、典故.postman_collection.json`。
- 使用 `https://api.cnkgraph.com` 实测 5 个接口：词典 ID、典故 ID、佛典 ID、词典批量 ID、典故关键词查询。
- 5 个请求均返回 HTTP 200，单次耗时约 20–105 ms。
- 完整请求和响应保存到 `data/generated/cnkgraph_glossary_probe.json`。
- 词典 ID 10 返回“青山”和 3 条释义；佛典 ID 100 返回“一心专念”和 2 条释义。
- 批量词典接口按 `[10, 15, 30, 42]` 返回 4 条结果：“青山、不见、悠悠、芙蓉”。
- 典故 ID 1000 返回关键词、相关人物、关联、出处、引文和解释等字段。
- 典故关键词“桃花”返回 3 个候选，ID 为 733、1907、2000。
- 当前仅验证示例请求成功；未测试无效 ID、空关键词、限流、并发、长期稳定性和使用许可。
- 尚未把 CNKGraph 接入 FastAPI、Tool Layer、缓存或数据库。
- `python -m compileall app scripts` 已通过。

### 2026-06-19 注释规范化

- 按 `low-noise-code-reading.md` 与 `python-file-reading.md` 收紧源码注释。
- 删除基础 import 翻译、重复代码表面含义和“第一阶段/第二阶段”式旁白。
- 缩短文件、类和函数 docstring，只保留职责与输出边界。
- 保留 FastAPI 自动注册/注入、ORM 关系预加载、`create_all` 限制、事务提交和清洗状态机等关键说明。
- 未修改 API、数据库结构、数据契约或业务执行逻辑。
- `python -m compileall app scripts` 已通过。
- 现有 5 项 unittest 已通过。

## 2. 本轮文件变化

以下范围对应提交 `dc2f704` 与 `e6fc486`。

### 新增

- `scripts/drop_redundant_indexes.sql`：供已有 PostgreSQL 数据库删除三个冗余普通索引。
- `scripts/zhoubangyan_rules.py`：从清洗脚本拆出的周邦彦词牌、宫调、套词标记和断句规则。
- `tests/test_core.py`：核心单元测试，覆盖 Schema、路由注册、JSON 提取和清洗辅助函数。
- `docs/sync/latest.md`：本同步文档，尚需单独提交。

### 修改

- `README.md`：原文件为空，本轮写入框架控制流、依赖注入、ORM、异步机制和阅读顺序。
- `.gitignore`：忽略 `data/generated/*_review.md`。
- `app/main.py`：改为只注册聚合后的 `api_router`；保留 `/health`；增加控制流注释。
- `app/api/__init__.py`：增加包职责说明。
- `app/api/routes/__init__.py`：当前只聚合 poems 路由。
- `app/api/routes/poems.py`：使用 Pydantic 响应模型；补充依赖注入和接口流程说明。
- `app/core/config.py`：统一 LLM 配置并补充 BaseSettings 自动加载说明。
- `app/crud/__init__.py`：增加包职责说明。
- `app/crud/poem.py`：只保留数据库查询职责，删除手写响应字典转换函数。
- `app/db/__init__.py`：增加包职责说明。
- `app/db/base.py`：补充 SQLAlchemy 声明式基类说明。
- `app/db/init_db.py`：补充模型注册与 `create_all` 行为说明。
- `app/db/session.py`：补充引擎、会话工厂和 `Depends(get_db)` 生命周期说明。
- `app/models/__init__.py`：增加模型包说明，继续统一导出三个 ORM 模型。
- `app/models/poem.py`：删除与唯一约束重复的普通索引；为关系增加稳定排序；补充 ORM 注释。
- `app/schemas/analysis.py`：补充结构化 LLM 输出说明。
- `app/schemas/poem.py`：增加 `PoemListItem`；启用 ORM 属性读取；补充 Schema 说明。
- `app/services/__init__.py`：增加服务层职责说明。
- `app/services/llm_client.py`：成为唯一 LLM 客户端，统一配置、超时、响应模型和异常。
- `app/services/poem_analyzer.py`：继续负责结构化赏析，补充处理阶段说明。
- `scripts/clean_zhoubangyan_working_text.py`：移出规则常量；保留解析状态机和报告生成；增加分区注释。
- `scripts/import_zhoubangyan_poems.py`：补充事务、flush/commit 和执行流程说明；调整项目路径导入顺序。
- `tests/test_core.py`：在文档化提交中补充测试意图说明。

### 删除

- `app/api/chat.py`：原 `/api/chat/test` 开发测试接口，已移除。
- `app/api/poetry.py`：路由迁移到 `app/api/routes/poetry.py`。
- `app/schemas/chat.py`：只服务于已删除的聊天测试接口。
- `app/services/deepseek.py`：与 `llm_client.py` 重复的 LLM 请求实现。
- `app/api/routes/poetry.py`：旧自由文本赏析路由，现已删除以聚焦数据库词作分析。
- `app/schemas/poetry.py`：只被旧自由文本赏析接口使用，现已删除。
- `app/services/poetry.py`：只为旧自由文本接口组装提示词，现已删除。
- `data/generated/zhoubangyan_review.md`：可由清洗脚本重新生成，现由 `.gitignore` 忽略。

## 3. 重要文件及连接关系

### 应用入口与路由

#### `app/main.py`

- 职责：创建 FastAPI 应用、注册聚合路由、提供健康检查。
- 主要对象：`app`。
- 主要函数：`health_check()`。
- 连接：导入 `app.api.routes.api_router` 和 `app.core.config.settings`；Uvicorn 通过 `app.main:app` 找到应用。

#### `app/api/routes/__init__.py`

- 职责：将 `poems_router` 收口为应用注册的 `api_router`。
- 主要对象：`api_router`。
- 连接：被 `app/main.py` 注册；导入 poems 路由模块会触发装饰器注册。

#### `app/api/routes/poems.py`

- 职责：诗词列表、详情和结构化分析接口。
- 主要函数：`read_poem_list()`、`read_poem_detail()`、`analyze_poem_detail()`。
- 连接：通过 `Depends(get_db)` 获取 `AsyncSession`；调用 `app.crud.poem` 查询；详情输出使用 `PoemCore`；分析调用 `app.services.poem_analyzer.analyze_poem()`。

### 配置与数据库

#### `app/core/config.py`

- 职责：从环境变量和根目录 `.env` 读取配置。
- 主要类：`Settings`。
- 主要对象：模块级单例 `settings`。
- 关键配置：`APP_NAME`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`LLM_TEMPERATURE`、`LLM_TIMEOUT_SECONDS`、`DATABASE_URL`。
- 连接：数据库会话和 LLM 客户端都读取同一个 `settings`。

#### `app/db/base.py`

- 职责：提供 ORM 模型共同继承的 `Base`。
- 主要类：`Base(DeclarativeBase)`。
- 连接：`app.models.poem` 的模型继承它；`app.db.init_db` 使用 `Base.metadata` 建表。

#### `app/db/session.py`

- 职责：创建异步数据库引擎、会话工厂和 FastAPI 数据库依赖。
- 主要对象：`engine`、`AsyncSessionLocal`。
- 主要函数：`get_db()`。
- 连接：读取 `settings.database_url`；路由通过 `Depends(get_db)` 自动获得并在请求结束后关闭会话；导入脚本直接调用 `AsyncSessionLocal()`。

#### `app/db/init_db.py`

- 职责：导入 ORM 模型并调用 `Base.metadata.create_all()` 创建缺失表。
- 主要函数：`register_models()`、`init_db()`。
- 限制：不能修改已有表结构，不能替代 Alembic。

### ORM 与数据访问

#### `app/models/poem.py`

- 职责：定义三层诗词数据库结构。
- `PoemModel`：主表 `poems`，保存作者、词牌、题名、正文、来源等。
- `PoemSectionModel`：表 `poem_sections`，保存片段序号和名称。
- `PoemLineModel`：表 `poem_lines`，保存全词编号、片内编号和词句正文。
- 关系：`PoemModel.sections -> PoemSectionModel.lines`；均设置级联删除和稳定排序。
- 连接：CRUD 查询这些模型；Pydantic Schema 通过 `from_attributes=True` 读取 ORM 属性；导入脚本创建这些对象。

#### `app/crud/poem.py`

- 职责：封装诗词读取查询，不处理 HTTP 和响应格式。
- `list_poems()`：按作者筛选、排序和分页，返回 `PoemModel` 列表。
- `get_poem_by_poem_id()`：按稳定 ID 查询详情，使用 `selectinload` 预加载 sections/lines。
- 连接：由 poems 路由调用；接收 FastAPI 注入的 `AsyncSession`。

### Pydantic Schema

#### `app/schemas/poem.py`

- 职责：约束诗词列表、详情和数据清洗结果的结构。
- `PoemLine`：词句编号和正文。
- `PoemSection`：片段及其词句。
- `PoemListItem`：列表摘要字段。
- `PoemCore`：继承列表字段并增加题序、全文、sections 和来源。
- 连接：API 输出和清洗/导入脚本共用；通过 `ConfigDict(from_attributes=True)` 支持 ORM 对象。

#### `app/schemas/analysis.py`

- 职责：校验 LLM 返回的结构化分析。
- 主要类：`LineExplanation`、`ImageryItem`、`PoemAnalysis`。
- 连接：`poem_analyzer.analyze_poem()` 在 JSON 解析后调用 `PoemAnalysis.model_validate()`。

### LLM 服务

#### `app/services/llm_client.py`

- 职责：唯一的 LLM HTTP 客户端，隐藏 URL、认证、超时和响应嵌套结构。
- 主要类：`LLMClientError`、`LLMMessage`、`LLMChoice`、`LLMChatResponse`。
- 主要函数：`chat_completion(messages, model=None, temperature=None)`。
- 连接：读取 `settings`；通过 httpx 请求 `/v1/chat/completions`；当前只被 `services/poem_analyzer.py` 调用。

#### `app/services/poem_analyzer.py`

- 职责：把完整 ORM 诗词转换成提示词，并将 LLM 文本转换成结构化分析。
- `build_poem_text_for_prompt()`：按片段和词句编号生成提示词正文。
- `extract_json()`：兼容纯 JSON 和 Markdown JSON 代码围栏。
- `build_analysis_prompt()`：生成要求严格 JSON 的消息列表。
- `analyze_poem()`：调用 LLM、解析 JSON、验证 `PoemAnalysis`。

### 数据脚本

#### `scripts/clean_zhoubangyan_working_text.py`

- 职责：把 `data/working/zhoubangyan.txt` 解析为结构化 JSON，并生成忽略跟踪的复核报告。
- 主要函数：`parse_meta_line()`、`split_lines()`、`build_sections()`、`parse_working_text()`、`write_review()`、`main()`。
- 输入：`data/working/zhoubangyan.txt`。
- 输出：`data/generated/zhoubangyan_poems.json` 与 `data/generated/zhoubangyan_review.md`。
- 连接：规则来自 `scripts/zhoubangyan_rules.py`；结果使用 `PoemCore` 验证。

#### `scripts/zhoubangyan_rules.py`

- 职责：保存清洗器使用的词牌、宫调、套词序号、断句标点和正则表达式。
- 连接：只由 `clean_zhoubangyan_working_text.py` 导入。

#### `scripts/import_zhoubangyan_poems.py`

- 职责：在单个事务中删除数据库内已有周邦彦数据并重新导入 JSON。
- 主要函数：`load_poems()`、`import_one_poem()`、`main()`。
- 连接：输入由清洗脚本产生；使用 `PoemCore` 验证；使用 ORM 模型和 `AsyncSessionLocal` 写数据库。

#### `scripts/drop_redundant_indexes.sql`

- 职责：删除旧数据库中模型已不再声明的三个冗余普通索引。
- 状态：脚本已存在，但本轮没有在真实数据库执行。

## 4. 当前可用接口

### 业务接口

| Method | Path | 作用 | 输入概况 | 输出概况 |
|---|---|---|---|---|
| `GET` | `/health` | 健康检查 | 无 | `{"status":"ok","app_name":"Qingshang"}` |
| `GET` | `/api/poems` | 查询诗词列表 | Query：`author?: str`、`limit: 1..500 = 100`、`offset >= 0 = 0` | `PoemListItem[]`，包含 ID、作者、朝代、词牌、宫调、题名、套词标签等 |
| `GET` | `/api/poems/{poem_id}` | 查询一首词的完整详情 | Path：稳定 `poem_id` | `PoemCore`，包含全文、题序、sections、lines、来源；不存在返回 404 |
| `POST` | `/api/poems/{poem_id}/analyze` | 调用 LLM 生成结构化整首分析 | Path：`poem_id`；无 Body | JSON：摘要、情感流动、风格、意象、逐句翻译与解释；不存在返回 404，分析错误当前返回 500 |

### FastAPI 自动接口

| Method | Path | 作用 |
|---|---|---|
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc |
| `GET` | `/openapi.json` | OpenAPI Schema |

## 5. 当前运行与测试命令

以下命令以 Windows PowerShell、项目根目录为前提。

### 安装依赖

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 必要环境变量

根目录 `.env` 至少应按实际环境配置：

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/qingshang
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

### 创建缺失数据库表

```powershell
.venv\Scripts\python.exe -m app.db.init_db
```

### 清洗周邦彦数据

```powershell
.venv\Scripts\python.exe scripts\clean_zhoubangyan_working_text.py
```

### 导入周邦彦数据

```powershell
.venv\Scripts\python.exe scripts\import_zhoubangyan_poems.py
```

### 启动开发服务器

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

默认访问：`http://127.0.0.1:8000/docs`。

### 运行测试

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 编译检查

```powershell
.venv\Scripts\python.exe -m compileall app scripts tests
```

### 清理旧数据库冗余索引

按实际 PostgreSQL 连接参数执行：

```powershell
psql -d qingshang -f scripts\drop_redundant_indexes.sql
```

此命令尚未在当前环境验证，执行前应确认目标数据库和备份策略。

## 6. 已经跑通的功能

本轮实际验证结果：

- `app/`、`scripts/`、`tests/` 全部 Python 文件通过 `compileall`。
- 5 个 unittest 全部通过：
  - Markdown JSON 围栏提取。
  - 宫调与题名元数据解析。
  - 词句切分及全局编号递增。
  - `PoemCore` 从嵌套 ORM 风格对象读取和验证数据。
  - OpenAPI 中存在 `/api/poems`，且旧 `/api/chat/test` 和 `/api/poetry/explain` 均已移除。
- 路由聚合可以在不连接数据库的情况下成功导入并生成 OpenAPI。
- Git 差异检查 `git diff --check` 已通过。
- 已启动本地 Uvicorn 并完成实际 HTTP 检查：
  - `GET /health` 返回 200。
  - `GET /api/poems` 返回 200，说明 PostgreSQL 查询链路可用。
  - `GET /api/poems/zhoubangyan-0001` 返回 200，详情及嵌套数据可读取。
  - `POST /api/poems/zhoubangyan-0001/analyze` 成功进入接口，但约 30 秒后返回 500；当前非敏感配置显示 API key 已配置、目标为 DeepSeek、超时为 30 秒，表现符合外部 LLM 读取超时。

不能据此宣称已经跑通的部分：

- 已验证 PostgreSQL 读取，但没有重新验证建表、级联删除或全量导入。
- 结构化 LLM 分析尚未成功返回 200；当前检查停在外部请求超时。
- `drop_redundant_indexes.sql` 尚未对真实数据库执行。

## 7. 尚未解决的问题与技术债

### 当前问题

1. **没有数据库迁移系统。** `create_all()` 只会创建缺失表，不能升级已有表；索引变更目前依靠独立 SQL 文件。
2. **缺少真实集成测试。** 当前测试不覆盖 PostgreSQL、asyncpg、FastAPI 请求生命周期和 LLM HTTP 请求。
3. **分析接口异常过宽。** `/api/poems/{poem_id}/analyze` 捕获全部 `Exception` 并返回 500，还会把内部异常文本直接暴露给客户端。
4. **分析接口没有声明 `response_model=PoemAnalysis`。** 当前手动 `model_dump`，OpenAPI 无法完整展示结构化输出。
5. **没有 `.env.example`。** 新会话无法只看仓库确认必需环境变量；真实 `.env` 已被忽略，这是正确的。
6. **脚本路径依赖当前工作目录。** 数据文件使用相对路径，当前命令必须从项目根目录执行。
7. **LLM 客户端每次请求创建新的 `httpx.AsyncClient`。** 功能简单但不能复用连接；高并发前需要生命周期管理。
8. **LLM 接口没有认证、限流、缓存或成本保护。** 暴露到公网前风险较高。
9. **列表分页没有总数和 next/previous 元数据。** 目前只返回数组。
10. **测试工具链很轻。** 没有覆盖率、lint、format、类型检查或 CI 配置。
11. **生成数据策略未完全明确。** `zhoubangyan_poems.json` 仍被 Git 跟踪，但又可由脚本生成；需要决定它是正式 seed 还是纯构建产物。

### 建议暂时不要动

- **不要直接重构三层诗词表结构。** `poem_id`、section/line 编号、外键和唯一约束已经与现有 JSON 和导入流程绑定；应先建立 Alembic 和集成测试。
- **保留关键的低噪声注释。** FastAPI 控制反转、ORM 预加载和事务边界仍需在源码附近提示；详细教学应继续放在 `docs/code-reading/`。
- **不要大改周邦彦解析状态机和规则集合。** 当前只有少量辅助函数测试，缺少完整语料快照测试；看似简单的清理可能改变 500KB 生成 JSON。
- **不要贸然升级全部依赖。** 当前版本已经固定；应先有集成测试，再分批升级 FastAPI、Pydantic、SQLAlchemy 和 asyncpg。
- **不要删除 `poem_lines.poem_db_id` 这类看似重复的字段。** 它参与全词句号唯一约束和查询设计，删除需要数据库迁移与性能验证。
- **不要把同步文档中的“已通过单元测试”理解成生产就绪。** 数据库和 LLM 端到端链路仍需验证。

## 8. 下一步建议（按优先级）

1. **补齐可重复运行环境。** 新增 `.env.example`，明确 PostgreSQL 初始化步骤；可选增加 Docker Compose 只启动 PostgreSQL。
2. **做一次真实端到端冒烟验证。** 建表、清洗、导入，然后依次请求 health、列表、详情和结构化分析；记录命令与结果。
3. **引入 Alembic 并建立基线迁移。** 将当前三张表和索引作为首个基线，之后不再用零散 SQL 管理结构变更。
4. **补 API/数据库集成测试。** 使用测试数据库覆盖依赖注入、分页、404、嵌套详情、级联删除；使用 mock transport 覆盖 LLM 成功与错误响应。
5. **收紧分析接口契约。** 为 analyze 声明 `response_model=PoemAnalysis`，只捕获预期异常，服务端记录详细错误，客户端返回稳定错误消息。
6. **增加完整语料回归测试。** 对清洗结果记录词作数、关键 ID、片数、句数和稳定哈希，保护解析器重构。
7. **明确生成 JSON 的版本策略。** 若作为数据库 seed，移动到明确的 seed 目录并记录来源；若为构建产物，则从 Git 移除并在运行流程中生成。
8. **增加基础工程检查。** 选择 Ruff/Black、类型检查和 GitHub Actions，在每次提交运行测试与编译检查。
9. **公网部署前补安全与成本控制。** 增加认证、限流、请求大小限制、日志脱敏、LLM 调用超时/重试策略和可选缓存。
