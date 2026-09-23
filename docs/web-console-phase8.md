# 阶段 8：Web 控制台

## 确认项（1C 2A 3A 4A 5B 6B 7A 8C）

- JWT 登录 + API Key 自动化双轨
- Ant Design 5 + Vite + React Router
- Nginx 同源部署
- Dashboard / Events / Trace / 协查 / 防御资产 / Settings
- Event 为主，Alert 为子表
- Admin Web 编辑 system_config
- Settings 集中 manual run
- Trace：messages 聊天流 + tool_calls 侧栏

## 后端新增

- `app/services/auth.py` — JWT + bcrypt
- `app/api/deps.py` — `require_auth` / `require_admin`
- `app/console/queries.py` — dashboard / events / pending
- `app/api/routes/auth.py` / `dashboard.py` / `events.py` / `alerts.py` / `system.py` / `console.py`
- `alembic/versions/009_console_seed.py` — admin 用户

## 前端

```bash
cd web
npm install
npm run dev    # http://localhost:5173 → proxy /api
npm run build  # dist → nginx root
```

## 登录

- 默认：`admin` / `changeme`（`ADMIN_INITIAL_PASSWORD`）
- 或使用 `X-API-Key` 调用原有 API

## 部署

见 `deploy/nginx.ma-minsight.conf.example`
