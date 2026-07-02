plugins {
    id("com.android.application")
    id("com.google.devtools.ksp")
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
val configuredAmapAndroidApiKey = providers.gradleProperty("AMAP_ANDROID_API_KEY")
    .orElse(providers.environmentVariable("AMAP_ANDROID_API_KEY"))
    .orElse(localEnvValue("AMAP_ANDROID_API_KEY"))
    .get()
val amapAndroidApiKey = configuredAmapAndroidApiKey.ifBlank { localEnvValue("AMAP_MAPS_API_KEY") }

val releaseStoreFilePath = providers.gradleProperty("ANDROID_RELEASE_STORE_FILE")
    .orElse(providers.environmentVariable("ANDROID_RELEASE_STORE_FILE"))
    .orElse(localEnvValue("ANDROID_RELEASE_STORE_FILE"))
    .get()
val releaseStorePassword = providers.gradleProperty("ANDROID_RELEASE_STORE_PASSWORD")
    .orElse(providers.environmentVariable("ANDROID_RELEASE_STORE_PASSWORD"))
    .orElse(localEnvValue("ANDROID_RELEASE_STORE_PASSWORD"))
    .get()
val releaseKeyAlias = providers.gradleProperty("ANDROID_RELEASE_KEY_ALIAS")
    .orElse(providers.environmentVariable("ANDROID_RELEASE_KEY_ALIAS"))
    .orElse(localEnvValue("ANDROID_RELEASE_KEY_ALIAS"))
    .get()
val releaseKeyPassword = providers.gradleProperty("ANDROID_RELEASE_KEY_PASSWORD")
    .orElse(providers.environmentVariable("ANDROID_RELEASE_KEY_PASSWORD"))
    .orElse(localEnvValue("ANDROID_RELEASE_KEY_PASSWORD"))
    .get()
val releaseSigningConfigured = listOf(
    releaseStoreFilePath,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
).all { it.isNotBlank() }

gradle.taskGraph.whenReady {
    if (allTasks.any { it.name == "assembleRelease" || it.name == "bundleRelease" }) {
        check(releaseSigningConfigured) { "Release signing is not configured." }
    }
}

android {
    namespace = "com.semap.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.semap.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 102
        versionName = "1.2"
        buildConfigField(
            "String",
            "SEMAP_API_BASE_URL",
            "\"${providers.gradleProperty("SEMAP_API_BASE_URL").orElse("https://semap.xyz/api/").get()}\"",
        )
        buildConfigField("Boolean", "GOOGLE_MAPS_CONFIGURED", googleMapsApiKey.isNotBlank().toString())
        buildConfigField("Boolean", "AMAP_MAPS_CONFIGURED", amapAndroidApiKey.isNotBlank().toString())
        manifestPlaceholders["googleMapsApiKey"] = googleMapsApiKey
        manifestPlaceholders["amapMapsApiKey"] = amapAndroidApiKey
    }

    buildFeatures {
        buildConfig = true
        compose = true
    }

    lint {
        checkReleaseBuilds = false
    }

    signingConfigs {
        getByName("debug") {
            enableV1Signing = true
            enableV2Signing = true
            enableV3Signing = true
        }
        create("release") {
            if (releaseSigningConfigured) {
                storeFile = file(releaseStoreFilePath)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
            enableV1Signing = true
            enableV2Signing = true
            enableV3Signing = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.06.01"))
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.core:core-ktx:1.18.0")
    implementation("androidx.datastore:datastore-preferences:1.2.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.room:room-ktx:2.8.4")
    implementation("androidx.room:room-runtime:2.8.4")
    implementation("io.coil-kt.coil3:coil-compose:3.4.0")
    implementation("io.coil-kt.coil3:coil-network-okhttp:3.4.0")
    implementation("com.google.android.gms:play-services-location:21.4.0")
    implementation("com.google.maps.android:maps-compose:8.3.0")
    implementation("com.amap.api:3dmap:10.0.600")
    implementation("com.squareup.okhttp3:okhttp:5.4.0")
    implementation("com.squareup.retrofit2:retrofit:3.0.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:3.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.11.0")
    ksp("androidx.room:room-compiler:2.8.4")
}
