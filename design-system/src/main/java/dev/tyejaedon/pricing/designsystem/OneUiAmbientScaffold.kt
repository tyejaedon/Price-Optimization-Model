package dev.tyejaedon.pricing.designsystem

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.TopAppBarScrollBehavior
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.text.style.TextOverflow
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.haze

@Composable
fun OneUiGlassTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val glassColors = if (darkTheme) DarkOneUiGlassColors else LightOneUiGlassColors
    val colorScheme =
        if (darkTheme) {
            darkColorScheme(
                primary = glassColors.primaryAccent,
                onPrimary = Color.White,
                secondary = glassColors.secondaryAccent,
                onSecondary = Color(0xFF042F2E),
                tertiary = Color(0xFF818CF8),
                background = glassColors.ambientBaseTop,
                onBackground = glassColors.textPrimary,
                surface = glassColors.ambientBaseBottom,
                onSurface = glassColors.textPrimary,
                onSurfaceVariant = glassColors.textSecondary,
                error = glassColors.errorTint,
                outline = glassColors.recessedWellBorder,
            )
        } else {
            lightColorScheme(
                primary = glassColors.primaryAccent,
                onPrimary = Color.White,
                secondary = glassColors.secondaryAccent,
                onSecondary = Color.White,
                tertiary = Color(0xFF6366F1),
                background = glassColors.ambientBaseTop,
                onBackground = glassColors.textPrimary,
                surface = glassColors.ambientBaseBottom,
                onSurface = glassColors.textPrimary,
                onSurfaceVariant = glassColors.textSecondary,
                error = glassColors.errorTint,
                outline = glassColors.recessedWellBorder,
            )
        }

    CompositionLocalProvider(LocalOneUiGlassColors provides glassColors) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = OneUiTypography.Material,
            shapes = OneUiShapes.Material,
            content = content,
        )
    }
}

/**
 * Full-bleed ambient canvas with deep gradient base and soft oversized radial light orbs so
 * foreground glassmorphic layers have color and depth to refract.
 */
@Composable
fun OneUiAmbientCanvas(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    val hazeState = remember { HazeState() }

    Box(modifier = modifier.fillMaxSize()) {
        Box(
            modifier =
                Modifier
                    .fillMaxSize()
                    .haze(state = hazeState)
                    .background(glass.ambientBackgroundBrush),
        ) {
            Canvas(modifier = Modifier.fillMaxSize()) {
                val width = size.width
                val height = size.height

                drawCircle(
                    brush =
                        Brush.radialGradient(
                            colors = listOf(glass.ambientOrbPrimary, Color.Transparent),
                            center = Offset(width * 0.15f, height * 0.14f),
                            radius = width * 0.85f,
                        ),
                    center = Offset(width * 0.15f, height * 0.14f),
                    radius = width * 0.85f,
                )
                drawCircle(
                    brush =
                        Brush.radialGradient(
                            colors = listOf(glass.ambientOrbSecondary, Color.Transparent),
                            center = Offset(width * 0.88f, height * 0.42f),
                            radius = width * 0.75f,
                        ),
                    center = Offset(width * 0.88f, height * 0.42f),
                    radius = width * 0.75f,
                )
                drawCircle(
                    brush =
                        Brush.radialGradient(
                            colors = listOf(glass.ambientOrbTertiary, Color.Transparent),
                            center = Offset(width * 0.25f, height * 0.86f),
                            radius = width * 0.70f,
                        ),
                    center = Offset(width * 0.25f, height * 0.86f),
                    radius = width * 0.70f,
                )
            }
        }

        CompositionLocalProvider(LocalHazeState provides hazeState) {
            Box(modifier = Modifier.fillMaxSize(), content = content)
        }
    }
}

/**
 * Samsung One UI ergonomic scaffold:
 * - Top 30–35% Viewing Zone via collapsing [LargeTopAppBar] with exitUntilCollapsedScrollBehavior.
 * - Bottom 65–70% Interaction Zone with optional floating frosted navigation dock.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OneUiGlassScaffold(
    title: String,
    modifier: Modifier = Modifier,
    scrollBehavior: TopAppBarScrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(),
    navigationIcon: @Composable () -> Unit = {},
    actions: @Composable RowScope.() -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    OneUiAmbientCanvas(modifier = modifier) {
        Scaffold(
            modifier =
                Modifier
                    .fillMaxSize()
                    .nestedScroll(scrollBehavior.nestedScrollConnection),
            containerColor = Color.Transparent,
            contentColor = glass.textPrimary,
            topBar = {
                LargeTopAppBar(
                    title = {
                        Text(
                            text = title,
                            style =
                                if (scrollBehavior.state.collapsedFraction > 0.5f) {
                                    MaterialTheme.typography.titleLarge
                                } else {
                                    MaterialTheme.typography.displayLarge
                                },
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    navigationIcon = navigationIcon,
                    actions = actions,
                    scrollBehavior = scrollBehavior,
                    colors =
                        TopAppBarDefaults.largeTopAppBarColors(
                            containerColor = Color.Transparent,
                            scrolledContainerColor =
                                if (glass.isDark) {
                                    glass.ambientBaseTop.copy(alpha = 0.72f)
                                } else {
                                    glass.ambientBaseTop.copy(alpha = 0.80f)
                                },
                            titleContentColor = glass.textPrimary,
                            navigationIconContentColor = glass.textPrimary,
                            actionIconContentColor = glass.textPrimary,
                        ),
                )
            },
            bottomBar = {
                Box(
                    modifier =
                        Modifier
                            .navigationBarsPadding()
                            .padding(horizontal = OneUiSpacing.DockHorizontal, vertical = OneUiSpacing.Small),
                ) {
                    bottomBar()
                }
            },
            content = content,
        )
    }
}
