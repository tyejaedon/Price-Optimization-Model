pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

// Native Android client for the pricing API (Milestone 12-14, issues #74-#77, #85-#87, #140-#142).
// Kept alongside the Python backend per docs/architecture_blueprint (1).md section 2; this file does
// not replace or move any existing src/ Python module.
rootProject.name = "price-optimization-model-android"
include(":app")

