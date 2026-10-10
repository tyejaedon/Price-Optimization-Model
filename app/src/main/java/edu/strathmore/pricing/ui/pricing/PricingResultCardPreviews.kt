package edu.strathmore.pricing.ui.pricing

import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import edu.strathmore.pricing.data.network.dto.PeerMatchDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.ui.pricing.components.PricingResultCard
import edu.strathmore.pricing.ui.theme.PricingTheme

/**
 * Previews required by issue #140's acceptance criteria: light, dark, and large font-scale
 * variants of a core component must render without runtime exceptions.
 */
private val previewResult = PredictionResultDTO(
    basePredictedRate = 2500f,
    mpesaTariffSurcharge = 57f,
    finalQuotedRate = 2557f,
    minQuotedRate = 2125f,
    maxQuotedRate = 3375f,
    kNeighborsUsed = 5,
    bilateralArbitrageFactor = 1.0f,
    confidenceScore = 0f,
    comparables = listOf(
        PeerMatchDTO("list_001", "Senior Android Architect", 2600f, 0.92f, 0.41f),
        PeerMatchDTO("list_045", "Kotlin Mentor", 2400f, 0.88f, 0.55f),
    ),
    reason = "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge.",
    timestamp = "2026-10-10T00:00:00Z",
)

@Preview(name = "Light", showBackground = true)
@Composable
private fun PricingResultCardLightPreview() {
    PricingTheme(darkTheme = false) { PricingResultCard(result = previewResult) }
}

@Preview(name = "Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun PricingResultCardDarkPreview() {
    PricingTheme(darkTheme = true) { PricingResultCard(result = previewResult) }
}

@Preview(name = "Large font", fontScale = 2.0f, showBackground = true)
@Composable
private fun PricingResultCardLargeFontPreview() {
    PricingTheme(darkTheme = false) { PricingResultCard(result = previewResult) }
}
