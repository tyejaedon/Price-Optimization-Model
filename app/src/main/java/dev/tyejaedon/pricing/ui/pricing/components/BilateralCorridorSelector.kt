package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.ui.pricing.formatting.formatKesRate
import dev.tyejaedon.pricing.ui.theme.AccentMint
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
    val progress = ((finalRate - minRate) / range).coerceIn(0f, 1f)

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
        )
        Box(modifier = Modifier.fillMaxWidth().padding(top = PricingSpacing.ExtraSmall)) {
            LinearProgressIndicator(
                progress = { progress },
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .height(PricingSpacing.RangeIndicatorHeight),
                color = AccentMint,
            )
        }
        Text(
            text = "Base rate (excl. M-Pesa): ${formatKesRate(finalRate)} $currencyUnit",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Preview(name = "BilateralCorridorSelector - Light", showBackground = true)
@Composable
private fun BilateralCorridorSelectorLightPreview() {
    PricingTheme(darkTheme = false) {
        Surface {
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
        Surface {
            BilateralCorridorSelector(
                minRate = 2125f,
                maxRate = 3375f,
                finalRate = 2900f,
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}
