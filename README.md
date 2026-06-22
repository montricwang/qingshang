# 清商 Qingshang

清商是一个面向宋词阅读的 vertical-domain、evidence-grounded AI 应用。项目以结构化词作数据为底本，通过固定工作流串联候选识别、CNKGraph 候选证据检索、受控 Evidence Review 与谨慎短注，同时保留每一步的输入摘要、输出摘要、耗时和局部错误。

当前版本是 **Reader v0.2.0-preview**。它不是开放式 Agent：不使用 Web Search、Poetry RAG 或 LangGraph，也不会把检索命中直接称为定论。

## 当前链路

```text
Reader 选句
  -> Intent Router（规则）
  -> Candidate Extraction（LLM）
  -> CNKGraph Evidence Retrieval（现有典故与出处工具）
  -> Evidence Review（只审阅已检索证据）
  -> Final Answer（确定性聚合）
```

后端使用 FastAPI、PostgreSQL、SQLAlchemy Async ORM 与 Pydantic；前端入口是 `apps/reader_app.py`。

## 本地运行

1. 复制 `.env.example` 为 `.env`，填写本地 PostgreSQL 和 LLM 配置。
2. 启动 FastAPI：

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

3. 在另一个终端启动 Reader：

```powershell
.venv\Scripts\python.exe -m streamlit run apps/reader_app.py --server.port 8501
```

打开 `http://127.0.0.1:8501/`。FastAPI 文档位于 `http://127.0.0.1:8000/docs`。

## Public Demo Mode

Streamlit Cloud 的 entry file 使用 `apps/reader_app.py`。在部署 secrets 中设置：

```toml
PUBLIC_DEMO_MODE = true
```

此模式使用内置固定样例，不需要数据库、LLM key 或 CNKGraph；页面会明确标记为 `sample data`。配置模板见 `.streamlit/secrets.toml.example`，真实 secrets 不应提交到 Git。

本地也可使用：

```powershell
$env:PUBLIC_DEMO_MODE="true"
.venv\Scripts\python.exe -m streamlit run apps/reader_app.py --server.port 8501
```

## 验证

```powershell
.venv\Scripts\python.exe -m compileall app apps scripts tests
.venv\Scripts\python.exe -m pytest -q
```

## 部署方向

正式部署可逐步迁移到 Azure：FastAPI 运行于 App Service 或 Container Apps，PostgreSQL 使用 Azure Database for PostgreSQL，配置进入 Key Vault；Streamlit 可先独立部署。迁移不改变当前 API 与 evidence-first workflow 边界。

初学者代码阅读说明保留在 `docs/code-reading/`，最新项目状态见 `docs/sync/latest.md`。
