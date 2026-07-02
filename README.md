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
- Android SDK Platform 36
- Android Build Tools 36.0.0
- Gradle 9.6.1
- Node.js 20
- Git
- React + TypeScript + Vite Web 前端工程
- Kotlin + Jetpack Compose Android 工程

已运行服务：

- `postgresql`
- `nginx`
- `semap-backend`

当前仓库已有初始提交。后端已具备健康检查、数据库迁移、账号注册登录、JWT 鉴权、当前用户接口、轨迹列表、轨迹详情、轨迹编辑、轨迹删除、用户数据隔离和版本冲突检测。Web 前端已具备 API 客户端、健康检查状态、登录注册、token 持久化、轨迹列表拉取、Google Maps 地图代码接入、轨迹点和轨迹线绘制逻辑、选中高亮、导入面板框架和轨迹详情编辑面板。Android App 已具备 Compose 工程骨架、登录注册、token 持久化、网络层、轨迹列表页面和 Google 地图展示页面。

健康检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
```

## 目录

- `AGENTS.md`：确定性交付计划和 agent 工作规则。
- `backend/`：FastAPI 后端。
- `frontend/`：React + TypeScript Web 前端。
- `android/`：Kotlin + Jetpack Compose Android App。
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

当前 Web 前端能力：

- 登录和注册。
- 登录 token 保存到浏览器本地存储。
- 页面刷新后自动读取当前用户。
- 拉取当前用户轨迹列表。
- 使用 Google Maps JavaScript API 绘制轨迹点和轨迹线。
- 没有轨迹时仍显示 Google 地图底图。
- 选中轨迹后高亮 Marker 和 Polyline。
- 根据选中轨迹或全部轨迹自适应地图视野。
- 航班导入和火车导入面板框架。
- 轨迹详情编辑和删除。
- 后端健康状态显示。

当前 Web 地图代码通过 `@googlemaps/js-api-loader` 加载 Google Maps JavaScript API。构建时读取仓库根目录 `.env` 中的 `VITE_GOOGLE_MAPS_API_KEY` 和 `VITE_GOOGLE_MAPS_MAP_ID`。当前服务器已配置本机 Web key，生产使用前需要确认 HTTP 来源限制。

当前 Web 视觉规则：

- 卡片、面板和表单容器默认白底。
- 区域层级主要通过细边框、留白和文字层级表达。
- 少用大面积色块填充。
- 选中状态优先使用边框和左侧强调线。

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

浏览器截图验证：

```bash
cd /root/semap/frontend
npx playwright --version
```

当前服务器已安装 Playwright Chromium 和 Noto Sans CJK 字体，可用于中文页面截图验证。

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

## Android App

当前 Android App 能力：

- Kotlin + Jetpack Compose 工程骨架。
- Retrofit + OkHttp 网络层。
- Kotlinx Serialization JSON 解析。
- 登录和注册。
- 登录 token 使用 DataStore 持久化。
- 启动后读取 token 并恢复登录状态。
- 拉取当前用户轨迹列表。
- 使用 Google Maps SDK for Android 和 Maps Compose 展示地图。
- 绘制轨迹点 Marker 和轨迹 Polyline。
- 选中轨迹后高亮 Marker 和 Polyline。
- 根据选中轨迹或全部轨迹自适应地图视野。
- Room 留到 GPS 离线缓存阶段引入。

构建 Debug APK：

```bash
cd /root/semap/android
./gradlew --no-daemon :app:assembleDebug
```

构建产物：

```bash
/root/semap/android/app/build/outputs/apk/debug/app-debug.apk
```

默认 API 地址为 Android 模拟器访问宿主机的 `http://10.0.2.2/api/`。Android 当前只对 `10.0.2.2` 允许明文 HTTP，真机或公网验收时通过 Gradle 属性指定 HTTPS 公网 API：

```bash
cd /root/semap/android
./gradlew --no-daemon :app:assembleDebug -PSEMAP_API_BASE_URL=https://你的域名/api/
```

Android Google Maps key 注入顺序为 Gradle 属性 `GOOGLE_MAPS_API_KEY`、环境变量 `GOOGLE_MAPS_API_KEY`、仓库根目录 `.env` 中的 `GOOGLE_MAPS_API_KEY`。构建脚本只读取密钥，不在源码和文档中写入密钥内容。

当前服务器内存较小，已启用 `/swapfile-semap` 作为 Android 构建 swap。Gradle 配置限制为单 worker 和较小 JVM heap。

## 配置

本机配置文件：

```bash
/root/semap/.env
```

示例配置：

```bash
/root/semap/.env.example
```

密钥不写入说明文档和源码。FlightRadar24 token 只允许后端使用。Google Maps key 需要设置 Android 包名、SHA-1 或 HTTP 来源限制。Web Advanced Marker 使用 `VITE_GOOGLE_MAPS_MAP_ID`，开发环境没有 Map ID 时可临时使用 `DEMO_MAP_ID`。
