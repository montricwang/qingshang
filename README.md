# Qingshang 代码阅读指南

这是一个使用 FastAPI、Pydantic、SQLAlchemy 和 httpx 编写的异步 API 项目。
它和普通顺序执行脚本最大的区别是：应用启动时主要在**登记规则**，真正的函数调用
由 Web 请求触发，FastAPI 再根据这些规则替我们准备参数、调用函数和生成响应。

## 从哪里开始读

推荐按照下面的顺序阅读：

1. `app/main.py`：创建应用并注册总路由。
2. `app/api/routes/poems.py`：观察路由装饰器、参数来源和依赖注入。
3. `app/db/session.py`：观察数据库会话怎样由 `Depends` 自动创建和关闭。
4. `app/crud/poem.py`：观察查询表达式何时构造、何时真正执行。
5. `app/models/poem.py`：理解 ORM 如何把数据库记录表示成 Python 对象。
6. `app/schemas/poem.py`：理解 Pydantic 如何校验输入和限制输出。
7. `app/services/llm_client.py`：观察异步外部 HTTP 调用。

## 启动阶段发生什么

执行：

```powershell
uvicorn app.main:app
```

大致过程如下：

1. Uvicorn 导入 `app.main`。
2. Python 执行模块顶层代码，创建 `FastAPI` 对象。
3. 导入 `app.api.routes` 时，各路由模块也被导入。
4. `@router.get(...)` 和 `@router.post(...)` 装饰器把函数登记进路由表。
5. `app.include_router(api_router)` 把总路由表登记进应用。
6. Uvicorn 启动事件循环，等待请求。

这时 `read_poem_list` 等路由函数还没有执行。装饰器只是把“什么请求应调用什么函数”
保存下来，这就是框架取得控制权的第一处。

## 查询列表的调用链

请求示例：

```text
GET /api/poems?author=周邦彦&limit=20
```

FastAPI 自动完成以下流程：

1. 在路由表中找到 `read_poem_list`。
2. 从 URL 查询字符串读取 `author` 和 `limit`。
3. 按 `Query` 中的规则校验范围；失败就直接返回 422。
4. 发现参数 `db=Depends(get_db)`，于是先调用 `get_db`。
5. `get_db` 创建 `AsyncSession`，通过 `yield` 交给路由的 `db` 参数。
6. 路由调用 `list_poems`，后者构造 SQLAlchemy 查询并执行 SQL。
7. 路由把 ORM 对象转换成 `PoemListItem`。
8. FastAPI 按 `response_model` 再校验输出并序列化为 JSON。
9. 请求结束后，FastAPI 回到 `get_db` 的 `yield` 后面并关闭 session。

这里没有代码显式写出“调用 get_db，再把结果传给 read_poem_list”，因为这段调用由
FastAPI 的依赖注入系统执行。

## Pydantic 做了什么

`BaseModel` 子类是一份运行时数据契约。例如：

```python
class PoetryExplainRequest(BaseModel):
    text: str = Field(..., min_length=1)
```

它不仅是类型提示。FastAPI 收到 JSON 后会要求 Pydantic：

1. 把 JSON 转成 Python 数据；
2. 检查 `text` 是否存在、是否是字符串、长度是否至少为 1；
3. 成功后创建 `PoetryExplainRequest` 对象；
4. 失败时生成结构化错误，由 FastAPI 返回 HTTP 422。

`ConfigDict(from_attributes=True)` 表示除了字典，Pydantic 也可以从 ORM 对象的同名
属性读取数据。

## SQLAlchemy ORM 做了什么

`mapped_column` 和 `relationship` 在类定义时向 SQLAlchemy 描述数据库结构：

- `mapped_column` 描述数据库列、类型、主键和外键。
- `relationship` 描述 Python 对象之间如何导航，例如 `poem.sections`。
- `select(PoemModel)` 构造查询表达式，还没有访问数据库。
- `await db.execute(stmt)` 才真正通过 asyncpg 把 SQL 发给 PostgreSQL。
- `result.scalars()` 把结果中的 ORM 实体取出来。

`relationship` 可能采用延迟加载，即读取属性时才查询数据库。本项目的详情查询使用
`selectinload` 预先加载 `sections` 和 `lines`，使后面的响应序列化不再偷偷发 SQL。

## async 和 await 做了什么

`async def` 创建的是异步函数。调用它不会像普通函数一样直接完成，必须使用
`await`。等待数据库或网络时，事件循环可以切换去处理其他请求；等待结束后再从
当前代码位置继续执行。

`async with` 是异步上下文管理器。它保证资源在代码块结束时被释放，例如：

- `AsyncSessionLocal()` 在退出时关闭数据库会话；
- `httpx.AsyncClient()` 在退出时释放 HTTP 连接资源。

## 建议设置的断点

为了亲眼看到控制流，可以依次在这些函数第一行设置断点：

1. `app/main.py` 的模块顶层：观察启动导入。
2. `app/api/routes/poems.py:read_poem_list`：观察请求参数已经被准备好。
3. `app/db/session.py:get_db`：观察 `yield` 前后分别在请求开始和结束执行。
4. `app/crud/poem.py:list_poems`：观察 `stmt` 与 `execute` 的区别。
5. `app/services/llm_client.py:chat_completion`：观察外部请求和响应转换。

## 离线脚本与 Web 应用的区别

`scripts/` 下的文件是普通脚本。它们通过 `if __name__ == "__main__"` 主动调用
`main()`，执行顺序从上到下，更接近常规 Python 程序。它们不会使用 FastAPI 的
`Depends`，因此必须自行创建和关闭数据库 session。
