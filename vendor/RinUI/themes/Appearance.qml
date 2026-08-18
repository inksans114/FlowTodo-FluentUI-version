pragma Singleton
import QtQuick 2.15
import "../themes"

QtObject {
    id: root

    readonly property var themeColors: Theme.currentTheme !== null && Theme.currentTheme !== undefined
    ? Theme.currentTheme.appearance
    : undefined

    // JS Proxy 模拟动态属性访问
    readonly property var proxy: (function() {
        if (typeof Proxy === "undefined") {
            console.warn("Proxy is not supported in this QML environment.")
            return {}
        }

        return new Proxy({}, {
            get(target, prop) {
                if (root.themeColors && prop in root.themeColors) {
                    return root.themeColors[prop]
                }
                return undefined
            },
            has(target, prop) {
                return root.themeColors && prop in root.themeColors
            }
        })
    })()

    // Sample: Appearance.get("controlColor") 或 Colors.proxy.controlColor
    function get(name) {
        return root.proxy[name]
    }
}
