# SEMAP 项目说明

SEMAP 是 Web 前端 + Android App + 云端后端的移动轨迹记录与地图展示系统。

## 目录

- `AGENTS.md`：确定性交付计划和 agent 工作规则。
- `backend/`：FastAPI 后端。
- `frontend/`：React + TypeScript Web 前端。
- `android/`：Kotlin + Jetpack Compose Android App。
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

## 后端接口约束

账号接口：

- `POST /api/auth/register`：注册账号，字段为 `username` 和 `password`。
- `POST /api/auth/login`：登录账号，返回 `accessToken` 和 `tokenType=bearer`。
- `GET /api/auth/me`：读取当前用户，使用 `Authorization: Bearer <token>`。

轨迹版本规则：

- `GET /api/segments` 返回当前用户的轨迹列表，包含点位数组。
- `GET /api/segments/{segmentId}` 返回当前用户的单条轨迹和点位。
- `PATCH /api/segments/{segmentId}` 编辑标题、开始时间、结束时间和摘要。
- `DELETE /api/segments/{segmentId}?version={version}` 删除轨迹。

外部导入接口：

- `POST /api/import/flight`：字段为 `flightNumber` 和 `date`，返回新建航班轨迹。
- `POST /api/import/train/stations`：字段为 `trainCode` 和 `date`，返回车次经停站列表。
- `POST /api/import/train`：字段为 `trainCode`、`date`、`fromStation` 和 `toStation`，返回新建火车近似轨迹。

同步火车站坐标：

```bash
source /root/semap/.venv/bin/activate
cd /root/semap
python backend/scripts/sync_train_stations.py
```

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

构建 Debug APK：

```bash
cd /root/semap/android
./gradlew --no-daemon :app:assembleDebug
```

当前 APK 正式版本为 `1.4`

发布 APK 校验：

```bash
AAPT=$(find "$ANDROID_HOME" -name aapt -type f | sort | tail -n 1)
"$AAPT" dump badging /var/www/semap/downloads/SEMAP-1.4.apk

APKSIGNER=$(find "$ANDROID_HOME" -name apksigner -type f | sort | tail -n 1)
"$APKSIGNER" verify --verbose --print-certs /var/www/semap/downloads/SEMAP-1.4.apk

curl -I -L https://semap.xyz/downloads/SEMAP-1.4.apk
```

正式 APK 构建：

```bash
cd /root/semap/android
./gradlew --no-daemon --max-workers=1 :app:assembleRelease
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

