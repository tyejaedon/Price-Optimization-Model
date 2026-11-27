package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiAmbientCanvas
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
    val glass = LocalOneUiGlassColors.current
    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "Niche competitiveness: $percent%",
                style = MaterialTheme.typography.labelLarge,
                color = glass.textPrimary,
            )
            GlassStatusBadge(text = "$percent%", tint = glass.primaryAccent)
        }
        @OptIn(ExperimentalMaterial3Api::class)
        Slider(
            value = score,
            onValueChange = onScoreChanged,
            valueRange = 0f..1f,
            thumb = {
                val interactionSource = remember { MutableInteractionSource() }
                SliderDefaults.Thumb(
                    interactionSource = interactionSource,
                    colors = SliderDefaults.colors(thumbColor = glass.textPrimary),
                    thumbSize = DpSize(20.dp, 20.dp),
                    modifier = Modifier.zIndex(2f),
                )
            },
            track = { sliderState ->
                val activeColor = glass.primaryAccent
                val inactiveColor = glass.recessedWellFill
                val range = sliderState.valueRange.endInclusive - sliderState.valueRange.start
                val fraction = if (range > 0f) {
                    ((sliderState.value - sliderState.valueRange.start) / range).coerceIn(0f, 1f)
                } else 0f

                Box(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(6.dp)
                            .clip(CircleShape)
                            .background(inactiveColor),
                ) {
                    if (fraction > 0f) {
                        Box(
                            modifier =
                                Modifier
                                    .fillMaxWidth(fraction)
                                    .fillMaxHeight()
                                    .background(activeColor),
                        )
                    }
                }
            },
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
        OneUiAmbientCanvas {
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
        OneUiAmbientCanvas {
            SaturationSlider(
                score = 0.35f,
                onScoreChanged = {},
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}
