package com.semap.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.time.Instant

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
    private lateinit var dao: PendingLocationPointDao
    private var authHeader: String? = null
    private var sessionId: Int? = null

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) {
            scope.launch { cacheAndUpload(location) }
        }

        override fun onProviderDisabled(provider: String) = Unit
        override fun onProviderEnabled(provider: String) = Unit
        override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
    }

    override fun onCreate() {
        super.onCreate()
        locationManager = getSystemService(LocationManager::class.java)
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
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        locationManager.removeUpdates(locationListener)
        super.onDestroy()
    }

    private fun startRecording() {
        startForegroundNotification("正在启动 GPS 记录")
        val header = authHeader ?: return fail("缺少登录令牌")
        scope.launch {
            runCatching {
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
            }.onFailure { fail("GPS 会话创建失败：${it.message}") }
        }
    }

    private fun pauseRecording() {
        val id = sessionId ?: GpsRecorderStore.state.value.sessionId ?: return
        val header = authHeader ?: return fail("缺少登录令牌")
        locationManager.removeUpdates(locationListener)
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
        locationManager.removeUpdates(locationListener)
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

    private fun startLocationUpdates() {
        if (!hasLocationPermission()) {
            fail("缺少定位权限")
            return
        }
        val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .filter { locationManager.isProviderEnabled(it) }
        if (providers.isEmpty()) {
            fail("设备没有可用定位提供方")
            return
        }
        runCatching {
            for (provider in providers) {
                locationManager.requestLocationUpdates(
                    provider,
                    10_000L,
                    10f,
                    locationListener,
                    mainLooper,
                )
            }
        }.onFailure {
            fail("定位启动失败：${it.message}")
        }
    }

    private suspend fun cacheAndUpload(location: Location) {
        val id = sessionId ?: return
        dao.insert(
            PendingLocationPoint(
                sessionId = id,
                lat = location.latitude,
                lng = location.longitude,
                altitude = if (location.hasAltitude()) location.altitude else null,
                speed = if (location.hasSpeed()) location.speed.toDouble() else null,
                recordedAt = Instant.ofEpochMilli(location.time).toString(),
            ),
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

    private fun hasLocationPermission(): Boolean {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) ==
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
