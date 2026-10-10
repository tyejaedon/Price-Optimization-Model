# Android Client Implementation Guide (Milestone 12-14)

This guide is the **guiding, explicit breakdown** for the native Android client referenced from
`docs/architecture_blueprint (1).md` section 7 and the class diagram at
`docs/Architecture/Class/mobile class diagram.svg`. It exists so every subsequent Android PR maps to
a concrete issue, a concrete class-diagram element, and an explicit UI/UX or CI acceptance bar,
instead of ad hoc scope creep. It does not replace or move any Python module under `src/`.

## Issue map

| Issue | Milestone | Scope | Status after this scaffold |
| --- | --- | --- | --- |
| #74 M12.1 | 12 | Compose MVVM scaffold, `CapabilityInputForm`, `BilateralCorridorSelector`, `SaturationSlider`, Idle/Loading/Success/Error states | Implemented in this PR; see below |
| #140 M12.1.1 | 12 | Material 3 design system, accessibility, motion polish | Theme/primitives/previews/semantics landed in this PR; automated accessibility-check test and dynamic-color QA remain open follow-up |
| #75 M12.2 | 12 | Firebase sign-in, encrypted token storage, refresh/logout | Not implemented here; `IAuthTokenProvider`/`FirebaseAuthManager` stub only fixes the shape |
| #76 M13.1 | 13 | Full Retrofit networking, token attachment, HTTP error taxonomy | Not implemented here; `PricingApiService`/`PricingRepositoryImpl` fix the shape, gated behind `BuildConfig.USE_LIVE_BACKEND = false` |
| #141 M13.2.1 | 13 | Android CI: Gradle build, lint, ktlint, unit tests as a required check | `.github/workflows/android-ci.yml` added in this PR; verified green on this PR's branch |
| #142 M13.1.2 | 13 | Results dashboard UX: corridor, M-Pesa breakdown, comparables, confidence disclosure, `AnimateRecommendation` motion | `PricingResultCard` implemented in this PR; instrumented Compose UI tests remain open follow-up |
| #144 M12.1.4 | 12 | Shared Android Studio run/debug configuration for `app` | Implemented in this PR; `.idea/runConfigurations/` committed, see "IDE caveat" below |
| #77 M13.2 | 13 | Backend Docker/CI | Already closed; unrelated to the Android module |
| #85-#87 M14 | 14 | Browser demo harness, 3G RTT validation, SUS study | Unaffected by this PR |

## IDE caveat: PyCharm vs. Android Studio

Opening this repo in **PyCharm** (or IntelliJ IDEA Community without the Android plugin) imports
`app` as a generic Kotlin/JVM module -- there is no Android facet. The IDE then auto-generates a
run configuration like `price-optimization-model-android.app.main` and running it fails with:

```
Run configuration price-optimization-model-android.app.main is not supported in the current
project. Cannot obtain the package...
```

This is expected: Android app modules have no `main()` entry point (they launch `MainActivity` on
a device/emulator via an APK), so that auto-generated config can never work. If you see this:

- Delete the stray config (`Run ▸ Edit Configurations… ▸` select it ▸ remove), and
- Open/run `app` from **Android Studio** instead (it understands the Android facet and provides a
  real "Android App" run/debug configuration), or
- Use Gradle directly from a terminal: `gradle :app:assembleDebug`, `:app:installDebug`,
  `:app:testDebugUnitTest`, `:app:lintDebug`, `:app:ktlintCheck` -- exactly what
  `.github/workflows/android-ci.yml` runs.

### Shared run/debug configurations (#144)

`.idea/runConfigurations/` is committed to VCS so every contributor gets the same four
configurations after cloning (no per-machine "Edit Configurations…" setup):

| Configuration         | Type                                                                                            | What it does                                                                                                                                                                                                                                                                                                  |
|-----------------------|--------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `app`                 | Android App (`AndroidRunConfigurationType`), module `price-optimization-model-android.app.main` | Builds, installs and launches the default launcher activity (`MainActivity`) on a selected device/emulator with debugging attached. **Only resolves in Android Studio** -- it needs the Android Gradle facet that Android Studio creates on sync; PyCharm has no Android plugin so this entry is inert there. |
| `app [assembleDebug]` | Gradle                                                                                     | Runs `:app:assembleDebug`. Works in both Android Studio and PyCharm (Gradle plugin).                                                                                                                                                                                                                          |
| `app [unit tests]`    | Gradle                                                                                     | Runs `:app:testDebugUnitTest` (same task `android-ci.yml` runs). Works in both IDEs.                                                                                                                                                                                                                          |
| `app [lint + ktlint]` | Gradle                                                                                     | Runs `:app:lintDebug` and `:app:ktlintCheck`. Works in both IDEs.                                                                                                                                                                                                                                             |

PyCharm users should prefer the three `Gradle`-type configurations above; they do not require an
Android facet and mirror `.github/workflows/android-ci.yml` exactly. The `app` Android App
configuration is for Android Studio only, and replaces the manual "Edit Configurations…" step this
IDE caveat previously described.

#### Troubleshooting: "Run configuration app is not supported... Cannot obtain the package"

If Android Studio shows this error on the committed `app` config, the project was not synced with
a real Android Gradle Plugin facet attached to `:app` -- the IDE fell back to importing it as a
plain `JAVA_MODULE` (check `.idea/modules/price-optimization-model-android.iml`: it should **not**
say `type="JAVA_MODULE"` with no Android facet). This repo's `.idea/` started life as a plain
PyCharm/Python project (`misc.xml` sets the Project SDK to a Python interpreter), which can confuse
a first Gradle import if Android Studio has no Gradle JDK configured yet. Fix:

1. **File ▸ Settings ▸ Build, Execution, Deployment ▸ Build Tools ▸ Gradle** -- set **Gradle JDK**
   to an installed JDK 17+ (not the Python SDK, not a flaky embedded JBR if sync keeps failing).
2. **File ▸ Sync Project with Gradle Files** and actually read the **Build/Sync** tool window for
   errors instead of assuming a silent success.
3. **File ▸ Project Structure ▸ Modules** should now show `app` with the Android icon/facet, and
   `.idea/modules/app/*.iml` should be populated (not empty).
4. Open **Run ▸ Edit Configurations…**, select `app`, and reselect the **Module** dropdown even if
   it looks correct, so it re-binds to the freshly synced facet module.

## Module layout

```
app/
├── build.gradle.kts                 # Compose, Retrofit, Firebase Auth (shape only), security-crypto, ktlint
└── src/main/java/edu/strathmore/pricing/
    ├── PricingApplication.kt         # Owns the single AppContainer (manual DI)
    ├── MainActivity.kt               # Hosts PricingScreen under PricingTheme
    ├── di/AppContainer.kt            # Fake vs live repository selection (BuildConfig.USE_LIVE_BACKEND)
    ├── ui/theme/                     # Color.kt, PricingTypography.kt, Shape.kt, Theme.kt (#140)
    ├── ui/components/                # PrimaryActionButton, SectionCard, InlineErrorText (#140)
    ├── ui/pricing/PricingScreen.kt   # Class-diagram PricingScreen boundary
    ├── ui/pricing/components/        # CapabilityInputForm, BilateralCorridorSelector, SaturationSlider, PricingResultCard
    ├── viewmodel/                    # PricingUiState, PricingViewModel, PricingViewModelFactory
    ├── domain/                       # IPricingRepository, PricingOutcome/PricingFailure
    └── data/
        ├── network/                  # PricingApiService (Retrofit), dto/ (mirrors src/api_contracts.py canonical DTOs)
        ├── repository/                # PricingRepositoryImpl (live), FakePricingRepository (offline/demo/tests)
        └── auth/                     # IAuthTokenProvider, FirebaseAuthManager (shape only; real impl is #75)
```

## Why a fake repository ships by default

`AppContainer.pricingRepository` resolves to `FakePricingRepository` while
`BuildConfig.USE_LIVE_BACKEND = false`. This lets the app build, run, and demo the full Idle →
Loading → Success/Error flow and the results dashboard **without** a configured Firebase project or
a reachable backend — required because #75 and #76 are separate, not-yet-landed issues. Flipping
`USE_LIVE_BACKEND` to `true` is explicitly scoped to #76 once the authenticated Retrofit path has
its own mock-server test coverage (401/403/422/503/timeout/cancellation per that issue's acceptance
criteria).

## DTO parity contract

`data/network/dto/PricingDTOs.kt` must stay byte-for-byte aligned with the canonical camelCase
models in `src/api_contracts.py` (`CanonicalPricingQueryDTO`, `CanonicalPeerMatchDTO`,
`CanonicalPredictionResultDTO`, `HealthStatusDTO`). Any backend field rename/addition under #67/#83
must be reflected here in the same PR, or the Kotlin client will silently drop or misread fields.

## Verifying this scaffold

Not every contributor environment has an Android SDK or local Gradle distribution pre-installed.
This scaffold has been verified locally (Gradle 9.3.0, JDK 22 daemon, compileOptions/kotlinOptions
pinned to JVM target 17): `gradle :app:ktlintCheck`, `:app:assembleDebug`, `:app:lintDebug` and
`:app:testDebugUnitTest` (6/6 `PricingViewModelTest` cases) all pass, and the same four tasks are
enforced on every PR by `.github/workflows/android-ci.yml`. If your environment lacks Gradle/the
Android SDK, verify with one of:

- Open `app/` in Android Studio (Giraffe+); it regenerates `gradlew`/`gradle-wrapper.jar` on sync
  (see the IDE caveat above for why PyCharm alone is not sufficient for running the app).
- Let `.github/workflows/android-ci.yml` run on the PR.

## Known follow-up gaps (tracked, not silently skipped)

- #140: an automated accessibility check (Compose `SemanticsNode` traversal or
  `AccessibilityChecks.enable()`) is not yet wired; only manual `contentDescription`/semantics and
  48dp touch targets are in place so far.
- #142: `PricingResultCard` success/empty-comparables/error rendering is only covered indirectly via
  `PricingViewModelTest`; dedicated Compose UI tests (`createComposeRule`) are still open.
- #75/#76: `FirebaseAuthManager` and `PricingRepositoryImpl` compile against the class-diagram shape
  but are not wired as the default path and have no live-service test coverage yet.

