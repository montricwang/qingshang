# CNKGraph 全接口实测与清商适用性报告

> 测试时间：`2026-06-20T13:30:18.180704+00:00`  
> 数据来源：`docs/cnkgraph/postman/` 内 12 份 Postman 集合  
> 测试范围：71 个集合请求，逐项真实访问 `https://api.cnkgraph.com`

## 1. 结论摘要

- HTTP 成功：**69/71**；失败：**2**。
- 本报告证明的是测试时点的可访问性和响应形态，不等同于 SLA、长期稳定性、授权许可或字段契约保证。
- 近期最值得接入：诗文库的作品详情/平仄/出处、词汇典故、词谱、韵典、字典，以及工具中的出处与化用分析。
- 中期适合补充：人物、地理、年历、古籍与类书，用于可追溯的作者生平、创作时空和原典上下文。
- 远期再考虑：全库总览、跨库链接、曲谱和大范围目录遍历；它们价值存在，但不应拖慢 poems 阅读主链路。

## 2. 测试方法与边界

- 请求定义直接读取仓库中的 Postman collection，不手工改写接口路径或请求体。
- 仓库没有 Postman environment；优先使用 collection 自带变量，其余占位符使用脚本中的明确回退值。诗文样例沿用 collection 的杜甫（作者 `17270`、作品 `10000`）。
- 所有请求按顺序执行，默认超时 90 秒、间隔 0.1 秒；没有并发压测，也没有故意发送破坏性或异常输入。
- 原始结果保存在 `data/generated/cnkgraph_all_probe.json`；超过 20,000 字符的响应只保留前段样本，但记录完整响应字符数和结构摘要。
- 只要 HTTP 为 2xx 即计为本轮成功；正式集成仍需为目标字段增加契约测试和空结果检查。

## 3. 分组结果与阶段建议

| 接口组 | 通过 | 建议阶段 | 清商中的用途与判断 |
|---|---:|---|---|
| 人物 | 6/6 | 中期 | 可补作者、相关人物、籍贯和谥号信息，适合人物关系与生平背景模块。 |
| 古籍库 | 7/7 | 中期 | 可提供原典、出处和上下文证据，适合在基本注释稳定后构建可追溯引用。 |
| 地理 | 7/7 | 中期 | 可为地名、景观和作品关联提供背景，但需先解决文本实体与行政区划 ID 的消歧。 |
| 字典 | 1/1 | 近期 | 单字释义是逐字阅读的基础能力，接口简单，适合作为按需查询工具。 |
| 工具 | 4/5 | 近期 | 出处与化用分析可直接支持阅读辅助；繁简转换与短信息查询属于配套能力，自动笺注本轮不可用。 |
| 年历 | 7/7 | 中期 | 可把年号、干支和具体日期标准化，用于作者生平与创作背景时间线。 |
| 曲谱 | 4/4 | 远期 | 清商当前聚焦宋词，曲谱主要用于跨文体比较和后续元曲扩展。 |
| 类书 | 6/6 | 中期 | 适合扩展名物、地域和典故背景，但条目层级复杂，首版不宜直接耦合。 |
| 词汇、典故 | 5/5 | 近期 | 直接支持词句释义、典故候选与阅读注释，是首版赏析的核心外部数据。 |
| 词谱 | 5/5 | 近期 | 可校验词牌、检索同调作品并匹配平仄片段，直接补足结构化词作的格律维度。 |
| 诗文库 | 12/13 | 近期 | 作品详情、平仄和出处能与本地 poems 数据直接对照，是集成优先级最高的一组；自动笺注本轮不可用。 |
| 韵典 | 5/5 | 近期 | 可解释韵目、韵字和单字归韵，能支撑押韵展示与格律分析。 |

## 4. 逐接口实测结果

| 接口组 | 请求 | Method | Path | 状态 | 耗时(ms) | 响应形态 | 建议阶段 |
|---|---|---|---|---:|---:|---|---|
| 人物 | 人物总览 | GET | /api/people | 200 | 62.38 | object(2 keys) | 远期 |
| 人物 | 按朝代浏览 | GET | /api/people/%E5%94%90 | 200 | 133.26 | object(5 keys) | 远期 |
| 人物 | 获取特定人物介绍 | GET | /api/people/15188 | 200 | 29.62 | object(2 keys) | 中期 |
| 人物 | 搜索符合指定籍贯与生卒时间范围的人物 | POST | /api/people/find | 200 | 17.61 | object(1 keys) | 中期 |
| 人物 | 按姓氏搜索人物列表 | POST | /api/people/find | 200 | 24.64 | object(1 keys) | 中期 |
| 人物 | 按谥号搜索人物列表 | POST | /api/people/find | 200 | 16.44 | object(1 keys) | 中期 |
| 古籍库 | 获取古籍库总览 | GET | /api/book | 200 | 15.02 | object(2 keys) | 远期 |
| 古籍库 | 获取某一分类下详细书目 | GET | /api/book/%E5%8F%B2%E9%83%A8/%E6%AD%A3%E5%8F%B2%E7%B1%BB | 200 | 18.37 | object(3 keys) | 远期 |
| 古籍库 | 获取某一部书的详细信息 | GET | /api/book/2180 | 200 | 21.18 | object(1 keys) | 中期 |
| 古籍库 | 获取某一卷详细内容 | GET | /api/book/volume/KR4h0140_024 | 200 | 28.32 | object(3 keys) | 中期 |
| 古籍库 | 按关键词搜索古籍库 | POST | /Api/Book/Find | 200 | 129.52 | object(8 keys) | 中期 |
| 古籍库 | 检索古籍库时在关键词中使用问号通配符 | POST | /Api/Book/Find | 200 | 100.17 | object(8 keys) | 中期 |
| 古籍库 | 检索同时包含多个关键词的古籍 | POST | /Api/Book/Find | 200 | 133.71 | object(8 keys) | 中期 |
| 地理 | 行政区划总览 | GET | /api/map/region | 200 | 39.86 | array[15] | 中期 |
| 地理 | 按 Id 查询某一行政区划及其下级区划的信息 | GET | /api/map/region/CN11 | 200 | 14.97 | array[1] | 中期 |
| 地理 | 按名称查询某一行政区划及其下级区划的信息 | GET | /api/map/region/%E6%BD%AE%E5%B7%9E%E5%B8%82 | 200 | 15.93 | array[1] | 中期 |
| 地理 | 查询与某一行政区划相关的链接 | GET | /api/map/region/CN11/links?pageNo=0 | 200 | 22.23 | object(3 keys) | 远期 |
| 地理 | 查询某一行政区划下有哪些景观 | GET | /api/map/scenery/CN11 | 200 | 30.85 | array[2606] | 中期 |
| 地理 | 查询某一景观的详细信息 | GET | /api/map/scenery/CN3301/%E8%A5%BF%E6%B9%96 | 200 | 15.7 | object(9 keys) | 中期 |
| 地理 | 查询某一景观的相关链接 | GET | /api/map/scenery/CN4201/%E9%BB%84%E9%B9%A4%E6%A5%BC/links?pageNo=0 | 200 | 20.14 | object(3 keys) | 远期 |
| 字典 | 查字 | GET | /api/char/%E4%B8%AD | 200 | 19.36 | object(3 keys) | 近期 |
| 工具 | 简体转繁体 | POST | /api/tool/charsetConvert | 200 | 18.65 | object(2 keys) | 中期 |
| 工具 | 繁体转简体 | POST | /api/tool/charsetConvert | 200 | 16.55 | object(2 keys) | 中期 |
| 工具 | 自动笺注 | POST | /api/tool/labelize | 404 | 14.08 | str | 暂缓 |
| 工具 | 出处与化用分析 | POST | /api/tool/reference | 200 | 325.33 | object(1 keys) | 近期 |
| 工具 | 短信息查询 | POST | /api/tool/texting | 200 | 19.38 | object(1 keys) | 中期 |
| 年历 | 总览 | GET | /api/calendar | 200 | 17.83 | object(1 keys) | 远期 |
| 年历 | 按朝代浏览 | GET | /api/calendar/%E5%AE%8B | 200 | 20.93 | object(2 keys) | 远期 |
| 年历 | 查看某一年号详细信息 | GET | /api/calendar/eraYear/%E5%AE%8B%E7%BB%8D%E5%85%B4 | 200 | 19.17 | object(6 keys) | 中期 |
| 年历 | 查某一年 | GET | /api/calendar/date/901%E5%B9%B4 | 200 | 18.27 | object(4 keys) | 中期 |
| 年历 | 查某一日期 | GET | /api/calendar/date/%E5%AE%8B%E7%BB%8D%E5%85%B4%E4%BA%94%E5%B9%B4%E4%B8%83%E6%9C%88%E4%B8%81%E9%85%89 | 200 | 20.2 | object(4 keys) | 中期 |
| 年历 | 查历代某一干支年 | GET | /api/calendar/GanZhi/%E5%BA%9A%E5%AD%90 | 200 | 29.5 | object(2 keys) | 远期 |
| 年历 | 查询与某一时间相关的链接 | GET | /api/calendar/date/901%E5%B9%B4/links?pageNo=0 | 200 | 27.62 | object(2 keys) | 远期 |
| 曲谱 | 曲谱总览 | GET | /api/quTune | 200 | 21.08 | array[1073] | 远期 |
| 曲谱 | 查询特定曲谱 | GET | /api/quTune/90 | 200 | 18.39 | object(7 keys) | 远期 |
| 曲谱 | 查询历代使用指定曲谱的作品 | GET | /api/quTune/1/writings | 200 | 15.8 | object(3 keys) | 远期 |
| 曲谱 | 搜索名称含某一关键词的曲谱 | POST | /api/quTune/find | 200 | 16.65 | array[43] | 远期 |
| 类书 | 获取类书列表 | GET | /api/category | 200 | 15.62 | object(1 keys) | 远期 |
| 类书 | 获取某一本类书的目录结构 | GET | /api/category/%E9%92%A6%E5%AE%9A%E5%8F%A4%E4%BB%8A%E5%9B%BE%E4%B9%A6%E9%9B%86%E6%88%90 | 200 | 67.44 | object(2 keys) | 远期 |
| 类书 | 获取古今图书集成某一条目某一卷的详细内容 | GET | /api/category/%E9%92%A6%E5%AE%9A%E5%8F%A4%E4%BB%8A%E5%9B%BE%E4%B9%A6%E9%9B%86%E6%88%90/0002/KR7a0001_018 | 200 | 30.48 | object(7 keys) | 中期 |
| 类书 | 获取渊鉴类函某一条目的详细内容 | GET | /api/category/%E6%B8%8A%E9%89%B4%E7%B1%BB%E5%87%BD/0024 | 200 | 16.18 | object(7 keys) | 中期 |
| 类书 | 获取方舆胜览某一条目详细内容 | GET | /api/category/%E6%96%B9%E8%88%86%E8%83%9C%E8%A7%88/0012 | 200 | 15.82 | object(7 keys) | 中期 |
| 类书 | 查询含某一关键词的条目 | POST | /api/category/find | 200 | 16.33 | array[3] | 中期 |
| 词汇、典故 | 按词汇 Id 查询 | GET | /api/glossary/%E8%AF%8D%E5%85%B8/10 | 200 | 18.25 | object(8 keys) | 近期 |
| 词汇、典故 | 按典故 Id 查询 | GET | /api/glossary/%E5%85%B8%E6%95%85/1000 | 200 | 14.48 | object(9 keys) | 近期 |
| 词汇、典故 | 按佛典 Id 查询 | GET | /api/glossary/%E4%BD%9B%E5%85%B8/100 | 200 | 14.83 | object(8 keys) | 近期 |
| 词汇、典故 | 按词典 Id 批量查询 | POST | /api/glossary/%E8%AF%8D%E5%85%B8 | 200 | 16.18 | array[4] | 近期 |
| 词汇、典故 | 按关键词查询典故 | POST | /api/glossary/%E5%85%B8%E6%95%85/find | 200 | 17.99 | array[3] | 近期 |
| 词谱 | 词谱总览 | GET | /api/ciTune | 200 | 26.46 | array[819] | 近期 |
| 词谱 | 查询特定词谱 | GET | /api/ciTune/90 | 200 | 15.45 | object(7 keys) | 近期 |
| 词谱 | 查询历代使用指定词谱的作品 | GET | /api/ciTune/1/writings | 200 | 18.58 | object(3 keys) | 中期 |
| 词谱 | 搜索含某一关键词的词谱 | POST | /api/ciTune/find | 200 | 15.42 | array[49] | 近期 |
| 词谱 | 查询哪些词牌含有与输入句子平仄结构相同的片段 | POST | /api/ciTune/pattern | 200 | 24.32 | object(3 keys) | 近期 |
| 诗文库 | 总览 | GET | /api/writing | 200 | 15.6 | object(2 keys) | 远期 |
| 诗文库 | 按朝代浏览 | GET | /api/writing/%E5%94%90 | 200 | 40.86 | object(1 keys) | 远期 |
| 诗文库 | 按作家浏览 | GET | /api/writing/%E5%94%90/%E6%9D%9C%E7%94%AB/17270/Poem?pageNo=0 | 200 | 22.52 | object(10 keys) | 中期 |
| 诗文库 | 获取特定作品 | GET | /api/writing/10000 | 200 | 15.06 | object(2 keys) | 近期 |
| 诗文库 | 获取特定作品，返回结果不作繁简转换 | GET | /api/writing/10000 | 200 | 15.44 | object(2 keys) | 近期 |
| 诗文库 | 获取含特定对仗词汇组的律句 | GET | /api/writing/couplet/%E5%A4%A9%E5%9C%B0,%E5%8F%A4%E4%BB%8A | 200 | 24.37 | object(3 keys) | 中期 |
| 诗文库 | 组合搜索 | POST | /api/writing/find | 200 | 18.08 | object(6 keys) | 中期 |
| 诗文库 | 获取作品库中有相似句子的作品 | GET | /api/writing/SimilarClauses/31190 | 200 | 395.82 | array[8] | 中期 |
| 诗文库 | 获取作品库中与指定作品所押韵脚相同的作品 | GET | /api/writing/SameRhymes/31190 | 200 | 42.56 | array[84] | 中期 |
| 诗文库 | 为作品标注平仄 | GET | /api/writing/10000/tones | 200 | 25.62 | object(2 keys) | 近期 |
| 诗文库 | 获取作品在古籍库中的出处及引用信息 | GET | /api/writing/10000/bookLinks | 200 | 24.85 | object(7 keys) | 近期 |
| 诗文库 | 自动笺注 | GET | /api/writing/10000/labelize | 404 | 17.42 | str | 暂缓 |
| 诗文库 | 查询符合某一平仄句式的律句 | POST | /api/writing/find | 200 | 15.51 | object(6 keys) | 中期 |
| 韵典 | 总览 | GET | /api/rhyme | 200 | 14.81 | object(1 keys) | 近期 |
| 韵典 | 获取某一韵书韵目信息 | GET | /api/rhyme/%E5%B9%B3%E6%B0%B4%E9%9F%B5 | 200 | 15.43 | object(2 keys) | 近期 |
| 韵典 | 获取某一韵目字表 | GET | /api/rhyme/%E5%B9%B3%E6%B0%B4%E9%9F%B5/%E9%9D%92 | 200 | 15.57 | object(2 keys) | 近期 |
| 韵典 | 获取韵字详细信息 | GET | /api/rhyme/%E5%B9%B3%E6%B0%B4%E9%9F%B5/%E4%BE%B5/%E5%8F%82 | 200 | 19.02 | object(9 keys) | 近期 |
| 韵典 | 查某字在某一韵书中的信息 | POST | /api/rhyme/find | 200 | 43.24 | object(9 keys) | 近期 |

## 5. 失败与异常观察

- `POST https://api.cnkgraph.com/api/tool/labelize`：状态 `404`；``
- `GET https://api.cnkgraph.com/api/writing/10000/labelize`：状态 `404`；`作者不存在`

## 6. 面向清商草案的落地论证

### 近期：增强单首词阅读闭环

近期目标应只围绕本地 `poems -> sections -> lines` 数据增加按需辅助信息。诗文详情可用于外部对照，平仄、词谱和韵典可形成可解释的格律层；词汇、典故、字典和出处分析可形成逐句阅读层。它们均能以 `poem_id` 或句子为入口，不要求先改变数据库结构。两个自动笺注接口本轮均返回 404，不应进入近期依赖清单。

建议先做独立 CNKGraph 客户端和 Tool Layer，不把第三方完整响应直接作为清商 API 契约。首批只保留稳定内部字段，例如候选词、释义、出处、置信来源、韵目和平仄字符串；设置超时、缓存和失败降级，确保 CNKGraph 不可用时本地词作仍能阅读。

### 中期：构建可追溯的知识背景

人物、地理、年历、古籍和类书适合用于作者页、创作时间线、地点卡片和出处证据链。它们的共同难点不是请求接口，而是实体消歧：同名人物、古今地名、模糊年号、不同版本书目都不能仅凭字符串自动绑定。中期应先保存外部实体 ID、来源和人工确认状态，再考虑关系图或批量回填。

诗文库的相似句、同韵、组合搜索和按作者浏览也属于中期：它们可支持延伸阅读与横向比较，但需要排序、去重和解释推荐原因，不能只把搜索结果原样展示。

### 远期：跨文体检索与知识图谱

曲谱、全库总览、目录树和跨库 links 更适合远期的跨文体研究与知识图谱。此类接口返回规模大、层级深，并可能随服务端数据更新而变化。远期若使用，应采用离线同步或受控缓存，而不是在用户请求中遍历远端全库。

## 7. 风险与尚未证明的事项

- Postman 文件没有声明认证、配额、限流、版本号、SLA 和授权条款；公开可访问不代表可在产品中无限制使用或再分发。
- 本轮是单次顺序冒烟测试，未测并发、峰值延迟、重复运行稳定性、错误码语义和服务端变更频率。
- 接口响应没有被官方 schema 约束；字段缺失、`null`、繁简转换和同名实体仍需逐接口契约测试。
- 部分搜索样例返回的是候选集合，不能视作已经完成文本实体识别或学术判断。
- `POST /api/tool/labelize` 与 `GET /api/writing/{writingId}/labelize` 按 Postman 原始定义测试均返回 404，暂不能用于产品设计。
- 不建议把 CNKGraph ID 直接写入现有 poem/section/line 核心表；当前数据库结构不应为本轮测试修改。

## 8. 下一步建议

1. 先确认 CNKGraph 的使用许可、调用频率和可接受的缓存策略。
2. 为近期接口建立一个只读客户端，优先接入作品平仄、词谱、韵典、字典、词汇典故和出处分析。
3. 定义清商自己的窄响应模型，并用保存的样本增加契约测试；第三方字段变化不能直接穿透到 `/api/poems`。
4. 增加缓存、超时、有限重试和熔断降级；外部失败时返回本地 poems 数据，而不是让整页失败。
5. 中期设计外部实体映射表与人工确认流程，再接人物、地理、年历、古籍和类书。
6. 在不同日期重复运行本脚本并比较响应结构，确认稳定性后再做生产集成。
