package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.ui.theme.PricingTheme
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

@Preview(name = "SaturationSlider - Light", showBackground = true)
@Composable
private fun SaturationSliderLightPreview() {
    PricingTheme(darkTheme = false) {
        Surface {
            SaturationSlider(
                score = 0.65f,
                onScoreChanged = {},
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}

@Preview(name = "SaturationSlider - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun SaturationSliderDarkPreview() {
    PricingTheme(darkTheme = true) {
        Surface {
            SaturationSlider(
                score = 0.35f,
                onScoreChanged = {},
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}
