# SEMAP agent 工作手册

## 1. 项目定义

SEMAP 是一个 Web 前端 + Android App + 云端后端的移动轨迹记录与地图展示系统。

系统由四部分组成：

1. Web 前端：用户登录、查看地图、上传航班号、上传车次号、查看和管理轨迹。
2. Android App：用户登录、查看地图、上传航班号、上传车次号、记录 GPS 轨迹、编辑和删除轨迹。
3. 后端 API：账号鉴权、轨迹数据存储、外部交通信息解析、移动端定位点接收、并发冲突检测。
4. PostgreSQL 数据库：保存账号、轨迹片段、轨迹点、定位会话和外部导入记录。

首版必须在当前公网服务器上运行后端和 Web 前端。Android App 通过公网 API 访问后端。公网账号登录和令牌传输必须使用 HTTPS。

## 2. 确定性交付范围

### 2.1 Web 前端

必须交付可公网访问的 Web 前端。

技术栈固定为：

- React
- TypeScript
- Vite
- Google Maps JavaScript API
- Fetch API
- Nginx 静态文件服务

Web 前端必须包含以下页面：

1. 登录页。
2. 注册页。
3. 轨迹地图页。
4. 轨迹列表页。
5. 航班号导入面板。
6. 火车车次导入面板。
7. 轨迹详情面板。

Web 前端必须包含以下能力：

1. 用户注册登录。
2. 保存登录令牌。
3. 拉取当前用户的轨迹列表。
4. 在 Google 地图上绘制轨迹点和轨迹线。
5. 选中轨迹后高亮显示。
6. 输入航班号生成航班轨迹。
7. 输入车次号、日期和乘车起止站生成火车近似轨迹。
8. 查看轨迹详情，详细卡片显示运营方、机型或担当车型、注册号、起降地点或出发到达地点、出发时间和到达时间。
9. 选中轨迹的详细卡片右下角提供“更改”入口，通过弹窗修改标题、起止时间或删除路径。
10. 提供 Android APK 下载入口。

Web 前端不负责 GPS 后台定位记录。GPS 记录由 Android App 交付。

Web 前端视觉约束：

1. 卡片、面板和表单容器默认使用白底。
2. 尽量用细边框、留白和文字层级区分区域。
3. 少用大面积色块填充，选中状态优先使用边框、左侧强调线和文字颜色。
4. 主要操作按钮可以使用品牌色，普通卡片不使用浅色背景作为默认状态。

### 2.2 Android App

必须交付原生 Android App。

技术栈固定为：

- Kotlin
- Jetpack Compose
- Android Gradle Plugin
- Retrofit + OkHttp
- Kotlinx Serialization
- Google Maps SDK for Android
- Room 仅用于短时离线缓存定位点

App 必须包含以下页面：

1. 登录页。
2. 注册页。
3. 轨迹列表页。
4. 地图页。
5. 航班号导入页。
6. 火车车次导入页。
7. GPS 轨迹记录页。
8. 轨迹详情页。

App 必须包含以下能力：

1. 用户注册登录。
2. 保存登录令牌。
3. 拉取当前用户的轨迹列表。
4. 在 Google 地图上绘制轨迹点和轨迹线。
5. 选中轨迹后高亮显示。
6. 输入航班号生成航班轨迹。
7. 输入车次号、日期和乘车起止站生成火车近似轨迹。
8. 开始、暂停、继续、结束 GPS 记录。
9. 网络短时不可用时缓存定位点。
10. 恢复网络后补传定位点。
11. 查看轨迹详情。
12. 地图页、导入页和 GPS 记录页在小屏幕上必须可纵向滚动。

Android 版本规则：

1. 当前第一个正式 APK 版本为 `1.0`。
2. 发布到 Web 下载入口的 APK 文件命名为 `SEMAP-版本号.apk`。
3. Gradle `versionName` 和发布文件名必须同步更新。

### 2.3 后端 API

技术栈固定为：

- Python 3.11
- FastAPI
- Uvicorn
- PostgreSQL
- psycopg
- systemd
- Nginx 反向代理

后端必须包含以下能力：

1. 账号注册。
2. 账号登录。
3. JWT 鉴权。
4. 用户数据隔离。
5. 轨迹片段读取、编辑和删除。
6. 外部导入轨迹和 GPS 轨迹的点位写入。
7. 航班号解析。
8. 火车车次解析。
9. GPS 定位会话管理。
10. 写操作版本冲突检测。
11. 中文错误响应。
12. 健康检查接口。

### 2.4 外部服务

航班信息固定使用 FlightRadar24 API。当前账号计划为 Explorer，开发航班导入前必须先验证当前 token 可用的接口权限。

地图能力固定使用 Google Maps：

- Web 前端使用 Google Maps JavaScript API。
- Android App 使用 Google Maps SDK for Android。
- 后端火车站坐标不在导入请求中实时调用地图解析服务。

火车车次信息固定使用 12306：

- 查询入口：`https://kyfw.12306.cn/otn/queryTrainInfo/init`
- 查询日期：用户输入日期。
- 语义：使用指定日期车次信息和用户乘车起止站近似生成轨迹。
- 兜底：用户输入日期没有车次时，后端自动枚举服务器当前日期起未来 7 天，使用第一组可用车次和时刻信息。
- 返回：兜底查询不提示用户，摘要和点位日期仍使用用户输入日期。
- 标记：所有 12306 生成的轨迹都设置 `isApproximate=true`。
- 解析方式：先用 `https://search.12306.cn/search/v1/train/search` 按 `trainCode` 和 `yyyyMMdd` 日期获取内部 `train_no`，再用 `queryTrainInfo/query` 获取经停站。
- 坐标生成：后端读取 PostgreSQL `train_stations` 坐标库，不在火车导入请求中实时调用 Google Geocoding。
- 坐标同步：使用 `backend/scripts/sync_train_stations.py` 拉取 12306 全量站名并导入种子 CSV，默认不批量请求地图检索。
- 坐标按需补全：火车导入遇到缺失站点坐标时，后端按需调用高德 POI 搜索和百度地点检索并缓存结果。
- 坐标校验：外部检索结果必须落在中国范围内，POI 名称必须包含目标站名，标签必须是铁路相关；高德和百度都使用 GCJ-02 坐标。
- 缺失处理：火车导入时起点或终点缺坐标必须失败；中间站缺坐标不阻断导入，只跳过该中间站点。
- 稳定性：12306 不是公开稳定 API，每次修改适配器前必须现场验证响应结构。

### 2.5 不交付内容

首版不做以下内容：

1. iOS App。
2. 社交分享。
3. 公开社区。
4. 商业计费。
5. 后台管理系统。
6. 历史航班真实轨迹复原承诺。
7. 历史铁路真实轨迹复原承诺。

## 3. 当前服务器部署状态

当前服务器作为 SEMAP 后端运行环境和编码环境。

已确定组件：

- 操作系统：Alibaba Cloud Linux 3。
- 后端运行时：Python 3.11。
- 后端框架：FastAPI。
- Web 前端：React + TypeScript + Vite。
- 数据库：PostgreSQL 13。
- 反向代理：Nginx。
- Android 构建基础：Java 17 + Android SDK command line tools + Gradle 9.6.1。
- Node.js：用于后续文档工具或辅助脚本。

已启用服务：

- `postgresql`
- `nginx`
- `semap-backend`

服务入口：

- 后端本机端口：`127.0.0.1:8000`
- 公网 Web 入口：Nginx `80` 端口静态文件服务
- 公网 API 入口：Nginx `/api/` 反向代理到后端
- 健康检查：`GET /health`
- API 健康检查：`GET /api/health`

## 4. 环境变量

本机运行配置文件为 `/root/semap/.env`，示例文件为 `/root/semap/.env.example`。

必须使用的变量：

- `SEMAP_HOST`
- `SEMAP_PORT`
- `DATABASE_URL`
- `JWT_SECRET`
- `FR24_API_TOKEN`
- `GOOGLE_MAPS_API_KEY`
- `BAIDU_MAPS_API_KEY`
- `AMAP_MAPS_API_KEY`
- `VITE_API_BASE_URL`
- `VITE_GOOGLE_MAPS_API_KEY`
- `VITE_GOOGLE_MAPS_MAP_ID`
- `ANDROID_HOME`

约束：

1. 密钥不写入 README、AGENTS、代码注释和提交说明。
2. FlightRadar24 token 只允许后端使用。
3. Web Google Maps key 必须设置 HTTP 来源限制。
4. Android Google Maps key 必须设置应用包名和 SHA-1 限制。
5. Android App 和 Web 前端都不保存 FlightRadar24 token。

## 5. 数据模型

### 5.1 accounts

- `id`
- `username`
- `password_hash`
- `created_at`
- `updated_at`

### 5.2 track_segments

- `id`
- `account_id`
- `title`
- `source_type`: `flight`、`train`、`gps`
- `transport_type`: `flight`、`train`、`walk`、`car`、`other`
- `external_code`
- `started_at`
- `ended_at`
- `summary`
- `is_approximate`
- `metadata`: 外部导入展示信息和 logo 信息
- `version`
- `created_at`
- `updated_at`

### 5.3 track_points

- `id`
- `segment_id`
- `sequence`
- `lat`
- `lng`
- `altitude`
- `speed`
- `recorded_at`
- `name`
- `raw`

### 5.4 location_sessions

- `id`
- `account_id`
- `segment_id`
- `status`: `active`、`paused`、`finished`
- `started_at`
- `ended_at`
- `created_at`
- `updated_at`

### 5.5 import_records

- `id`
- `account_id`
- `segment_id`
- `source_type`: `flight`、`train`
- `external_code`
- `request_payload`
- `response_payload`
- `status`
- `created_at`

### 5.6 train_stations

- `id`
- `name`
- `telecode`
- `pinyin`
- `short_pinyin`
- `sequence_no`
- `city`
- `lat`
- `lng`
- `coordinate_source`
- `coordinate_status`: `missing`、`verified`、`rejected`
- `coordinate_query`
- `coordinate_raw`
- `created_at`
- `updated_at`

## 6. 后端接口

### 6.1 健康检查

- `GET /health`
- `GET /api/health`

返回后端和数据库状态。

### 6.2 账号

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

登录返回 JWT。App 后续请求使用 `Authorization: Bearer <token>`。

### 6.3 轨迹

- `GET /api/segments`
- `GET /api/segments/{segmentId}`
- `PATCH /api/segments/{segmentId}`
- `DELETE /api/segments/{segmentId}?version={version}`

版本规则：

1. 普通轨迹片段不提供通用创建接口。
2. 航班导入、火车导入和 GPS 会话负责创建轨迹。
3. `PATCH /api/segments/{segmentId}` 必须在请求体携带当前 `version`。
4. `DELETE /api/segments/{segmentId}` 必须在 query 参数携带当前 `version`。
5. 版本不一致时返回 `409`。
6. 普通轨迹点不提供独立批量写入接口。外部导入轨迹由导入接口一次性写入点位，GPS 点位由定位会话接口写入。

### 6.4 航班导入

- `POST /api/import/flight`

请求字段：

- `flightNumber`
- `date`

处理规则：

1. 后端调用 FlightRadar24 API。
2. 优先使用 API 返回的轨迹点。
3. 没有轨迹点时使用起飞机场和降落机场坐标生成近似轨迹。
4. 外部服务失败时不写入轨迹。
5. 标题由后端按航班号生成。
6. `metadata` 写入机型、飞机注册号、航空公司、起飞地点、降落地点、后端航司 logo URL 和文字 fallback。
7. 航司 logo 由后端通过 `/api/assets/airline-logos/{code}.png` 获取并缓存，客户端不直接访问第三方 logo 源。
8. 航空公司使用 IATA code-search 按航班号中的航司二字码解析公司名，查询失败时返回导入错误，不写入运营方兜底值。
9. 起飞地点和降落地点使用 IATA code-search 将 IATA 代码解析为城市和机场名。
10. 返回生成的 `TrackSegment`。

### 6.5 火车导入

- `POST /api/import/train`

请求字段：

- `trainCode`
- `date`
- `fromStation`
- `toStation`

处理规则：

1. 后端使用用户输入日期查询 12306。
2. 用户输入日期没有可用车次时，自动尝试服务器当前日期起未来 7 天。
3. 先通过 `https://search.12306.cn/search/v1/train/search` 获取内部 `train_no`。
4. 精确匹配 `station_train_code` 等于用户输入车次号的结果。
5. 再通过 `queryTrainInfo/query` 获取车次经停站。
6. 使用用户乘车起点和终点截取经停站列表。
7. 将截取区间内站点转换成坐标。
8. 按站点顺序生成轨迹点。
9. 只有起点和终点保留 `name`，中间站不在地图上显示 Marker。
10. 标题由后端按车次和乘车区间生成。
11. 通过 `https://api.rail.re/train/{trainCode}` 读取第一条担当记录，使用原始 `emu_no` 去掉最后四位作为担当车型展示值。
12. `metadata` 写入担当车型和项目本地中国铁路 logo URL，不写入中国铁路运营方。
13. 设置 `isApproximate=true`。
14. 摘要中写明按用户输入日期和乘车区间近似生成。

### 6.6 GPS 定位会话

- `POST /api/location-sessions`
- `POST /api/location-sessions/{sessionId}/points`
- `PATCH /api/location-sessions/{sessionId}/pause`
- `PATCH /api/location-sessions/{sessionId}/resume`
- `PATCH /api/location-sessions/{sessionId}/finish`

会话生命周期：

1. 开始会话时创建 `gps` 类型轨迹片段和 `active` 会话。
2. GPS 轨迹标题按当前用户已有 GPS 轨迹数量生成，格式为 `定位上传 N`。
3. GPS 轨迹 metadata 写入 `logoKind=gps_road` 和 `/logos/road.png`。
4. 会话点位只允许通过定位会话接口上传。
5. Android 开始记录前必须具备精确定位权限并确认系统定位已开启。
6. Android 使用 Google Play services 融合定位请求高精度点位，只上传带精度信息且误差不超过 50 米、未过期、非模拟的定位点。
7. Android 在中国大陆范围内将原始 WGS84 坐标转换为地图展示坐标后上传，同时保留原始坐标。
8. Android 启动中、记录中和暂停状态下重复点击开始记录不得创建新会话。
9. 暂停时会话状态改为 `paused`，不接收定位点。
10. 继续时会话状态改为 `active`。
11. 点位请求体为 `points` 数组，每个点包含 `lat`、`lng`、可选 `altitude`、可选 `speed`、`recordedAt`、`accuracy`、`provider`、`rawLat`、`rawLng` 和 `coordinateSystem`。
12. 后端按轨迹当前最大序号追加 GPS 点位，并把精度、provider、原始坐标和坐标系写入点位 raw 字段。
13. 结束时会话状态改为 `finished`，轨迹片段写入结束时间并更新摘要。

## 7. 实施顺序

### 阶段 1：服务器基础环境

状态：已完成。

交付内容：

1. Python 3.11。
2. PostgreSQL。
3. Nginx。
4. Java 17。
5. Android SDK。
6. FastAPI 最小健康检查服务。
7. systemd 后端服务。

验收：

- `curl http://127.0.0.1:8000/health` 返回数据库正常。
- `curl http://127.0.0.1/health` 返回数据库正常。

### 阶段 2：后端数据模型和账号

交付内容：

1. 精简 SQL 迁移脚本和迁移执行命令。
2. 账号注册登录。
3. JWT 鉴权。
4. 当前用户接口。
5. 密码哈希。
6. 公网 HTTPS 入口。

验收：

- 能注册账号。
- 能登录获取 token。
- 未登录不能访问受保护接口。

### 阶段 3：轨迹基础能力

交付内容：

1. 轨迹片段读取、编辑和删除。
2. 轨迹点随轨迹片段返回。
3. 用户数据隔离。
4. `version` 冲突检测。

验收：

- 用户只能看到自己的轨迹。
- 并发更新同一条轨迹时返回 `409`。

### 阶段 4：Web 前端基础框架

状态：已完成。

交付内容：

1. React + TypeScript + Vite 项目骨架。
2. API 客户端。
3. 健康检查页面。
4. 登录注册视图框架。
5. 轨迹地图和轨迹列表布局。
6. Nginx 静态文件部署。

验收：

- `npm run build` 成功。
- 浏览器访问服务器 80 端口能看到 Web 前端。
- Web 前端能访问 `/api/health`。

### 阶段 5：Web 地图展示

状态：已完成。

交付内容：

1. Web Google Maps JavaScript API。
2. 轨迹点 Marker。
3. 轨迹 Polyline。
4. 选中高亮。
5. 地图视野自适应。

验收：

- Web 能展示用户轨迹。
- 选中轨迹后地图高亮。

### 阶段 6：Android App 基础框架

状态：已完成。

交付内容：

1. Android 项目骨架。
2. Kotlin + Compose。
3. 网络层。
4. 登录注册页面。
5. token 本地保存。
6. 轨迹列表页面。

验收：

- App 能登录服务器。
- App 能拉取轨迹列表。

### 阶段 7：Android 地图展示

状态：已完成。

交付内容：

1. Android Google Maps SDK for Android。
3. 轨迹点 Marker。
4. 轨迹 Polyline。
5. 选中高亮。
6. 地图视野自适应。

验收：

- Android 能展示用户轨迹。
- 选中轨迹后地图高亮。

### 阶段 8：航班和火车导入

状态：已完成。

交付内容：

1. FlightRadar24 后端适配器。
2. 12306 后端适配器。
3. 站点坐标解析。
4. Web 航班导入面板。
5. Web 火车导入面板。
6. App 航班导入页。
7. App 火车导入页。

验收：

- 输入有效航班号能生成轨迹。
- 输入有效车次号能生成近似轨迹。
- 外部 API 失败时返回中文错误且不写入错误数据。

### 阶段 9：GPS 轨迹记录

状态：代码已完成，待真机 GPS 验收。

交付内容：

1. Android 定位权限。
2. 开始、暂停、继续、结束。
3. 定位点上传。
4. Room 短时离线缓存。
5. 后端会话管理。
6. Web Android APK 下载入口。
7. GPS 轨迹使用 road 图标和 `定位上传 N` 标题。
8. Android GPS 记录使用融合定位的高精度点，重复开始不会创建多个会话。
9. Android GPS 点位上传时保留精度、provider、原始坐标和坐标系。

验收：

- 手机能记录真实定位点。
- 网络恢复后能补传缓存点。
- 结束后地图显示本次轨迹。
- Web 登录页和侧栏能下载当前 Debug APK。

### 阶段 10：交付测试

交付内容：

1. 后端接口测试。
2. Web 关键流程测试。
3. Android 关键流程测试。
4. 部署说明。
5. 演示账号。
6. 演示脚本。

验收：

- 后端服务重启后可恢复。
- Web 前端可公网访问。
- App 可安装并完成完整演示流程。

## 8. 测试要求

后端必须测试：

1. 健康检查。
2. 注册登录。
3. 鉴权失败。
4. 用户数据隔离。
5. 轨迹读取、编辑和删除。
6. 版本冲突。
7. 航班导入成功和失败。
8. 火车导入成功和失败。
9. GPS 会话完整流程。

Android 必须测试：

1. 登录注册。
2. token 持久化。
3. 轨迹列表。
4. 地图绘制。
5. 航班导入。
6. 火车导入。
7. GPS 权限拒绝。
8. GPS 正常记录。
9. 网络失败提示。

Web 必须测试：

1. 健康检查状态。
2. 登录注册。
3. token 持久化。
4. 轨迹列表。
5. 地图绘制。
6. 航班导入。
7. 火车导入。
8. 轨迹详情展示。
9. 网络失败提示。

## 9. 协作规则

1. 开始新任务前先读 `AGENTS.md`、`README.md`、`doc/实现日志.md` 和相关源码。
2. 每次改动后更新中文 README 和实现日志。
3. 说明文档描述当前状态。
4. 开发过程、失败尝试和取舍写入实现日志。
5. 不保留过期路径代码。
6. 不添加当前交付范围之外的功能。
7. 删除文件前先确认用途并说明原因。
8. 外部 API 行为变化时先验证，再修改适配器。
9. 密钥只放在本机环境变量或受控部署配置中。
