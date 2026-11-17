package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
 * synthesized `[minQuotedRate, maxQuotedRate]` corridor (docs/architecture_blueprint (1).md section
 * 3.3) with the final quoted rate marked inside it. Full result-card integration/motion polish is
 * issue #142; this composable is the reusable, test-covered building block.
 */
@Composable
fun BilateralCorridorSelector(
    minRate: Float,
    maxRate: Float,
    finalRate: Float,
    currencyUnit: String = "KES/hour",
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
        }
        Text(
            text = "Base rate (excl. M-Pesa): ${formatKesRate(finalRate)} $currencyUnit",
            style = MaterialTheme.typography.bodyMedium,
            color = glass.textSecondary,
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
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}
