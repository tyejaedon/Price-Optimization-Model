package dev.tyejaedon.pricing.ui.pricing

import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import dev.tyejaedon.pricing.data.network.dto.PeerMatchDTO
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteExplanationDTO
import dev.tyejaedon.pricing.ui.pricing.components.PricingResultCard
import dev.tyejaedon.pricing.ui.theme.PricingTheme

/**
 * Previews required by issue #140's acceptance criteria: light, dark, and large font-scale
 * variants of a core component must render without runtime exceptions.
 */
private val previewResult =
    PredictionResultDTO(
        basePredictedRate = 2500f,
        mpesaTariffSurcharge = 57f,
        finalQuotedRate = 2557f,
        minQuotedRate = 2125f,
        maxQuotedRate = 3375f,
        kNeighborsUsed = 5,
        bilateralArbitrageFactor = 0.51f,
        confidenceScore = 0f,
        comparables =
            listOf(
                PeerMatchDTO("list_001", "Senior Android Architect", 2600f, 0.92f, 0.41f, idwWeight = 0.62f),
                PeerMatchDTO("list_045", "Kotlin Mentor", 2400f, 0.88f, 0.55f, idwWeight = 0.38f),
            ),
        reason = "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge.",
        explanation =
            QuoteExplanationDTO(
                requestedPartition = "mobile",
                routedPartition = "mobile",
                corridorUpliftMultiplier = 1.49f,
                topMatchedTerms = listOf("android", "kotlin", "jetpack compose"),
            ),
        timestamp = "2026-10-10T00:00:00Z",
    )

@Preview(name = "Light", showBackground = true)
@Composable
private fun PricingResultCardLightPreview() {
    PricingTheme(darkTheme = false) { PricingResultCard(result = previewResult, onOpenDetails = {}) }
}

@Preview(name = "Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun PricingResultCardDarkPreview() {
    PricingTheme(darkTheme = true) { PricingResultCard(result = previewResult, onOpenDetails = {}) }
}

@Preview(name = "Large font", fontScale = 2.0f, showBackground = true)
@Composable
private fun PricingResultCardLargeFontPreview() {
    PricingTheme(darkTheme = false) { PricingResultCard(result = previewResult, onOpenDetails = {}) }
}
