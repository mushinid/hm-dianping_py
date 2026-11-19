# HM Dianping FastAPI

当前实现用户模块，与 Java 项目的 `/user` 接口保持相同路径、Redis key 和响应包装。

## 本地启动

1. 复制 `.env.example` 为 `.env`，填写本机 MySQL 和 Redis 连接信息。
2. 安装依赖：`uv sync`
3. 启动：`uv run uvicorn hm_dianping_py.app.app:app --reload`

应用复用现有的 `tb_user` 和 `tb_user_info` 表，不会自动创建或修改数据库表。`/user/code` 目前只将验证码写入 Redis，联调时可读取 `login:code:{手机号}`；尚未接入短信服务。
