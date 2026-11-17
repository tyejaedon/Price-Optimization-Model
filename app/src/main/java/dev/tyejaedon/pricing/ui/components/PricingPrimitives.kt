package dev.tyejaedon.pricing.ui.components

import android.content.res.Configuration
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.designsystem.GlassCard
import dev.tyejaedon.pricing.designsystem.GlassPrimaryButton
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiAmbientCanvas
import dev.tyejaedon.pricing.designsystem.OneUiShapes
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme

/**
 * Shared One UI Glassmorphic primitives (issue #140) so feature screens compose from one
 * cohesive vocabulary of translucent cards, pill buttons, and high-contrast error pills.
 */

@Composable
fun PrimaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentDescription: String? = null,
) {
    GlassPrimaryButton(
        text = text,
        onClick = onClick,
        modifier = modifier,
        enabled = enabled,
        contentDescription = contentDescription,
    )
}

@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    GlassCard(
        modifier = modifier,
        shape = OneUiShapes.OuterContainer,
        contentPadding = PaddingValues(PricingSpacing.CardPadding),
    ) {
        content()
    }
}

@Composable
fun InlineErrorText(
    message: String,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    val pillShape = RoundedCornerShape(16.dp)
    Row(
        modifier =
            modifier
                .clip(pillShape)
                .background(glass.errorTint.copy(alpha = 0.14f), pillShape)
                .border(BorderStroke(1.dp, glass.errorTint.copy(alpha = 0.28f)), pillShape)
                .padding(horizontal = 14.dp, vertical = 10.dp)
                .semantics { contentDescription = "Error: $message" },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
    ) {
        Icon(
            imageVector = Icons.Filled.ErrorOutline,
            contentDescription = null,
            tint = glass.errorTint,
            modifier = Modifier.size(18.dp),
        )
        Text(
            text = message,
            color = glass.errorTint,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Preview(name = "Primitives - Light", showBackground = true)
@Composable
private fun PricingPrimitivesLightPreview() {
    PricingTheme(darkTheme = false) {
        OneUiAmbientCanvas {
            Column(
                modifier = Modifier.padding(PricingSpacing.Medium),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
            ) {
                SectionCard(modifier = Modifier.fillMaxWidth()) {
                    Text("Sample Section Card", style = MaterialTheme.typography.titleMedium)
                }
                PrimaryActionButton(
                    text = "Calculate rate",
                    onClick = {},
                    modifier = Modifier.fillMaxWidth(),
                )
                InlineErrorText(message = "Description must be at least 20 characters.")
            }
        }
    }
}

@Preview(name = "Primitives - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun PricingPrimitivesDarkPreview() {
    PricingTheme(darkTheme = true) {
        OneUiAmbientCanvas {
            Column(
                modifier = Modifier.padding(PricingSpacing.Medium),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
            ) {
                SectionCard(modifier = Modifier.fillMaxWidth()) {
                    Text("Sample Section Card", style = MaterialTheme.typography.titleMedium)
                }
                PrimaryActionButton(
                    text = "Disabled action",
                    onClick = {},
                    enabled = false,
                    modifier = Modifier.fillMaxWidth(),
                )
                InlineErrorText(message = "Network timeout while contacting pricing service.")
            }
        }
    }
}
