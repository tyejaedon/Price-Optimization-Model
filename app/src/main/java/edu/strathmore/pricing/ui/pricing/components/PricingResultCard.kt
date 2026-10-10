package edu.strathmore.pricing.ui.pricing.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.ui.components.SectionCard
import edu.strathmore.pricing.ui.theme.PricingSpacing
import edu.strathmore.pricing.ui.theme.WarningAmber

/**
 * Pricing result presentation (issue #142). Keeps corridor, M-Pesa surcharge and the uncalibrated
 * confidence score visually distinct per line item, and never fabricates placeholder comparables.
 * `AnimateRecommendation(rate, similarity)` from the class diagram is implemented as an animated
 * count-up of the final rate that is skipped when the system "reduce motion" setting is enabled.
 */
@Composable
fun PricingResultCard(
    result: PredictionResultDTO,
    modifier: Modifier = Modifier,
) {
    val reduceMotion = isReduceMotionEnabled()
    val animatedRate by animateFloatAsState(
        targetValue = result.finalQuotedRate,
        animationSpec = if (reduceMotion) tween(durationMillis = 0) else tween(durationMillis = 600),
        label = "finalQuotedRateCountUp",
    )

    SectionCard(modifier = modifier) {
        Column {
            Text(
                text = "Recommended rate",
                style = MaterialTheme.typography.labelLarge,
            )
            Text(
                text = "${animatedRate.toInt()} KES/hour",
                style = MaterialTheme.typography.headlineMedium,
                modifier =
                    Modifier.semantics {
                        contentDescription = "Final quoted rate ${result.finalQuotedRate.toInt()} KES per hour"
                    },
            )

            Spacer(modifier = Modifier.height(PricingSpacing.Small))
            BilateralCorridorSelector(
                minRate = result.minQuotedRate,
                maxRate = result.maxQuotedRate,
                finalRate = result.basePredictedRate,
            )

            Spacer(modifier = Modifier.height(PricingSpacing.Medium))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(PricingSpacing.Small))

            LineItem(label = "M-Pesa transfer fee", value = "+${result.mpesaTariffSurcharge.toInt()} KES/hour")
            LineItem(
                label = "Confidence (uncalibrated)",
                value = "${(result.confidenceScore * 100).toInt()}%",
                caption = "Not a probability that this quote is accurate.",
            )

            Spacer(modifier = Modifier.height(PricingSpacing.Medium))
            Text(text = "Comparable peers", style = MaterialTheme.typography.labelLarge)
            ComparablesList(result = result)

            Spacer(modifier = Modifier.height(PricingSpacing.Small))
            Text(text = result.reason, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun LineItem(
    label: String,
    value: String,
    caption: String? = null,
) {
    Column {
        Row(modifier = Modifier.fillMaxWidth()) {
            Text(text = label, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
            Text(text = value, style = MaterialTheme.typography.bodyMedium)
        }
        if (caption != null) {
            Text(text = caption, style = MaterialTheme.typography.bodySmall, color = WarningAmber)
        }
    }
}

@Composable
private fun ComparablesList(result: PredictionResultDTO) {
    if (result.comparables.isEmpty()) {
        Text(
            text = "No listing-backed comparables are available for this quote yet.",
            style = MaterialTheme.typography.bodySmall,
        )
        return
    }
    if (result.comparables.size < result.kNeighborsUsed) {
        Text(
            text =
                "Showing ${result.comparables.size} of ${result.kNeighborsUsed} indexed peers; " +
                    "some listings lack public provenance.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
    LazyColumn(modifier = Modifier.height((result.comparables.size.coerceAtMost(4) * 56).dp)) {
        items(result.comparables) { peer ->
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = peer.jobTitle ?: peer.listingId,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.weight(1f),
                )
                Text(text = "${peer.verifiedRate.toInt()} KES/hr", style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

/**
 * Reads the platform "remove animations" accessibility setting. Defaults to `false` (motion
 * enabled) if the setting cannot be read, which matches Android's own fallback behavior.
 */
@Composable
private fun isReduceMotionEnabled(): Boolean {
    val context = LocalContext.current
    return try {
        android.provider.Settings.Global.getFloat(
            context.contentResolver,
            android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        ) == 0f
    } catch (_: Exception) {
        false
    }
}
