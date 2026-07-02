package com.semap.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

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
            else -> TrackListScreen(
                state = state,
                onRefresh = viewModel::loadSegments,
                onLogout = viewModel::logout,
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
private fun TrackListScreen(
    state: SemapUiState,
    onRefresh: () -> Unit,
    onLogout: () -> Unit,
) {
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
                Text("轨迹列表", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(state.account?.username.orEmpty(), color = Muted)
            }
            OutlinedButton(onClick = onLogout) {
                Text("退出")
            }
        }
        Spacer(Modifier.height(14.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(
                enabled = !state.busy,
                onClick = onRefresh,
                colors = ButtonDefaults.buttonColors(containerColor = Brand),
            ) {
                Text("刷新")
            }
            Text("${state.segments.size} 条轨迹", modifier = Modifier.align(Alignment.CenterVertically), color = Muted)
        }
        if (state.error != null) {
            Spacer(Modifier.height(10.dp))
            Text(state.error, color = Danger, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(14.dp))
        if (state.busy && state.segments.isEmpty()) {
            CenterStatus("正在同步轨迹")
        } else if (state.segments.isEmpty()) {
            EmptyPanel("暂无轨迹")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                items(state.segments, key = { it.id }) { segment ->
                    TrackRow(segment)
                }
            }
        }
    }
}

@Composable
private fun TrackRow(segment: TrackSegment) {
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                sourceLabel(segment.sourceType),
                modifier = Modifier
                    .border(1.dp, Border, RoundedCornerShape(6.dp))
                    .padding(horizontal = 8.dp, vertical = 3.dp),
                color = TextPrimary,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.width(8.dp))
            Text("${segment.points.size} 点", color = Muted)
        }
        Spacer(Modifier.height(8.dp))
        Text(segment.title, fontWeight = FontWeight.Bold, color = TextPrimary)
        if (segment.summary != null) {
            Spacer(Modifier.height(4.dp))
            Text(segment.summary, color = Muted)
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
            contentColor = TextPrimary,
        ),
    ) {
        Text(text)
    }
}

@Composable
private fun Panel(content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, Border, RoundedCornerShape(8.dp))
            .background(Color.White, RoundedCornerShape(8.dp))
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
private fun CenterStatus(text: String) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator(color = Brand)
            Spacer(Modifier.height(12.dp))
            Text(text, color = Muted)
        }
    }
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
private val Muted = Color(0xFF687986)
private val TextPrimary = Color(0xFF1D2730)
