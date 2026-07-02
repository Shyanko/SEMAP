package com.semap.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.google.android.gms.maps.CameraUpdateFactory
import com.google.android.gms.maps.model.CameraPosition
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.maps.android.compose.GoogleMap
import com.google.maps.android.compose.MapUiSettings
import com.google.maps.android.compose.Marker
import com.google.maps.android.compose.MarkerState
import com.google.maps.android.compose.Polyline
import com.google.maps.android.compose.rememberCameraPositionState
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val DefaultCenter = LatLng(35.8617, 104.1954)

class MainActivity : ComponentActivity() {
    private val viewModel by viewModels<SemapViewModel>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SemapTheme {
                SemapApp(viewModel)
            }
        }
    }
}

@Composable
private fun SemapTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = MaterialTheme.colorScheme.copy(
            primary = Brand,
            background = Page,
            surface = Color.White,
        ),
        content = content,
    )
}

@Composable
private fun SemapApp(viewModel: SemapViewModel) {
    val state = viewModel.state

    LaunchedEffect(Unit) {
        viewModel.restoreSession()
    }

    Surface(
        modifier = Modifier
            .fillMaxSize()
            .background(Page),
        color = Page,
    ) {
        when {
            state.booting -> CenterStatus("正在读取登录状态")
            state.account == null -> AuthScreen(
                busy = state.busy,
                error = state.error,
                onLogin = viewModel::login,
                onRegister = viewModel::register,
            )
            else -> MainScreen(
                state = state,
                onRefresh = viewModel::loadSegments,
                onLogout = viewModel::logout,
                onSelectSegment = viewModel::selectSegment,
                onShowMap = viewModel::showMap,
                onShowList = viewModel::showList,
                onShowFlightImport = viewModel::showFlightImport,
                onShowTrainImport = viewModel::showTrainImport,
                onImportFlight = viewModel::importFlight,
                onImportTrain = viewModel::importTrain,
            )
        }
    }
}

@Composable
private fun AuthScreen(
    busy: Boolean,
    error: String?,
    onLogin: (String, String) -> Unit,
    onRegister: (String, String) -> Unit,
) {
    var registerMode by remember { mutableStateOf(false) }
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Panel {
            BrandHeader()
            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ModeButton("登录", !registerMode) { registerMode = false }
                ModeButton("注册", registerMode) { registerMode = true }
            }
            Spacer(Modifier.height(14.dp))
            OutlinedTextField(
                value = username,
                onValueChange = { username = it },
                label = { Text("用户名") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("密码") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
            )
            if (error != null) {
                Spacer(Modifier.height(10.dp))
                Text(error, color = Danger, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(16.dp))
            Button(
                enabled = !busy,
                onClick = {
                    if (registerMode) {
                        onRegister(username, password)
                    } else {
                        onLogin(username, password)
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = Brand),
            ) {
                Text(if (busy) "提交中" else if (registerMode) "注册并登录" else "登录")
            }
        }
    }
}

@Composable
private fun MainScreen(
    state: SemapUiState,
    onRefresh: () -> Unit,
    onLogout: () -> Unit,
    onSelectSegment: (Int) -> Unit,
    onShowMap: () -> Unit,
    onShowList: () -> Unit,
    onShowFlightImport: () -> Unit,
    onShowTrainImport: () -> Unit,
    onImportFlight: (String, String) -> Unit,
    onImportTrain: (String, String, String, String) -> Unit,
) {
    val selectedSegment = state.segments.firstOrNull { it.id == state.selectedSegmentId }
    val title = when (state.view) {
        AppView.Map -> "轨迹地图"
        AppView.List -> "轨迹列表"
        AppView.FlightImport -> "航班导入"
        AppView.TrainImport -> "火车导入"
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(18.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                )
                Text(state.account?.username.orEmpty(), color = Muted)
            }
            OutlinedButton(onClick = onLogout) {
                Text("退出")
            }
        }
        Spacer(Modifier.height(14.dp))
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                ModeButton("地图", state.view == AppView.Map, onShowMap)
                ModeButton("列表", state.view == AppView.List, onShowList)
                Button(
                    enabled = !state.busy,
                    onClick = onRefresh,
                    colors = ButtonDefaults.buttonColors(containerColor = Brand),
                ) {
                    Text("刷新")
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                ModeButton("航班", state.view == AppView.FlightImport, onShowFlightImport)
                ModeButton("火车", state.view == AppView.TrainImport, onShowTrainImport)
            }
        }
        Spacer(Modifier.height(8.dp))
        Text("${state.segments.size} 条轨迹", color = Muted)
        if (state.error != null) {
            Spacer(Modifier.height(10.dp))
            Text(state.error, color = Danger, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(14.dp))
        if (state.busy && state.segments.isEmpty()) {
            CenterStatus("正在同步轨迹")
        } else {
            when (state.view) {
                AppView.Map -> TrackMapScreen(
                    segments = state.segments,
                    selectedSegment = selectedSegment,
                    onSelectSegment = onSelectSegment,
                )
                AppView.List -> TrackList(
                    segments = state.segments,
                    selectedSegment = selectedSegment,
                    onSelectSegment = onSelectSegment,
                )
                AppView.FlightImport -> FlightImportScreen(
                    busy = state.busy,
                    onImport = onImportFlight,
                )
                AppView.TrainImport -> TrainImportScreen(
                    busy = state.busy,
                    onImport = onImportTrain,
                )
            }
        }
    }
}

@Composable
private fun TrackMapScreen(
    segments: List<TrackSegment>,
    selectedSegment: TrackSegment?,
    onSelectSegment: (Int) -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .border(1.dp, Border, RoundedCornerShape(8.dp))
                .clip(RoundedCornerShape(8.dp))
                .background(Color.White),
        ) {
            if (BuildConfig.GOOGLE_MAPS_CONFIGURED) {
                SegmentMap(
                    segments = segments,
                    selectedSegment = selectedSegment,
                    onSelectSegment = onSelectSegment,
                )
            } else {
                EmptyPanel("缺少 GOOGLE_MAPS_API_KEY")
            }
            if (segments.isEmpty() && BuildConfig.GOOGLE_MAPS_CONFIGURED) {
                MapHint("暂无轨迹")
            }
        }
        Panel {
            if (selectedSegment == null) {
                Text("暂无选中轨迹", color = Muted, fontWeight = FontWeight.SemiBold)
            } else {
                TrackSummary(selectedSegment)
            }
        }
    }
}

@Composable
private fun SegmentMap(
    segments: List<TrackSegment>,
    selectedSegment: TrackSegment?,
    onSelectSegment: (Int) -> Unit,
) {
    val cameraPositionState = rememberCameraPositionState {
        position = CameraPosition.fromLatLngZoom(DefaultCenter, 4f)
    }
    var mapLoaded by remember { mutableStateOf(false) }

    LaunchedEffect(mapLoaded, segments, selectedSegment?.id) {
        if (!mapLoaded) {
            return@LaunchedEffect
        }
        val points = visiblePoints(selectedSegment, segments)
        when (points.size) {
            0 -> cameraPositionState.animate(CameraUpdateFactory.newLatLngZoom(DefaultCenter, 4f))
            1 -> cameraPositionState.animate(CameraUpdateFactory.newLatLngZoom(points.first(), 10f))
            else -> {
                val bounds = LatLngBounds.builder()
                points.forEach { bounds.include(it) }
                cameraPositionState.animate(CameraUpdateFactory.newLatLngBounds(bounds.build(), 90))
            }
        }
    }

    GoogleMap(
        modifier = Modifier.fillMaxSize(),
        cameraPositionState = cameraPositionState,
        uiSettings = MapUiSettings(
            compassEnabled = true,
            mapToolbarEnabled = false,
            zoomControlsEnabled = false,
        ),
        onMapLoaded = { mapLoaded = true },
    ) {
        for (segment in segments) {
            val selected = segment.id == selectedSegment?.id
            val path = segment.points.map { LatLng(it.lat, it.lng) }
            if (path.size > 1) {
                Polyline(
                    points = path,
                    clickable = true,
                    color = if (selected) Danger else Brand,
                    geodesic = true,
                    width = if (selected) 10f else 6f,
                    zIndex = if (selected) 20f else 5f,
                    onClick = { onSelectSegment(segment.id) },
                )
            }
            for ((index, point) in segment.points.withIndex()) {
                if (!shouldShowMarker(segment, index, point)) {
                    continue
                }
                Marker(
                    state = MarkerState(position = LatLng(point.lat, point.lng)),
                    title = segment.title,
                    snippet = point.name,
                    zIndex = if (selected) 30f else 10f,
                    onClick = {
                        onSelectSegment(segment.id)
                        true
                    },
                )
            }
        }
    }
}

@Composable
private fun TrackList(
    segments: List<TrackSegment>,
    selectedSegment: TrackSegment?,
    onSelectSegment: (Int) -> Unit,
) {
    if (segments.isEmpty()) {
        EmptyPanel("暂无轨迹")
        return
    }

    LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        items(segments, key = { it.id }) { segment ->
            TrackRow(
                segment = segment,
                selected = selectedSegment?.id == segment.id,
                onClick = { onSelectSegment(segment.id) },
            )
        }
    }
}

@Composable
private fun FlightImportScreen(
    busy: Boolean,
    onImport: (String, String) -> Unit,
) {
    var flightNumber by remember { mutableStateOf("") }
    var date by remember { mutableStateOf(LocalDate.now().toString()) }

    Panel {
        Text("FlightRadar24", color = Muted, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = flightNumber,
            onValueChange = { flightNumber = it.uppercase() },
            label = { Text("航班号") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = date,
            onValueChange = { date = it },
            label = { Text("日期 YYYY-MM-DD") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(10.dp))
        Button(
            enabled = !busy && flightNumber.isNotBlank() && date.isNotBlank(),
            onClick = { onImport(flightNumber, date) },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Brand),
        ) {
            Text(if (busy) "导入中" else "导入轨迹")
        }
    }
}

@Composable
private fun TrainImportScreen(
    busy: Boolean,
    onImport: (String, String, String, String) -> Unit,
) {
    var trainCode by remember { mutableStateOf("") }
    var date by remember { mutableStateOf(LocalDate.now().toString()) }
    var fromStation by remember { mutableStateOf("") }
    var toStation by remember { mutableStateOf("") }

    Panel {
        Text("12306 指定日期", color = Muted, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = trainCode,
            onValueChange = { trainCode = it.uppercase() },
            label = { Text("车次号") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = date,
            onValueChange = { date = it },
            label = { Text("日期 YYYY-MM-DD") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = fromStation,
            onValueChange = { fromStation = it },
            label = { Text("乘车起点") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = toStation,
            onValueChange = { toStation = it },
            label = { Text("乘车终点") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Spacer(Modifier.height(10.dp))
        Button(
            enabled = !busy && trainCode.isNotBlank() && date.isNotBlank() &&
                fromStation.isNotBlank() && toStation.isNotBlank(),
            onClick = { onImport(trainCode, date, fromStation, toStation) },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Brand),
        ) {
            Text(if (busy) "导入中" else "导入轨迹")
        }
    }
}

@Composable
private fun TrackRow(segment: TrackSegment, selected: Boolean, onClick: () -> Unit) {
    Panel(
        modifier = Modifier
            .border(
                width = if (selected) 2.dp else 1.dp,
                color = if (selected) Brand else Border,
                shape = RoundedCornerShape(8.dp),
            )
            .clickable(onClick = onClick),
    ) {
        if (selected) {
            TrackSummary(segment)
        } else {
            CompactTrackSummary(segment)
        }
    }
}

@Composable
private fun CompactTrackSummary(segment: TrackSegment) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        TrackLogo(segment)
        Spacer(Modifier.width(8.dp))
        Text(
            sourceLabel(segment.sourceType),
            modifier = Modifier
                .border(1.dp, Border, RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 3.dp),
            color = TextPrimary,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.width(8.dp))
        Text(
            segment.title,
            modifier = Modifier.weight(1f),
            fontWeight = FontWeight.Bold,
            color = TextPrimary,
        )
        Text(formatDate(segment.startedAt), color = Muted, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun TrackSummary(segment: TrackSegment) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        TrackLogo(segment)
        Spacer(Modifier.width(8.dp))
        Text(
            sourceLabel(segment.sourceType),
            modifier = Modifier
                .border(1.dp, Border, RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 3.dp),
            color = TextPrimary,
            fontWeight = FontWeight.SemiBold,
        )
    }
    Spacer(Modifier.height(8.dp))
    Text(segment.title, fontWeight = FontWeight.Bold, color = TextPrimary)
    SegmentMetadata(segment)
    if (segment.summary != null) {
        Spacer(Modifier.height(4.dp))
        Text(segment.summary, color = Muted)
    }
}

@Composable
private fun TrackLogo(segment: TrackSegment) {
    val metadata = segment.metadata
    val label = metadata.logoText ?: metadata.operatorCode ?: sourceLabel(segment.sourceType)
    val textColor = if (metadata.logoKind == "railway_12306") RailwayBlue else TextPrimary
    val logoUrl = if (metadata.logoKind == "railway_12306") {
        "/logos/China_Railways.svg"
    } else {
        metadata.logoUrl
    }
    Box(
        modifier = Modifier.size(40.dp),
        contentAlignment = Alignment.Center,
    ) {
        if (logoUrl == null) {
            Text(label.take(5), color = textColor, fontWeight = FontWeight.ExtraBold)
        } else {
            AsyncImage(
                model = absoluteAssetUrl(logoUrl),
                contentDescription = null,
                modifier = Modifier.size(32.dp),
            )
        }
    }
}

@Composable
private fun SegmentMetadata(segment: TrackSegment) {
    val metadata = segment.metadata
    val startPlace = segmentStartPlace(segment)
    val endPlace = segmentEndPlace(segment)
    val items = listOfNotNull(
        metadata.operatorName?.let { "运营方：$it" },
        metadata.vehicleModel?.let { "${if (segment.sourceType == "train") "担当车型" else "机型"}：$it" },
        metadata.registration?.let { "注册号：$it" },
        startPlace?.let { "${if (segment.sourceType == "train") "出发地点" else "起飞地点"}：$it" },
        endPlace?.let { "${if (segment.sourceType == "train") "到达地点" else "降落地点"}：$it" },
        "出发时间：${formatDateTime(segment.startedAt)}",
        "到达时间：${formatDateTime(segment.endedAt)}",
        metadata.unitNo?.let { "车组号：$it" },
    )
    if (items.isEmpty()) {
        return
    }
    Spacer(Modifier.height(6.dp))
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        for (item in items) {
            Text(item, color = Muted, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun BrandHeader() {
    Text("SEMAP", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.ExtraBold)
    Text("移动轨迹记录与地图展示", color = Muted)
}

@Composable
private fun ModeButton(text: String, active: Boolean, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = if (active) Color.White else Page,
            contentColor = if (active) Brand else TextPrimary,
        ),
    ) {
        Text(text)
    }
}

@Composable
private fun Panel(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(Color.White, RoundedCornerShape(8.dp))
            .border(1.dp, Border, RoundedCornerShape(8.dp))
            .padding(18.dp),
        content = content,
    )
}

@Composable
private fun EmptyPanel(text: String) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, Border, RoundedCornerShape(8.dp))
            .background(Color.White, RoundedCornerShape(8.dp))
            .padding(32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = Muted, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun BoxScope.MapHint(text: String) {
    Text(
        text,
        modifier = Modifier
            .align(Alignment.TopStart)
            .padding(14.dp)
            .background(Color.White, RoundedCornerShape(8.dp))
            .border(1.dp, Border, RoundedCornerShape(8.dp))
            .padding(horizontal = 10.dp, vertical = 7.dp),
        color = Muted,
        fontWeight = FontWeight.SemiBold,
    )
}

@Composable
private fun CenterStatus(text: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = Brand)
            Spacer(Modifier.height(12.dp))
            Text(text, color = Muted)
        }
    }
}

private fun visiblePoints(selectedSegment: TrackSegment?, segments: List<TrackSegment>): List<LatLng> {
    val source = if (selectedSegment?.points?.isNotEmpty() == true) listOf(selectedSegment) else segments
    return source.flatMap { segment -> segment.points.map { LatLng(it.lat, it.lng) } }
}

private fun shouldShowMarker(segment: TrackSegment, index: Int, point: TrackPoint): Boolean {
    if (segment.sourceType == "train") {
        return index == 0 || index == segment.points.lastIndex
    }
    return point.name != null
}

private fun trainStationName(value: String?): String? {
    if (value == null) {
        return null
    }
    return if (value.endsWith("站")) value else "${value}站"
}

private fun segmentStartPlace(segment: TrackSegment): String? {
    if (segment.sourceType == "train") {
        return trainStationName(segment.points.firstOrNull()?.name)
    }
    return segment.metadata.originLocation ?: segment.points.firstOrNull()?.name
}

private fun segmentEndPlace(segment: TrackSegment): String? {
    if (segment.sourceType == "train") {
        return trainStationName(segment.points.lastOrNull()?.name)
    }
    return segment.metadata.destinationLocation ?: segment.points.lastOrNull()?.name
}

private fun absoluteAssetUrl(value: String): String {
    if (value.startsWith("http://") || value.startsWith("https://")) {
        return value
    }
    val origin = BuildConfig.SEMAP_API_BASE_URL.substringBefore("/api/").trimEnd('/')
    return "$origin$value"
}

private fun formatDate(value: String?): String {
    if (value == null) {
        return "未设置"
    }
    return formatDateTime(value).take(10)
}

private fun formatDateTime(value: String?): String {
    if (value == null) {
        return "未设置"
    }
    return OffsetDateTime.parse(value.replace("Z", "+00:00"))
        .atZoneSameInstant(ChinaZone)
        .format(DateTimeFormatter.ofPattern("yyyy/MM/dd HH:mm"))
}

private fun sourceLabel(sourceType: String) = when (sourceType) {
    "flight" -> "航班"
    "train" -> "火车"
    "gps" -> "GPS"
    else -> sourceType
}

private val Brand = Color(0xFF22736F)
private val Page = Color(0xFFF4F7F6)
private val Border = Color(0xFFD4DFDC)
private val Danger = Color(0xFFB94B42)
private val RailwayBlue = Color(0xFF1F5FA8)
private val Muted = Color(0xFF687986)
private val TextPrimary = Color(0xFF1D2730)
private val ChinaZone = ZoneId.of("Asia/Shanghai")
