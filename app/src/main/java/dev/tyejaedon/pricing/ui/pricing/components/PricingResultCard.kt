package dev.tyejaedon.pricing.ui.pricing.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.designsystem.GlassInsetDivider
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.ui.components.SectionCard
import dev.tyejaedon.pricing.ui.pricing.formatting.formatKesRate
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import kotlin.math.roundToInt

/**
 * Compact summary card for a pricing quote on the main Quote tab. Replaces the uncalibrated `0%`
 * confidence pill with peer-match evidence, summarizes take-home vs. M-Pesa pass-through in one
 * line, and navigates to `QuoteDetailScreen` on click for full explainability.
 */
@Composable
fun PricingResultCard(
    result: PredictionResultDTO,
    modifier: Modifier = Modifier,
    onOpenDetails: (() -> Unit)? = null,
) {
    val reduceMotion = isReduceMotionEnabled()
    val glass = LocalOneUiGlassColors.current
    val animatedRate by animateFloatAsState(
        targetValue = result.finalQuotedRate,
        animationSpec = if (reduceMotion) tween(durationMillis = 0) else tween(durationMillis = 600),
        label = "finalQuotedRateCountUp",
    )

    val evidenceLabel =
        if (result.comparables.isNotEmpty()) {
            val avgSim =
                (
                    result.comparables
                        .map { it.similarityScore.coerceIn(0f, 1f) }
                        .average() * 100.0
                ).roundToInt()
            "${result.kNeighborsUsed} peers • $avgSim% match"
        } else {
            "${result.kNeighborsUsed} indexed peers"
        }

    val takeHomeSummary =
        if (result.mpesaTariffSurcharge > 0f) {
            "You net ${formatKesRate(result.basePredictedRate)} KES + ${formatKesRate(result.mpesaTariffSurcharge)} KES M-Pesa fee"
        } else {
            "You net ${formatKesRate(result.basePredictedRate)} KES • No M-Pesa fee"
        }

    val explanation = result.explanation
    val highlightBadge: Pair<String, androidx.compose.ui.graphics.Color>? =
        when {
            explanation?.floorExceedsBase == true ->
                "Your floor is above market median" to glass.warningTint
            explanation?.usedFallbackPartition == true ->
                "Broadened to ${formatIndustryLabel(explanation.routedPartition ?: "general_tech")}" to glass.infoTint
            (explanation?.corridorUpliftMultiplier ?: 1f) > 1.01f -> {
                val upliftPct = (((explanation?.corridorUpliftMultiplier ?: 1f) - 1f) * 100f).roundToInt()
                "+$upliftPct% cross-border ceiling headroom" to glass.secondaryAccent
            }
            else -> null
        }

    val cardModifier =
        if (onOpenDetails != null) {
            modifier.semantics { contentDescription = "Open full quote breakdown" }
        } else {
            modifier
        }

    SectionCard(
        modifier = cardModifier,
        onClick = onOpenDetails,
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Recommended rate",
                    style = MaterialTheme.typography.labelLarge,
                    color = glass.textSecondary,
                )
                GlassStatusBadge(
                    text = evidenceLabel,
                    tint = glass.primaryAccent,
                )
            }
            Text(
                text = "${formatKesRate(animatedRate)} KES/hour",
                style = MaterialTheme.typography.displayLarge,
                color = glass.textPrimary,
                modifier =
                    Modifier.semantics {
                        contentDescription = "Final quoted rate ${formatKesRate(result.finalQuotedRate)} KES per hour"
                    },
            )
            Text(
                text = takeHomeSummary,
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
            )

            BilateralCorridorSelector(
                minRate = result.minQuotedRate,
                maxRate = result.maxQuotedRate,
                finalRate = result.basePredictedRate,
            )

            if (highlightBadge != null) {
                GlassStatusBadge(
                    text = highlightBadge.first,
                    tint = highlightBadge.second,
                )
            }

            if (onOpenDetails != null) {
                GlassInsetDivider(startIndent = 0.dp)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    val ctaText =
                        if (result.comparables.isNotEmpty()) {
                            "View full breakdown & ${result.comparables.size} peers"
                        } else {
                            "View full breakdown & drivers"
                        }
                    Text(
                        text = ctaText,
                        style = MaterialTheme.typography.labelLarge,
                        color = glass.primaryAccent,
                    )
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                        contentDescription = null,
                        tint = glass.primaryAccent,
                        modifier = Modifier.size(20.dp),
                    )
                }
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
    return remember(context) {
        try {
            android.provider.Settings.Global.getFloat(
                context.contentResolver,
                android.provider.Settings.Global.ANIMATOR_DURATION_SCALE,
                1f,
            ) == 0f
        } catch (_: SecurityException) {
            false
        }
    }
}
