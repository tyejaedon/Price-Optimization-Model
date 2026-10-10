package edu.strathmore.pricing.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val LightColors = lightColorScheme(
    primary = PrimaryNavy,
    secondary = AccentMint,
    tertiary = AccentLavender,
    background = SurfaceLight,
    surface = SurfaceLight,
    error = ErrorRed,
)

private val DarkColors = darkColorScheme(
    primary = PrimaryNavyLight,
    secondary = AccentMint,
    tertiary = AccentLavender,
    background = SurfaceDark,
    surface = SurfaceDark,
    error = ErrorRed,
)

/**
 * Single theming entry point for the whole app (issue #140). Every screen must be wrapped in
 * [PricingTheme] instead of defining ad hoc colors/typography/shapes.
 *
 * @param dynamicColor opt-in to Material You dynamic color on Android 12+; disabled by default so
 *   Compose previews and screenshot tests stay deterministic across devices.
 */
@Composable
fun PricingTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }

    MaterialTheme(
        colorScheme = colorScheme,
        shapes = PricingShapes,
        content = content,
    )
}
