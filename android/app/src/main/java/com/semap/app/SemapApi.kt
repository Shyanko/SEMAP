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

    @POST("import/flight")
    suspend fun importFlight(
        @Header("Authorization") authorization: String,
        @Body request: FlightImportRequest,
    ): TrackSegment

    @POST("import/train")
    suspend fun importTrain(
        @Header("Authorization") authorization: String,
        @Body request: TrainImportRequest,
    ): TrackSegment
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
data class FlightImportRequest(
    val flightNumber: String,
    val date: String,
)

@Serializable
data class TrainImportRequest(
    val trainCode: String,
    val date: String,
    val fromStation: String,
    val toStation: String,
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
    val isApproximate: Boolean,
    val metadata: TrackSegmentMetadata = TrackSegmentMetadata(),
    val version: Int,
    val createdAt: String,
    val updatedAt: String,
    val points: List<TrackPoint>,
)

@Serializable
data class TrackSegmentMetadata(
    val vehicleModel: String? = null,
    val registration: String? = null,
    val operatorName: String? = null,
    val operatorCode: String? = null,
    val logoKind: String? = null,
    val logoUrl: String? = null,
    val logoText: String? = null,
    val unitNo: String? = null,
    val originLocation: String? = null,
    val destinationLocation: String? = null,
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
