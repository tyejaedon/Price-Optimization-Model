package edu.strathmore.pricing.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import edu.strathmore.pricing.ui.theme.ErrorRed
import edu.strathmore.pricing.ui.theme.MinTouchTarget
import edu.strathmore.pricing.ui.theme.PricingSpacing

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
            tint = ErrorRed,
        )
        Box(modifier = Modifier.padding(start = PricingSpacing.ExtraSmall)) {
            Text(text = message, color = ErrorRed, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
