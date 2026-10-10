package edu.strathmore.pricing.ui.pricing.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import kotlin.math.roundToInt

/**
 * `SaturationSlider` from the canonical Sprint 4 acceptance (issue #74). Feeds
 * `competitivenessScore` in `[0.0, 1.0]`, which the backend maps to the fitted market-saturation
 * feature (docs/architecture_blueprint (1).md migration table) -- never to cost-of-living.
 */
@Composable
fun SaturationSlider(
    score: Float,
    onScoreChanged: (Float) -> Unit,
    modifier: Modifier = Modifier,
) {
    val percent = (score * 100).roundToInt()
    Column(modifier = modifier.fillMaxWidth()) {
        Text(
            text = "Niche competitiveness: $percent%",
            style = MaterialTheme.typography.labelLarge,
        )
        Slider(
            value = score,
            onValueChange = onScoreChanged,
            valueRange = 0f..1f,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = "Niche competitiveness slider, $percent percent" },
        )
    }
}
