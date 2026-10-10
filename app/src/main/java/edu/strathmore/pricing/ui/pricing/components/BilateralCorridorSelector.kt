package edu.strathmore.pricing.ui.pricing.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import edu.strathmore.pricing.ui.theme.AccentMint
import edu.strathmore.pricing.ui.theme.PricingSpacing
import kotlin.math.roundToInt

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
                        "Negotiation range from ${minRate.roundToInt()} to ${maxRate.roundToInt()} $currencyUnit, " +
                        "recommended ${finalRate.roundToInt()}"
                },
    ) {
        Text(
            text = "${minRate.roundToInt()} - ${maxRate.roundToInt()} $currencyUnit",
            style = MaterialTheme.typography.titleMedium,
        )
        Box(modifier = Modifier.fillMaxWidth().padding(top = PricingSpacing.ExtraSmall)) {
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().height(10.dp),
                color = AccentMint,
            )
        }
        Text(
            text = "Recommended: ${finalRate.roundToInt()} $currencyUnit",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
