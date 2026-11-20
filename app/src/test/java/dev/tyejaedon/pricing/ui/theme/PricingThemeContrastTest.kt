package dev.tyejaedon.pricing.ui.theme

import androidx.compose.ui.graphics.Color
import com.google.common.truth.Truth.assertThat
import dev.tyejaedon.pricing.designsystem.DarkOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.LightOneUiGlassColors
import org.junit.Test
import kotlin.math.pow

class PricingThemeContrastTest {
    @Test
    fun `text colors meet WCAG AA contrast on their theme surfaces`() {
        assertThat(contrastRatio(PrimaryNavy, SurfaceLight)).isAtLeast(4.5)
        assertThat(contrastRatio(OnSurfaceMutedLight, SurfaceLight)).isAtLeast(4.5)
        assertThat(contrastRatio(ErrorRed, SurfaceLight)).isAtLeast(4.5)
        assertThat(contrastRatio(OnSurfaceMutedDark, SurfaceDark)).isAtLeast(4.5)
        assertThat(contrastRatio(ErrorRedDark, SurfaceDark)).isAtLeast(4.5)
        assertThat(contrastRatio(WarningAmber, SurfaceLight)).isAtLeast(4.5)
        assertThat(contrastRatio(WarningAmberDark, SurfaceDark)).isAtLeast(4.5)
    }

    @Test
    fun `accent color meets non-text contrast in light and dark themes`() {
        assertThat(contrastRatio(AccentMint, SurfaceLight)).isAtLeast(3.0)
        assertThat(contrastRatio(AccentMint, SurfaceDark)).isAtLeast(3.0)
    }

    @Test
    fun `one ui glass text colors meet WCAG AA contrast on ambient bases`() {
        assertThat(contrastRatio(LightOneUiGlassColors.textPrimary, LightOneUiGlassColors.ambientBaseBottom)).isAtLeast(4.5)
        assertThat(contrastRatio(LightOneUiGlassColors.textSecondary, LightOneUiGlassColors.ambientBaseBottom)).isAtLeast(4.5)
        assertThat(contrastRatio(LightOneUiGlassColors.errorTint, LightOneUiGlassColors.ambientBaseBottom)).isAtLeast(4.5)
        assertThat(contrastRatio(DarkOneUiGlassColors.textPrimary, DarkOneUiGlassColors.ambientBaseTop)).isAtLeast(4.5)
        assertThat(contrastRatio(DarkOneUiGlassColors.textSecondary, DarkOneUiGlassColors.ambientBaseTop)).isAtLeast(4.5)
        assertThat(contrastRatio(DarkOneUiGlassColors.errorTint, DarkOneUiGlassColors.ambientBaseTop)).isAtLeast(4.5)
    }

    private fun contrastRatio(
        foreground: Color,
        background: Color,
    ): Double {
        val foregroundLuminance = luminance(foreground)
        val backgroundLuminance = luminance(background)
        return (maxOf(foregroundLuminance, backgroundLuminance) + 0.05) /
            (minOf(foregroundLuminance, backgroundLuminance) + 0.05)
    }

    private fun luminance(color: Color): Double {
        fun channel(value: Float): Double {
            val normalized = value.toDouble()
            return if (normalized <= 0.04045) {
                normalized / 12.92
            } else {
                ((normalized + 0.055) / 1.055).pow(2.4)
            }
        }
        return 0.2126 * channel(color.red) + 0.7152 * channel(color.green) + 0.0722 * channel(color.blue)
    }
}
