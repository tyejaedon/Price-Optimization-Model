package dev.tyejaedon.pricing.designsystem

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Immutable
data class OneUiGlassColors(
    val isDark: Boolean,
    val ambientBaseTop: Color,
    val ambientBaseBottom: Color,
    val ambientOrbPrimary: Color,
    val ambientOrbSecondary: Color,
    val ambientOrbTertiary: Color,
    val glassSurfaceTop: Color,
    val glassSurfaceBottom: Color,
    val glassElevatedTop: Color,
    val glassElevatedBottom: Color,
    val specularRimTop: Color,
    val specularRimBottom: Color,
    val elevatedRimTop: Color,
    val elevatedRimBottom: Color,
    val recessedWellFill: Color,
    val recessedWellBorder: Color,
    val insetDivider: Color,
    val primaryAccent: Color,
    val primaryAccentDeep: Color,
    val secondaryAccent: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val textMuted: Color,
    val successTint: Color,
    val warningTint: Color,
    val errorTint: Color,
    val infoTint: Color,
) {
    val ambientBackgroundBrush: Brush
        get() = Brush.verticalGradient(listOf(ambientBaseTop, ambientBaseBottom))

    val glassCardBrush: Brush
        get() = Brush.verticalGradient(listOf(glassSurfaceTop, glassSurfaceBottom))

    val glassElevatedBrush: Brush
        get() = Brush.verticalGradient(listOf(glassElevatedTop, glassElevatedBottom))

    val specularRimBrush: Brush
        get() = Brush.verticalGradient(listOf(specularRimTop, specularRimBottom))

    val elevatedRimBrush: Brush
        get() = Brush.verticalGradient(listOf(elevatedRimTop, elevatedRimBottom))

    val primaryPillBrush: Brush
        get() = Brush.horizontalGradient(listOf(Color(0xFF3E8BFF), Color(0xFF6366F1)))
}

val DarkOneUiGlassColors =
    OneUiGlassColors(
        isDark = true,
        ambientBaseTop = Color(0xFF0A0C10),
        ambientBaseBottom = Color(0xFF121620),
        ambientOrbPrimary = Color(0xFF3B82F6).copy(alpha = 0.16f),
        ambientOrbSecondary = Color(0xFF6366F1).copy(alpha = 0.14f),
        ambientOrbTertiary = Color(0xFF06B6D4).copy(alpha = 0.10f),
        glassSurfaceTop = Color(0xFF232836).copy(alpha = 0.62f),
        glassSurfaceBottom = Color(0xFF181C26).copy(alpha = 0.50f),
        glassElevatedTop = Color(0xFF2A3142).copy(alpha = 0.84f),
        glassElevatedBottom = Color(0xFF1B202C).copy(alpha = 0.78f),
        specularRimTop = Color.White.copy(alpha = 0.28f),
        specularRimBottom = Color.White.copy(alpha = 0.06f),
        elevatedRimTop = Color.White.copy(alpha = 0.36f),
        elevatedRimBottom = Color.White.copy(alpha = 0.10f),
        recessedWellFill = Color.White.copy(alpha = 0.06f),
        recessedWellBorder = Color.White.copy(alpha = 0.12f),
        insetDivider = Color.White.copy(alpha = 0.08f),
        primaryAccent = Color(0xFF3B82F6),
        primaryAccentDeep = Color(0xFF2563EB),
        secondaryAccent = Color(0xFF34D399),
        textPrimary = Color(0xFFF8FAFC),
        textSecondary = Color(0xFFCBD5E1),
        textMuted = Color(0xFF94A3B8),
        successTint = Color(0xFF34D399),
        warningTint = Color(0xFFFBBF24),
        errorTint = Color(0xFFF87171),
        infoTint = Color(0xFF60A5FA),
    )

val LightOneUiGlassColors =
    OneUiGlassColors(
        isDark = false,
        ambientBaseTop = Color(0xFFF2F4F8),
        ambientBaseBottom = Color(0xFFE6EAF2),
        ambientOrbPrimary = Color(0xFF3B82F6).copy(alpha = 0.12f),
        ambientOrbSecondary = Color(0xFF8B5CF6).copy(alpha = 0.10f),
        ambientOrbTertiary = Color(0xFF10B981).copy(alpha = 0.09f),
        glassSurfaceTop = Color.White.copy(alpha = 0.78f),
        glassSurfaceBottom = Color.White.copy(alpha = 0.58f),
        glassElevatedTop = Color.White.copy(alpha = 0.90f),
        glassElevatedBottom = Color(0xFFF8FAFC).copy(alpha = 0.80f),
        specularRimTop = Color.White.copy(alpha = 0.85f),
        specularRimBottom = Color.White.copy(alpha = 0.25f),
        elevatedRimTop = Color.White.copy(alpha = 0.95f),
        elevatedRimBottom = Color.White.copy(alpha = 0.40f),
        recessedWellFill = Color(0xFF0F172A).copy(alpha = 0.05f),
        recessedWellBorder = Color(0xFF0F172A).copy(alpha = 0.10f),
        insetDivider = Color(0xFF0F172A).copy(alpha = 0.08f),
        primaryAccent = Color(0xFF2563EB),
        primaryAccentDeep = Color(0xFF1D4ED8),
        secondaryAccent = Color(0xFF059669),
        textPrimary = Color(0xFF0F172A),
        textSecondary = Color(0xFF334155),
        textMuted = Color(0xFF64748B),
        successTint = Color(0xFF047857),
        warningTint = Color(0xFFB45309),
        errorTint = Color(0xFFB91C1C),
        infoTint = Color(0xFF1D4ED8),
    )

val LocalOneUiGlassColors = staticCompositionLocalOf { LightOneUiGlassColors }

object OneUiShapes {
    val OuterContainer: Shape = RoundedCornerShape(26.dp)
    val BottomSheet: Shape = RoundedCornerShape(28.dp)
    val InnerCard: Shape = RoundedCornerShape(18.dp)
    val InputWell: Shape = RoundedCornerShape(16.dp)
    val Pill: Shape = CircleShape

    val Material =
        Shapes(
            extraSmall = RoundedCornerShape(12.dp),
            small = RoundedCornerShape(16.dp),
            medium = RoundedCornerShape(20.dp),
            large = RoundedCornerShape(24.dp),
            extraLarge = RoundedCornerShape(28.dp),
        )
}

object OneUiSpacing {
    val ExtraSmall = 4.dp
    val Small = 8.dp
    val Medium = 16.dp
    val CardPadding = 20.dp
    val Large = 24.dp
    val ExtraLarge = 32.dp
    val DockHorizontal = 20.dp
    val MinTouchTarget = 48.dp
    val InputMinHeight = 52.dp
}

object OneUiMotion {
    const val PRESS_SCALE = 0.97f
    val PressSpring = spring<Float>(dampingRatio = 0.75f, stiffness = 500f)
    val ExpandSpring = spring<IntSize>(dampingRatio = 0.82f, stiffness = 380f)
    val TransitionTween = tween<Float>(durationMillis = 280, easing = FastOutSlowInEasing)
    val DockSlideSpring = spring<Float>(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = 400f)
}

object OneUiTypography {
    val DisplayLarge =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Bold,
            fontSize = 34.sp,
            lineHeight = 40.sp,
            letterSpacing = (-0.5).sp,
        )
    val HeadlineMedium =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Bold,
            fontSize = 26.sp,
            lineHeight = 32.sp,
            letterSpacing = (-0.4).sp,
        )
    val TitleMedium =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.SemiBold,
            fontSize = 18.sp,
            lineHeight = 24.sp,
            letterSpacing = (-0.2).sp,
        )
    val BodyLarge =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Normal,
            fontSize = 15.sp,
            lineHeight = 22.sp,
        )
    val BodyMedium =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.Medium,
            fontSize = 14.sp,
            lineHeight = 20.sp,
        )
    val LabelLarge =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.SemiBold,
            fontSize = 14.sp,
            lineHeight = 18.sp,
        )
    val LabelSmall =
        TextStyle(
            fontFamily = FontFamily.SansSerif,
            fontWeight = FontWeight.SemiBold,
            fontSize = 12.sp,
            lineHeight = 16.sp,
            letterSpacing = 0.5.sp,
        )

    val Material =
        Typography(
            displayLarge = DisplayLarge,
            displayMedium = DisplayLarge,
            displaySmall = HeadlineMedium,
            headlineLarge = DisplayLarge,
            headlineMedium = HeadlineMedium,
            headlineSmall = TitleMedium,
            titleLarge = TitleMedium,
            titleMedium = TitleMedium,
            titleSmall = LabelLarge,
            bodyLarge = BodyLarge,
            bodyMedium = BodyMedium,
            bodySmall = LabelSmall,
            labelLarge = LabelLarge,
            labelMedium = BodyMedium,
            labelSmall = LabelSmall,
        )
}
