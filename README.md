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

当前仓库已有初始提交。后端已具备健康检查、数据库迁移、账号注册登录、JWT 鉴权、当前用户接口、轨迹列表、轨迹详情、轨迹编辑、轨迹删除、用户数据隔离、版本冲突检测、航班导入、火车导入、火车站坐标库和 GPS 定位会话。航班导入会保存机型、飞机注册号、航空公司、起降地点和航空公司 logo 信息，火车导入会保存担当车型和中国铁路 logo 信息。Web 前端已具备 API 客户端、健康检查状态、登录注册、token 持久化、轨迹列表拉取、Google 和高德地图展示、轨迹点和轨迹线绘制、选中高亮、航班导入、火车导入、外部导入展示信息和 Android APK 下载入口。Android App 已具备 Compose 工程骨架、登录注册、token 持久化、网络层、轨迹列表页面、Google 和高德地图展示页面、航班导入页、火车导入页、外部导入展示信息和 GPS 轨迹记录页；地图页不显示轨迹详情卡片，地图容器占满内容区剩余空间。Web 和 Android 使用 `logos/semap-logo.png` 作为 SEMAP 品牌 logo。

健康检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
curl https://semap.xyz/api/health
```

公网入口：

```bash
https://semap.xyz/
https://semap.xyz/api/
```

`http://semap.xyz/` 会自动跳转到 `https://semap.xyz/`。

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
- 左栏入口为轨迹地图、航班导入和火车导入。
- 拉取当前用户轨迹列表。
- 使用 Google Maps JavaScript API 绘制轨迹点和轨迹线。
- 地图区域支持 Google 和高德底图切换。
- 没有轨迹时仍显示地图底图。
- 选中轨迹后高亮 Marker 和 Polyline。
- 根据选中轨迹或全部轨迹自适应地图视野。
- 航班导入会调用后端 FlightRadar24 适配器生成轨迹。
- 火车导入会先按车次和日期查询 12306 经停站，再由用户选择乘车起止站生成近似轨迹。
- 航班和火车导入卡片在工作区居中显示。
- 火车查询站点后，导入页使用工作区内部纵向滚动，导入按钮不会被大屏固定布局裁掉。
- 航班轨迹显示机型、飞机注册号、航空公司和航空公司 logo。
- 火车轨迹显示担当车型和项目本地中国铁路 logo。
- GPS 轨迹显示项目本地 road 图标，后端默认标题格式为 `定位上传 N`。
- 未选中的轨迹卡片显示一行缩略信息，选中后在卡片内展开详细信息。
- 轨迹列表右栏在宽屏两栏布局中与地图区域等高，列表内容在右栏内部滚动。
- 选中卡片显示运营方、机型或担当车型、注册号、起降地点或出发到达地点、出发时间和到达时间。
- 选中卡片右下角提供“更改”按钮，弹窗内可修改标题、起止时间、保存或删除路径。
- 轨迹卡片 logo 使用正方形容器，航司 logo 和中国铁路 logo 都按正方形图标居中显示。
- 点击轨迹列表以外的页面区域会取消选中。
- 登录页和登录后的侧栏提供 Android APK 下载入口，并提示手机端支持定位上传功能。
- APK 下载入口指向当前正式版本 `SEMAP-1.3.apk`。
- 后端健康状态显示。

当前 Web 地图代码通过 `@googlemaps/js-api-loader` 加载 Google Maps JavaScript API，通过高德 JSAPI v2 加载高德底图。构建时读取仓库根目录 `.env` 中的 `VITE_GOOGLE_MAPS_API_KEY`、`VITE_GOOGLE_MAPS_MAP_ID`、`VITE_AMAP_JS_API_KEY` 和 `VITE_AMAP_SECURITY_JS_CODE`。当前服务器已配置本机 Web key，生产使用前需要确认 Google HTTP 来源限制和高德 Web 端安全配置。

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

- `https://semap.xyz/` 服务 Web 前端静态文件。
- `https://semap.xyz/api/` 代理到后端 `127.0.0.1:8000`。
- `https://semap.xyz/health` 代理到后端健康检查。
- `http://semap.xyz/` 自动跳转到 HTTPS。

HTTPS 使用 Let's Encrypt 证书，Nginx 站点配置在 `/etc/nginx/conf.d/semap.conf`，证书路径由 Certbot 管理。当前证书域名为 `semap.xyz`，自动续期由 `certbot-renew.timer` 负责。

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
- `PATCH /api/segments/{segmentId}` 编辑标题、开始时间、结束时间和摘要。
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

外部导入接口：

- `POST /api/import/flight`：字段为 `flightNumber` 和 `date`，返回新建航班轨迹。
- `POST /api/import/train/stations`：字段为 `trainCode` 和 `date`，返回车次经停站列表。
- `POST /api/import/train`：字段为 `trainCode`、`date`、`fromStation` 和 `toStation`，返回新建火车近似轨迹。
- 导入轨迹标题由后端按航班号、车次号和乘车区间生成。
- 航班导入使用 FlightRadar24 航班摘要和机场坐标生成轨迹，当前不承诺复原历史真实飞行轨迹。
- 火车导入使用用户输入日期的 12306 经停站信息。前端和 App 先查询站点列表，再用用户选择的乘车起点和终点截取区间，所有结果设置 `isApproximate=true`。
- 火车站坐标使用 PostgreSQL `train_stations` 表。导入火车轨迹时不再实时调用 Google Geocoding。
- 起点或终点缺坐标时火车导入失败并返回中文错误；中间站缺坐标时跳过该中间站点，轨迹仍保留可用站点折线。
- 用户输入日期没有可用车次时，火车导入会自动尝试服务器当前日期起未来 7 天，并把查询到的车次和时刻映射到用户输入日期返回。
- 火车导入轨迹会保留区间内中间站坐标用于折线，地图 Marker 只显示起点和终点。
- 航班导入使用 IATA code-search 将起降 IATA 代码解析为城市和机场名，用于 `originLocation` 和 `destinationLocation` 展示。
- 航班导入使用 IATA code-search 按航班号中的航司二字码解析运营方公司名，例如 `UA` 解析为 `United Airlines Inc`。航司查询失败时返回导入错误，不写入 `UAL` 这类兜底值。
- 外部导入轨迹返回 `metadata`。航班轨迹包含 `vehicleModel`、`registration`、`operatorName`、`operatorCode`、`originLocation`、`destinationLocation`、`logoUrl` 和 `logoText`。航班 `logoUrl` 使用后端缓存代理 `/api/assets/airline-logos/{code}.png`，客户端不直接访问第三方 logo 源。火车轨迹包含 `vehicleModel`、`unitNo`、`operatorCode=12306`、`logoKind=railway_12306`、`logoUrl=/logos/China_Railways.svg` 和 `logoText=12306`。
- 外部服务失败时接口返回包含外部服务详情的中文错误，不写入轨迹数据。

火车站坐标库：

- `backend/migrations/008_train_stations.sql` 创建 `train_stations` 表。
- `backend/data/train_station_seed.csv` 保存人工确认的种子坐标。
- `backend/scripts/sync_train_stations.py` 默认只拉取 12306 `station_name.js` 全量站名并导入种子 CSV，不批量请求地图检索。
- 火车导入遇到缺失站点坐标时，后端按需调用高德 POI 搜索和百度地点检索并缓存结果。
- 高德 POI 搜索使用 `types=150200` 限定火车站类，百度地点检索请求 `gcj02ll` 坐标；两个服务都使用 12306 城市字段缩小检索范围。
- 外部检索结果必须落在中国范围内，POI 名称必须包含目标站名，标签必须是铁路相关。高德或百度任一服务返回可信结果即可使用。
- 高德和百度都未返回可信结果时保留缺坐标状态，起点或终点缺坐标会让本次导入失败，中间站缺坐标会跳过。
- 同步脚本保留 `--baidu-limit` 和 `--nominatim-limit` 作为人工维护参数，默认值为 0。
- 同步脚本运行结束会输出总站数、已覆盖坐标数、缺失数和拒绝数。

同步火车站坐标：

```bash
source /root/semap/.venv/bin/activate
cd /root/semap
python backend/scripts/sync_train_stations.py
```

GPS 会话规则：

- 开始会话时创建 `gps` 类型轨迹片段和 `active` 会话。
- 新建 GPS 轨迹标题格式为 `定位上传 N`。
- GPS 轨迹 metadata 写入 `/logos/road.png`，Web 和 Android 使用该 road 图标展示。
- Android 端开始 GPS 会话前要求精确定位权限和系统定位已开启。
- Android 端 GPS 服务使用 Google Play services 融合定位请求高精度点位，忽略无精度信息、精度误差超过 50 米、过期或模拟定位点。
- Android 端在中国大陆范围内把原始 WGS84 坐标转换为地图展示坐标后上传，同时保留原始坐标。
- 暂停状态不接收定位点。
- 继续状态重新接收定位点。
- 点位上传请求字段为 `points`，每个点包含 `lat`、`lng`、可选 `altitude`、可选 `speed`、`recordedAt`、`accuracy`、`provider`、`rawLat`、`rawLng` 和 `coordinateSystem`。
- 后端按轨迹当前最大序号追加 GPS 点位。
- 结束会话时写入轨迹结束时间并更新摘要。

## 外部服务验证

FlightRadar24 使用 Explorer 计划。当前已验证 `flight-summary/full` 和 `live/flight-positions/full` 可用于航班导入。

12306 当前验证结果：

- `https://kyfw.12306.cn/otn/queryTrainInfo/init` 可访问。
- `queryTrainInfo/query` 不能直接用用户输入的车次号稳定查询。
- 可用链路是先调用 `https://search.12306.cn/search/v1/train/search?keyword={trainCode}&date={yyyyMMdd}` 获取内部 `train_no`，再调用 `queryTrainInfo/query` 获取经停站。
- 2026-07-02 验证北京到上海方向 `G803` 可返回经停站列表。
- 2026-07-02 验证 `G803` 支持按 `廊坊` 到 `济南西` 截取乘车区间。
- 2026-07-02 验证 `G803` 站点响应包含 `station_name`、`arrive_time`、`start_time` 和 `arrive_day_diff` 字段。
- 2026-07-03 验证 `https://kyfw.12306.cn/otn/resources/js/framework/station_name.js` 可返回全量站名，当前解析得到 3375 个站。
- 12306 不是公开稳定 API，修改适配器前需要重新验证响应结构。

rail.re 当前验证结果：

- `https://api.rail.re/train/{trainCode}` 返回按时间倒序排列的担当记录数组。
- 记录字段包含 `date`、`emu_no` 和 `train_no`。
- 火车导入使用第一条记录的 `emu_no` 生成担当车型展示值，展示值为原始 `emu_no` 去掉最后四位，例如 `CR400BFB5154` 显示为 `CR400BFB`。

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
- 使用 Google Maps SDK for Android、Maps Compose 和高德地图 Android SDK 展示地图。
- 绘制轨迹点 Marker 和轨迹 Polyline。
- 选中轨迹后高亮 Marker 和 Polyline。
- 根据选中轨迹或全部轨迹自适应地图视野。
- 航班导入页调用后端导入接口生成航班轨迹。
- 火车导入页先按车次和日期查询经停站，再选择乘车起止站生成火车近似轨迹。
- 地图页不显示轨迹详情卡片，地图容器占满标题、导航和状态文本以外的剩余屏幕空间。
- 登录、航班导入、火车导入和 GPS 记录页面支持纵向滚动，内容不会被屏幕高度裁掉。
- Android 主界面避开系统状态栏和导航栏，文字不会贴到屏幕顶端。
- 轨迹列表和地图详情显示外部导入展示信息，航班轨迹通过后端缓存接口加载航空公司 logo，火车轨迹使用本地中国铁路图标，logo 加载失败时显示文字 fallback。
- GPS 记录页支持开始、暂停、继续和结束。
- GPS 记录使用 Android 前台定位服务，定位来源为 Google Play services 融合定位。
- GPS 开始记录操作在启动中、记录中和暂停状态下保持幂等，不会重复创建定位会话。
- GPS 点位只保留带精度信息且误差不超过 50 米的高精度定位点，并过滤过期点和模拟点。
- GPS 点位在中国大陆范围内上传地图展示坐标，后端 raw 字段保留原始 WGS84 坐标、精度、provider 和坐标系。
- GPS 点位先写入 Room 短时缓存，再上传到后端定位会话接口。
- 网络短时不可用时点位保留在 Room，恢复后按会话批量补传。
- Android 14+ 已声明前台定位服务类型和 `FOREGROUND_SERVICE_LOCATION` 权限。
- 当前正式 APK 已通过 Web 静态目录提供下载。

构建 Debug APK：

```bash
cd /root/semap/android
./gradlew --no-daemon :app:assembleDebug
```

构建产物：

```bash
/root/semap/android/app/build/outputs/apk/debug/app-debug.apk
```

Web 下载地址：

```bash
https://semap.xyz/downloads/SEMAP-1.3.apk
```

当前 APK 正式版本为 `1.3`，发布文件命名格式为 `SEMAP-版本号.apk`。当前包使用 `versionCode=103`、`versionName=1.3`、`minSdk=26`、`targetSdk=35`，编译环境为 Android SDK 36。Nginx 对 `.apk` 下载返回 `application/vnd.android.package-archive`。

发布 APK 校验：

```bash
AAPT=$(find "$ANDROID_HOME" -name aapt -type f | sort | tail -n 1)
"$AAPT" dump badging /var/www/semap/downloads/SEMAP-1.3.apk

APKSIGNER=$(find "$ANDROID_HOME" -name apksigner -type f | sort | tail -n 1)
"$APKSIGNER" verify --verbose --print-certs /var/www/semap/downloads/SEMAP-1.3.apk

curl -I -L https://semap.xyz/downloads/SEMAP-1.3.apk
```

默认 API 地址为 `https://semap.xyz/api/`。本地或模拟器验收时可以通过 Gradle 属性覆盖：

```bash
cd /root/semap/android
./gradlew --no-daemon :app:assembleDebug -PSEMAP_API_BASE_URL=http://10.0.2.2/api/
```

Android Google Maps key 注入顺序为 Gradle 属性 `GOOGLE_MAPS_API_KEY`、环境变量 `GOOGLE_MAPS_API_KEY`、仓库根目录 `.env` 中的 `GOOGLE_MAPS_API_KEY`。Android 高德 key 注入顺序为 Gradle 属性 `AMAP_ANDROID_API_KEY`、环境变量 `AMAP_ANDROID_API_KEY`、仓库根目录 `.env` 中的 `AMAP_ANDROID_API_KEY`，未配置时回退读取 `AMAP_MAPS_API_KEY`。Release APK 签名读取 `.env` 中的 `ANDROID_RELEASE_STORE_FILE`、`ANDROID_RELEASE_STORE_PASSWORD`、`ANDROID_RELEASE_KEY_ALIAS` 和 `ANDROID_RELEASE_KEY_PASSWORD`。构建脚本只读取密钥，不在源码和文档中写入密钥内容。

正式 APK 构建：

```bash
cd /root/semap/android
./gradlew --no-daemon --max-workers=1 :app:assembleRelease
```

当前服务器内存较小，已启用 `/swapfile-semap` 和 `/swapfile-semap-build` 作为 Android 构建 swap。Gradle 配置限制为单 worker 和较小 JVM heap。加入高德 SDK 后，release 构建前需要确认没有残留 Kotlin daemon 占用内存。

## 配置

本机配置文件：

```bash
/root/semap/.env
```

示例配置：

```bash
/root/semap/.env.example
```

密钥不写入说明文档和源码。FlightRadar24 token 只允许后端使用。Google Maps key 需要设置 Android 包名、SHA-1 或 HTTP 来源限制。Web Advanced Marker 使用 `VITE_GOOGLE_MAPS_MAP_ID`，开发环境没有 Map ID 时可临时使用 `DEMO_MAP_ID`。高德 Web 底图使用 `VITE_AMAP_JS_API_KEY` 和 `VITE_AMAP_SECURITY_JS_CODE`，Android 高德地图使用 `AMAP_ANDROID_API_KEY`。
