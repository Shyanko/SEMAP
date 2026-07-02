package com.semap.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.location.LocationManager
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.time.Instant
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

data class GpsRecorderState(
    val status: String = "idle",
    val sessionId: Int? = null,
    val segment: TrackSegment? = null,
    val pendingCount: Int = 0,
    val error: String? = null,
)

object GpsRecorderStore {
    private val mutableState = MutableStateFlow(GpsRecorderState())
    val state: StateFlow<GpsRecorderState> = mutableState

    fun update(next: GpsRecorderState) {
        mutableState.value = next
    }
}

class GpsRecordingService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val api = SemapApiClient.create()
    private lateinit var locationManager: LocationManager
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var dao: PendingLocationPointDao
    private var authHeader: String? = null
    private var sessionId: Int? = null
    private var creatingSession = false

    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.locations.forEach { location ->
                scope.launch { cacheAndUpload(location) }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        locationManager = getSystemService(LocationManager::class.java)
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
        dao = SemapDatabase.get(this).pendingLocationPointDao()
        ensureNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val token = intent?.getStringExtra(EXTRA_TOKEN)
        if (token != null) {
            authHeader = "Bearer $token"
        }
        when (intent?.action) {
            ACTION_START -> startRecording()
            ACTION_PAUSE -> pauseRecording()
            ACTION_RESUME -> resumeRecording()
            ACTION_FINISH -> finishRecording()
        }
        return START_NOT_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopLocationUpdates()
        super.onDestroy()
    }

    private fun startRecording() {
        startForegroundNotification("正在启动 GPS 记录")
        val current = GpsRecorderStore.state.value
        if (creatingSession || current.status in setOf("active", "paused")) {
            sessionId = current.sessionId ?: sessionId
            updateNotification(if (current.status == "paused") "GPS 记录已暂停" else "正在记录 GPS 轨迹")
            return
        }
        if (!hasFineLocationPermission()) {
            failStart("缺少精确定位权限")
            return
        }
        if (!isSystemLocationEnabled()) {
            failStart("请开启系统定位后再开始记录")
            return
        }
        val header = authHeader ?: return failStart("缺少登录令牌")
        creatingSession = true
        GpsRecorderStore.update(GpsRecorderState(status = "starting"))
        scope.launch {
            try {
                val session = api.createLocationSession(header)
                sessionId = session.id
                GpsRecorderStore.update(
                    GpsRecorderState(
                        status = "active",
                        sessionId = session.id,
                        segment = session.segment,
                    ),
                )
                startLocationUpdates()
                updateNotification("正在记录 GPS 轨迹")
            } catch (error: Throwable) {
                failStart("GPS 会话创建失败：${error.message}")
            } finally {
                creatingSession = false
            }
        }
    }

    private fun pauseRecording() {
        val id = sessionId ?: GpsRecorderStore.state.value.sessionId ?: return
        val header = authHeader ?: return fail("缺少登录令牌")
        stopLocationUpdates()
        scope.launch {
            runCatching { api.pauseLocationSession(header, id) }
                .onSuccess {
                    updateStateFromSession(it, "paused")
                    updateNotification("GPS 记录已暂停")
                }
                .onFailure { fail("暂停失败：${it.message}") }
        }
    }

    private fun resumeRecording() {
        val id = sessionId ?: GpsRecorderStore.state.value.sessionId ?: return
        val header = authHeader ?: return fail("缺少登录令牌")
        scope.launch {
            runCatching { api.resumeLocationSession(header, id) }
                .onSuccess {
                    sessionId = it.id
                    updateStateFromSession(it, "active")
                    startLocationUpdates()
                    runCatching { uploadPending() }
                        .onFailure { fail("定位点已暂存，等待网络恢复后补传") }
                    updateNotification("正在记录 GPS 轨迹")
                }
                .onFailure { fail("继续失败：${it.message}") }
        }
    }

    private fun finishRecording() {
        val id = sessionId ?: GpsRecorderStore.state.value.sessionId ?: return
        val header = authHeader ?: return fail("缺少登录令牌")
        stopLocationUpdates()
        scope.launch {
            runCatching {
                uploadPending()
                val pendingCount = dao.countForSession(id)
                if (pendingCount > 0) {
                    error("还有 $pendingCount 个定位点未上传")
                }
                api.finishLocationSession(header, id)
            }.onSuccess {
                updateStateFromSession(it, "finished")
                ServiceCompat.stopForeground(this@GpsRecordingService, ServiceCompat.STOP_FOREGROUND_REMOVE)
                stopSelf()
            }.onFailure { fail("结束失败：${it.message}") }
        }
    }

    @SuppressLint("MissingPermission")
    private fun startLocationUpdates() {
        if (!hasFineLocationPermission()) {
            fail("缺少精确定位权限")
            return
        }
        if (!isSystemLocationEnabled()) {
            fail("请开启系统定位后再开始记录")
            return
        }
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, LOCATION_INTERVAL_MS)
            .setMinUpdateDistanceMeters(MIN_LOCATION_DISTANCE_METERS)
            .setWaitForAccurateLocation(false)
            .build()
        fusedLocationClient.requestLocationUpdates(
            request,
            locationCallback,
            Looper.getMainLooper(),
        ).addOnFailureListener {
            fail("定位启动失败：${it.message}")
        }
    }

    private fun stopLocationUpdates() {
        if (::fusedLocationClient.isInitialized) {
            fusedLocationClient.removeLocationUpdates(locationCallback)
        }
    }

    private fun isSystemLocationEnabled(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            locationManager.isLocationEnabled
        } else {
            locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER) ||
                locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
        }
    }

    private fun waitForAccurateLocation(location: Location) {
        val message = if (location.hasAccuracy()) {
            "等待高精度定位信号，当前误差约 ${location.accuracy.toInt()} 米"
        } else {
            WAITING_ACCURATE_LOCATION
        }
        val current = GpsRecorderStore.state.value
        if (current.error != message) {
            GpsRecorderStore.update(current.copy(error = message))
        }
    }

    private fun clearWaitingLocationError() {
        val current = GpsRecorderStore.state.value
        if (current.error?.startsWith(WAITING_ACCURATE_LOCATION) == true) {
            GpsRecorderStore.update(current.copy(error = null))
        }
    }

    private fun isAccurateLocation(location: Location): Boolean {
        return location.hasAccuracy() && location.accuracy <= MAX_ACCEPTED_ACCURACY_METERS
    }

    private fun isFreshLocation(location: Location): Boolean {
        val ageMillis = (SystemClock.elapsedRealtimeNanos() - location.elapsedRealtimeNanos) / 1_000_000
        return ageMillis in 0..MAX_LOCATION_AGE_MS
    }

    @Suppress("DEPRECATION")
    private fun isMockLocation(location: Location): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) location.isMock else location.isFromMockProvider
    }

    private suspend fun cacheAndUpload(location: Location) {
        if (!isAccurateLocation(location)) {
            waitForAccurateLocation(location)
            return
        }
        if (!isFreshLocation(location) || isMockLocation(location)) {
            waitForFreshLocation()
            return
        }
        clearWaitingLocationError()
        val id = sessionId ?: return
        val coordinate = mapCoordinate(location.latitude, location.longitude)
        dao.insert(
            PendingLocationPoint(
                sessionId = id,
                lat = coordinate.lat,
                lng = coordinate.lng,
                altitude = if (location.hasAltitude()) location.altitude else null,
                speed = if (location.hasSpeed()) location.speed.toDouble() else null,
                recordedAt = Instant.ofEpochMilli(location.time).toString(),
                accuracy = location.accuracy,
                provider = location.provider,
                rawLat = location.latitude,
                rawLng = location.longitude,
                coordinateSystem = coordinate.coordinateSystem,
            )
        )
        updatePendingCount(id)
        runCatching { uploadPending() }
            .onFailure { fail("定位点已暂存，等待网络恢复后补传") }
    }

    private suspend fun uploadPending() {
        val id = sessionId ?: return
        val header = authHeader ?: return
        while (true) {
            val pending = dao.pendingForSession(id, 100)
            if (pending.isEmpty()) {
                updatePendingCount(id)
                return
            }
            val response = api.uploadLocationPoints(
                header,
                id,
                LocationPointsRequest(
                    pending.map {
                        LocationPointRequest(
                            lat = it.lat,
                            lng = it.lng,
                            altitude = it.altitude,
                            speed = it.speed,
                            recordedAt = it.recordedAt,
                            accuracy = it.accuracy,
                            provider = it.provider,
                            rawLat = it.rawLat,
                            rawLng = it.rawLng,
                            coordinateSystem = it.coordinateSystem,
                        )
                    },
                ),
            )
            dao.deleteByIds(pending.map { it.id })
            updateStateFromSession(response, response.status)
        }
    }

    private suspend fun updatePendingCount(sessionId: Int) {
        val current = GpsRecorderStore.state.value
        GpsRecorderStore.update(current.copy(pendingCount = dao.countForSession(sessionId)))
    }

    private suspend fun updateStateFromSession(session: LocationSessionResponse, status: String) {
        GpsRecorderStore.update(
            GpsRecorderState(
                status = status,
                sessionId = session.id,
                segment = session.segment,
                pendingCount = dao.countForSession(session.id),
            ),
        )
    }

    private fun fail(message: String) {
        val current = GpsRecorderStore.state.value
        GpsRecorderStore.update(current.copy(error = message))
        updateNotification(message)
    }

    private fun failStart(message: String) {
        creatingSession = false
        GpsRecorderStore.update(GpsRecorderState(status = "idle", error = message))
        updateNotification(message)
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun waitForFreshLocation() {
        val current = GpsRecorderStore.state.value
        if (current.error != WAITING_FRESH_LOCATION) {
            GpsRecorderStore.update(current.copy(error = WAITING_FRESH_LOCATION))
        }
    }

    private fun hasFineLocationPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
    }

    private fun startForegroundNotification(text: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification(text),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION,
            )
        } else {
            startForeground(NOTIFICATION_ID, notification(text))
        }
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification(text))
    }

    private fun notification(text: String) = NotificationCompat.Builder(this, CHANNEL_ID)
        .setSmallIcon(android.R.drawable.ic_menu_mylocation)
        .setContentTitle("SEMAP GPS 记录")
        .setContentText(text)
        .setOngoing(true)
        .build()

    private fun ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "SEMAP GPS 记录",
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    companion object {
        private const val CHANNEL_ID = "gps_recording"
        private const val NOTIFICATION_ID = 1001
        private const val LOCATION_INTERVAL_MS = 5_000L
        private const val MIN_LOCATION_DISTANCE_METERS = 5f
        private const val MAX_LOCATION_AGE_MS = 30_000L
        private const val MAX_ACCEPTED_ACCURACY_METERS = 50f
        private const val WAITING_ACCURATE_LOCATION = "等待高精度定位信号"
        private const val WAITING_FRESH_LOCATION = "等待新的真实定位信号"
        private const val EXTRA_TOKEN = "token"
        private const val ACTION_START = "com.semap.app.gps.START"
        private const val ACTION_PAUSE = "com.semap.app.gps.PAUSE"
        private const val ACTION_RESUME = "com.semap.app.gps.RESUME"
        private const val ACTION_FINISH = "com.semap.app.gps.FINISH"

        fun startIntent(context: Context, token: String) = Intent(context, GpsRecordingService::class.java)
            .setAction(ACTION_START)
            .putExtra(EXTRA_TOKEN, token)

        fun pauseIntent(context: Context, token: String) = Intent(context, GpsRecordingService::class.java)
            .setAction(ACTION_PAUSE)
            .putExtra(EXTRA_TOKEN, token)

        fun resumeIntent(context: Context, token: String) = Intent(context, GpsRecordingService::class.java)
            .setAction(ACTION_RESUME)
            .putExtra(EXTRA_TOKEN, token)

        fun finishIntent(context: Context, token: String) = Intent(context, GpsRecordingService::class.java)
            .setAction(ACTION_FINISH)
            .putExtra(EXTRA_TOKEN, token)
    }
}

private data class Coordinate(val lat: Double, val lng: Double, val coordinateSystem: String)

private fun mapCoordinate(lat: Double, lng: Double): Coordinate {
    if (!isInMainlandChinaBounds(lat, lng)) {
        return Coordinate(lat, lng, "wgs84")
    }
    val dLat = transformLat(lng - 105.0, lat - 35.0)
    val dLng = transformLng(lng - 105.0, lat - 35.0)
    val radLat = lat / 180.0 * PI
    var magic = sin(radLat)
    magic = 1 - EE * magic * magic
    val sqrtMagic = sqrt(magic)
    val mgLat = lat + (dLat * 180.0) / ((AXIS * (1 - EE)) / (magic * sqrtMagic) * PI)
    val mgLng = lng + (dLng * 180.0) / (AXIS / sqrtMagic * cos(radLat) * PI)
    return Coordinate(mgLat, mgLng, "gcj02")
}

private fun isInMainlandChinaBounds(lat: Double, lng: Double): Boolean {
    return lng in 72.004..137.8347 && lat in 0.8293..55.8271
}

private fun transformLat(x: Double, y: Double): Double {
    var value = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * sqrt(kotlin.math.abs(x))
    value += (20.0 * sin(6.0 * x * PI) + 20.0 * sin(2.0 * x * PI)) * 2.0 / 3.0
    value += (20.0 * sin(y * PI) + 40.0 * sin(y / 3.0 * PI)) * 2.0 / 3.0
    value += (160.0 * sin(y / 12.0 * PI) + 320.0 * sin(y * PI / 30.0)) * 2.0 / 3.0
    return value
}

private fun transformLng(x: Double, y: Double): Double {
    var value = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * sqrt(kotlin.math.abs(x))
    value += (20.0 * sin(6.0 * x * PI) + 20.0 * sin(2.0 * x * PI)) * 2.0 / 3.0
    value += (20.0 * sin(x * PI) + 40.0 * sin(x / 3.0 * PI)) * 2.0 / 3.0
    value += (150.0 * sin(x / 12.0 * PI) + 300.0 * sin(x / 30.0 * PI)) * 2.0 / 3.0
    return value
}

private const val PI = 3.14159265358979324
private const val AXIS = 6378245.0
private const val EE = 0.00669342162296594323
