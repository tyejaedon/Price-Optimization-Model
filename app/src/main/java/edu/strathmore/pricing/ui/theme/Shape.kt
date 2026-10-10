package edu.strathmore.pricing.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

val PricingShapes =
    Shapes(
        extraSmall = RoundedCornerShape(4.dp),
        small = RoundedCornerShape(8.dp),
        medium = RoundedCornerShape(12.dp),
        large = RoundedCornerShape(16.dp),
        extraLarge = RoundedCornerShape(28.dp),
    )

/** Spacing tokens so screens never hardcode raw `dp` literals (issue #140). */
object PricingSpacing {
    val ExtraSmall = 4.dp
    val Small = 8.dp
    val Medium = 16.dp
    val Large = 24.dp
    val ExtraLarge = 32.dp
}

/** Minimum touch target enforced on every interactive composable (WCAG 2.5.5 / Android a11y guidance). */
val MinTouchTarget = 48.dp
