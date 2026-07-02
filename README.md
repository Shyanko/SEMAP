# SEMAP 项目说明

SEMAP 是 Web 前端 + Android App + 云端后端的移动轨迹记录与地图展示系统。

当前服务器承担两个角色：

1. 后端运行服务器。
2. 后端和 Android App 编码环境。

## 当前状态

已安装并启用：

- Python 3.11
- FastAPI 运行环境
- PostgreSQL 13
- Nginx
- Java 17
- Android SDK command line tools
- Android platform-tools
- Android SDK Platform 35
- Android Build Tools 35.0.0
- Node.js 20
- Git
- React + TypeScript + Vite Web 前端工程

已运行服务：

- `postgresql`
- `nginx`
- `semap-backend`

当前仓库已有初始提交。后端已具备健康检查、数据库迁移、账号注册登录、JWT 鉴权、当前用户接口、轨迹列表、轨迹详情、轨迹编辑、轨迹删除、用户数据隔离和版本冲突检测。Web 前端仍处于基础框架阶段。

健康检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
```

## 目录

- `AGENTS.md`：确定性交付计划和 agent 工作规则。
- `backend/`：FastAPI 后端。
- `frontend/`：React + TypeScript Web 前端。
- `api/`：本机 API 配置信息。
- `doc/实现日志.md`：非正式中文实现日志。
- `.env.example`：环境变量示例。

## 后端本地运行

```bash
source /root/semap/.venv/bin/activate
cd /root/semap/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

数据库迁移：

```bash
source /root/semap/.venv/bin/activate
cd /root/semap/backend
python -m app.migrate
```

生产运行使用 systemd：

```bash
systemctl status semap-backend
systemctl restart semap-backend
```

后端测试：

```bash
source /root/semap/.venv/bin/activate
cd /root/semap/backend
python -m pytest -q
```

## Web 前端

本地开发：

```bash
cd /root/semap/frontend
npm install
npm run dev
```

生产构建：

```bash
cd /root/semap/frontend
npm run build
```

部署目录：

```bash
/var/www/semap
```

Nginx 当前规则：

- `/` 服务 Web 前端静态文件。
- `/api/` 代理到后端 `127.0.0.1:8000`。
- `/health` 代理到后端健康检查。

公网登录和 JWT 传输需要 HTTPS。账号体系进入公网验收前需要完成 TLS 配置。

## 后端接口约束

账号接口：

- `POST /api/auth/register`：注册账号，字段为 `username` 和 `password`。
- `POST /api/auth/login`：登录账号，返回 `accessToken` 和 `tokenType=bearer`。
- `GET /api/auth/me`：读取当前用户，使用 `Authorization: Bearer <token>`。

账号数据规则：

- 用户名长度为 3 到 64。
- 密码长度为 8 到 128。
- 密码只保存 Argon2 哈希。
- JWT 有效期为 7 天。

轨迹版本规则：

- `GET /api/segments` 返回当前用户的轨迹列表，包含点位数组。
- `GET /api/segments/{segmentId}` 返回当前用户的单条轨迹和点位。
- `PATCH /api/segments/{segmentId}` 编辑标题、开始时间、结束时间、摘要和备注。
- `DELETE /api/segments/{segmentId}?version={version}` 删除轨迹。
- 普通轨迹片段不提供通用创建接口。
- 航班导入、火车导入和 GPS 会话负责创建轨迹。
- 新轨迹由对应创建流程返回 `version=1`。
- 更新轨迹在请求体携带当前 `version`。
- 删除轨迹使用 `DELETE /api/segments/{segmentId}?version={version}`。
- 普通轨迹点不提供独立批量写入接口。
- 外部导入轨迹由导入接口一次性写入点位。
- GPS 点位只通过定位会话接口上传。
- 版本不一致时返回 `409` 和中文错误。
- 访问其他用户轨迹时返回 `404`。

GPS 会话规则：

- 开始会话时创建 `gps` 类型轨迹片段和 `active` 会话。
- 暂停状态不接收定位点。
- 结束会话时写入轨迹结束时间并更新摘要。

## 外部服务验证

FlightRadar24 使用 Explorer 计划。开发航班导入前需要先验证当前 token 可访问的接口范围。

12306 当前验证结果：

- `https://kyfw.12306.cn/otn/queryTrainInfo/init` 可访问。
- `queryTrainInfo/query` 不能直接用用户输入的车次号稳定查询。
- 可用链路是先调用 `https://search.12306.cn/search/v1/train/search?keyword={trainCode}&date={yyyyMMdd}` 获取内部 `train_no`，再调用 `queryTrainInfo/query` 获取经停站。
- 2026-07-02 验证北京到上海方向 `G803` 可返回经停站列表。
- 12306 不是公开稳定 API，修改适配器前需要重新验证响应结构。

## Android 环境

系统环境变量文件：

```bash
/etc/profile.d/semap-android.sh
```

加载后可使用：

```bash
sdkmanager --list
adb version
```

## 配置

本机配置文件：

```bash
/root/semap/.env
```

示例配置：

```bash
/root/semap/.env.example
```

密钥不写入说明文档和源码。FlightRadar24 token 只允许后端使用。Google Maps key 需要设置 Android 包名、SHA-1 或 HTTP 来源限制。
