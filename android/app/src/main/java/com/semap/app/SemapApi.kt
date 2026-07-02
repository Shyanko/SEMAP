package com.semap.app

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

interface SemapApi {
    @POST("auth/register")
    suspend fun register(@Body request: AuthRequest): Account

    @POST("auth/login")
    suspend fun login(@Body request: AuthRequest): LoginResponse

    @GET("auth/me")
    suspend fun me(@Header("Authorization") authorization: String): Account

    @GET("segments")
    suspend fun segments(@Header("Authorization") authorization: String): List<TrackSegment>
}

object SemapApiClient {
    val json = Json {
        ignoreUnknownKeys = true
    }

    fun create(): SemapApi {
        val client = OkHttpClient.Builder().build()

        return Retrofit.Builder()
            .baseUrl(BuildConfig.SEMAP_API_BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SemapApi::class.java)
    }
}

@Serializable
data class AuthRequest(
    val username: String,
    val password: String,
)

@Serializable
data class LoginResponse(
    val accessToken: String,
    val tokenType: String,
    val account: Account,
)

@Serializable
data class Account(
    val id: Int,
    val username: String,
    val createdAt: String,
    val updatedAt: String,
)

@Serializable
data class TrackSegment(
    val id: Int,
    val title: String,
    val sourceType: String,
    val transportType: String,
    val externalCode: String? = null,
    val startedAt: String? = null,
    val endedAt: String? = null,
    val summary: String? = null,
    val note: String? = null,
    val isApproximate: Boolean,
    val version: Int,
    val createdAt: String,
    val updatedAt: String,
    val points: List<TrackPoint>,
)

@Serializable
data class TrackPoint(
    val id: Int,
    val sequence: Int,
    val lat: Double,
    val lng: Double,
    val altitude: Double? = null,
    val speed: Double? = null,
    val recordedAt: String? = null,
    val name: String? = null,
)

@Serializable
data class ErrorResponse(
    val detail: String? = null,
)
