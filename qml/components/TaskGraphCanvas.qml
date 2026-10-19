import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../i18n"

Item {
    id: graph
    objectName: "taskGraphCanvas"
    property var graphData: ({nodes: [], edges: [], collections: [], width: 720, height: 480})
    property string selectedKey: ""
    property string selectedEdge: ""
    property string pendingSource: ""
    property string linkType: "next"
    property string query: ""
    property real zoom: 0.85
    property point pointer: Qt.point(0, 0)
    property var collectionPreview: null
    signal connectRequested(string sourceKey, string targetKey, string kind)
    signal moveRequested(string key, real x, real y)
    signal collectionMoveRequested(string key, real x, real y)
    signal deleteRequested(string edgeId)
    readonly property color accent: Theme.currentTheme.colors.primaryColor
    readonly property color pairedColor: Theme.currentTheme.colors.systemSuccessColor
    clip: true
    activeFocusOnTab: true
    Accessible.name: I18n.t("任务关系图")
    Keys.onEscapePressed: { pendingSource = ""; selectedEdge = "" }
    Keys.onDeletePressed: if (selectedEdge.length) deleteRequested(selectedEdge)
    onGraphDataChanged: lines.requestPaint()
    onSelectedKeyChanged: lines.requestPaint()
    onSelectedEdgeChanged: lines.requestPaint()
    onPendingSourceChanged: lines.requestPaint()
    onPointerChanged: lines.requestPaint()
    onAccentChanged: lines.requestPaint()
    onPairedColorChanged: lines.requestPaint()
    onQueryChanged: lines.requestPaint()

    function itemFor(key) {
        for (var i = 0; i < nodes.count; i++) {
            var item = nodes.itemAt(i)
            if (item && item.modelData.key === key) return item
        }
        return null
    }
    function collectionFor(key) {
        for (var i = 0; i < collections.count; i++) {
            var item = collections.itemAt(i)
            if (item && item.modelData.key === key) return item
        }
        return null
    }
    function matches(node) {
        return !query.trim().length || (node.title + " " + node.collectionTitle).toLowerCase().indexOf(query.trim().toLowerCase()) >= 0
    }
    function selectTarget(key) {
        if (pendingSource && pendingSource !== key) {
            connectRequested(pendingSource, key, linkType)
            pendingSource = ""
        }
        selectedKey = key
        selectedEdge = ""
        forceActiveFocus()
    }
    function nodeAt(point) {
        for (var i = nodes.count - 1; i >= 0; i--) {
            var item = nodes.itemAt(i)
            if (item && point.x >= item.x - 14 && point.x <= item.x + item.width + 14
                && point.y >= item.y && point.y <= item.y + item.height) return item
        }
        return null
    }
    function curve(edge) {
        var a = itemFor(edge.source), b = itemFor(edge.target)
        if (!a || !b) return null
        if (edge.readonly) {
            var from = {x: a.x + a.width / 2, y: a.y + a.height}
            var to = {x: b.x + b.width / 2, y: b.y}
            var middle = (from.y + to.y) / 2
            return {p: from, q: to, c1: {x: from.x, y: middle}, c2: {x: to.x, y: middle}}
        }
        var p = {x: a.x + a.width, y: a.y + a.height / 2}
        var q = {x: b.x, y: b.y + b.height / 2}
        var bend = Math.max(72, Math.abs(q.x - p.x) * 0.45)
        if (b.x + b.width < a.x) {
            p = {x: a.x, y: a.y + a.height / 2}
            q = {x: b.x + b.width, y: b.y + b.height / 2}
            bend = Math.max(36, Math.abs(p.x - q.x) * 0.45)
            return {p: p, q: q, c1: {x: p.x - bend, y: p.y}, c2: {x: q.x + bend, y: q.y}}
        }
        return {p: p, q: q, c1: {x: p.x + bend, y: p.y}, c2: {x: q.x - bend, y: q.y}}
    }
    function pointOn(c, t) {
        var u = 1 - t
        return Qt.point(u*u*u*c.p.x + 3*u*u*t*c.c1.x + 3*u*t*t*c.c2.x + t*t*t*c.q.x,
                        u*u*u*c.p.y + 3*u*u*t*c.c1.y + 3*u*t*t*c.c2.y + t*t*t*c.q.y)
    }
    function hitEdge(point) {
        var closest = "", distance = 14 / zoom
        ;(graphData.edges || []).forEach(function(edge) {
            if (edge.readonly) return
            var c = curve(edge)
            if (!c) return
            for (var j = 0; j <= 50; j++) {
                var p = pointOn(c, j / 50)
                var d = Math.sqrt(Math.pow(p.x - point.x, 2) + Math.pow(p.y - point.y, 2))
                if (d < distance) { distance = d; closest = edge.id }
            }
        })
        return closest
    }
    function centerOn(key) {
        var item = itemFor(key)
        if (!item) return
        viewport.contentX = Math.max(0, Math.min(viewport.contentWidth - viewport.width, (item.x + item.width / 2) * zoom - viewport.width / 2))
        viewport.contentY = Math.max(0, Math.min(viewport.contentHeight - viewport.height, (item.y + item.height / 2) * zoom - viewport.height / 2))
    }

    Rectangle { anchors.fill: parent; color: Theme.currentTheme.colors.backgroundColor; radius: 8 }
    Flickable {
        id: viewport
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: Math.max(width, scene.width * graph.zoom)
        contentHeight: Math.max(height, scene.height * graph.zoom)
        ScrollBar.vertical: ScrollBar {}
        ScrollBar.horizontal: ScrollBar {}
        Item {
            id: scene
            width: Math.max(Number(graph.graphData.width || 720), graph.collectionPreview ? graph.collectionPreview.x + graph.collectionPreview.width + 80 : 0)
            height: Math.max(Number(graph.graphData.height || 480), graph.collectionPreview ? graph.collectionPreview.y + graph.collectionPreview.height + 80 : 0)
            scale: graph.zoom
            transformOrigin: Item.TopLeft
            Repeater {
                id: collections
                model: graph.graphData.collections || []
                delegate: Rectangle {
                    required property var modelData
                    objectName: "relationCollection_" + modelData.key
                    x: modelData.x; y: modelData.y
                    width: modelData.width; height: modelData.height
                    color: Theme.currentTheme.colors.cardColor
                    radius: Theme.currentTheme.appearance.cardRadius
                    border.color: Theme.currentTheme.colors.dividerBorderColor
                    RowLayout {
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                        anchors.margins: 18
                        Icon { name: modelData.key.indexOf("project:") === 0 ? "ic_fluent_board_20_regular" : modelData.key.indexOf("group:") === 0 ? "ic_fluent_list_20_regular" : "ic_fluent_folder_20_regular"; size: 18; color: graph.accent }
                        Text { Layout.fillWidth: true; text: I18n.t(modelData.title); typography: Typography.BodyStrong; elide: Text.ElideRight }
                        Text { text: graph.graphData.nodes.filter(function(n) { return n.collection === modelData.key }).length; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor }
                    }
                }
            }
            Canvas {
                id: lines
                anchors.fill: parent
                renderStrategy: Canvas.Cooperative
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    function draw(c, color, dashed, selected, arrow) {
                        ctx.strokeStyle = color
                        ctx.lineWidth = selected ? 3.5 : 2
                        ctx.setLineDash(dashed ? [7, 5] : [])
                        ctx.beginPath(); ctx.moveTo(c.p.x, c.p.y)
                        ctx.bezierCurveTo(c.c1.x, c.c1.y, c.c2.x, c.c2.y, c.q.x, c.q.y); ctx.stroke()
                        ctx.setLineDash([])
                        if (arrow) {
                            var dx = c.q.x - c.c2.x, dy = c.q.y - c.c2.y
                            var size = Math.max(1, Math.sqrt(dx * dx + dy * dy)); dx /= size; dy /= size
                            ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(c.q.x, c.q.y)
                            ctx.lineTo(c.q.x - 10 * dx + 5 * dy, c.q.y - 10 * dy - 5 * dx)
                            ctx.lineTo(c.q.x - 10 * dx - 5 * dy, c.q.y - 10 * dy + 5 * dx); ctx.closePath(); ctx.fill()
                        }
                    }
                    ;(graph.graphData.edges || []).forEach(function(edge) {
                        var c = graph.curve(edge)
                        if (!c) return
                        var emphasis = edge.id === graph.selectedEdge || edge.source === graph.selectedKey || edge.target === graph.selectedKey
                        ctx.globalAlpha = emphasis ? 1 : 0.5
                        draw(c, edge.type === "next" ? graph.accent : graph.pairedColor, edge.type === "together", emphasis, edge.type === "next")
                    })
                    ctx.globalAlpha = 1
                    var source = graph.itemFor(graph.pendingSource)
                    if (source) {
                        var p = {x: source.x + source.width, y: source.y + source.height / 2}, q = graph.pointer
                        draw({p:p, q:q, c1:{x:p.x + 80,y:p.y}, c2:{x:q.x - 80,y:q.y}}, graph.linkType === "next" ? graph.accent : graph.pairedColor, true, true, graph.linkType === "next")
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: function(mouse) { graph.selectedEdge = graph.hitEdge(Qt.point(mouse.x, mouse.y)); if (!graph.selectedEdge) graph.selectedKey = ""; graph.forceActiveFocus() }
                    onPositionChanged: function(mouse) { if (graph.pendingSource) graph.pointer = Qt.point(mouse.x, mouse.y) }
                }
            }
            Repeater {
                id: nodes
                model: graph.graphData.nodes || []
                onItemAdded: lines.requestPaint()
                delegate: Item {
                    id: node
                    required property var modelData
                    objectName: "relationNode_" + modelData.key
                    x: modelData.x; y: modelData.y
                    width: modelData.width; height: modelData.height
                    opacity: graph.matches(modelData) ? 1 : 0.25
                    z: graph.selectedKey === modelData.key ? 2 : 1
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.title + " · " + modelData.collectionTitle
                    Accessible.onPressAction: graph.selectTarget(modelData.key)
                    Keys.onReturnPressed: graph.selectTarget(modelData.key)
                    Keys.onSpacePressed: graph.selectTarget(modelData.key)
                    onXChanged: lines.requestPaint()
                    onYChanged: lines.requestPaint()
                    Rectangle {
                        anchors.fill: parent
                        radius: Theme.currentTheme.appearance.cardRadius
                        color: Theme.currentTheme.colors.controlInputActiveColor
                        border.width: graph.selectedKey === node.modelData.key || node.activeFocus ? 2 : 1
                        border.color: graph.selectedKey === node.modelData.key || node.activeFocus ? graph.accent : Theme.currentTheme.colors.controlBorderColor
                        Rectangle { x: 0; y: 14; width: 3; height: parent.height - 28; radius: 1.5; color: node.modelData.done ? graph.pairedColor : graph.accent }
                    }
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 15
                        spacing: 5
                        Text { Layout.fillWidth: true; text: node.modelData.title; typography: Typography.BodyStrong; elide: Text.ElideRight; font.strikeout: node.modelData.done }
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: node.modelData.minutes > 0 ? node.modelData.minutes + I18n.t(" 分钟") : ""; typography: Typography.Caption; color: Theme.currentTheme.colors.textSecondaryColor; elide: Text.ElideRight }
                            Icon { visible: node.modelData.done; name: "ic_fluent_checkmark_circle_20_regular"; size: 16; color: graph.pairedColor }
                        }
                    }
                    MouseArea {
                        id: dragArea
                        anchors.fill: parent
                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        preventStealing: true
                        property point pressPoint
                        property point origin
                        property bool moved: false
                        onPressed: function(mouse) { pressPoint = mapToItem(scene, mouse.x, mouse.y); origin = Qt.point(node.x, node.y); moved = false; graph.selectedKey = node.modelData.key; graph.selectedEdge = "" }
                        onPositionChanged: function(mouse) {
                            if (!pressed) return
                            var point = mapToItem(scene, mouse.x, mouse.y)
                            var dx = point.x - pressPoint.x, dy = point.y - pressPoint.y
                            if (Math.abs(dx) + Math.abs(dy) < 4 && !moved) return
                            moved = true
                            var bucket = graph.graphData.collections.find(function(c) { return c.key === node.modelData.collection })
                            node.x = Math.max(bucket.x + 16, Math.min(bucket.x + bucket.width - node.width - 16, origin.x + dx))
                            node.y = Math.max(bucket.y + 58, Math.min(bucket.y + bucket.height - node.height - 16, origin.y + dy))
                        }
                        onReleased: {
                            if (moved) {
                                var bucket = graph.graphData.collections.find(function(c) { return c.key === node.modelData.collection })
                                graph.moveRequested(node.modelData.key, node.x - bucket.x, node.y - bucket.y)
                            }
                        }
                        onClicked: if (!moved) graph.selectTarget(node.modelData.key)
                    }
                    Rectangle {
                        x: -7; y: parent.height / 2 - 7; width: 14; height: 14; radius: 7
                        color: Theme.currentTheme.colors.controlInputActiveColor; border.width: 2; border.color: graph.accent
                        MouseArea { anchors.centerIn: parent; width: 28; height: 28; cursorShape: Qt.CrossCursor; onClicked: graph.selectTarget(node.modelData.key) }
                    }
                    Rectangle {
                        x: parent.width - 7; y: parent.height / 2 - 7; width: 14; height: 14; radius: 7
                        color: graph.pendingSource === node.modelData.key ? graph.accent : Theme.currentTheme.colors.controlInputActiveColor
                        border.width: 2; border.color: graph.accent
                        MouseArea {
                            anchors.centerIn: parent; width: 28; height: 28; cursorShape: Qt.CrossCursor; preventStealing: true
                            onPressed: function(mouse) { graph.pendingSource = node.modelData.key; graph.selectedKey = node.modelData.key; graph.pointer = mapToItem(scene, mouse.x, mouse.y) }
                            onPositionChanged: function(mouse) { if (pressed) graph.pointer = mapToItem(scene, mouse.x, mouse.y) }
                            onReleased: function(mouse) {
                                var target = graph.nodeAt(mapToItem(scene, mouse.x, mouse.y))
                                if (target && target.modelData.key !== node.modelData.key) graph.selectTarget(target.modelData.key)
                            }
                        }
                    }
                }
            }
            Repeater {
                model: graph.graphData.collections || []
                delegate: Item {
                    id: handle
                    required property var modelData
                    readonly property var frame: graph.collectionFor(modelData.key)
                    objectName: "relationCollectionHandle_" + modelData.key
                    x: frame ? frame.x : modelData.x
                    y: frame ? frame.y : modelData.y
                    width: modelData.width; height: 54; z: 5
                    Accessible.name: I18n.t("移动集合") + " · " + modelData.title
                    MouseArea {
                        anchors.fill: parent
                        preventStealing: true
                        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                        property point pressPoint
                        property point origin
                        property var childrenAtPress: []
                        property bool moved: false
                        onPressed: function(mouse) {
                            pressPoint = mapToItem(scene, mouse.x, mouse.y)
                            origin = Qt.point(handle.frame.x, handle.frame.y)
                            childrenAtPress = []
                            for (var i = 0; i < nodes.count; i++) {
                                var child = nodes.itemAt(i)
                                if (child && child.modelData.collection === handle.modelData.key)
                                    childrenAtPress.push({item: child, x: child.x, y: child.y})
                            }
                            moved = false
                        }
                        onPositionChanged: function(mouse) {
                            if (!pressed) return
                            var point = mapToItem(scene, mouse.x, mouse.y)
                            var dx = point.x - pressPoint.x, dy = point.y - pressPoint.y
                            if (Math.abs(dx) + Math.abs(dy) < 4 && !moved) return
                            moved = true
                            var x = Math.max(0, origin.x + dx), y = Math.max(0, origin.y + dy)
                            handle.frame.x = x; handle.frame.y = y
                            childrenAtPress.forEach(function(c) { c.item.x = c.x + x - origin.x; c.item.y = c.y + y - origin.y })
                            graph.collectionPreview = {x:x, y:y, width:handle.width, height:handle.modelData.height}
                            lines.requestPaint()
                        }
                        onReleased: {
                            graph.collectionPreview = null
                            if (moved) graph.collectionMoveRequested(handle.modelData.key, handle.frame.x, handle.frame.y)
                        }
                        onCanceled: {
                            handle.frame.x = origin.x; handle.frame.y = origin.y
                            childrenAtPress.forEach(function(c) { c.item.x = c.x; c.item.y = c.y })
                            graph.collectionPreview = null
                        }
                    }
                }
            }
        }
    }
    Frame {
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 14
        padding: 4
        contentItem: RowLayout {
            spacing: 2
            ToolButton { text: "−"; onClicked: graph.zoom = Math.max(0.35, graph.zoom - 0.1); Accessible.name: I18n.t("缩小") }
            Text { text: Math.round(graph.zoom * 100) + "%"; typography: Typography.Caption }
            ToolButton { text: "+"; onClicked: graph.zoom = Math.min(1.6, graph.zoom + 0.1); Accessible.name: I18n.t("放大") }
            ToolButton { icon.name: "ic_fluent_arrow_expand_20_regular"; ToolTip.text: I18n.t("适应宽度"); ToolTip.visible: hovered; onClicked: { graph.zoom = Math.max(0.35, Math.min(1, viewport.width / scene.width)); viewport.contentX = 0; viewport.contentY = 0 } }
        }
    }
    ColumnLayout {
        anchors.centerIn: parent
        visible: (graph.graphData.nodes || []).length === 0
        Icon { Layout.alignment: Qt.AlignHCenter; name: "ic_fluent_folder_20_regular"; size: 36; color: Theme.currentTheme.colors.textSecondaryColor }
        Text { text: I18n.t("先添加任务、任务流或项目"); typography: Typography.BodyStrong }
    }
}
