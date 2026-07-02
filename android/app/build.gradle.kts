plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

fun localEnvValue(name: String): String {
    val envFile = rootProject.file("../.env")
    if (!envFile.isFile) {
        return ""
    }
    return envFile.readLines()
        .firstOrNull { it.startsWith("$name=") }
        ?.substringAfter("=")
        ?.trim()
        ?.trim('"', '\'')
        .orEmpty()
}

val googleMapsApiKey = providers.gradleProperty("GOOGLE_MAPS_API_KEY")
    .orElse(providers.environmentVariable("GOOGLE_MAPS_API_KEY"))
    .orElse(localEnvValue("GOOGLE_MAPS_API_KEY"))
    .get()

android {
    namespace = "com.semap.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.semap.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField(
            "String",
            "SEMAP_API_BASE_URL",
            "\"${providers.gradleProperty("SEMAP_API_BASE_URL").orElse("http://10.0.2.2/api/").get()}\"",
        )
        buildConfigField("Boolean", "GOOGLE_MAPS_CONFIGURED", googleMapsApiKey.isNotBlank().toString())
        manifestPlaceholders["googleMapsApiKey"] = googleMapsApiKey
    }

    buildFeatures {
        buildConfig = true
        compose = true
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.06.01"))
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.datastore:datastore-preferences:1.2.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("io.coil-kt.coil3:coil-compose:3.4.0")
    implementation("com.google.maps.android:maps-compose:8.3.0")
    implementation("com.squareup.okhttp3:okhttp:5.4.0")
    implementation("com.squareup.retrofit2:retrofit:3.0.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:3.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.11.0")
}
