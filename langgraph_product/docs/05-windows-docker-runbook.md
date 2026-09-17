# 05 Windows + Docker 本地运行手册

这份文档说明如何在 Windows 本地用 Docker Desktop 启动项目需要的生产形态基础设施：

- PostgreSQL 16
- pgvector
- Redis
- FastAPI 应用

项目默认也可以直接用 SQLite 跑起来；Docker 模式更接近真实生产项目，因为长期记忆、RAG、用户数据、运行记录、token 用量等都应该落到数据库里。

## 一、准备 Windows 环境

建议环境：

- Windows 10/11
- Python 3.12
- Git
- Docker Desktop
- PowerShell

安装 Docker Desktop 后，确认 Docker Engine 正常：

```powershell
docker --version
docker compose version
docker ps
```

如果 `docker ps` 提示 Docker daemon 未运行，先打开 Docker Desktop，等左下角状态变成 running。

## 二、进入项目目录

```powershell
cd C:\Users\200没有5\Desktop\AiAgentStudy\AgentSkillTools\langgraph_product
```

## 三、创建并激活 Python 虚拟环境

如果你已经在上层目录创建过 `.venv`，可以继续复用。下面是从零开始的方式：

```powershell
py -3.12 -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

如果 PowerShell 禁止激活脚本，临时允许当前终端执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
..\.venv\Scripts\Activate.ps1
```

## 四、准备环境变量

复制示例配置：

```powershell
Copy-Item .env.example .env
```

默认 `.env` 会使用 Docker 中的 PostgreSQL 和 Redis：

```text
DATABASE_URL=postgresql+psycopg://agent:agent@localhost:5432/agent
REDIS_URL=redis://localhost:6379/0
```

本地学习时可以不填真实模型配置。模型网关会保留生产设计边界，测试仍可使用 stub/fallback 路径。

## 五、启动 PostgreSQL + pgvector + Redis

```powershell
docker compose up -d
```

查看容器状态：

```powershell
docker compose ps
```

查看数据库日志：

```powershell
docker compose logs postgres
```

查看 Redis 日志：

```powershell
docker compose logs redis
```

## 六、确认 pgvector 已启用

进入 PostgreSQL 容器：

```powershell
docker exec -it agent_postgres psql -U agent -d agent
```

在 psql 中执行：

```sql
\dx
```

你应该能看到 `vector` 扩展。退出 psql：

```sql
\q
```

项目的初始化脚本在：

```text
sql/init_pgvector.sql
```

## 七、启动 API 服务

确保仍在虚拟环境中，然后执行：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开另一个 PowerShell 终端验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

期望结果：

```text
healthz: status = ok
readyz:  status = ready, database = ok
```

`readyz` 会真实访问数据库，所以它比 `healthz` 更适合验证 Docker 数据库是否连通。

## 八、跑测试

测试默认可以在 SQLite/stub 路径下运行，适合快速验证业务逻辑：

```powershell
pytest tests
```

如果当前终端加载了 `.env` 并连接 PostgreSQL，也可以先保持 Docker 服务运行，再跑同样的测试。

## 九、生成一个 AI Agent 项目

启动 API 后，可以按下面顺序调用：

1. `POST /v1/tenants`
2. `POST /v1/users`
3. `POST /v1/users/{user_id}/api-token`
4. `POST /v1/builder/runs`
5. `POST /v1/builder/runs/{run_id}/invoke`
6. 如命中高风险领域，调用 `POST /v1/reviews/{review_id}/decide`
7. 查看 `generated_projects/` 下生成的项目

生成项目本身也会带：

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`
- `docker-compose.yml`
- `app/settings.py`
- `app/auth/policy.py`
- `app/observability/events.py`
- `app/evals/cases.py`

这部分是为了让“生成出来的项目”更像真实生产项目，而不是只生成几个 demo 文件。

## 十、常见问题

### 端口 5432 被占用

说明本机可能已经有 PostgreSQL。可以先停掉本机 PostgreSQL，或修改 `docker-compose.yml`：

```yaml
ports:
  - "15432:5432"
```

然后同步修改 `.env`：

```text
DATABASE_URL=postgresql+psycopg://agent:agent@localhost:15432/agent
```

### 端口 6379 被占用

修改 `docker-compose.yml`：

```yaml
ports:
  - "16379:6379"
```

然后同步修改 `.env`：

```text
REDIS_URL=redis://localhost:16379/0
```

### Docker 镜像下载慢

这是 Docker Hub 网络问题。可以先只验证 SQLite 快速路径：

```powershell
Remove-Item .env
uvicorn app.main:app --reload
```

没有 `.env` 时，项目默认使用本地 SQLite：

```text
app/agent_platform.db
```

### 想重置数据库

这会删除 Docker PostgreSQL 数据卷中的数据：

```powershell
docker compose down -v
docker compose up -d
```

重置后重新启动 API，应用会在启动时创建表并写入默认领域模板。

