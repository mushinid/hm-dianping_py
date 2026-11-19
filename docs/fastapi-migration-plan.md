# HM Dianping FastAPI 重构开发流程

> 目标目录：`D:\PythonProjects\hm-dianping_py`  
> 现有项目：`D:\ideaProjects\hm-dianping`  
> 方案基于当前 Spring Boot 代码、`hmdp.sql` 和现有 `ai-service` 盘点整理。

## 1. 重构目标与原则

在新目录从零搭建 FastAPI 应用，逐步替换现有 Spring Boot 服务。第一阶段以兼容现有客户端和数据为目标，不重建数据库、不一次性切换流量，也不把 Java 的类结构机械翻译成 Python。

基本原则：

- 继续使用现有 MySQL 数据库和 `tb_*` 表；确认字段、索引、字符集及生产数据后再做 schema 变更。
- 先记录并兼容前端实际使用的 URL、HTTP 方法、参数、请求头和 JSON 响应，再考虑 API 清理。
- 保留 `authorization` 请求头及 `{success, errorMsg, data, total}` 响应结构，减少旧前端改动。
- Redis 登录态、缓存、地理位置查询、点赞/关注时间线、签到位图和秒杀 Lua 都是业务行为，迁移时逐项验证。
- 新旧服务可并行准备，但同一业务写操作在切换阶段只能有一个权威写入方，避免双写造成数据不一致。
- AI 服务并入同一个 FastAPI 应用，AI 上下文直接调用本地业务服务，不再经 HTTP 回调旧 Java 服务。

## 2. 现状与需要确认的边界

### 已有业务域

数据库包含用户、用户资料、商铺、商铺类型、探店笔记、笔记评论、关注、签到、优惠券、秒杀库存和优惠券订单等表。建表定义和示例数据位于旧项目 `src/main/resources/db/hmdp.sql`。

当前路由大致分为：

| 业务 | 当前路由范围 | 迁移注意点 |
|---|---|---|
| 用户 | `/user/code`、`/user/login`、`/user/logout`、`/user/me`、`/user/info/{id}`、`/user/{id}`、`/user/sign`、`/user/sign/count` | 令牌放在 Redis Hash 中，访问时刷新 TTL；logout 当前返回“功能未完成” |
| 商铺 | `/shop/{id}`、`POST/PUT /shop`、`/shop/of/type`、`/shop/of/name` | 店铺缓存、附近商铺 GEO 查询、分页参数和距离排序 |
| 商铺类型 | `/shop-type/list` | Redis 缓存及排序行为 |
| 探店笔记 | `POST /blog`、`/blog/like/{id}`、`/blog/of/me`、`/blog/hot`、`/blog/{id}`、`/blog/likes/{id}`、`/blog/of/user`、`/blog/of/follow` | 点赞 ZSET、关注 Feed 游标、分页及作者信息拼装 |
| 关注 | `/follow/{id}/{isFollow}`、`/follow/or/not/{id}`、`/follow/common/{id}` | 关注/取关幂等性及共同关注查询 |
| 优惠券与秒杀 | `/voucher`、`/voucher/seckill`、`/voucher/list/{shopId}`、`/voucher-order/seckill/{id}` | 秒杀 Lua 原子校验库存/一人一单，再发送 RabbitMQ 消息建单 |
| 图片 | `/upload/blog`、`/upload/blog/delete` | 文件大小、类型、文件名和路径校验；生产环境应优先使用对象存储 |
| AI | `/ai/chat`；Python AI 服务有 `/ui/chat/stream` 和 `/v1/chat/stream` | 合并页面、流式回答、温度参数、模型 Provider 和业务上下文查询 |

### 现有实现并不等同于完整需求

- `BlogCommentsController` 当前没有接口方法；虽然有 `tb_blog_comments` 表和 Service/Mapper，不能假定评论 API 已经对前端可用。
- `/user/logout` 当前未实现。
- `/user/code` 当前把验证码写入 Redis，并通过日志输出验证码；没有接入真实短信供应商。开发环境可保留测试适配器，生产环境需接入短信服务并限流。
- 当前秒杀消息消费者存在于 `PayStatusLinsener`；切换前需要确认线上 RabbitMQ 拓扑、消息持久化、失败重试和重复投递策略。
- 当前仓库没有看到前端源码，因此 URL 和 JSON 结构必须再通过浏览器 Network、前端仓库或调用日志核实。

## 3. 推荐技术选型

| 层 | 选择 | 使用方式 |
|---|---|---|
| Python | Python 3.12 | 团队统一运行时版本，锁定补丁版本范围；部署前核对目标操作系统和依赖兼容性 |
| API | FastAPI + Pydantic v2 | 路由参数校验、OpenAPI 文档、响应 DTO；开发时启用 `/docs` |
| ASGI | Uvicorn | 本地开发启用 reload；生产按部署方式配置 worker、超时和健康检查 |
| MySQL | SQLAlchemy 2.x Async ORM + `asyncmy` | 复用现有表；每个请求独立 `AsyncSession`，显式控制事务和关系加载 |
| Schema 变更 | Alembic | 记录增量迁移；自动生成的 revision 必须人工检查，不在应用启动时自动建表 |
| Redis | `redis-py` 的 `redis.asyncio` | 统一封装连接生命周期、超时、序列化和 key 前缀；保留 GEO、ZSET、Bitmap、Lua 能力 |
| RabbitMQ | `aio-pika` | 秒杀订单消息采用可靠发布、幂等消费、失败重试/DLQ；消费成功后再 ACK |
| HTTP/AI | HTTPX AsyncClient | 连接池和超时；模型 Provider 抽象；SSE/NDJSON 流式返回按现有页面协议兼容 |
| 配置 | Pydantic Settings + 环境变量 | `.env.example` 放变量名和示例，不提交真实密码、Token 或模型密钥 |
| 依赖管理 | `uv` + `pyproject.toml` + `uv.lock` | 本地、CI 和部署使用相同锁文件安装依赖 |
| 测试/静态检查 | pytest、pytest-asyncio、HTTPX、Ruff | 路由契约、业务逻辑、数据库/Redis/MQ 集成测试分层执行 |

异步数据库能与 AI 流式响应、Redis 和 RabbitMQ 客户端在一个事件循环内协作，但必须避免在 `async def` 中调用阻塞式数据库/网络客户端。`AsyncSession` 不能被并发任务共享；并发子任务各自创建 Session，或按顺序使用同一个请求 Session。

## 4. 建议架构与目录

```text
客户端 / Web 页面
       |
       v
FastAPI Router -> Pydantic DTO -> Service -> SQLAlchemy -> MySQL
                                      |-> Redis
                                      |-> RabbitMQ
                                      |-> AI Provider / HTTPX
```

建议先采用清晰但不过度拆分的目录；只有复杂查询或跨业务复用明显时才单独增加 Repository：

```text
hm-dianping_py/
  app/
    main.py
    api/v1/                 # user、shop、blog、follow、voucher、ai 路由
    core/                   # settings、认证、日志、异常处理
    db/                     # SQLAlchemy Base、session、实体模型
    schemas/                # 请求和响应 DTO
    services/               # 业务逻辑
    integrations/           # Redis、RabbitMQ、短信、对象存储、AI Provider
    static/                 # 现有 AI 客服页面的 HTML/CSS/JS
  alembic/
  tests/
    unit/
    api/
    integration/
  docs/
  .env.example
  pyproject.toml
  uv.lock
  Dockerfile
```

路由只负责 HTTP 输入输出和依赖注入；业务规则放 Service；数据库事务在 Service 边界明确提交/回滚。不要把所有业务塞进一个 `main.py`，也不要为每个表无条件创建一套 Repository 抽象。

## 5. 从零开始的开发阶段

### 阶段 0：冻结现有行为和数据基线

1. 在旧服务可运行的环境记录所有前端实际调用的 API：方法、路径、Headers、Query、Body、成功/失败 JSON、分页和排序规则。
2. 盘点当前数据库版本与数据行数；备份数据库，确认生产 schema 与 `hmdp.sql` 是否一致。
3. 记录 Redis 中正在使用的 key 前缀、TTL、数据结构和初始化任务；记录 RabbitMQ Exchange、Queue、Binding、消费者和重试配置。
4. 把已实现、未实现和本次需要新增的能力区分开，尤其确认评论、登出、短信服务和上传存储的需求。
5. 建立 API 基线样例，供新服务做 JSON 对比。此阶段不改生产数据和生产流量。

### 阶段 1：初始化 FastAPI 工程

在 PowerShell 中：

```powershell
Set-Location 'D:\PythonProjects\hm-dianping_py'
uv init --python 3.12
uv add fastapi 'uvicorn[standard]' pydantic-settings sqlalchemy asyncmy redis aio-pika httpx alembic python-multipart
uv add --dev pytest pytest-asyncio ruff
```

随后建立上述目录结构，提交 `pyproject.toml`、`uv.lock`、`.env.example` 和 `.gitignore`。`.env`、数据库导出、上传图片、日志和密钥文件不得提交版本库。

先实现 `/health/live` 和 `/health/ready`：前者只判断进程可服务，后者检查必需的 MySQL/Redis 连接；RabbitMQ 可按部署需求单独暴露组件状态，避免短暂 MQ 故障导致所有只读 API 被误判不可用。配置使用应用启动生命周期创建、关闭连接池。

### 阶段 2：映射数据库并建立安全迁移基线

1. 按 `hmdp.sql` 映射现有 `tb_user`、`tb_user_info`、`tb_shop`、`tb_shop_type`、`tb_blog`、`tb_blog_comments`、`tb_follow`、`tb_sign`、`tb_voucher`、`tb_seckill_voucher`、`tb_voucher_order`。
2. 保持旧列名、主键类型、空值规则、金额单位、时间字段、字符集和评分缩放规则；例如商铺评分字段按现有库的存储值解释，不要直接按浮点分写回。
3. 对照真实数据库检查模型映射和索引；对现有库建立 Alembic baseline/stamp，不生成会删除或重建已有表的迁移。
4. 仅对确认需要的变更编写 migration。秒杀订单可评估增加 `(user_id, voucher_id)` 唯一约束，但必须先查重并制定清理/回滚方案。
5. 禁止生产启动时调用 ORM `create_all()` 或自动执行未经人工审查的迁移。

### 阶段 3：认证、响应和公共中间件

1. 实现兼容 `authorization` Header 的依赖项：读取 Redis 中的 opaque token，构建当前用户上下文，按旧行为刷新会话 TTL。
2. 公共路由与需登录路由使用明确的路由依赖，不依赖易遗漏的全局排除列表；未登录响应保持旧前端所需的状态码/JSON 约定。
3. 统一成功和业务错误响应，兼容 `{success, errorMsg, data, total}`；FastAPI 验证错误也转换为客户端可理解的结构。
4. 确认 Token 生成、注销、过期和轮换策略；日志只记录 trace id、路由和错误类型，不记录完整 Token、手机号、验证码、密码或模型密钥。

### 阶段 4：按低风险到高风险迁移普通业务

建议顺序：

1. 商铺类型列表、商铺详情、商铺名称查询和基础分页。
2. 商铺详情缓存、空值缓存、逻辑过期重建、附近商铺 Redis GEO 查询及更新缓存策略。
3. 用户资料读取、登录/验证码、签到和签到连续天数。
4. 探店笔记发布、详情、热门列表、作者列表、点赞与点赞用户排序。
5. 关注/取关、共同关注和关注 Feed 游标分页。
6. 普通优惠券查询/创建及图片上传/删除。

每组功能按“单元测试 -> API 契约测试 -> 依赖服务集成测试 -> 旧服务结果对比”推进。优先实现真实调用链，不要把测试成功建立在 mock 掉所有 Service 的基础上。

### 阶段 5：单独迁移秒杀和异步订单

秒杀具有并发和数据一致性风险，应在普通接口稳定后再做：

1. 把现有 Lua 的库存扣减和一人一单检查放在 Redis 原子脚本中，保持库存不会被并发超卖。
2. 校验 Redis 库存缓存初始化、失效与数据库库存之间的恢复规则；避免初始化时无条件清空已存在的用户购买集合。
3. 使用订单唯一约束或等效幂等机制，处理 RabbitMQ 重复投递；创建订单、扣 DB 库存和 ACK 顺序必须可恢复。
4. 配置持久化消息、Publisher Confirms、有限重试、死信队列和告警；消息失败不得静默 ACK。
5. 用并发测试覆盖库存边界、同一用户重复请求、消息重复消费、消费者重启和 Redis/MQ 短暂故障。

现有流程是 Lua 检查/扣 Redis 库存后发 RabbitMQ 消息，再由消费者创建 DB 订单。新实现必须先解释并验证 Redis 已扣库存但消息未送达、消息已送达但消费者失败等崩溃窗口，再决定 Outbox、补偿任务或可靠消息策略。

### 阶段 6：合并 AI 客服

1. 将现有 `ai-service/app` 的意图识别、上下文整理、Provider、temperature 校验和流式输出迁入主 FastAPI 工程。
2. 商铺/达人上下文从本地 Service 查询，限定结果数量，只返回模型回答必需字段；手机号、密码和完整 Token 不进入 Prompt。
3. 保留 `/ai/chat` 的登录态和响应结构；页面流式接口保留明确的 NDJSON 或 SSE 协议，前后端使用同一套事件字段。
4. Provider 超时、业务上下文失败和模型异常返回可理解的降级消息；温度值服务端校验范围，API Key 仅从环境变量读取。
5. 用无笔记/无评论、未知达人、模型超时、上下文服务失败等场景验证回答不能编造事实。

合并后不再需要 Java 到 Python 的内部上下文 HTTP 接口，也不需要把服务间共享密钥暴露在浏览器页面。

### 阶段 7：兼容性验收、部署与切流

1. 使用脱敏的开发/测试数据库恢复样本数据，验证旧 API 样例和新服务的状态码、字段、分页、默认值及排序。
2. 先部署 FastAPI，健康检查、日志、指标和依赖连接稳定后，仅对低风险只读接口做影子对比；不要影子执行写请求。
3. 按路由组切换流量，记录每组的回滚开关；遇到错误率、延迟、数据库连接池、Redis 错误或队列积压超阈值，立即切回旧服务。
4. 切流后检查订单数/库存、用户登录、笔记点赞/Feed、商铺缓存和 AI 回答引用来源；确认稳定后再停止旧服务。
5. 最后才删除旧 Java 部署与过渡逻辑；保留数据库备份和可执行的回滚步骤。

## 6. 测试与验收清单

- API：公开/需登录路由、请求校验、旧 JSON 包装、分页、排序、异常状态码和 CORS。
- 认证：缺失/无效/过期 Token、续期、注销、并发请求及敏感字段过滤。
- MySQL：真实 schema 映射、事务回滚、唯一约束、时区和金额/评分转换。
- Redis：店铺缓存击穿/空值、GEO 距离排序、点赞/Feed ZSET、签到 Bitmap、Lua 原子性。
- RabbitMQ：发布确认、重复消费、重试/DLQ、服务重启恢复、Redis 与 DB 库存最终一致。
- AI：shop/expert 上下文、字段脱敏、无数据、模型超时、temperature 边界、流式事件顺序。
- 上传：只接受允许的图片格式和大小；删除路径必须限制在上传根目录内，避免目录穿越。
- 发布：配置校验、进程优雅关闭、连接池回收、结构化日志、错误追踪和回滚演练。

## 7. 开发顺序与完成定义

建议先完成“契约/环境 -> FastAPI 骨架 -> 数据映射 -> 认证 -> 普通读接口 -> 内容/关注 -> 写接口/上传 -> 秒杀 -> AI -> 切流”。每个阶段都应有可运行版本和验收记录，不要等所有功能完成后才第一次联调。

某业务组的完成定义：

- 前端所需 API 与旧服务兼容或已有书面批准的变更。
- 正常、边界、未登录和依赖异常路径均有测试。
- 写操作事务、幂等和失败恢复方式明确。
- 不泄露敏感数据；配置从环境注入；部署、健康检查和回滚方式可复现。

## 8. 官方技术文档

- [FastAPI 异步与并发](https://fastapi.tiangolo.com/async/)
- [FastAPI 测试](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 自动生成迁移及其限制](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [redis-py asyncio 示例](https://redis.readthedocs.io/en/latest/examples/asyncio_examples.html)
- [aio-pika Quick Start](https://docs.aio-pika.com/quick-start.html)
