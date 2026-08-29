# Theme tokens

The app uses RinUI's light/dark theme objects; do not introduce a second CSS token system.

- Font: system QML font with RinUI `Typography` roles (`Caption` 12, `Body` 14, `BodyLarge` 18, `Subtitle` 20, `Title` 28, `TitleLarge` 40, `Display` 68).
- Core light background: `#F3F3F3`; acrylic `#F9F9F9`; text `#1b1b1b`; secondary text is black at 60.63% alpha; card/control white at ~70% alpha.
- Core dark background: `#202020`; acrylic `#2c2c2c`; text `#ffffff`; secondary text is white at 60.47% alpha; cards are white at ~5% alpha.
- Primary accent is runtime-selected through `Theme.setThemeColor`, default native theme accent is Material You (`#7054b8` fallback). Other accents: Fluent blue `#0f6cbd`, success `#0f7b0f`, critical `#c42b1c`, caution `#9d5d00`.
- Radius: window 7, button 5, small 3; border width 1; card shadow blur 4 / y 2; flyout blur 24 / y 8.
- Spacing in existing pages is compact: 4, 8, 10, 12, 14, 16, 18, 20, 34/36 page padding.

Primary source files: `vendor/RinUI/themes/light.qml`, `vendor/RinUI/themes/dark.qml`, `vendor/RinUI/themes/theme.qml`, `vendor/RinUI/utils/Typography.qml`.

