# Beginner Code Map

## 1. 项目入口

后端启动：

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`app.main:app` 中的 `app`【FastAPI 应用对象】是后端入口。Uvicorn 导入 `app/main.py`，FastAPI 注册 `/health` 和 `/api/poems...` 路由，然后等待 HTTP 请求。

前端启动：

```powershell
.venv\Scripts\python.exe -m streamlit run apps\reader_app.py
```

`apps/reader_app.py`【Streamlit 页面入口】负责装配 Reader 页面。它读取本地 FastAPI 数据，然后把目录、正文和工具面板交给 `apps/reader/` 下的模块渲染。

## 2. 文件地图

`app/main.py`：创建 FastAPI 应用、注册总路由，并提供 `/health`。

`app/api/routes/__init__.py`：把 poems 路由聚合成 `api_router`，供 `app/main.py` 注册。

`app/api/routes/poems.py`：定义诗词列表、详情、赏析、典故候选、候选证据和 AI 审阅接口。

`app/core/config.py`：从环境变量和 `.env` 读取数据库、LLM 等配置。

`app/db/session.py`：创建异步数据库引擎、会话工厂和 FastAPI 的 `get_db` 依赖。

`app/db/init_db.py`：导入 ORM 模型并创建缺失数据表，不负责迁移已有表结构。

`app/models/poem.py`：定义 poems / poem_sections / poem_lines 三层 ORM 数据结构。

`app/crud/poem.py`：封装词作列表和详情查询，不处理 HTTP 响应。

`app/schemas/poem.py`：定义诗词列表、详情和清洗结果的数据结构。

`app/schemas/analysis.py`：定义整首词结构化赏析的 LLM 输出结构。

`app/schemas/allusion.py`：定义典故候选、候选证据结果和 Evidence Review 结果的数据结构。

`app/schemas/cnkgraph.py`：定义 CNKGraph 阅读辅助接口返回给前端的窄数据结构。

`app/services/llm_client.py`：统一调用兼容 OpenAI Chat Completions 协议的 LLM 接口。

`app/services/poem_analyzer.py`：把词作转换成 prompt，调用 LLM，并校验成结构化赏析。

`app/services/cnkgraph_client.py`：封装 CNKGraph HTTP 请求和错误转换。

`app/services/reading_aids.py`：聚合字词、典故、出处、韵部、词谱等阅读辅助结果。

`app/services/allusion_candidate_extractor.py`：让 LLM 从整首词中识别值得查证的典故/化用候选。

`app/services/allusion_evidence.py`：对候选逐个查询 CNKGraph，并生成可展示的候选证据预览。

`app/services/allusion_evidence_reviewer.py`：只基于已有候选证据调用 Reviewer，生成受控审阅状态和短注。

`apps/reader_app.py`：Streamlit Reader 装配文件，负责页面配置、主题、横幅和左右栏组合。

`apps/reader/api_client.py`：前端访问本地 FastAPI 的薄 HTTP 客户端。

`apps/reader/config.py`：保存 Reader 常量、中文标签、主题颜色、超时和资源路径。

`apps/reader/directory.py`：渲染侧栏词作目录、筛选、分页和无题词起句。

`apps/reader/poem_view.py`：渲染词作正文、阅读模式、慢读分片、转轮和领读。

`apps/reader/tools_panel.py`：渲染右侧 AI 审阅入口、候选结果、手动 reading-aids 表单和结果 Tabs。

`apps/reader/state.py`：集中管理 `st.session_state` 中的词作切换、文本选择、候选回填和领读状态。

`apps/reader/text.py`：整理慢读分片、缩进、句子展开和索引边界等纯展示逻辑。

`apps/reader/evidence.py`：把后端证据 dict 转成安全 HTML 片段，不直接调用 Streamlit。

`apps/assets/reader.css`：Reader 页面样式。

`scripts/clean_zhoubangyan_working_text.py`：把工作文本清洗成结构化 JSON。

`scripts/import_zhoubangyan_poems.py`：把清洗后的周邦彦数据导入 PostgreSQL。

`scripts/zhoubangyan_rules.py`：保存周邦彦文本清洗用的词牌、宫调、套词和断句规则。

`tests/`：保存当前单元测试，覆盖核心 schema、路由注册、清洗和典故证据逻辑。

## 3. AI 审阅按钮数据流

用户点击按钮。

→ `apps/reader/tools_panel.py` 中的 `_render_ai_review_section()`【函数 / Streamlit 渲染函数】响应点击。

→ `apps/reader/api_client.py` 中的 `fetch_allusion_candidates()`【函数 / 前端 API 客户端函数】发送 `POST /api/poems/{poem_id}/allusion-candidates/with-review`。

→ 后端 `app/api/routes/poems.py` 中的 poems route【FastAPI 路由】先查询当前词作。

→ `build_allusion_evidence_review()`【函数 / 服务函数】成为后端审阅主入口。

→ `extract_allusion_candidates()`【函数 / 服务函数】先识别候选；它由证据预览构建流程间接调用。

→ `build_allusion_evidence_preview()`【函数 / 服务函数】为候选逐项查询 CNKGraph，并形成原始候选证据预览。

→ `review_allusion_candidate()`【函数 / 服务函数】只拿已有候选证据调用 Reviewer，判断证据角色、相关度和短注状态。

→ 后端返回 JSON【HTTP 响应】，结构符合 `AllusionCandidateReviewResponse`。

→ `st.session_state.allusion_candidates`【Streamlit 状态】保存本次 AI 审阅结果，页面 rerun 后仍可显示。

→ `render_allusion_evidence_preview()`【函数 / Streamlit 渲染函数】展示审阅状态、短注、最佳候选证据，以及折叠的原候选证据预览。
