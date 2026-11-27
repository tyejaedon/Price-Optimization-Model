package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiAmbientCanvas
import dev.tyejaedon.pricing.designsystem.recessedGlassWell
import dev.tyejaedon.pricing.ui.pricing.formatting.formatKesRate
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme

/**
 * `BilateralCorridorSelector` from the canonical Sprint 4 acceptance (issue #74). Visualizes the
 * synthesized `[minQuotedRate, maxQuotedRate]` corridor with the base rate marked inside it, plus
 * optional comparable peer markers, requested floor marker, and negotiation anchor labels.
 */
@Composable
fun BilateralCorridorSelector(
    minRate: Float,
    maxRate: Float,
    finalRate: Float,
    currencyUnit: String = "KES/hour",
    peerRates: List<Float> = emptyList(),
    floorRate: Float? = null,
    showAnchorLabels: Boolean = false,
    modifier: Modifier = Modifier,
) {
    val range = (maxRate - minRate).coerceAtLeast(1f)
    val progress = ((finalRate - minRate) / range).coerceIn(0.06f, 1f)
    val glass = LocalOneUiGlassColors.current

    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription =
                        "Negotiation range from ${formatKesRate(minRate)} to ${formatKesRate(maxRate)} $currencyUnit, " +
                        "base rate ${formatKesRate(finalRate)}"
                },
    ) {
        Text(
            text = "${formatKesRate(minRate)} - ${formatKesRate(maxRate)} $currencyUnit",
            style = MaterialTheme.typography.titleMedium,
            color = glass.textPrimary,
        )
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(vertical = PricingSpacing.Small)
                    .height(PricingSpacing.RangeIndicatorHeight)
                    .recessedGlassWell(shape = CircleShape),
        ) {
            Box(
                modifier =
                    Modifier
                        .fillMaxWidth(progress)
                        .fillMaxHeight()
                        .clip(CircleShape)
                        .background(
                            brush =
                                Brush.horizontalGradient(
                                    listOf(glass.primaryAccent, glass.secondaryAccent),
                                ),
                        ),
            )
            if (peerRates.isNotEmpty() || floorRate != null) {
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val centerY = size.height / 2f
                    val dotRadius = (size.height * 0.24f).coerceIn(3.dp.toPx(), 6.dp.toPx())
                    if (floorRate != null && floorRate.isFinite()) {
                        val floorFraction = ((floorRate - minRate) / range).coerceIn(0.02f, 0.98f)
                        val floorX = size.width * floorFraction
                        drawLine(
                            color = glass.warningTint,
                            start = Offset(floorX, 2.dp.toPx()),
                            end = Offset(floorX, size.height - 2.dp.toPx()),
                            strokeWidth = 2.dp.toPx(),
                        )
                    }
                    peerRates.filter { it.isFinite() }.forEach { peerRate ->
                        val peerFraction = ((peerRate - minRate) / range).coerceIn(0.03f, 0.97f)
                        val x = size.width * peerFraction
                        drawCircle(
                            color = Color.White.copy(alpha = 0.92f),
                            radius = dotRadius,
                            center = Offset(x, centerY),
                        )
                        drawCircle(
                            color = glass.primaryAccent,
                            radius = dotRadius,
                            center = Offset(x, centerY),
                            style = Stroke(width = 1.5.dp.toPx()),
                        )
                    }
                }
            }
        }
        if (showAnchorLabels) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                AnchorLabel(
                    title = "Walk-away floor",
                    rate = "${formatKesRate(minRate)} KES",
                    alignment = TextAlign.Start,
                    modifier = Modifier.weight(1f),
                )
                AnchorLabel(
                    title = "Market anchor",
                    rate = "${formatKesRate(finalRate)} KES",
                    alignment = TextAlign.Center,
                    modifier = Modifier.weight(1f),
                )
                AnchorLabel(
                    title = "Stretch ask",
                    rate = "${formatKesRate(maxRate)} KES",
                    alignment = TextAlign.End,
                    modifier = Modifier.weight(1f),
                )
            }
        } else {
            Text(
                text = "Base rate (excl. M-Pesa): ${formatKesRate(finalRate)} $currencyUnit",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
            )
        }
    }
}

@Composable
private fun AnchorLabel(
    title: String,
    rate: String,
    alignment: TextAlign,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    Column(modifier = modifier) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelSmall,
            color = glass.textMuted,
            textAlign = alignment,
            modifier = Modifier.fillMaxWidth(),
        )
        Text(
            text = rate,
            style = MaterialTheme.typography.bodySmall,
            color = glass.textSecondary,
            textAlign = alignment,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Preview(name = "BilateralCorridorSelector - Light", showBackground = true)
@Composable
private fun BilateralCorridorSelectorLightPreview() {
    PricingTheme(darkTheme = false) {
        OneUiAmbientCanvas {
            BilateralCorridorSelector(
                minRate = 2125f,
                maxRate = 3375f,
                finalRate = 2500f,
                peerRates = listOf(2400f, 2600f, 2850f),
                showAnchorLabels = true,
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}

@Preview(name = "BilateralCorridorSelector - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun BilateralCorridorSelectorDarkPreview() {
    PricingTheme(darkTheme = true) {
        OneUiAmbientCanvas {
            BilateralCorridorSelector(
                minRate = 2125f,
                maxRate = 3375f,
                finalRate = 2900f,
                peerRates = listOf(2400f, 2600f, 2900f),
                showAnchorLabels = true,
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}
