package dev.tyejaedon.pricing.ui.theme

import dev.tyejaedon.pricing.designsystem.OneUiTypography

/**
 * Type scale used across the pricing shell, aligned with [OneUiTypography]. Sizes are specified
 * in `sp` (never `dp`) so system font-scale accessibility applies correctly (issue #140).
 */
object PricingTypography {
    val Headline = OneUiTypography.DisplayLarge
    val Title = OneUiTypography.TitleMedium
    val Body = OneUiTypography.BodyLarge
    val Label = OneUiTypography.LabelLarge
    val Caption = OneUiTypography.LabelSmall

    val Material = OneUiTypography.Material
}
