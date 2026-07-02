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

当前仓库已有初始提交。后端仍处于健康检查阶段，Web 前端仍处于基础框架阶段。

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

生产运行使用 systemd：

```bash
systemctl status semap-backend
systemctl restart semap-backend
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

轨迹版本规则：

- 创建轨迹不携带 `version`，服务端返回 `version=1`。
- 更新轨迹在请求体携带当前 `version`。
- 删除轨迹使用 `DELETE /api/segments/{segmentId}?version={version}`。
- 普通轨迹点不提供独立批量写入接口。
- 手动轨迹和外部导入轨迹由创建或导入接口一次性写入点位。
- GPS 点位只通过定位会话接口上传。

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
