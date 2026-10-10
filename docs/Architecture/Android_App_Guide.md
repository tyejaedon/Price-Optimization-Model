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
| #141 M13.2.1 | 13 | Android CI: Gradle build, lint, ktlint, unit tests as a required check | `.github/workflows/android-ci.yml` added in this PR |
| #142 M13.1.2 | 13 | Results dashboard UX: corridor, M-Pesa breakdown, comparables, confidence disclosure, `AnimateRecommendation` motion | `PricingResultCard` implemented in this PR; instrumented Compose UI tests remain open follow-up |
| #77 M13.2 | 13 | Backend Docker/CI | Already closed; unrelated to the Android module |
| #85-#87 M14 | 14 | Browser demo harness, 3G RTT validation, SUS study | Unaffected by this PR |

## Module layout

```
app/
├── build.gradle.kts                 # Compose, Retrofit, Firebase Auth (shape only), security-crypto, ktlint
└── src/main/java/edu/strathmore/pricing/
    ├── PricingApplication.kt         # Owns the single AppContainer (manual DI)
    ├── MainActivity.kt               # Hosts PricingScreen under PricingTheme
    ├── di/AppContainer.kt            # Fake vs live repository selection (BuildConfig.USE_LIVE_BACKEND)
    ├── ui/theme/                     # Color.kt, Type.kt, Shape.kt, Theme.kt (#140)
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

No Android SDK or local Gradle distribution is available in every contributor environment. Verify
with one of:

- Open `app/` in Android Studio (Giraffe+); it regenerates `gradlew`/`gradle-wrapper.jar` on sync.
- Let `.github/workflows/android-ci.yml` run on the PR (`gradle :app:assembleDebug`,
  `:app:lintDebug`, `:app:ktlintCheck`, `:app:testDebugUnitTest`).

## Known follow-up gaps (tracked, not silently skipped)

- #140: an automated accessibility check (Compose `SemanticsNode` traversal or
  `AccessibilityChecks.enable()`) is not yet wired; only manual `contentDescription`/semantics and
  48dp touch targets are in place so far.
- #142: `PricingResultCard` success/empty-comparables/error rendering is only covered indirectly via
  `PricingViewModelTest`; dedicated Compose UI tests (`createComposeRule`) are still open.
- #75/#76: `FirebaseAuthManager` and `PricingRepositoryImpl` compile against the class-diagram shape
  but are not wired as the default path and have no live-service test coverage yet.

