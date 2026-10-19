"""Render the screenshot-review pages with temporary data and assert geometry."""
from pathlib import Path

# Reuse the application's isolated offscreen harness, stopping before its tests.
source = Path(__file__).with_name('focus_preview.py').read_text(encoding='utf-8')
exec(compile(source.split('QTest.qWait(500)')[0], str(Path(__file__).with_name('focus_preview.py')), 'exec'))

def local_eval(item, code):
    from PySide6.QtQml import QQmlEngine
    expression = QQmlExpression(QQmlEngine.contextForObject(item), item, code)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result

def scroll_to(item):
    parent = item.parentItem()
    while parent and not parent.metaObject().indexOfProperty('contentY') >= 0:
        parent = parent.parentItem()
    if parent:
        point = item.mapToItem(parent.property('contentItem'), 0, 0)
        parent.setProperty('contentY', max(0, min(point.y() - 130, parent.property('contentHeight') - parent.height())))

QTest.qWait(500)
for width in (1600, 1180):
    root.setWidth(width)
    root.setHeight(1000)
    for name in ('AppSettings', 'IslandSettings', 'AccountOverview', 'FocusWorkspace'):
        print('Checking', name, width, flush=True)
        open_page(name + '.qml')
        QTest.qWait(450)
        component = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / 'qml/pages' / (name + '.qml'))))
        assert not component.isError(), '\n'.join(error.toString() for error in component.errors())
        if name == 'AppSettings':
            switch = find_visual(root.contentItem(), 'soundEnabled')
            assert switch and switch.width() >= switch.implicitWidth() - 1
            scroll_to(switch)
            combo = find_visual(root.contentItem(), 'closeBehavior')
            row = combo.parentItem()
            assert abs(row.width() - combo.x() - combo.width()) < 1, (row.width(), combo.x(), combo.width())
        if name == 'AccountOverview':
            page = find_visual(root.contentItem(), 'activitySection')
            while page and page.metaObject().indexOfProperty('stats') < 0:
                page = page.parentItem()
            assert page is not None, '\n'.join(warnings)
            local_eval(page, '''page.stats = {tasks: {done:20}, focus: {totalMinutes:2935, todayMinutes:67, totalSessions:81, dailyFocusSeconds:{}}};
                page.focusSessions = [{date:page.today, title:'自由专注', subtitle:'从一个小动作开始', seconds:540}, {date:page.today, title:'阅读文献', subtitle:'整理三个观点', seconds:1500}, {date:page.today, title:'自由专注', subtitle:'自由专注', seconds:30}]; page.rebuildCalendar()''')
            QTest.qWait(250)
            grid = find_visual(root.contentItem(), 'metricGrid')
            cards = [child for child in grid.childItems() if child.width() > 20]
            widths = [round(card.width(), 1) for card in cards]
            assert max(widths) - min(widths) < 1, widths
            scroller = find_visual(root.contentItem(), 'activityScroller')
            heatmap = find_visual(root.contentItem(), 'activityGrid')
            assert heatmap.width() >= scroller.width() - 1
            assert heatmap.height() > 50 and len(page.property('monthMarkers').toVariant()) >= 6
        if name == 'FocusWorkspace':
            switch = find_visual(root.contentItem(), 'immersiveSwitch')
            assert switch and switch.isVisible()
            switch.setProperty('checked', True)
            local_eval(switch, 'page.immersive = true')
            QTest.qWait(150)
            assert find_visual(root.contentItem(), 'immersiveScenes').isVisible()
        render('review-' + name + '-' + str(width), width, 1000)
errors = [warning for warning in warnings if any(word in warning for word in ('ReferenceError', 'TypeError', 'Cannot assign', 'Binding loop', 'Error:'))]
assert not errors, '\n'.join(errors)
backend.shutdown()
root.hide()
app.processEvents()
print(json.dumps({'ok': True, 'warnings': warnings, 'renders': str(output)}, ensure_ascii=False))
DATA.cleanup()
# The harness uses native offscreen windows; avoid late Qt/Python teardown
# ordering after explicitly shutting down the backend and disposing its data.
sys.stdout.flush()
os._exit(0)
