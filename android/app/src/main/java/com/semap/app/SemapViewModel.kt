package com.semap.app

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import retrofit2.HttpException

private val Application.sessionStore by preferencesDataStore("session")
private val tokenKey = stringPreferencesKey("access_token")

class SemapViewModel(application: Application) : AndroidViewModel(application) {
    private val api = SemapApiClient.create()

    var state by mutableStateOf(SemapUiState())
        private set

    fun restoreSession() {
        viewModelScope.launch {
            val token = getApplication<Application>().sessionStore.data.first()[tokenKey]
            if (token == null) {
                state = state.copy(booting = false)
                return@launch
            }

            runCatching {
                val account = api.me("Bearer $token")
                val segments = api.segments("Bearer $token")
                state.copy(
                    booting = false,
                    token = token,
                    account = account,
                    segments = segments,
                    selectedSegmentId = null,
                    error = null,
                )
            }.onSuccess { state = it }
                .onFailure {
                    clearToken()
                    state = SemapUiState(booting = false, error = "登录已失效")
                }
        }
    }

    fun register(username: String, password: String) {
        submitAuth {
            api.register(AuthRequest(username, password))
            api.login(AuthRequest(username, password))
        }
    }

    fun login(username: String, password: String) {
        submitAuth {
            api.login(AuthRequest(username, password))
        }
    }

    fun loadSegments() {
        val token = state.token ?: return
        viewModelScope.launch {
            state = state.copy(busy = true, error = null)
            runCatching { api.segments("Bearer $token") }
                .onSuccess {
                    state = state.copy(
                        busy = false,
                        segments = it,
                        selectedSegmentId = state.selectedSegmentId?.takeIf { id ->
                            it.any { segment -> segment.id == id }
                        },
                    )
                }
                .onFailure { state = state.copy(busy = false, error = errorMessage(it, "轨迹同步失败")) }
        }
    }

    fun selectSegment(segmentId: Int) {
        state = state.copy(selectedSegmentId = segmentId)
    }

    fun showMap() {
        state = state.copy(view = AppView.Map)
    }

    fun showList() {
        state = state.copy(view = AppView.List)
    }

    fun showFlightImport() {
        state = state.copy(view = AppView.FlightImport)
    }

    fun showTrainImport() {
        state = state.copy(view = AppView.TrainImport)
    }

    fun importFlight(flightNumber: String, date: String) {
        val token = state.token ?: return
        viewModelScope.launch {
            state = state.copy(busy = true, error = null)
            runCatching {
                api.importFlight(
                    "Bearer $token",
                    FlightImportRequest(flightNumber, date),
                )
            }.onSuccess { segment ->
                state = state.copy(
                    busy = false,
                    view = AppView.Map,
                    segments = listOf(segment) + state.segments.filterNot { it.id == segment.id },
                    selectedSegmentId = segment.id,
                    error = null,
                )
            }.onFailure {
                state = state.copy(busy = false, error = errorMessage(it, "航班导入失败"))
            }
        }
    }

    fun importTrain(
        trainCode: String,
        date: String,
        fromStation: String,
        toStation: String,
    ) {
        val token = state.token ?: return
        viewModelScope.launch {
            state = state.copy(busy = true, error = null)
            runCatching {
                api.importTrain(
                    "Bearer $token",
                    TrainImportRequest(
                        trainCode,
                        date,
                        fromStation,
                        toStation,
                    ),
                )
            }.onSuccess { segment ->
                state = state.copy(
                    busy = false,
                    view = AppView.Map,
                    segments = listOf(segment) + state.segments.filterNot { it.id == segment.id },
                    selectedSegmentId = segment.id,
                    error = null,
                )
            }.onFailure {
                state = state.copy(busy = false, error = errorMessage(it, "火车导入失败"))
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            clearToken()
            state = SemapUiState(booting = false)
        }
    }

    private fun submitAuth(request: suspend () -> LoginResponse) {
        viewModelScope.launch {
            state = state.copy(busy = true, error = null)
            runCatching {
                val login = request()
                saveToken(login.accessToken)
                val segments = api.segments("Bearer ${login.accessToken}")
                state.copy(
                    busy = false,
                    token = login.accessToken,
                    account = login.account,
                    segments = segments,
                    selectedSegmentId = null,
                    error = null,
                )
            }.onSuccess { state = it }
                .onFailure { state = state.copy(busy = false, error = errorMessage(it, "请求失败")) }
        }
    }

    private suspend fun saveToken(token: String) {
        getApplication<Application>().sessionStore.edit { it[tokenKey] = token }
    }

    private suspend fun clearToken() {
        getApplication<Application>().sessionStore.edit { it.remove(tokenKey) }
    }

    private fun errorMessage(error: Throwable, fallback: String): String {
        if (error is HttpException) {
            val body = error.response()?.errorBody()?.string()
            val detail = body?.let {
                runCatching { SemapApiClient.json.decodeFromString<ErrorResponse>(it).detail }.getOrNull()
            }
            return detail ?: fallback
        }
        return error.message ?: fallback
    }
}

data class SemapUiState(
    val booting: Boolean = true,
    val busy: Boolean = false,
    val token: String? = null,
    val account: Account? = null,
    val segments: List<TrackSegment> = emptyList(),
    val selectedSegmentId: Int? = null,
    val view: AppView = AppView.Map,
    val error: String? = null,
)

enum class AppView {
    Map,
    List,
    FlightImport,
    TrainImport,
}
