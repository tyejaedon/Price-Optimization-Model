plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jlleitschuh.gradle.ktlint")
}

// Target package per issue #74 canonical acceptance and docs/architecture_blueprint (1).md section 2.
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
    namespace = "dev.tyejaedon.pricing"
    compileSdk = 37

    defaultConfig {
        applicationId = "dev.tyejaedon.pricing"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-m12"

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
        buildConfigField(
            "String",
            "PRICING_API_BASE_URL",
            "\"$pricingApiBaseUrl\"",
        )
        buildConfigField("String", "FIREBASE_API_KEY", "\"${buildConfigValue("firebaseApiKey", "FIREBASE_API_KEY")}\"")
        buildConfigField("String", "FIREBASE_APPLICATION_ID", "\"${buildConfigValue("firebaseApplicationId", "FIREBASE_APPLICATION_ID")}\"")
        buildConfigField("String", "FIREBASE_PROJECT_ID", "\"${buildConfigValue("firebaseProjectId", "FIREBASE_PROJECT_ID")}\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
        debug {
            // Allows PricingDemoActivity/fake-repository wiring for offline UI review (see AppContainer.kt).
            isDebuggable = true
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    packaging {
        resources.excludes.add("/META-INF/{AL2.0,LGPL2.1}")
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
        unitTests.isIncludeAndroidResources = true
    }
}

// Issue #146: pin the Kotlin compiler's own JVM toolchain to 17 so the Kotlin daemon runs on a JDK
// that Kotlin 1.9.24 can parse, regardless of which JDK launches Gradle itself (e.g. a newer
// IDE-bundled JDK such as 25). Gradle auto-provisions/auto-detects a matching JDK (see
// gradle.properties `org.gradle.java.installations.*`) instead of relying on a machine-specific
// org.gradle.java.home path, so this works unchanged in CI and on every contributor's machine.
kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation(project(":design-system"))
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")

    val composeBom = platform("androidx.compose:compose-bom:2024.06.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.11.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.11.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.11.1")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.ui:ui-util")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Networking for M13.1 (#76): Retrofit is exercised with MockWebServer in repository tests.
    implementation("com.squareup.retrofit2:retrofit:3.0.0")
    implementation("com.squareup.retrofit2:converter-gson:3.0.0")
    implementation("com.squareup.okhttp3:okhttp:5.5.1")
    implementation("com.squareup.okhttp3:logging-interceptor:5.5.1")

    // Firebase persists and refreshes its own session; the app does not persist ID tokens.
    implementation("com.google.firebase:firebase-auth-ktx:23.2.1")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.11.0")
    testImplementation("app.cash.turbine:turbine:1.2.1")
    testImplementation("com.google.truth:truth:1.4.5")
    testImplementation("com.squareup.okhttp3:mockwebserver:5.5.1")

    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}

ktlint {
    android.set(true)
    version.set("1.3.1")
    filter {
        exclude("**/build/**")
    }
}
