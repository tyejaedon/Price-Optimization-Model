package dev.tyejaedon.pricing.ui.components

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.ui.theme.MinTouchTarget
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme

/**
 * Shared Material 3 primitives (issue #140) so feature screens compose from one vocabulary of
 * reusable widgets instead of redefining paddings/colors ad hoc.
 */

@Composable
fun PrimaryActionButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentDescription: String? = null,
) {
    androidx.compose.material3.Button(
        onClick = onClick,
        enabled = enabled,
        modifier =
            modifier
                .defaultMinSize(minHeight = MinTouchTarget)
                .semantics { if (contentDescription != null) this.contentDescription = contentDescription },
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier,
        shape = MaterialTheme.shapes.medium,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Box(modifier = Modifier.padding(PaddingValues(PricingSpacing.Medium))) {
            content()
        }
    }
}

@Composable
fun InlineErrorText(
    message: String,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.semantics { contentDescription = "Error: $message" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Filled.ErrorOutline,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.error,
        )
        Box(modifier = Modifier.padding(start = PricingSpacing.ExtraSmall)) {
            Text(text = message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Preview(name = "Primitives - Light", showBackground = true)
@Composable
private fun PricingPrimitivesLightPreview() {
    PricingTheme(darkTheme = false) {
        Surface {
            Column(
                modifier = Modifier.padding(PricingSpacing.Medium),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
            ) {
                SectionCard(modifier = Modifier.fillMaxWidth()) {
                    Text("Sample Section Card", style = MaterialTheme.typography.titleSmall)
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
        Surface {
            Column(
                modifier = Modifier.padding(PricingSpacing.Medium),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
            ) {
                SectionCard(modifier = Modifier.fillMaxWidth()) {
                    Text("Sample Section Card", style = MaterialTheme.typography.titleSmall)
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
