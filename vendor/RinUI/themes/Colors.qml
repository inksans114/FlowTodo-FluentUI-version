pragma Singleton
import QtQuick 2.15
import "../themes"

QtObject {
    id: root

    readonly property var themeColors: Theme.currentTheme !== null && Theme.currentTheme !== undefined
        ? Theme.currentTheme.colors
        : undefined

    // 明亮和暗色主题颜色，直接访问
    readonly property var light: Qt.createQmlObject("import '../themes'; Light {}", root).colors
    readonly property var dark: Qt.createQmlObject("import '../themes'; Dark {}", root).colors

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

    // Sample: Colors.get("controlColor") 或 Colors.proxy.controlColor
    function get(name) {
        return root.proxy[name]
    }
}
