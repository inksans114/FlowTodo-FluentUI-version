"""Exercise the native WebEngine studio with isolated user data."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import faulthandler
import traceback
from pathlib import Path

faulthandler.enable()
faulthandler.dump_traceback_later(90, repeat=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "vendor"), str(ROOT)]
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
DATA = tempfile.TemporaryDirectory(prefix="flowtodo-studio-qa-")
os.environ["LOCALAPPDATA"] = DATA.name
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-gpu-compositing --disable-smooth-scrolling"
if "--webgl" in sys.argv:
    # QA only: trusted local assets, for exercising shaders with SwiftShader.
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] += " --use-gl=angle --use-angle=swiftshader-webgl --enable-unsafe-swiftshader"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PySide6.QtCore import QEventLoop, QPoint, QTimer, Qt, QUrl
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlExpression, QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QSoundEffect
from RinUI import RinUIWindow
from compat_backend import RinUIBackend
from i18n_runtime import translator

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
for font in ("msyh.ttc", "segoeui.ttf", "seguisb.ttf"):
    QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / font))
backend = RinUIBackend()
backend._apply_focus_environment = lambda _options: None
backend._restore_focus_environment = lambda: None
backend._show_main_window = lambda: None
backend._minimize_main_window = lambda: None
backend.settings_database["language"] = "zh_CN"
backend.settings_database["focusWeatherMode"] = "off"  # QA never sends location.
window = RinUIWindow(shared_engine=False)
window.engine.rootContext().setContextProperty("Backend", backend)
window.engine.rootContext().setContextProperty("I18nBridge", translator())
warnings = []
window.engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
window.load(ROOT / "qml/Main.qml")
root = window.root_window
assert root is not None
backend.attach_native_window(root)
output = ROOT / ".superdesign/qa"
if "--webgl" in sys.argv:
    output = output / "webgl"
output.mkdir(parents=True, exist_ok=True)


def wait_ms(milliseconds):
    # QtTest.qWait drains posted events and can starve its own deadline while
    # offscreen WebEngine publishes continuous frames. Use a bounded event loop.
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        result = find(child, name)
        if result is not None:
            return result


def wait_until(check, message, timeout=12000):
    for _ in range(timeout // 100):
        if check():
            return
        wait_ms(100)
    raise AssertionError(message + "\n" + "\n".join(warnings))


def js(code):
    # The same trusted script snippets now go to the native page directly.
    box = {}
    script = json.loads(code.removeprefix("runJavaScript(")[:-1])
    view.page().runJavaScript(script, lambda result: box.update(done=True))
    wait_until(lambda: box.get("done"), "JS did not finish")
    wait_ms(200)


def probe(code):
    result = {}
    view.page().runJavaScript("JSON.stringify(" + code + ")", lambda value: result.update(value=value))
    wait_until(lambda: "value" in result, "Probe did not finish")
    return json.loads(result["value"])


def render(name):
    studio.showNormal()
    studio.resize(1280, 800)
    wait_ms(700)
    frame = studio.grab()
    assert not frame.isNull()
    assert frame.save(str(output / f"{name}.png"))


def visual_state(value):
    js("runJavaScript(" + json.dumps("window.flowFocus.update(" + json.dumps(value, ensure_ascii=False) + ")", ensure_ascii=False) + ")")


try:
    assert backend.startPomodoroFocus(-1, 1, 1, 2, 5, "阅读一篇文献，记下三个观点", False)
    assert backend.enterFocusStudio("tree")
    wait_ms(600)
    studio = backend._studio_window
    if studio is None:
        diagnostic = QQmlComponent(window.engine, QUrl.fromLocalFile(str(ROOT / "qml/FocusStudioWindow.qml")))
        raise AssertionError("Studio did not load: " + str([error.toString() for error in diagnostic.errors()]))
    assert studio.isFullScreen()
    studio.rain_sound.setMuted(True)  # Check playback without disturbing the user.
    wait_until(lambda: studio.rain_sound.status() == QSoundEffect.Ready, "Rain WAV did not load")
    assert not root.isVisible()
    island = next(iter(backend.island_windows.values()))
    assert not island.isVisible(), "Floating island overlays immersion"
    view = studio
    assert view is not None
    wait_until(lambda: view.loaded, "Local page did not finish loading")
    # A JS assertion reports through console as a QML signal, without changing the clock.
    assert probe("Boolean(window.flowFocus && window.flowFocus.connected)")
    assert not view.studio_page.console_errors, view.studio_page.console_errors
    occlusion = probe("window.FocusDepthRenderer.occlusionProbe()")
    if "--webgl" in sys.argv:
        assert occlusion["mode"] == "webgl-depth", "WebGL test environment did not create a context"
    assert occlusion["orderIndependent"] and occlusion["nearRed"] and occlusion["nearGreen"], occlusion
    island._deadline -= 35
    island._tick()
    backend._refresh_focus_snapshot()
    wait_ms(250)
    first_clock = probe("document.getElementById('timer').textContent")
    remaining = island.focus_snapshot()["remaining"]
    shown_minutes, shown_seconds = map(int, first_clock.split(":"))
    assert abs(shown_minutes * 60 + shown_seconds - remaining) <= 1, ("Web display differs from authoritative clock", first_clock, remaining)
    wait_ms(2200)
    second_clock = probe("document.getElementById('timer').textContent")
    assert second_clock != first_clock, "Web countdown is frozen"
    assert probe("window.focusScene3D.diagnostics().meshes") > 60
    render("studio-tree")
    js('runJavaScript("document.getElementById(\'pause\').click()")')
    assert backend.focus_journey.active["status"] == "paused", "WebChannel pause failed"
    paused = island.focus_snapshot()["remaining"]
    wait_ms(1100)
    assert island.focus_snapshot()["remaining"] == paused
    js('runJavaScript("document.getElementById(\'rain-sound\').click()")')
    assert backend.settings_database["focusRainSound"] and studio.rain_sound.isPlaying()
    assert studio.rain_sound.loopCount() == QSoundEffect.Infinite.value
    js('runJavaScript("document.getElementById(\'rain-volume\').value=35;document.getElementById(\'rain-volume\').dispatchEvent(new Event(\'input\'))")')
    wait_ms(350)
    wait_until(lambda: abs(studio.rain_sound.volume() - .35) < .001, "Volume setting did not reach native audio")
    wait_ms(11200)  # At least one complete sample loop, with the real timer paused.
    assert studio.rain_sound.isPlaying() and island.focus_snapshot()["remaining"] == paused
    js('runJavaScript("document.getElementById(\'rain-sound\').click()")')
    assert not studio.rain_sound.isPlaying()
    js('runJavaScript("document.getElementById(\'pause\').click()")')
    assert backend.focus_journey.active["status"] == "work", "WebChannel resume failed"
    js('runJavaScript("document.querySelector(\'[data-scene-button=room]\').click()")')
    assert backend._studio_scene == "room"
    render("studio-room")
    # Real pointer orbit changes the world-space camera, and reset restores it.
    before_orbit = probe("window.focusScene3D.diagnostics().yaw")
    rect = probe("(()=>{const r=document.getElementById('scene-canvas').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()")
    start_point = QPoint(int(rect["x"] + rect["width"] / 2), int(rect["y"] + rect["height"] / 2))
    end_point = start_point + QPoint(110, 10)
    input_target = studio.focusProxy() or studio.childAt(start_point) or studio
    mapped_start = input_target.mapFrom(studio, start_point)
    mapped_end = input_target.mapFrom(studio, end_point)
    QTest.mousePress(input_target, Qt.LeftButton, Qt.NoModifier, mapped_start)
    QTest.mouseMove(input_target, mapped_end, 150)
    QTest.mouseRelease(input_target, Qt.LeftButton, Qt.NoModifier, mapped_end)
    wait_ms(250)
    assert probe("window.focusScene3D.diagnostics().yaw") != before_orbit
    render("studio-room-rotated")
    js('runJavaScript("document.getElementById(\'reset-view\').click()")')
    assert abs(probe("window.focusScene3D.diagnostics().yaw") - before_orbit) < .001
    # Preview the endpoints without changing any timer or persisted session state.
    assert backend.pauseStepFocus("测试天亮", "继续")
    wait_ms(200)
    backend._focus_snapshot_timer.stop()
    morning = dict(json.loads(backend.focusStudioStateJson), scene="room", progress=1, status="paused")
    js("runJavaScript(" + json.dumps("window.flowFocus.update(" + json.dumps(morning, ensure_ascii=False) + ")", ensure_ascii=False) + ")")
    assert probe("window.focusScene3D.diagnostics().daylight") == 1
    render("studio-room-morning")
    grown = dict(morning, scene="tree", sessionSeed=0)
    js("runJavaScript(" + json.dumps("window.flowFocus.update(" + json.dumps(grown, ensure_ascii=False) + ")", ensure_ascii=False) + ")")
    assert probe("window.focusScene3D.diagnostics().progress") == 1
    render("studio-tree-grown")
    assert probe("window.focusScene3D.diagnostics().flowerCount") == 12
    assert probe("window.focusScene3D.diagnostics().fruitCount") > 0
    # Backend is paused and disconnected from these controlled visual previews.
    visual_state(dict(grown, progress=.2))
    visual_state(dict(grown, progress=.8, status="work"))
    growth_first = probe("window.focusScene3D.diagnostics()")
    assert .2 < growth_first["renderedProgress"] < .8 and growth_first["growthAnimating"], growth_first
    wait_ms(500)
    growth_second = probe("window.focusScene3D.diagnostics()")
    assert growth_first["renderedProgress"] < growth_second["renderedProgress"] < .8, growth_second
    # During active growth the opaque backing and island never clear or flash.
    frames_before = growth_second["frames"]
    samples = []
    for _ in range(16):
        image = studio.grab().toImage()
        samples.append((image.pixelColor(15, 150).rgba(), image.pixelColor(15, 300).rgba()))
        wait_ms(50)
    assert len(set(samples)) == 1, "Static background flickered across frames"
    assert probe("window.focusScene3D.diagnostics().frames") > frames_before
    visual_state(dict(grown, progress=.8))
    frozen = probe("window.focusScene3D.diagnostics().animationTime")
    wait_ms(350)
    assert probe("window.focusScene3D.diagnostics().animationTime") == frozen
    rain = {"status": "ready", "kind": "rain", "city": "测试城市", "temperature": 18}
    visual_state(dict(morning, weather=rain))
    clock = probe("window.focusScene3D.diagnostics().monitorTime")
    assert clock == probe("(()=>{const d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')})()")
    assert probe("window.focusScene3D.diagnostics().weather") == "rain"
    ambience = probe("window.focusAmbience.diagnostics()")
    assert ambience["raining"] and ambience["fullViewport"] and ambience["rainCount"] >= 100, ambience
    rain_pixels = probe("(()=>{const c=document.getElementById('rain-curtain'),x=c.getContext('2d'),d=x.getImageData(0,0,200,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n})()")
    assert rain_pixels > 10, "Rain never reaches outside the central stage"
    assert "测试城市" in probe("document.getElementById('weather').textContent")
    render("studio-room-rain")
    visual_state(dict(grown, weather=rain))
    render("studio-tree-rain")
    # Weather dialog Escape stays in the studio; disabling goes through Python.
    js('runJavaScript("document.getElementById(\'weather\').click()")')
    QTest.keyClick(studio, Qt.Key_Escape)
    wait_ms(250)
    assert backend._immersive_active and not probe("document.getElementById('weather-dialog').open")
    js('runJavaScript("document.getElementById(\'weather\').click();document.getElementById(\'weather-off\').click()")')
    assert backend.settings_database["focusWeatherMode"] == "off"
    backend._focus_snapshot_timer.start()
    backend.resumeStepFocus("继续")
    backend.focusSessionChanged.emit()
    assert not view.studio_page.console_errors, view.studio_page.console_errors
    js('runJavaScript("document.getElementById(\'thought\').click();document.getElementById(\'thought-input\').value=\'稍后查找引用来源\';document.getElementById(\'thought-form\').requestSubmit()")')
    assert backend.focus_journey.data["thoughts"][-1]["text"] == "稍后查找引用来源"
    # First work period ends, then a real short break, then the next work period.
    print("QA: sound/weather/3D checks passed", flush=True)
    island._deadline -= 70
    island._tick()
    wait_ms(500)
    backend._refresh_focus_snapshot()
    assert island._current_task()["type"] == "break"
    elapsed = backend.focus_journey.active["elapsedSeconds"]
    render("studio-break")
    print("QA: break rendered", flush=True)
    island._deadline -= 70
    island._tick()
    wait_ms(500)
    backend._refresh_focus_snapshot()
    assert island._current_task()["type"] == "focus"
    assert island._current_task()["round"] == 2
    print("QA: second work interval running", flush=True)
    assert backend.focus_journey.active["elapsedSeconds"] <= elapsed + 2, "Break counted as focused work"
    # Escape exits fullscreen while retaining the running timer.
    js('runJavaScript("document.getElementById(\'rain-sound\').click()")')
    assert studio.rain_sound.isPlaying()
    QTest.keyClick(studio, Qt.Key_Escape)
    wait_ms(300)
    assert not backend._immersive_active
    assert not studio.rain_sound.isPlaying() and backend.settings_database["focusRainSound"]
    assert root.isVisible()
    print("QA: Escape returned to app", flush=True)
    assert island.focus_running()
    assert backend.enterFocusStudio("room")
    wait_ms(1500)
    assert studio.rain_sound.isPlaying(), "Saved rain preference did not resume on entry"
    view = studio
    assert view is not None
    js('runJavaScript("document.getElementById(\'finish\').click()")')
    wait_until(lambda: backend.focus_journey.active["status"] == "review", "Finishing from the web page failed")
    assert not studio.isVisible()
    assert not backend._immersive_active
    assert backend.stats_database["todayFocusSeconds"] < 70
    assert len(backend.focus_journey.data["forest"]) == 1
    print("QA: room completion planted one tree", flush=True)
    assert backend.saveStepReview("完成第一轮", "", False)
    assert backend.startStepFocus(-1, 1, "让森林再多一棵树", False)
    assert backend.enterFocusStudio("tree")
    wait_ms(350)
    del backend.__dict__["_show_main_window"]  # Exercise the real completion visibility guard.
    js('runJavaScript("document.getElementById(\'scene-canvas\').dispatchEvent(new KeyboardEvent(\'keydown\',{key:\'ArrowLeft\'}))")')
    assert abs(probe("window.focusScene3D.diagnostics().yaw") - .72) > .1
    island = next(iter(backend.island_windows.values()))
    island._deadline -= 70
    island._tick()
    wait_ms(350)
    assert backend.focus_journey.active["status"] == "review" and backend._studio_celebrating
    assert studio.isVisible() and not root.isVisible()
    assert len(backend.focus_journey.data["forest"]) == 2
    completed_state = json.loads(backend.focusStudioStateJson)
    assert completed_state["sessionSeed"] == backend.focus_journey.data["forest"][-1]["seed"]
    assert probe("window.focusScene3D.diagnostics().celebrating")
    reveal_before = probe("window.focusScene3D.diagnostics().reveal")
    wait_ms(300)
    assert probe("window.focusScene3D.diagnostics().reveal") > reveal_before
    assert probe("window.focusScene3D.diagnostics().forestRendered") == 2
    backend._focus_snapshot_timer.stop()
    completed = json.loads(backend.focusStudioStateJson)
    demo_trees = [{"id": "demo-" + str(i), "seed": i * 7907 + 13} for i in range(4)] + [{"id": completed["sessionId"], "seed": 21532}]
    forest_demo = dict(completed, forest=demo_trees, trees=5, weather={"kind": "sunny", "status": "ready", "city": "预览", "temperature": 23})
    visual_state(forest_demo)
    wait_ms(2000)
    render("studio-forest-five")
    forest = probe("window.focusScene3D.diagnostics()")
    assert forest["forestTotal"] == forest["forestRendered"] == forest["clearTrees"] == 5, forest
    assert forest["reveal"] == forest["landSpread"] == forest["forestGrowth"] == 1
    assert abs(forest["yaw"] - .72) < .001 and abs(forest["pitch"] - .48) < .001
    assert forest["landX"] > 2.35 and forest["zoom"] < 1
    assert forest["plotFlowerCount"] == 8, forest
    assert not probe("Boolean(document.getElementById('forest-canopy'))"), "Unexpected 2D forest layer"
    demo_trees = [{"id": "demo-" + str(i), "seed": i * 7907 + 13} for i in range(48)] + [{"id": completed["sessionId"], "seed": 21532}]
    visual_state(dict(forest_demo, forest=demo_trees, trees=49))
    render("studio-forest-completed")
    forest = probe("window.focusScene3D.diagnostics()")
    assert forest["clearTrees"] == 30 and forest["distantTrees"] == 19 and forest["forestRendered"] == 49, forest
    assert forest["plotFlowerCount"] == 58, forest
    benchmark_state = dict(forest_demo, forest=demo_trees[:-1] + [{"id": "benchmark-tree", "seed": 21532}], trees=49, sessionId="benchmark-tree", sessionSeed=21532)
    visual_state(benchmark_state)
    benchmark_start = probe("({now:performance.now(),frames:window.focusScene3D.diagnostics().frames})")
    wait_ms(1800)
    benchmark_end = probe("({now:performance.now(),frames:window.focusScene3D.diagnostics().frames,scene:window.focusScene3D.diagnostics()})")
    performance = {"trees": 49, "fps": round((benchmark_end["frames"] - benchmark_start["frames"]) * 1000 / (benchmark_end["now"] - benchmark_start["now"]), 1), "geometry_ms": round(benchmark_end["scene"]["geometryMs"], 1), "raster_ms": round(benchmark_end["scene"]["renderMs"], 1)}
    print("QA: forest performance " + json.dumps(performance), flush=True)
    visual_state(dict(forest_demo, forest=demo_trees + [{"id": "extra-"+str(i), "seed": i+11000} for i in range(100)], trees=149))
    wait_ms(250)
    assert probe("window.focusScene3D.diagnostics().forestRendered") <= 60
    visual_state(forest_demo)
    wait_ms(3000)
    resting_frame = probe("window.focusScene3D.diagnostics().frames")
    wait_ms(350)
    assert probe("window.focusScene3D.diagnostics().frames") == resting_frame, "Finished forest keeps redrawing while idle"
    before = probe("window.focusScene3D.diagnostics().yaw")
    js('runJavaScript("document.getElementById(\'scene-canvas\').dispatchEvent(new KeyboardEvent(\'keydown\',{key:\'ArrowRight\'}))")')
    assert probe("window.focusScene3D.diagnostics().yaw") > before
    print("QA: real 3D forest expanded and count verified", flush=True)
    js('runJavaScript("document.getElementById(\'pause\').click()")')
    assert not studio.isVisible() and not backend._immersive_active
    assert not studio.rain_sound.isPlaying() and root.isVisible()
    from focus_journey import FocusJourney
    assert len(FocusJourney(Path(backend.data_dir) / "focus_journey.json").data["forest"]) == 2
    errors = [warning for warning in warnings if any(word in warning for word in ("ReferenceError", "TypeError", "is not a type", "Cannot assign", "Binding loop", "Error:"))]
    assert not errors, "\n".join(errors)
    print(json.dumps({"ok": True, "renderer": occlusion["mode"], "checks": ["native fullscreen WebEngine", "per-pixel occlusion independent of draw order", "authoritative visible countdown ticks", "WebChannel pause/resume", "two real 3D scenes", "pointer orbit and reset", "daylight endpoint", "flowers", "smooth growth interpolation", "16 stable backing frames", "pause freezes animation", "local monitor clock", "rain across full viewport", "local audio loop on/off and volume", "weather dialog and settings channel", "thought capture", "automatic work/break transitions", "break excluded from stats", "Escape retains timer", "room finish opens review", "tree finish stays immersive and reveals forest", "one durable tree per completed session", "record button leaves celebration"], "warnings": warnings, "renders": str(output)}, ensure_ascii=False, indent=2))
except BaseException:
    traceback.print_exc()
    raise
finally:
    print("QA: shutting down", flush=True)
    faulthandler.cancel_dump_traceback_later()
    backend.shutdown()
    for item in app.topLevelWindows():
        item.hide()
    app.processEvents()
    QTimer.singleShot(0, app.quit)
    app.exec()
    DATA.cleanup()
