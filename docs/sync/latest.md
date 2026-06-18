# Qingshang 项目现状同步

> 生成日期：2026-06-18  
> 仓库基线：`main` / `e6fc486`  
> 当前工作区：已移除旧 `/api/poetry/explain`，本文件包含未提交的新状态  
> 最近两次提交：  
> `e6fc486 docs: document framework control flow and core architecture`  
> `dc2f704 refactor: streamline API, LLM client, and data processing`

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

当前只包含后端、数据清洗/导入脚本和少量单元测试，没有前端、用户系统、权限系统、
Alembic 数据库迁移、Docker 配置或 CI。

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
- 连接：被 `app/main.py` 注册；导入两个业务路由模块会触发装饰器注册。

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
- **不要删除目前新增的解释性注释。** 当前维护者正在理解控制反转、依赖注入和 ORM，注释具有实际维护价值；以后只删除过时或重复表面语义的内容。
- **不要大改周邦彦解析状态机和规则集合。** 当前只有少量辅助函数测试，缺少完整语料快照测试；看似简单的清理可能改变 500KB 生成 JSON。
- **不要贸然升级全部依赖。** 当前版本已经固定；应先有集成测试，再分批升级 FastAPI、Pydantic、SQLAlchemy 和 asyncpg。
- **不要删除 `poem_lines.poem_db_id` 这类看似重复的字段。** 它参与全词句号唯一约束和查询设计，删除需要数据库迁移与性能验证。
- **不要把同步文档中的“已通过单元测试”理解成生产就绪。** 数据库和 LLM 端到端链路仍需验证。

## 8. 下一步建议（按优先级）

1. **补齐可重复运行环境。** 新增 `.env.example`，明确 PostgreSQL 初始化步骤；可选增加 Docker Compose 只启动 PostgreSQL。
2. **做一次真实端到端冒烟验证。** 建表、清洗、导入，然后依次请求 health、列表、详情、自由赏析和结构化分析；记录命令与结果。
3. **引入 Alembic 并建立基线迁移。** 将当前三张表和索引作为首个基线，之后不再用零散 SQL 管理结构变更。
4. **补 API/数据库集成测试。** 使用测试数据库覆盖依赖注入、分页、404、嵌套详情、级联删除；使用 mock transport 覆盖 LLM 成功与错误响应。
5. **收紧分析接口契约。** 为 analyze 声明 `response_model=PoemAnalysis`，只捕获预期异常，服务端记录详细错误，客户端返回稳定错误消息。
6. **增加完整语料回归测试。** 对清洗结果记录词作数、关键 ID、片数、句数和稳定哈希，保护解析器重构。
7. **明确生成 JSON 的版本策略。** 若作为数据库 seed，移动到明确的 seed 目录并记录来源；若为构建产物，则从 Git 移除并在运行流程中生成。
8. **增加基础工程检查。** 选择 Ruff/Black、类型检查和 GitHub Actions，在每次提交运行测试与编译检查。
9. **公网部署前补安全与成本控制。** 增加认证、限流、请求大小限制、日志脱敏、LLM 调用超时/重试策略和可选缓存。
