# 01 使用文档

## 两种本地运行方式

### 方式一：SQLite 快速运行

适合学习代码、跑测试、验证主流程。

```bash
uvicorn app.main:app --reload
```

没有 `.env` 时，项目默认使用 SQLite：

```text
app/agent_platform.db
```

### 方式二：Windows + Docker 生产形态运行

适合验证 PostgreSQL、pgvector、Redis 这些更接近生产项目的基础设施。

```powershell
Copy-Item .env.example .env
docker compose up -d
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

完整 Windows 配置、Docker Desktop、端口冲突、pgvector 检查见：

```text
docs/05-windows-docker-runbook.md
```

## 跑测试

```bash
pytest tests
```

## 生成一个生产级 Agent 项目的最小流程

1. 创建租户：`POST /v1/tenants`
2. 创建 owner 用户：`POST /v1/users`
3. 创建 builder run：`POST /v1/builder/runs`
4. 执行 run：`POST /v1/builder/runs/{run_id}/invoke`
5. 如果进入人工审核，用 owner token 调用：`POST /v1/reviews/{review_id}/decide`
6. 查看生成项目、验证报告和 eval 报告。

高风险领域，例如律所、医院，会默认触发人工审核。
