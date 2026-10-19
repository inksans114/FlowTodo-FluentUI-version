"""Native account summary/detail navigation with isolated application data."""
from pathlib import Path
import faulthandler

faulthandler.dump_traceback_later(55, exit=True)
source = Path(__file__).with_name("focus_preview.py").read_text(encoding="utf-8").split("QTest.qWait(500)")[0]
source = source.replace('os.environ["LOCALAPPDATA"] = DATA.name', 'os.environ["LOCALAPPDATA"] = DATA.name\nos.environ["FLOWTODO_DATA_DIR"] = str(Path(DATA.name) / "data")\nos.environ["FLOWTODO_RINUI_CONFIG_DIR"] = str(Path(DATA.name) / "RinUI/config")')
exec(compile(source, str(Path(__file__).with_name("focus_preview.py")), "exec"))
from datetime import date, timedelta


def control(name):
    def visit(item):
        if item.objectName() == name and item.isVisible():
            return item
        for child in item.childItems():
            found = visit(child)
            if found is not None:
                return found
    result = visit(root.contentItem())
    assert result is not None, name + "\n" + "\n".join(warnings)
    return result


def qml(item, code):
    expression = QQmlExpression(window.engine.rootContext(), item, code)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result


def click(name):
    item = control(name)
    qml(item, "(function(){var p=parent;while(p){if(p.contentY!==undefined && p.contentItem){p.contentY=Math.max(0,Math.min(p.contentHeight-p.height,mapToItem(p.contentItem,0,0).y-80));break;}p=p.parent;}})()")
    QTest.qWait(250)
    root.grabWindow()
    point = item.mapToScene(item.boundingRect().center()).toPoint()
    assert 0 < point.x() < root.width() and 0 < point.y() < root.height(), (name, point)
    QTest.mouseMove(root, point)
    QTest.qWait(50)
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(400)


def route():
    return str(root.findChild(QObject, "MainNavigationView").property("currentPage"))


def top():
    qml(control("metricGrid"), "(function(){var p=parent;while(p){if(p.contentY!==undefined && p.contentItem){p.contentY=0;break;}p=p.parent;}})()")
    QTest.qWait(150)


QTest.qWait(500)
today = backend._today_key()
previous = (date.today() - timedelta(days=1)).isoformat()
backend.local_database = [{"id": i, "title": "已完成任务", "done": True} for i in range(1, 22)]
backend.renameAccount("专注探索者")
backend.stats_database.update({"totalFocusSeconds": 3030 * 60, "todayDate": today,
    "todayFocusSeconds": 25 * 60, "totalFocusSessions": 107, "todayFocusSessions": 1,
    "dailyFocusSeconds": {today: 1500, previous: 3000},
    "focusSessions": [{"id": "qa-session", "date": today, "seconds": 1500, "title": "阅读资料", "kind": "task"}]})
backend.statsChanged.emit()
items = root.property("navigationItems").toVariant()
assert len(items) == 6
assert all(not str(item["page"]).endswith("AccountOverview.qml") for item in items)

click("accountMenuButton")
click("accountProfileButton")
assert route().endswith("UserAccount.qml")
for name, expected in (("focusTotalCard", "3030 分钟"), ("focusTodayCard", "25 分钟"),
                       ("focusSessionsCard", "107"), ("tasksCompletedCard", "21")):
    assert control(name).property("value") == expected, (name, control(name).property("value"))
backend.stats_database["todayFocusSeconds"] = 1800
backend.statsChanged.emit()
QTest.qWait(100)
assert control("focusTodayCard").property("value") == "30 分钟"

top()
render("account-data-1180", 1180, 820)
click("accountFocusDataButton")
assert route().endswith("AccountOverview.qml")
detail = control("AccountOverview")
assert detail.property("title") == "我的专注数据"
assert len(detail.property("selectedFocusSessions").toVariant()) == 1
assert qml(detail, "focusSecondsFor(selectedDate)")[0] == 1500
assert detail.property("calendarCells").toVariant()
assert find_visual(detail, "metricGrid") is None, "Detail duplicates summary cards"
render("account-focus-details-1180", 1180, 820)
click("focusDataBackButton")
assert route().endswith("UserAccount.qml")

# Profile and service controls still work after the new section changes page height.
click("accountEditButton")
control("accountNickname").setProperty("text", "更新昵称")
click("accountSaveButton")
assert json.loads(backend.accountJson)["name"] == "更新昵称"
click("accountManageServiceButton")
assert route().endswith("AiSettings.qml")
open_page("UserAccount.qml")
QTest.qWait(400)

for width, mode in ((900, "Light"), (1600, "Light"), (1180, "Dark")):
    backend.setSetting("theme", mode.lower())
    evaluate("applySavedAppearance()")
    root.setWidth(width)
    root.setHeight(820)
    QTest.qWait(350)
    top()
    grid = control("metricGrid")
    assert grid.property("columns") == (4 if grid.width() >= 900 else 2)
    for name in ("focusTotalCard", "focusTodayCard", "focusSessionsCard", "tasksCompletedCard"):
        card = control(name)
        assert card.width() > 180
        assert card.mapToScene(card.boundingRect().bottomRight()).x() <= root.width()
    render("account-data-" + str(width) + "-" + mode.lower(), width, 820)
    click("accountFocusDataButton")
    assert route().endswith("AccountOverview.qml")
    click("focusDataBackButton")
    assert route().endswith("UserAccount.qml")

assert not warnings, "\n".join(warnings)
print("PASS: profile entry, four live metrics, focus history, back, profile edit/service, 900/1180/1600 and dark mode.", flush=True)
backend.shutdown()
root.hide()
app.processEvents()
DATA.cleanup()
faulthandler.cancel_dump_traceback_later()
os._exit(0)
