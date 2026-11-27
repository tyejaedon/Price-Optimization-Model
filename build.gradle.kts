// Root Gradle build for the Android client (Milestone 12-14). The Python backend under src/
// is built and tested independently (requirements.txt, pytest); this file only configures the
// Android Gradle module(s) and is not part of the Python package build.
plugins {
    id("com.android.application") version "9.1.0" apply false
    id("com.android.library") version "9.1.0" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10" apply false
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1" apply false
}

tasks.register("clean", Delete::class) {
    delete(rootProject.layout.buildDirectory)
}
