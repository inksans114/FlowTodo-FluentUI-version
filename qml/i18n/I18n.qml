pragma Singleton
import QtQuick

// Simplified Chinese is the source language: every UI string in the QML tree is
// written in zh_CN and used as the lookup key. `I18nBridge` is the Python-side
// translator injected into every QML engine, so `language` changes propagate to
// each binding that calls `t()`.
QtObject {
    id: root

    readonly property bool ready: typeof I18nBridge !== "undefined" && I18nBridge !== null
    readonly property string language: ready ? I18nBridge.language : "zh_CN"
    readonly property var table: ready ? I18nBridge.table : ({})

    function t(source) {
        if (root.language === "zh_CN")
            return source
        var value = root.table[source]
        return value === undefined ? source : value
    }
}
