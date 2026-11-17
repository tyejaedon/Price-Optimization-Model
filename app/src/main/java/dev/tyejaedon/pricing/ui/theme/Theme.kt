package dev.tyejaedon.pricing.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import dev.tyejaedon.pricing.designsystem.OneUiGlassTheme

/**
 * Single theming entry point for the whole app (issue #140), upgraded to the Samsung One UI 6/7
 * Glassmorphic Design System ([OneUiGlassTheme]).
 */
@Composable
fun PricingTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    @Suppress("UNUSED_PARAMETER") dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    OneUiGlassTheme(
        darkTheme = darkTheme,
        content = content,
    )
}
