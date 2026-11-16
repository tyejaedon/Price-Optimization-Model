plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jlleitschuh.gradle.ktlint")
}

fun buildConfigValue(
    propertyName: String,
    environmentName: String,
): String {
    val value =
        providers
            .gradleProperty(propertyName)
            .orElse(providers.environmentVariable(environmentName))
            .orElse("")
            .get()
    return value.replace("\\", "\\\\").replace("\"", "\\\"")
}

android {
    namespace = "dev.tyejaedon.pricing.admin"
    compileSdk = 34

    defaultConfig {
        applicationId = "dev.tyejaedon.pricing.admin"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-admin"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true

        val liveBackendValue =
            providers
                .gradleProperty("useLiveBackend")
                .orElse(providers.environmentVariable("USE_LIVE_BACKEND"))
                .orElse("false")
                .get()
        require(liveBackendValue == "true" || liveBackendValue == "false") {
            "useLiveBackend must be either true or false."
        }
        buildConfigField("boolean", "USE_LIVE_BACKEND", liveBackendValue)

        val pricingApiBaseUrl =
            buildConfigValue("pricingApiBaseUrl", "PRICING_API_BASE_URL")
                .ifBlank { "http://10.0.2.2:8000/" }
        require(pricingApiBaseUrl.endsWith("/")) {
            "pricingApiBaseUrl must end with a slash."
        }
        val isLocalCleartextUrl =
            pricingApiBaseUrl.startsWith("http://10.0.2.2") ||
                pricingApiBaseUrl.startsWith("http://localhost") ||
                pricingApiBaseUrl.startsWith("http://127.0.0.1")
        if (liveBackendValue == "true" && !isLocalCleartextUrl) {
            require(pricingApiBaseUrl.startsWith("https://")) {
                "Remote live backend URLs must use https://."
            }
        }
        buildConfigField("String", "PRICING_API_BASE_URL", "\"$pricingApiBaseUrl\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        debug {
            isDebuggable = true
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        resources.excludes.add("/META-INF/{AL2.0,LGPL2.1}")
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
        unitTests.isIncludeAndroidResources = true
    }
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")

    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1")
    testImplementation("app.cash.turbine:turbine:1.1.0")
    testImplementation("com.google.truth:truth:1.4.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")

    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}

ktlint {
    android.set(true)
    version.set("1.3.1")
    filter {
        exclude("**/build/**")
    }
}
