package dev.tyejaedon.pricing.ui.theme

import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.designsystem.OneUiShapes

val PricingShapes = OneUiShapes.Material

/** Spacing tokens so screens never hardcode raw `dp` literals (issue #140). */
object PricingSpacing {
    val ExtraSmall = 4.dp
    val Small = 8.dp
    val Medium = 16.dp
    val CardPadding = 20.dp
    val Large = 24.dp
    val ExtraLarge = 32.dp
    val RangeIndicatorHeight = 10.dp
    val ComparableRow = 96.dp
}

/** Minimum touch target enforced on every interactive composable (WCAG 2.5.5 / Android a11y guidance). */
val MinTouchTarget = 48.dp
