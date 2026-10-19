"""RinUI-facing adapter around FlowTodo's existing business backend.

The WebEngine application and the native QML application intentionally share
the same JSON files and the same :class:`main.BackendBridge` implementation.
This module only adds QML-friendly properties, signal aliases, and small
id-based helpers used by the native pages.
"""

from __future__ import annotations

import json
import copy
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QLocale, QTimer, Signal, Slot, QUrl, QSaveFile, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImageReader, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QFileDialog

from notification_audio import preview as preview_notification_sound, set_backend as set_audio_backend
from i18n_runtime import format_long_date, normalize_language, tr, translator
from main import BackendBridge
from notes import NoteManager
from focus_journey import FocusJourney
from focus_rhythm import pomodoro_tasks
from task_relations import TaskRelations, build_graph, ensure_child_ids
from speech_input import SpeechInput
from system_dictation import open_voice_typing, close_voice_typing, system_motion_enabled
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class RinUIBackend(BackendBridge):
    """Compatibility facade that keeps the old backend as the source of truth."""

    tasksChanged = Signal()
    groupsChanged = Signal()
    projectsChanged = Signal()
    statsChanged = Signal()
    achievementsChanged = Signal()
    settingsChanged = Signal()
    aiStateChanged = Signal()
    aiLibraryChanged = Signal()
    aiRequestChanged = Signal()
    aiServiceReadinessChanged = Signal()
    aiRequestFinished = Signal(bool, str)
    longPlanChanged = Signal()
    focusSessionChanged = Signal()
    focusJourneyChanged = Signal()
    guidedReward = Signal()
    immersiveFocusRequested = Signal(str)
    immersiveFocusClosed = Signal()
    supervisionViewRequested = Signal(str)
    supervisionViewClosed = Signal()
    messageRequested = Signal(str, str, str)
    focusStartResult = Signal(bool, str)
    quickCaptureReady = Signal(str, str, str)
    navigationContextChanged = Signal()
    desktopWidgetVisibilityRequested = Signal(bool)
    focusPreparationRequested = Signal(str, float)
    taskRelationsChanged = Signal()
    taskRelationsRequested = Signal(str)
    relationPreparationRequested = Signal(str)
    relationCompletionRequested = Signal(str, bool)
    flowInvalidRequested = Signal(str)
    flowPreparationRequested = Signal(str)
    notesChanged = Signal()
    noteVisibilityChanged = Signal()
    languageChanged = Signal()
    accountChanged = Signal()
    accountLoginRequested = Signal()
    systemDictationResult = Signal(QObject, bool)
    cloudAIRefreshRequested = Signal()

    def __init__(self):
        super().__init__()
        from account_state import AccountState
        self._account_state = AccountState(Path(self.data_dir) / "account_state.json")
        self.settingsChanged.connect(self.accountChanged.emit)
        self.accountChanged.connect(self.aiServiceReadinessChanged.emit)
        self._account_refresh = QTimer(self)
        self._account_refresh.setInterval(60000)
        self._account_refresh.timeout.connect(self.accountChanged.emit)
        self._account_refresh.start()
        set_audio_backend(self)
        self.note_manager = NoteManager(self)
        self.native_window = None
        self._last_focus_payload = "{}"
        self.focus_journey = FocusJourney(Path(self.data_dir) / "focus_journey.json")
        self.task_relations = TaskRelations(Path(self.data_dir) / "task_relations.json")
        self._relation_launch_key = ""
        self._pending_flow_key = ""
        self._journey_step = ""
        self._journey_resuming = False
        self._journey_parked = False
        self._journey_end_reason = "stopped"
        self._journey_ticks = 0
        self._immersive_active = False
        self._studio_celebrating = False
        self._studio_window = None
        self._focus_weather = None
        self._studio_scene = "tree"
        self._guided_pending = None
        self._guided_request_id = ""
        self._guided_reward_seq = 0
        self._guided_reward_text = ""
        self._guided_error = ""
        self.focusSessionChanged.connect(self._sync_guided_island_controls)
        self._active_group_id = -1
        self._active_project_id = -1
        self._ai_request_running = False
        self._quick_ai_pending = ""
        self.quickCaptureReady.connect(self._quick_capture_finished)
        self._speech_input = SpeechInput(self)
        self._dictation_pending = False
        self._dictation_generation = 0
        self._dictation_editor = None
        self._speech_input.failed.connect(lambda message: self.messageRequested.emit("error", "语音输入", message))
        self._focus_music = QMediaPlayer(self)
        self._focus_music_audio = QAudioOutput(self)
        self._focus_music.setAudioOutput(self._focus_music_audio)
        self._focus_music.setLoops(QMediaPlayer.Loops.Infinite)
        self._focus_music.errorOccurred.connect(lambda _error, _text: self.messageRequested.emit("warning", "背景音乐", "音乐无法播放，专注会继续；请在设置中更换音频文件。"))
        self.signalTasksUpdated.connect(lambda _payload: self.tasksChanged.emit())
        self.signalGroupsUpdated.connect(lambda _payload: self.groupsChanged.emit())
        self.signalProjectsUpdated.connect(lambda _payload: self.projectsChanged.emit())
        self.tasksChanged.connect(self.taskRelationsChanged.emit)
        self.groupsChanged.connect(self.taskRelationsChanged.emit)
        self.projectsChanged.connect(self.taskRelationsChanged.emit)
        self.signalStatsUpdated.connect(lambda _payload: self.statsChanged.emit())
        self.signalAchievementsUpdated.connect(lambda _payload: self.achievementsChanged.emit())
        self.signalFocusSessionChanged.connect(self._on_focus_session_payload)
        self.signalAiMessage.connect(lambda _payload: self.aiStateChanged.emit())
        self.signalAiPlanReady.connect(self._on_ai_plan_ready)
        self.signalPathSelected.connect(lambda _path: self.settingsChanged.emit())
        self.signalTaskReminder.connect(
            lambda kind, _title, message: self.messageRequested.emit(
                "warning",
                tr("日程提醒") if kind == "scheduled" else tr("每日重复任务提醒"),
                message,
            )
        )
        self.note_manager.notesChanged.connect(self.notesChanged.emit)
        self.note_manager.visibilityChanged.connect(self.noteVisibilityChanged.emit)
        self.settingsChanged.connect(self.note_manager.refresh_settings)
        # The stored language wins over the system locale so the choice survives
        # restarts; QML reads it through the shared translator singleton.
        self._translator = translator()
        self._translator.setLanguage(
            self.settings_database.get("language") or QLocale.system().name()
        )
        self._translator.languageChanged.connect(self.languageChanged.emit)
        self._focus_snapshot_timer = QTimer(self)
        self._focus_snapshot_timer.setInterval(1000)
        self._focus_snapshot_timer.timeout.connect(self._refresh_focus_snapshot)
        self._focus_snapshot_timer.start()
        self._restore_legacy_ai_journey()
        from supervision import SupervisionController
        self._supervision = SupervisionController(self)
        self._supervision.alertRaised.connect(self._supervision_alert)
        self._supervision.stopped.connect(self.supervisionViewClosed.emit)
        self.focusSessionChanged.connect(self._supervision._tick)
        self._relation_graph()
        from cloud_controller import CloudController
        self._cloud = CloudController(self)
        self.cloudAIRefreshRequested.connect(self._cloud.refresh)
        QApplication.instance().aboutToQuit.connect(self._cloud.close)

    def attach_native_window(self, window) -> None:
        self.native_window = window

    @Property(str, notify=accountChanged)
    def accountJson(self):
        account = self._account_state.snapshot(self.settings_database.get("aiServiceMode", "default"))
        avatar = self._account_state.path.parent / "avatar.png"
        account["avatarUrl"] = QUrl.fromLocalFile(str(avatar)).toString() + "?v=" + account["avatarRevision"] if avatar.is_file() else ""
        cloud = getattr(self, '_cloud', None)
        if cloud and cloud.logged_in():
            user=cloud.account();avatar=cloud.avatar_path()
            account.update(name=user['name'],initials=user['name'][:2].upper(),handle=user['email'],local=False,plan=user['plan'].title(),planId=user['plan'],balance=user['balance'],customAppearanceEligible=self._custom_appearance_eligible())
            account['avatarUrl']=QUrl.fromLocalFile(str(avatar)).toString()+'?v='+str(avatar.stat().st_mtime_ns) if avatar.is_file() else ''
            if account['service']=='official':
                quota=cloud.cache.get('officialAI',{});limit=quota.get('limit',0);remaining=quota.get('remaining',0)
                account['usage']={'limit':limit,'used':quota.get('used',0),'remaining':remaining,'remainingFraction':remaining/limit if limit else 0,'status':'available' if quota.get('active') and remaining else 'exhausted'}
        else:
            account.update(name='本地访客',initials='',avatarUrl='',local=True,planId='free',customAppearanceEligible=False)
        return self._json(account)

    def _custom_appearance_eligible(self):
        import time
        cloud=getattr(self,'_cloud',None)
        if not cloud or not cloud.logged_in():return False
        user=cloud.account()
        return user.get('plan') in ('lite','standard') and (not user.get('membershipExpires') or user['membershipExpires']>time.time()*1000)

    @Property(str, notify=settingsChanged)
    def appearanceJson(self):
        from appearance_customization import validate
        cloud=getattr(self,'_cloud',None);uid=cloud.account().get('id','') if cloud and cloud.logged_in() else ''
        settings=self.settings_database.get('customAppearance',{})
        try:value=validate(settings.get(uid,{}) if isinstance(settings,dict) else {})
        except ValueError:value=validate({})
        value['eligible']=self._custom_appearance_eligible();value['active']=value['eligible'] and value['enabled']
        return self._json(value)

    @Slot(str,result=bool)
    def saveCustomAppearance(self,value_json):
        if not self._custom_appearance_eligible():
            self.messageRequested.emit('warning','会员个性化','登录 Lite 或 Standard 账户后可使用自定义主题。');return False
        from appearance_customization import validate
        try:value=validate(json.loads(value_json))
        except (ValueError,TypeError) as error:
            self.messageRequested.emit('warning','配色未保存',str(error));return False
        profiles=self.settings_database.get('customAppearance',{})
        profiles=dict(profiles) if isinstance(profiles,dict) else {}
        profiles[self._cloud.account()['id']]=value
        settings=dict(self.settings_database);settings['customAppearance']=profiles
        self.save_settings(self._json(settings));self.settingsChanged.emit();return True

    @Slot(result=bool)
    def resetCustomAppearance(self):
        profiles=self.settings_database.get('customAppearance',{})
        profiles=dict(profiles) if isinstance(profiles,dict) else {}
        cloud=getattr(self,'_cloud',None)
        if cloud and cloud.logged_in():profiles.pop(cloud.account().get('id',''),None)
        settings=dict(self.settings_database);settings['customAppearance']=profiles
        self.save_settings(self._json(settings));self.settingsChanged.emit();return True

    @Property(str, notify=accountChanged)
    def cloudJson(self):
        return self._json(self._cloud.view())

    @Property(str, notify=accountChanged)
    def cloudRecordsJson(self):
        from cloud_records import snapshot
        return self._json([{'key':r['key'],'kind':r['kind'],'title':r['title']} for r in snapshot(self)])

    def _cloud_snapshot(self):
        from cloud_records import snapshot
        return snapshot(self)

    def _import_cloud_record(self,item,key=None):
        from cloud_records import import_record
        return import_record(self,item,key)

    @Slot()
    def cloudLogin(self):self.accountLoginRequested.emit()

    @Slot()
    def cloudRegister(self):self._cloud.start_login()

    @Slot(str)
    def cloudSendCode(self,email):self._cloud.send_code(email)

    @Slot(str,str)
    def cloudSignIn(self,email,code):self._cloud.sign_in(email,code)

    def _allow_account_edit(self):
        if self._cloud.logged_in():return True
        self.messageRequested.emit('info','请先登录','登录后可以设置头像和昵称。')
        self.accountLoginRequested.emit();return False

    @Slot()
    def cloudLogout(self):self._cloud.logout()

    @Slot()
    def cloudRefresh(self):self._cloud.refresh()

    @Slot(str,result=bool)
    def cloudSync(self, selected):
        try:return self._cloud.sync(json.loads(selected))
        except (ValueError,TypeError):return False

    @Slot(str,str)
    def cloudResolve(self,key,choice):
        try:self._cloud.resolve(key,choice)
        except Exception:self.messageRequested.emit('warning','云端同步','该版本暂时无法导入，本地记录已保留。')

    @Slot(bool)
    def cloudBrowse(self,trash):self._cloud.browse_cloud(trash)

    @Slot(str,int,bool)
    def cloudRecordAction(self,id,version,restore):self._cloud.cloud_record_action(id,version,restore)

    @Slot()
    def cloudSyncAll(self):self._cloud.sync([row['key'] for row in self._cloud_snapshot()])

    @Slot(str)
    def cloudImport(self,id):self._cloud.import_cloud(id)

    @Slot()
    def useCloudAvatar(self):
        self._cloud.avatar_dirty=False;self._cloud.save_pending();self._cloud.refresh()

    @Slot()
    def retryCloudAvatar(self):self._cloud.replace_cloud_avatar()

    @Slot(result=str)
    def chooseAccountAvatar(self):
        if not self._allow_account_edit():return ''
        path, _ = QFileDialog.getOpenFileName(None, "选择头像图片", "", "图片 (*.png *.jpg *.jpeg *.webp *.bmp)")
        return self.loadAccountAvatar(path) if path else ""

    @Slot(str, result=str)
    def loadAccountAvatar(self, path):
        if not self._allow_account_edit():return ''
        try:
            source = QUrl(path)
            filename = Path(source.toLocalFile() if source.isLocalFile() else path)
            if not filename.is_file() or filename.stat().st_size > 25 * 1024 * 1024:
                raise ValueError("请选择小于 25 MB 的本地图片。")
            reader = QImageReader(str(filename))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.width() * size.height() > 40_000_000:
                raise ValueError("图片尺寸过大，请选择不超过 4000 万像素的图片。")
            image = reader.read()
            if image.isNull():
                raise ValueError("无法读取这张图片，请尝试 PNG 或 JPG。")
            if max(image.width(), image.height()) > 4096:
                image = image.scaled(4096, 4096, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            preview = self._account_state.path.parent / "avatar-candidate.png"
            if not image.save(str(preview), "PNG"):
                raise OSError("无法准备头像预览。")
            self._avatar_candidate = image
            return self._json({"url": QUrl.fromLocalFile(str(preview)).toString() + "?v=" + uuid4().hex,
                               "width": image.width(), "height": image.height()})
        except (OSError, ValueError) as error:
            self.messageRequested.emit("warning", "头像图片", str(error))
            return ""

    @Slot(float, float, float, result=bool)
    def saveAccountAvatar(self, center_x, center_y, zoom):
        if not self._allow_account_edit():return False
        import math
        image = getattr(self, "_avatar_candidate", None)
        if image is None:
            return False
        try:
            if not all(math.isfinite(n) for n in (center_x, center_y, zoom)) or not (1 <= zoom <= 4):
                raise ValueError("裁剪参数无效，请重新选择图片。")
            side = max(1, round(min(image.width(), image.height()) / zoom))
            x = max(0, min(image.width() - side, round(center_x * image.width() - side / 2)))
            y = max(0, min(image.height() - side, round(center_y * image.height() - side / 2)))
            avatar = image.copy(x, y, side, side).scaled(256, 256, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            rounded = QImage(256, 256, QImage.Format_ARGB32_Premultiplied)
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            mask = QPainterPath()
            mask.addEllipse(0, 0, 256, 256)
            painter.setClipPath(mask)
            painter.drawImage(0, 0, avatar)
            painter.end()
            cloud=getattr(self,'_cloud',None)
            target = QSaveFile(str(cloud.avatar_path() if cloud and cloud.logged_in() else self._account_state.path.parent / "avatar.png"))
            if not target.open(QIODevice.WriteOnly) or not rounded.save(target, "PNG") or not target.commit():
                raise OSError("头像保存失败，请重试。")
            self._account_state.set_avatar_revision(uuid4().hex)
            if cloud and cloud.logged_in():cloud.upload_avatar()
            self.accountChanged.emit()
            return True
        except (OSError, ValueError) as error:
            self.messageRequested.emit("warning", "头像图片", str(error))
            return False

    @Slot(result=bool)
    def discardAccountAvatar(self):
        self._avatar_candidate = None
        try:
            (self._account_state.path.parent / "avatar-candidate.png").unlink(missing_ok=True)
            return True
        except OSError:
            return False

    @Slot(result=bool)
    def removeAccountAvatar(self):
        if not self._allow_account_edit():return False
        try:
            cloud=getattr(self,'_cloud',None)
            (cloud.avatar_path() if cloud and cloud.logged_in() else self._account_state.path.parent / "avatar.png").unlink(missing_ok=True)
            if cloud and cloud.logged_in():cloud.upload_avatar()
            self._account_state.set_avatar_revision("")
            self.accountChanged.emit()
            return True
        except OSError as error:
            self.messageRequested.emit("warning", "头像图片", str(error))
            return False

    @Slot(str, result=bool)
    def renameAccount(self, name):
        if not self._allow_account_edit():return False
        if self._cloud.logged_in():return self._cloud.rename(name)
        try:
            self._account_state.rename(name)
        except (ValueError, OSError) as error:
            self.messageRequested.emit("warning", "个人资料", str(error))
            return False
        self.accountChanged.emit()
        return True

    def _record_ai_usage(self, usage, service):
        self._account_state.record(usage, service)
        self.accountChanged.emit()

    def _call_ai_chat(self, messages, long_mode=False, output_limit=None):
        service = self.settings_database.get("aiServiceMode", "default")
        if service == 'official':
            if not self._cloud.logged_in():raise RuntimeError('请先在我的账户登录，再使用官方通道。')
            result=self._cloud.client.ai_chat(messages,min(8192,max(1,int(output_limit or (6000 if long_mode else 3000)))),self.settings_database.get('aiTemperature',0.7))
            choice=result['choices'][0];content=choice['message']['content']
            self._record_ai_usage(result.get('usage'),'official')
            self.cloudAIRefreshRequested.emit()
            if choice.get('finish_reason')=='length':
                from ai_planning import AIOutputLimit
                raise AIOutputLimit('官方模型输出达到上限，请缩短方案。')
            return content
        self._account_state.begin_request(service)
        try:
            return super()._call_ai_chat(messages, long_mode, output_limit)
        finally:
            self._account_state.end_request(service)

    @Property(QObject, constant=True)
    def supervision(self):
        return self._supervision

    @Slot(str, float, str, result=bool)
    def startSupervision(self, config_json, minutes, goal):
        try:
            if self._supervision.active:
                raise ValueError("监督模式已经在运行，可以返回当前监督窗口。")
            raw = json.loads(config_json)
            config = self._supervision.validate_start(raw)
            if not self.active_focus_session:
                if not self.startStepFocus(-1, minutes, str(goal).strip() or "做好眼前这一件事", False):
                    return False
            self.exitFocusStudio()
            self._supervision.start(raw)
            # Save preferences only; each session still requires explicit consent.
            self.setSettingJson("supervisionPreferences", self._json(config))
            self.presentSupervision(str(raw.get("view", "full")))
            return True
        except (ValueError, TypeError, RuntimeError) as error:
            self.messageRequested.emit("warning", "没有开启监督模式", str(error))
            return False

    @Slot(str)
    def presentSupervision(self, view):
        if self._supervision.active:
            self.supervisionViewRequested.emit("compact" if view == "compact" else "full")

    @Slot()
    def stopSupervision(self):
        self._supervision.stop()

    @Slot()
    def finishSupervision(self):
        self._supervision.stop()
        self.endStepFocus()

    @Slot(result=bool)
    def returnAiFromSupervision(self):
        self._supervision.stop()
        return self.returnToGuidedFocus()

    @Slot()
    def toggleSupervisionPause(self):
        if not self._supervision.active:
            return
        active = self.focus_journey.active or {}
        if active.get("status") == "paused":
            self.resumeStepFocus(str(active.get("step", "")))
        else:
            self.pauseStepFocus(str(active.get("progress", "")), str(active.get("step", "")))
        self._supervision._tick()

    def _supervision_alert(self, payload):
        alert = json.loads(payload)
        if self._supervision.config.get("sound", True):
            from notification_audio import play_notification_sound
            play_notification_sound()
        # Show the alert inside both supervision views; no focus stealing or
        # camera images in OS notification archives.
        for island in list(self.island_windows.values()):
            island.show_guard_alert("监督提醒 · " + alert["title"])

    def attach_qml_engine(self, engine) -> None:
        self.note_manager.attach_engine(engine)
        self.note_manager.restore_visible_notes()

    def _on_focus_session_payload(self, payload: str) -> None:
        self._last_focus_payload = payload or "{}"
        state = json.loads(self._last_focus_payload)
        event = state.get("event")
        if event == "started":
            island = next(iter(self.island_windows.values()), None)
            self.focus_journey.begin(state, island.tasks if island else [], self._journey_step, self._journey_resuming)
            if island:
                snapshot = island.focus_snapshot()
                state.update(snapshot)
                state["event"] = "started"
                self._last_focus_payload = self._json(state)
                self.focus_journey.snapshot(state)
        elif event in ("completed", "cancelled"):
            self._cancel_guided_request()
            self._pending_flow_key = ''
            if self._journey_parked:
                self.focus_journey.snapshot(state)
                if self.focus_journey.active:
                    self.focus_journey.active["status"] = "paused"
                    self.focus_journey.save()
            else:
                self.focus_journey.review(state, "timer" if event == "completed" else self._journey_end_reason)
            active = self.focus_journey.active or {}
            self._studio_celebrating = bool(not self._journey_parked and self._immersive_active and self._studio_scene == "tree"
                and self._studio_window is not None and self._studio_window.loaded
                and active.get("id") in self.focus_journey._tree_ids)
            if not self._studio_celebrating:
                self.exitFocusStudio()
        else:
            self.focus_journey.snapshot(state)
        if (state.get("kind") == "guided" or state.get('options', {}).get('flowConfirm')) and self.focus_journey.active:
            island = next(iter(self.island_windows.values()), None)
            if island:
                base = int(self.focus_journey.active.get("indexBase", 0))
                self.focus_journey.active["tasks"] = self.focus_journey.active.get("tasks", [])[:base] + copy.deepcopy(island.tasks)
                self.focus_journey.save()
            if state.get('kind') == 'guided' and event in ("started", "task", "paused", "resumed", "task_done", "cancelled", "completed"):
                self._sync_saved_ai_journey()
        if event in ("completed", "cancelled") and not self._journey_parked:
            self._finish_guided_capture(self.focus_journey.active or {})
        self.focusJourneyChanged.emit()
        self.focusSessionChanged.emit()
        if event == "started":
            self._play_focus_music()
        elif event in ("completed", "cancelled"):
            self._focus_music.stop()
        elif event == "paused":
            self._focus_music.pause()
        elif event == "resumed" and self._focus_music.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self._focus_music.play()
        if event == 'task_done' and state.get('flowWaiting'):
            self.exitFocusStudio()
            self._pending_flow_key = state.get('relationNodeKey', '')
            self.relationCompletionRequested.emit(self._pending_flow_key, True)
        elif event == 'completed' or (event == 'cancelled' and not self._journey_parked and self._journey_end_reason == 'step_done'):
            active = self.focus_journey.active or {}
            key = state.get('relationNodeKey') or self._session_relation_key(active)
            if key and not active.get('relationPrompted') and (state.get('flowOrigin') or self._relation_options(key)):
                active['relationPrompted'] = True
                self.focus_journey.save()
                QTimer.singleShot(0, lambda key=key: self.relationCompletionRequested.emit(key, True))
        elif event == 'task' and state.get('options', {}).get('flowConfirm'):
            key = state.get('relationNodeKey', '')
            island = next((i for i in self.island_windows.values() if i._current_task().get('relationNodeKey') == key), None)
            if island:
                QTimer.singleShot(0, lambda: self._skip_done_flow_step(island, key))

    def _skip_done_flow_step(self, island, key):
        if not self.active_focus_session or island._finished or island._cancelled or island._current_task().get('relationNodeKey') != key:
            return
        node = next((n for n in self._relation_graph()['nodes'] if n['key'] == key), {})
        if not node.get('done'):
            return
        island._timer.stop()
        island._stop_noise()
        island._current_task()['time'] = 0
        island._remaining = 0
        final = island.current_index + 1 >= len(island.tasks)
        group_key = f"group:{self.active_focus_session.get('groupId')}"
        if final and self.focus_journey.active:
            self.focus_journey.active['relationPrompted'] = True
        island._load_and_start_task(island.current_index + 1)
        if final and self._relation_options(group_key):
            self.relationCompletionRequested.emit(group_key, False)

    def _play_focus_music(self):
        if not self.settings_database.get("focusMusicAutoPlay", False):
            return
        path = str(self.settings_database.get("focusMusicPath") or "")
        if path and Path(path).is_file():
            self._focus_music_audio.setVolume(max(0, min(1, self._safe_float(self.settings_database.get("focusMusicVolume"), 0.25))))
            self._focus_music.setSource(QUrl.fromLocalFile(path))
            self._focus_music.play()

    @Slot(result=str)
    def chooseFocusMusic(self):
        path, _ = QFileDialog.getOpenFileName(None, "选择专注背景音乐", "", "音频文件 (*.mp3 *.wav *.ogg *.flac *.m4a)")
        if path:
            self.setSetting("focusMusicPath", path)
        return path

    @Slot()
    def stopFocusMusic(self):
        self._focus_music.stop()

    @Slot(str, result=bool)
    @Slot(str, str, result=bool)
    def importCapture(self, tasks_json, plan_id=""):
        try:
            from ai_planning import validate_shape
            tasks = json.loads(tasks_json)
            raw = validate_shape({"tasks": tasks}, capture=True)
            plan = self._normalize_ai_plan(raw)
            added = self._apply_ai_plan(plan, merge_missing=True, replace_ai=False)
            latest = self.ai_state_database.get("latestPlan")
            from ai_library import find
            record = find(self.ai_state_database, plan_id or (latest or {}).get("libraryId"))
            if record and record.get("kind") == "capture":
                record["plan"]["captureImported"] = True
                record["draft"]["drafts"] = []
            if isinstance(latest, dict) and latest.get("captureMode") and (not plan_id or latest.get("libraryId") == plan_id):
                latest["captureImported"] = True
                self.ai_state_database.pop("captureDraftInput", None)
                self._save_ai_state(latest_plan=latest)
                self.aiStateChanged.emit()
            elif record:
                self._save_ai_state()
                self.aiStateChanged.emit()
            self.aiLibraryChanged.emit()
            self.messageRequested.emit("success", "已经记下", f"添加了 {added['tasks']} 个任务，已有的同名任务不会重复添加。")
            return True
        except Exception as error:
            self.messageRequested.emit("error", "未能添加任务", str(error))
            return False

    @Slot(result=str)
    def getQuickCaptureDraft(self):
        path = Path(self.data_dir) / "quick_capture.json"
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
            from quick_capture import validate_tasks
            if not isinstance(draft, dict) or not isinstance(draft.get("original"), str) or len(draft["original"]) > 6000:
                raise ValueError("草稿格式错误")
            draft["tasks"] = validate_tasks(draft.get("tasks", []), allow_skip=True)
            from ai_library import valid_id
            if not valid_id(draft.get("batchId")):
                draft["batchId"] = uuid4().hex
            return self._json(draft)
        except (OSError, ValueError, TypeError):
            fresh = {"batchId": uuid4().hex, "original": "", "tasks": []}
            try:
                from ai_library import write_state
                write_state(path, fresh)
            except OSError:
                pass
            return self._json(fresh)

    @Slot(str, result=bool)
    def saveQuickCaptureDraft(self, payload):
        try:
            draft = json.loads(payload)
            from quick_capture import validate_tasks
            from ai_library import valid_id, write_state
            if not isinstance(draft, dict) or not valid_id(draft.get("batchId")) or not isinstance(draft.get("original"), str) or len(draft["original"]) > 6000:
                raise ValueError("快速录入草稿不完整。")
            tasks = validate_tasks(draft.get("tasks", []), allow_skip=True)
            path = Path(self.data_dir) / "quick_capture.json"
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
                if current.get("batchId") and current["batchId"] != draft["batchId"]:
                    return False  # A retired page cannot overwrite the next batch.
            except (OSError, ValueError, AttributeError):
                pass
            write_state(path, {"batchId": draft["batchId"], "original": draft["original"], "tasks": tasks})
            return True
        except (ValueError, TypeError, OSError):
            return False

    @Slot(str, result=str)
    def previewQuickCapture(self, text):
        from quick_capture import local_tasks
        try:
            return self._json({"tasks": local_tasks(text), "error": ""})
        except ValueError as error:
            return self._json({"tasks": [], "error": str(error)})

    @Slot(str, result=str)
    def addQuickCapture(self, payload):
        try:
            from quick_capture import validate_tasks, fingerprint
            from ai_library import valid_id, write_state
            draft = json.loads(payload)
            if not isinstance(draft, dict) or not valid_id(draft.get("batchId")):
                raise ValueError("请重新打开快速录入页面。")
            tasks = validate_tasks(draft.get("tasks"))
            if not tasks:
                raise ValueError("先记下一件事。")
            batch, digest = draft["batchId"], fingerprint(tasks)
            previous = [task for task in self.local_database if task.get("captureBatchId") == batch]
            if previous and any(task.get("captureBatchFingerprint") != digest for task in previous):
                raise ValueError("这一批已记下，请开始新的一批；原任务未修改。")
            existing = {task.get("captureIndex") for task in previous}
            next_id = max([999] + [int(task.get("id", 0)) for task in self.local_database]
                          + [int(task.get("id", 0)) for task in self.stats_database.get("taskHistory", [])]) + 1
            now = datetime.now().isoformat(timespec="seconds")
            added = [{"id": next_id + index, "title": task["title"], "category": task["category"],
                      "meta": "随口记下" + (" · " + task["category"] if task["category"] != "其他" else ""),
                      "taskType": "normal", "done": False, "completedAt": "", "createdAt": now,
                      "scheduledDate": self._today_key(), "scheduledTime": "",
                      "captureBatchId": batch, "captureBatchFingerprint": digest, "captureIndex": index}
                     for index, task in enumerate(tasks) if index not in existing]
            if added:
                updated = added + self.local_database
                write_state(self.tasks_file, updated)
                self.local_database = updated
                self.signalTasksUpdated.emit(self.get_tasks_json())
                self._emit_stats_and_achievements()
            # Repeated clicks with the same batch never create duplicates; a
            # new batch with the same title intentionally creates a new task.
            path = Path(self.data_dir) / "quick_capture.json"
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                current = {}
            if not current or current.get("batchId") == batch:
                write_state(path, {"batchId": uuid4().hex, "original": "", "tasks": []})
            return self._json({"ok": True, "added": len(added), "total": len(tasks)})
        except (ValueError, TypeError, OSError) as error:
            return self._json({"ok": False, "error": str(error)})

    @Slot(str, str, result=bool)
    def organizeQuickCapture(self, text, request_id):
        if not str(text).strip() or len(text) > 4000 or not request_id or len(request_id) > 100:
            self.messageRequested.emit("info", "分批整理", "AI 快速整理一次最多 4000 字；原话仍可直接记录。")
            return False
        if self._quick_ai_pending or self._ai_request_running:
            self.messageRequested.emit("info", "正在整理", "等这次完成后再试；直接记录仍可使用。")
            return False
        if not str(self.settings_database.get("aiApiKey") or "").strip():
            self.messageRequested.emit("info", "AI 整理未连接", "可以直接记下；需要分类整理时，再到 AI 服务设置填写密钥。")
            return False
        self._quick_ai_pending = request_id
        self._ai_request_running = True
        self.aiRequestChanged.emit()
        def work():
            from quick_capture import ai_tasks
            try:
                tasks = ai_tasks(self._call_ai_chat, text)
                self.quickCaptureReady.emit(request_id, self._json(tasks), "")
            except Exception:
                self.quickCaptureReady.emit(request_id, "[]", "这次 AI 整理没有完成，原话保留。可以直接记下，或分批后重试；没有自动追加请求。")
        import threading
        threading.Thread(target=work, daemon=True).start()
        return True

    @Slot(str, str, str)
    def _quick_capture_finished(self, request_id, tasks, error):
        if request_id == self._quick_ai_pending:
            self._quick_ai_pending = ""
            self._ai_request_running = False
            self.aiRequestChanged.emit()

    def _refresh_focus_snapshot(self) -> None:
        if not self.active_focus_session:
            return
        island = next(iter(self.island_windows.values()), None)
        if island is None:
            return
        state = dict(self.active_focus_session)
        state.update(island.focus_snapshot())
        self._last_focus_payload = self._json(state)
        self._journey_ticks += 1
        persist = self._journey_ticks % 5 == 0
        self.focus_journey.snapshot(state, persist=persist)
        if persist:
            self.focusJourneyChanged.emit()
        self.focusSessionChanged.emit()

    def _on_ai_plan_ready(self, payload: str) -> None:
        try:
            result = json.loads(payload or "{}")
        except (TypeError, ValueError):
            result = {"ok": False, "error": tr("AI 返回了无法识别的数据")}
        request_id = result.get("guidedRequestId")
        if request_id and request_id != self._guided_request_id:
            return  # Ended/rested sessions cannot unlock or replace a newer request.
        if request_id:
            self._guided_request_id = ""
        self._ai_request_running = False
        self.aiRequestChanged.emit()
        self.aiStateChanged.emit()

        pending = self._guided_pending
        if pending:
            self._guided_pending = None
            active = self.focus_journey.active or {}
            island = next(iter(self.island_windows.values()), None)
            if result.get("ok") and active.get("id") == pending["id"] and island and island.guided_waiting and island.current_index == pending["index"]:
                from guided_focus import island_tasks
                plan = result.get("plan") or {}
                if plan.get("guidance"):
                    island.tasks = island.tasks[:island.current_index + 1] + island_tasks(plan["guidance"])
                    active["source"]["guidance"] = plan["guidance"]
                    active["source"].pop("pendingClarification", None)
                    self.focus_journey.save()
                    island._load_and_start_task(island.current_index + 1)
                elif plan.get("questions"):
                    active["source"]["pendingClarification"] = {"questions": plan["questions"],
                        "context": pending["context"], "intro": plan.get("summary", ""),
                        "id": uuid4().hex}
                    self.focus_journey.save()
                else:
                    result = {"ok": False, "error": "这一段还没有准备好动作，原进展已保留。可以补充下一步的想法再试。"}
            if not result.get("ok"):
                self._guided_error = str(result.get("error") or "下一段暂时没准备好。")
            self.focusSessionChanged.emit()

        if result.get("ok"):
            long_mode = bool(result.get("longMode"))
            message = str(result.get("message") or (tr("长期计划已经生成，可以打开预览") if long_mode else tr("计划已经生成")))
            if not (result.get("plan") or {}).get("captureMode"):
                self.messageRequested.emit("success", tr("长期计划生成完成") if long_mode else tr("AI 计划生成完成"), message)
            self.aiRequestFinished.emit(True, message)
        else:
            message = str(result.get("error") or tr("请检查 API 设置和网络连接后重试"))
            self.messageRequested.emit("error", tr("AI 规划失败"), message)
            self.aiRequestFinished.emit(False, message)
        self._sync_saved_ai_journey()
        self.aiLibraryChanged.emit()

    def _main_window(self):
        if self.native_window is not None:
            return self.native_window
        windows = QGuiApplication.topLevelWindows()
        return windows[0] if windows else None

    def _show_main_window(self):
        if self._studio_celebrating and self._immersive_active:
            return
        window = self._main_window()
        if window is not None:
            window.showNormal()
            window.raise_()
            if hasattr(window, "requestActivate"):
                window.requestActivate()
            else:
                window.activateWindow()

    def _emit_settings_changed(self):
        self.settingsChanged.emit()

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _focus_options(self, options) -> dict:
        """Normalize native-page option names to the original focus backend."""
        result = dict(options or {})
        result.setdefault("keepWindowOpen", True)
        if sys.platform != "win32":
            result["disableOtherApps"] = False
            result["shieldEnabled"] = False
        if "shieldEnabled" in result and "disableOtherApps" not in result:
            result["disableOtherApps"] = bool(result.get("shieldEnabled"))
        if result.get("disableOtherApps") and "guardWhitelist" not in result:
            result["guardWhitelist"] = (
                self.settings_database["focusGuardWhitelist"]
                if "focusGuardWhitelist" in self.settings_database
                else self._default_focus_guard_apps()
            )
        return result

    @Property(str, notify=tasksChanged)
    def tasksJson(self) -> str:
        return self.get_tasks_json()

    @Property(str, notify=groupsChanged)
    def groupsJson(self) -> str:
        return self.get_groups_json()

    @Property(str, notify=projectsChanged)
    def projectsJson(self) -> str:
        return self.get_projects_json()

    @Property(str, notify=settingsChanged)
    def settingsJson(self) -> str:
        return self.get_settings_json()

    @Property(str, notify=notesChanged)
    def notesJson(self) -> str:
        return self.note_manager.notesJson

    @Property(int, notify=notesChanged)
    def noteCount(self) -> int:
        return self.note_manager.count

    @Property(str, notify=statsChanged)
    def statsJson(self) -> str:
        return self.get_stats_json()

    @Property(str, notify=achievementsChanged)
    def achievementsJson(self) -> str:
        return self.get_achievements_json()

    @Property(str, notify=aiStateChanged)
    def aiStateJson(self) -> str:
        return self.get_ai_state_json()

    @Property(str, notify=aiLibraryChanged)
    def savedAiPlansJson(self):
        from ai_library import summaries
        with self._ai_state_lock:
            return self._json(summaries(self.ai_state_database))

    @Slot(str, result=str)
    def getSavedAiPlan(self, plan_id):
        from ai_library import find
        with self._ai_state_lock:
            record = copy.deepcopy(find(self.ai_state_database, plan_id) or {})
        active = self.focus_journey.active
        if record and active and active.get("source", {}).get("libraryId") == plan_id:
            record["journey"] = copy.deepcopy(active)
        return self._json(record)

    @Slot(result=str)
    def getSelectedAiCapture(self):
        from ai_library import find
        with self._ai_state_lock:
            state = self.ai_state_database
            if state.get("captureFresh"):
                return self._json({"pendingInput": str(state.get("captureDraftInput") or "")})
            draft_id = state.get("captureDraftPlanId")
            if draft_id and not find(state, draft_id) and state.get("captureDraftInput"):
                return self._json({"pendingInput": state["captureDraftInput"]})
            record = find(state, state.get("selectedAiPlanId"))
            if not record or record.get("kind") != "capture":
                candidates = [item for item in state.get("savedPlans", []) if item.get("kind") == "capture"]
                record = max(candidates, key=lambda item: item.get("updatedAt", ""), default=None)
            return self._json(record or {})

    @Slot()
    def newAiCapture(self):
        with self._ai_state_lock:
            self.ai_state_database["captureFresh"] = True
            self.ai_state_database.pop("captureDraftInput", None)
            self.ai_state_database.pop("captureDraftPlanId", None)
            self._save_ai_state()
        self.aiStateChanged.emit()

    @Slot(str)
    def saveNewAiCaptureDraft(self, text):
        if self.ai_state_database.get("captureFresh") and not self._ai_request_running and len(text) <= 20000:
            with self._ai_state_lock:
                self.ai_state_database["captureDraftInput"] = text
                self._save_ai_state()

    @Slot(str, result=bool)
    def openSavedAiPlan(self, plan_id):
        if self._ai_request_running:
            self.messageRequested.emit("info", "正在准备方案", "等这次请求结束后再切换，原方案会保留。")
            return False
        from ai_library import find
        with self._ai_state_lock:
            record = find(self.ai_state_database, plan_id)
            if not record:
                return False
            record['plan']['libraryId']=record['id']
            self.ai_state_database["selectedAiPlanId"] = plan_id
            self.ai_state_database.pop("captureFresh", None)
            if record.get("kind") == "capture":
                self.ai_state_database["captureDraftInput"] = record.get("draft", {}).get("original", record["plan"].get("captureOriginal", ""))
                self.ai_state_database["captureDraftPlanId"] = plan_id
            else:
                self.ai_state_database.pop("captureDraftInput", None)
                self.ai_state_database.pop("captureDraftPlanId", None)
            self._save_ai_state(latest_plan=copy.deepcopy(record["plan"]), latest_path=record.get("path", ""), messages=record.get("messages", []))
        self.aiStateChanged.emit()
        return True

    @Slot(str, str, result=bool)
    def saveAiCaptureDraft(self, plan_id, payload):
        from ai_library import find, now
        try:
            draft = json.loads(payload)
            if not isinstance(draft, dict) or not isinstance(draft.get("original"), str) or len(draft["original"]) > 20000:
                return False
            answers, tasks = draft.get("answerTexts", []), draft.get("drafts", [])
            if not isinstance(answers, list) or len(answers) > 3 or any(not isinstance(answer, str) or len(answer) > 500 for answer in answers):
                return False
            if not isinstance(tasks, list) or len(tasks) > 20 or any(not isinstance(task, dict) or not isinstance(task.get("title"), str) or len(task["title"]) > 160 for task in tasks):
                return False
            with self._ai_state_lock:
                record = find(self.ai_state_database, plan_id)
                if not record or record.get("kind") != "capture":
                    return False
                record["draft"] = {"original": draft["original"], "drafts": copy.deepcopy(tasks), "answerTexts": answers,
                                   "editOriginal": bool(draft.get("editOriginal")), "showDrafts": bool(draft.get("showDrafts"))}
                record["updatedAt"] = now()
                self._save_ai_state()
            self.aiLibraryChanged.emit()
            return True
        except (TypeError, ValueError):
            return False

    @Slot(str, result=str)
    def copySavedAiPlan(self, plan_id):
        from ai_library import duplicate
        if self._ai_request_running:
            return ""
        try:
            with self._ai_state_lock:
                record = duplicate(self.ai_state_database, plan_id)
                self._save_ai_state()
            self.aiLibraryChanged.emit()
            self.openSavedAiPlan(record["id"])
            return record["id"]
        except ValueError:
            return ""

    @Slot(str, result=bool)
    def continueSavedAiPlan(self, plan_id):
        from ai_library import find
        if self._ai_request_running:
            return False
        with self._ai_state_lock:
            record = copy.deepcopy(find(self.ai_state_database, plan_id))
        if not record or record.get("kind") != "capture":
            return False
        active = self.focus_journey.active or {}
        if active.get("source", {}).get("libraryId") == plan_id and active.get("status") != "review":
            return self.returnToGuidedFocus()
        if self.active_focus_session:
            self.messageRequested.emit("info", "已有专注正在进行", "先留个接续点，稍后再继续这份保存的方案。")
            return False
        if active and active.get("status") != "review" and active.get("source", {}).get("kind") != "guided":
            self.messageRequested.emit("info", "还有一个接续点", "先处理当前专注的接续点，再切换到保存的方案。")
            return False
        self._sync_saved_ai_journey()
        journey = record.get("journey") or {}
        if journey.get("status") in ("work", "paused") and journey.get("source", {}).get("kind") == "guided":
            journey.update(status="paused", recovered=True)
            self.focus_journey.data["active"] = journey
            self.focus_journey.save()
            self.focusJourneyChanged.emit()
            self.openSavedAiPlan(plan_id)
            return self.resumeStepFocus(journey.get("step", ""))
        self.openSavedAiPlan(plan_id)
        return self.startGuidedCapture(plan_id)

    def _restore_legacy_ai_journey(self):
        from ai_library import find, remember
        active = self.focus_journey.active or {}
        source = active.get("source", {})
        if source.get("kind") != "guided":
            return
        with self._ai_state_lock:
            if not find(self.ai_state_database, source.get("libraryId")):
                selected = find(self.ai_state_database, self.ai_state_database.get("selectedAiPlanId"))
                if selected and selected.get("kind") == "capture" and selected["plan"].get("captureOriginal") == source.get("captureOriginal"):
                    record = selected
                else:
                    plan = {"captureMode": True, "capturePhase": "answers", "tasks": source.get("captureTasks", []),
                            "captureOriginal": source.get("captureOriginal", ""), "captureFacts": source.get("captureFacts", ""),
                            "captureAnswers": source.get("captureAnswers", []), "guidance": source.get("guidance"), "questions": []}
                    record = remember(self.ai_state_database, plan)
                source["libraryId"] = record["id"]
                self.focus_journey.save()
        self._sync_saved_ai_journey()
        if active.get("status") == "review":
            self._finish_guided_capture(active)

    def _cancel_guided_request(self):
        with self._ai_state_lock:
            owned = bool(self._guided_request_id)
            self._guided_request_id = ""
            self._guided_pending = None
            if owned:
                self._ai_request_running = False
        if owned:
            self.aiRequestChanged.emit()

    def _finish_guided_capture(self, active):
        source = active.get("source", {})
        if source.get("kind") != "guided" or active.get("status") != "review":
            return
        self._guided_error = ""
        state = self.ai_state_database
        # Preserve another draft or request the user started while focusing.
        if (not self._ai_request_running and not state.get("captureFresh")
                and state.get("selectedAiPlanId") == source.get("libraryId")
                and state.get("captureDraftPlanId", source.get("libraryId")) == source.get("libraryId")):
            self.newAiCapture()

    def _reject_ai_request(self, message):
        if self._guided_pending:
            self._cancel_guided_request()
            self._guided_error = message
            self.focusSessionChanged.emit()
        self.aiRequestFinished.emit(False, message)

    def _sync_saved_ai_journey(self):
        from ai_library import snapshot
        active = self.focus_journey.active
        if not active or active.get("source", {}).get("kind") != "guided":
            return
        island = next(iter(self.island_windows.values()), None)
        if island and self.active_focus_session:
            self.focus_journey.snapshot(island.focus_snapshot(), persist=False)
            base = int(active.get("indexBase", 0))
            active["tasks"] = active.get("tasks", [])[:base] + copy.deepcopy(island.tasks)
        with self._ai_state_lock:
            if snapshot(self.ai_state_database, active):
                self._save_ai_state()
                self.aiLibraryChanged.emit()

    @Property(bool, notify=aiRequestChanged)
    def aiRequestRunning(self) -> bool:
        return self._ai_request_running

    @Property(str, notify=longPlanChanged)
    def longPlanJson(self) -> str:
        return self.get_long_plan_json()

    @Property(str, notify=focusSessionChanged)
    def focusSessionJson(self) -> str:
        return self._last_focus_payload

    @Property(str, notify=focusJourneyChanged)
    def focusJourneyJson(self) -> str:
        return self._json(self.focus_journey.data)

    @Property(bool, constant=True)
    def focusWebAvailable(self) -> bool:
        try:
            import PySide6.QtWebEngineWidgets  # noqa: F401
            import PySide6.QtWebChannel  # noqa: F401
            return True
        except ImportError:
            return False

    @Property(str, notify=focusSessionChanged)
    def focusStudioStateJson(self) -> str:
        active = self.focus_journey.active or {}
        state = json.loads(self._last_focus_payload)
        island = next(iter(self.island_windows.values()), None)
        current = island._current_task() if island else {}
        target = sum(int(task.get("time", 0)) for task in active.get("tasks", []) if task.get("type", "focus") == "focus")
        elapsed = int(active.get("elapsedSeconds", 0))
        history = self.focus_journey.data.get("history", [])
        forest = self.focus_journey.data.get("forest", [])
        return self._json({
            "status": active.get("status", "prepare"), "phase": state.get("type", "focus"),
            "remaining": state.get("remaining") if state.get("remaining") is not None else active.get("remainingSeconds", 0),
            "goal": current.get("title", "") if active.get("source", {}).get("kind") == "guided" else active.get("step") or active.get("title") or tr("专注于眼前"),
            "title": active.get("title", ""), "elapsed": elapsed,
            "progress": 1.0 if self._studio_celebrating else min(1.0, elapsed / max(1, target)),
            "round": current.get("round", 1), "rounds": active.get("source", {}).get("pomodoroRounds", 1),
            "kind": active.get("source", {}).get("kind", "step"), "scene": self._studio_scene,
            "trees": len(forest), "forest": [{"id": tree["id"], "seed": tree["seed"]} for tree in forest],
            "sessionId": active.get("id", ""), "sessionSeed": FocusJourney.tree_seed(active.get("id", "")), "celebrating": self._studio_celebrating,
            "rainSound": bool(self.settings_database.get("focusRainSound", False)),
            "rainVolume": self.settings_database.get("focusRainVolume", .25),
            "minutes": sum(int(item.get("elapsedSeconds", 0)) for item in history) // 60,
            "language": self.settings_database.get("language", "zh_CN"),
            "weather": self._focus_weather.state if self._focus_weather else {"status": "idle", "kind": "neutral"},
            "weatherMode": self.settings_database.get("focusWeatherMode", "auto"),
            "weatherCity": self.settings_database.get("focusWeatherCity", ""),
            "guided": active.get("source", {}).get("kind") == "guided",
            "immersive": self._immersive_active,
            "guidedWaiting": bool(island and island.guided_waiting),
            "guidedStep": island.current_index if island else -1,
            "guidedBusy": self._guided_pending is not None,
            "guidedError": self._guided_error,
            "guidedDetail": current.get("subtitle", ""),
            "guidedIntro": active.get("source", {}).get("guidance", {}).get("intro", ""),
            "guidedRewardSeq": self._guided_reward_seq, "guidedRewardText": self._guided_reward_text,
            "rewardSound": bool(self.settings_database.get("guidedRewardSound", True)),
            "guidedCanContinue": bool(island and island.current_index + 1 < len(island.tasks)),
            "reportedProgress": active.get("source", {}).get("reportedProgress", {}),
            "guidedClarification": active.get("source", {}).get("pendingClarification"),
            "progressCheckMinutes": self._progress_check_minutes(),
        })

    @Slot(str, result=bool)
    def enterFocusStudio(self, scene: str) -> bool:
        if hasattr(self, "_supervision") and self._supervision.active:
            self.presentSupervision("full")
            return True
        if not self.active_focus_session or not self.focus_journey.active:
            return False
        self._studio_scene = "room" if scene == "room" else "tree"
        self._immersive_active = True
        self._studio_celebrating = False
        if self._focus_weather is None:
            from focus_weather import FocusWeather
            self._focus_weather = FocusWeather(self)
            self._focus_weather.changed.connect(self.focusSessionChanged.emit)
        self._focus_weather.refresh()
        if self.focusWebAvailable:
            from focus_studio_window import FocusStudioWindow
            if self._studio_window is None:
                self._studio_window = FocusStudioWindow(self)
            self._studio_window.present()
        self.immersiveFocusRequested.emit(self._studio_scene)
        for island in list(self.island_windows.values()):
            island.hide()
        self.focusSessionChanged.emit()
        return True

    @Slot()
    def exitFocusStudio(self) -> None:
        if not self._immersive_active:
            return
        self._sync_saved_ai_journey()
        self._immersive_active = False
        # Changing the presentation must not discard an in-flight guided step.
        self._studio_celebrating = False
        if self._studio_window is not None:
            self._studio_window.hide()
        self.immersiveFocusClosed.emit()
        for island in list(self.island_windows.values()):
            if not island._finished and not island._cancelled:
                island.show()

    @Slot(str, str)
    def focusStudioAction(self, name: str, value: str) -> None:
        # Only this small interface is registered in the local page's channel.
        active = self.focus_journey.active or {}
        if name.startswith("guided-"):
            if value.startswith("{"):
                try:
                    command = json.loads(value)
                    island = next(iter(self.island_windows.values()), None)
                    if not island or command.get("expectedStep") != island.current_index or command.get("expectedSession") != active.get("id"):
                        return
                    value = str(command.get("feedback") or "")
                except (TypeError, ValueError):
                    return
            self.guidedFocusAction(name[7:], value)
            return
        if name == "exit":
            self.exitFocusStudio()
        elif name == "review":
            self.exitFocusStudio()
        elif name == "rain-sound":
            settings = dict(self.settings_database)
            settings["focusRainSound"] = value == "on"
            self.save_settings(self._json(settings))
            self.focusSessionChanged.emit()
        elif name == "reward-sound":
            self.setSetting("guidedRewardSound", value == "on")
            self.focusSessionChanged.emit()
        elif name == "progress-check":
            try:
                minutes = int(value)
                if minutes in (0, 10, 20, 30):
                    self.setSetting("guidedProgressCheckMinutes", minutes)
                    self.focusSessionChanged.emit()
            except (TypeError, ValueError):
                return
        elif name == "rain-volume":
            try:
                volume = float(value)
                if 0 <= volume <= 1:
                    settings = dict(self.settings_database)
                    settings["focusRainVolume"] = volume
                    self.save_settings(self._json(settings))
                    self.focusSessionChanged.emit()
            except (TypeError, ValueError):
                pass
        elif name == "weather" and self._focus_weather is not None:
            try:
                config = json.loads(value)
                self._focus_weather.configure(config.get("mode"), config.get("city", ""))
            except (ValueError, TypeError, AttributeError):
                pass
        elif name == "weather-refresh" and self._focus_weather is not None:
            self._focus_weather.refresh(force=True)
        elif name == "pause":
            self.pauseStepFocus(active.get("progress", ""), active.get("nextAction") or active.get("step", ""))
        elif name == "resume":
            self.resumeStepFocus(active.get("step", ""))
        elif name == "leave":
            self.pauseStepFocus(active.get("progress", ""), active.get("nextAction") or active.get("step", ""))
            self.exitFocusStudio()
        elif name == "finish":
            self.endStepFocus()
        elif name == "thought":
            self.captureFocusThought(value)
        elif name == "scene":
            self._studio_scene = "room" if value == "room" else "tree"
            self.focusSessionChanged.emit()

    @Slot(float, int, int, int, int, str, bool, result=bool)
    @Slot(float, int, int, int, int, str, bool, int, result=bool)
    def startPomodoroFocus(self, task_id: float, work: int, short_break: int, long_break: int,
                           rounds: int, step: str, shield: bool, long_break_every: int = 4) -> bool:
        if self.active_focus_session:
            return False
        task = next((item for item in self._visible_tasks() if int(item.get("id", -1)) == int(task_id)), None)
        if task_id >= 0 and (not task or task.get("done")):
            self.messageRequested.emit("warning", tr("任务不可开始"), tr("请选择一个未完成任务"))
            return False
        self._journey_step = str(step).strip()[:1000]
        self._journey_end_reason = "stopped"
        title = task.get("title") if task else tr("自由专注")
        tasks = pomodoro_tasks(title, self._journey_step, work, short_break, long_break, rounds, long_break_every)
        options = self._focus_options({"disableOtherApps": bool(shield), "keepWindowOpen": True})
        session = {"mode": "single", "kind": "pomodoro", "title": title,
                   "workMinutes": max(1, min(180, work)),
                   "completedRounds": max(1, min(12, rounds)),
                   "shortBreakMinutes": max(1, min(30, short_break)),
                   "longBreakMinutes": max(1, min(60, long_break)),
                   "longBreakEvery": max(1, min(12, long_break_every)),
                   "subtitle": self._journey_step, "taskId": task.get("id") if task else None,
                   "totalTasks": len(tasks), "pomodoroRounds": max(1, min(12, rounds)),
                   "totalSeconds": sum(item["time"] for item in tasks),
                   "focusSeconds": sum(item["time"] for item in tasks if item["type"] == "focus"),
                   "options": self._public_focus_options(options)}
        try:
            return bool(self._launch_island(tasks, "single", session, options))
        except Exception as error:
            self.messageRequested.emit("error", tr("无法启动专注"), str(error))
            return False
        finally:
            self._journey_step = ""

    @Slot(float, float, str, bool, result=bool)
    def startStepFocus(self, task_id: float, minutes: float, step: str, shield: bool) -> bool:
        if self.active_focus_session:
            self.messageRequested.emit("warning", tr("已有专注正在进行"), tr("先回到当前这一轮，再开始下一步"))
            return False
        task = next((item for item in self._visible_tasks() if int(item.get("id", -1)) == int(task_id)), None)
        if task_id >= 0 and (not task or task.get("done")):
            self.messageRequested.emit("warning", tr("任务不可开始"), tr("请选择一个未完成任务"))
            return False
        self._journey_step = str(step).strip()[:1000]
        self._journey_end_reason = "stopped"
        payload = {
            "title": task.get("title") if task else tr("自由专注"),
            "taskId": task.get("id") if task else None,
            "subtitle": self._journey_step or tr("从一个小动作开始"),
            "minutes": max(1, min(180, int(minutes or 25))),
            "options": self._focus_options({"disableOtherApps": bool(shield), "keepWindowOpen": True}),
        }
        try:
            ok = bool(self.start_single_task(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动专注"), str(error))
        finally:
            self._journey_step = ""
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(str, result=bool)
    def captureFocusThought(self, text: str) -> bool:
        ok = self.focus_journey.capture(text)
        if ok:
            self.focusJourneyChanged.emit()
        return ok

    @Slot(str, result=bool)
    def resolveFocusThought(self, thought_id: str) -> bool:
        ok = self.focus_journey.resolve(thought_id)
        if ok:
            self.focusJourneyChanged.emit()
        return ok

    @Slot(str, str, result=bool)
    def pauseStepFocus(self, progress: str, next_action: str) -> bool:
        if not self.focus_journey.active:
            return False
        self.focus_journey.bookmark(progress, next_action)
        if not self.active_focus_session:
            self.focusJourneyChanged.emit()
            return self.focus_journey.active.get("status") == "paused"
        for island in list(self.island_windows.values()):
            island.pause_focus()
        return bool(self.focus_journey.active and self.focus_journey.active.get("status") == "paused")

    @Slot(str, str, result=bool)
    def parkStepFocus(self, progress: str, next_action: str) -> bool:
        if not self.focus_journey.bookmark(progress, next_action):
            return False
        self._journey_parked = True
        try:
            self.cancel_focus_session()
        finally:
            self._journey_parked = False
        self.focusJourneyChanged.emit()
        return True

    @Slot(str, result=bool)
    def resumeStepFocus(self, next_action: str) -> bool:
        active = self.focus_journey.active
        if not active:
            checkpoint = self.focus_journey.data.get("checkpoint")
            if not checkpoint:
                return False
            return self.startStepFocus(
                checkpoint.get("taskId") if checkpoint.get("taskId") is not None else -1,
                max(1, min(180, int(checkpoint.get("plannedSeconds", 1500)) // 60)),
                next_action or checkpoint.get("step", ""), False,
            )
        if active.get("status") != "paused":
            return False
        active["step"] = str(next_action or active.get("nextAction") or active.get("step") or "").strip()[:1000]
        if self.active_focus_session:
            if self._pending_flow_key:
                self.showPendingFlowStep()
                return True
            if active.get("source", {}).get("kind") == "guided" and any(island.guided_waiting for island in self.island_windows.values()):
                return self.enterFocusStudio(self._studio_scene)
            for island in list(self.island_windows.values()):
                island.resume_focus()
            return active.get("status") == "work"
        tasks = json.loads(self._json(active.get("tasks", [])))[int(active.get("index", 0)):]
        guided_boundary = active.get("source", {}).get("kind") == "guided" and int(active.get("remainingSeconds") or 0) == 0
        flow_boundary = bool(active.get('source', {}).get('options', {}).get('flowConfirm')) and int(active.get('remainingSeconds') or 0) == 0
        if active.get('source', {}).get('flowOrigin'):
            try:
                self._validate_flow(tasks[0].get('relationNodeKey') or self._session_relation_key(active))
            except (ValueError, OSError, IndexError) as error:
                self.flowInvalidRequested.emit(str(error))
                return False
        if not tasks or (int(active.get("remainingSeconds") or 0) <= 0 and not guided_boundary and not flow_boundary):
            active["status"] = "review"
            self.focus_journey.save()
            self.focusJourneyChanged.emit()
            return False
        tasks[0]["time"] = int(active["remainingSeconds"])
        if active.get("mode") == "single":
            tasks[0]["subtitle"] = active["step"]
        session = dict(active.get("source", {}))
        session.update(totalSeconds=sum(int(task.get("time", 0)) for task in tasks),
                       focusSeconds=sum(int(task.get("time", 0)) for task in tasks if task.get("type", "focus") == "focus"))
        options = self._focus_options(dict(session.get("options", {}), keepWindowOpen=True))
        if session.get("kind") == "guided":
            options["guided"] = True
        self._journey_resuming = True
        try:
            ok = bool(self._launch_island(tasks, active.get("mode", "single"), session, options))
            if ok and flow_boundary:
                island = next(iter(self.island_windows.values()))
                island._timer.stop()
                island.flow_waiting = True
                island._set_root_property('running', False)
                island._set_root_property('awaitingChoice', True)
                island._emit_state('task_done', 0)
            if ok and guided_boundary:
                island = next(iter(self.island_windows.values()))
                island._timer.stop()
                island.guided_waiting = True
                island._set_root_property("running", False)
                island._set_root_property("awaitingChoice", True)
                island._emit_state("task_done", 0)
            if ok and session.get("kind") == "guided":
                self.enterFocusStudio(self._studio_scene)
            return ok
        except Exception as error:
            self.messageRequested.emit("error", tr("无法恢复专注"), str(error))
            return False
        finally:
            self._journey_resuming = False

    @Slot(result=bool)
    def endStepFocus(self) -> bool:
        if not self.focus_journey.active:
            return False
        self._journey_end_reason = "step_done"
        if self.active_focus_session:
            self.cancel_focus_session()
        else:
            self._cancel_guided_request()
            self.focus_journey.active["status"] = "review"
            self.focus_journey.save()
            self._sync_saved_ai_journey()
            self._finish_guided_capture(self.focus_journey.active)
            self.focusJourneyChanged.emit()
            self.focusSessionChanged.emit()
        return True

    @Slot(str, str, bool, result=bool)
    def saveStepReview(self, progress: str, next_action: str, task_done: bool) -> bool:
        active = self.focus_journey.active
        if not active or self.active_focus_session:
            return False
        # The user's explicit checkbox, never clock expiration, completes a task.
        task_id = active.get("taskId")
        relation_key = self._session_relation_key(active)
        related = bool(relation_key and self._relation_options(relation_key))
        if task_done and task_id is not None and active.get("mode") == "single":
            self.toggle_task_status(float(task_id), True)
        elif task_done and relation_key:
            self._complete_relation_nodes([relation_key])
        record = self.focus_journey.finish(progress, next_action, bool(task_done))
        self.focusJourneyChanged.emit()
        if record and related and not active.get('relationPrompted'):
            self.relationCompletionRequested.emit(relation_key, bool(task_done))
        return record is not None

    def _relation_graph(self):
        # IDs are stored on children, rather than derived from their order/title.
        from ai_library import write_state
        for records, field, path in ((self.groups_database, "steps", self.groups_file),
                                     (self.projects_database, "milestones", self.projects_file)):
            prepared = copy.deepcopy(records)
            if ensure_child_ids(prepared, field):
                write_state(path, prepared)
                records[:] = prepared
        graph = build_graph(self.local_database, self.groups_database, self.projects_database,
                            self._today_key(), self.task_relations.data["positions"], self.task_relations.data["collectionPositions"])
        graph["edges"] = self.task_relations.execution_edges(graph["nodes"])
        return graph

    @Property(str, notify=taskRelationsChanged)
    def taskRelationsJson(self):
        return self._json(self._relation_graph())

    @Slot(str)
    def openTaskRelations(self, node_key):
        self.taskRelationsRequested.emit(node_key)

    @Slot(result=str)
    def newRelationId(self):
        return uuid4().hex

    @Slot(str, str, str, result=bool)
    def connectTaskRelation(self, source, target, kind):
        try:
            self.task_relations.connect(source, target, kind, self._relation_graph()["nodes"])
            self.taskRelationsChanged.emit()
            return True
        except (ValueError, OSError) as error:
            self.flowInvalidRequested.emit(str(error))
            return False

    @Slot(str, result=bool)
    def disconnectTaskRelation(self, edge_id):
        try:
            self.task_relations.disconnect(edge_id)
            self.taskRelationsChanged.emit()
            return True
        except (ValueError, OSError) as error:
            self.messageRequested.emit("error", "未能移除连线", str(error))
            return False

    @Slot(str, float, float, result=bool)
    def moveRelationNode(self, key, x, y):
        try:
            if not any(n["key"] == key for n in self._relation_graph()["nodes"]):
                return False
            self.task_relations.move(key, x, y)
            return True
        except (ValueError, OSError) as error:
            self.messageRequested.emit("error", "位置未保存", str(error))
            return False

    @Slot(result=bool)
    def resetRelationLayout(self):
        try:
            data = copy.deepcopy(self.task_relations.data)
            data["positions"] = {}
            data["collectionPositions"] = {}
            self.task_relations.commit(data)
            self.taskRelationsChanged.emit()
            return True
        except OSError as error:
            self.messageRequested.emit("error", "布局未保存", str(error))
            return False

    @Slot(str, float, float, result=bool)
    def moveRelationCollection(self, key, x, y):
        try:
            if not any(c["key"] == key for c in self._relation_graph()["collections"]):
                return False
            self.task_relations.move_collection(key, x, y)
            self.taskRelationsChanged.emit()
            return True
        except (ValueError, OSError) as error:
            self.messageRequested.emit("error", "集合位置未保存", str(error))
            self.taskRelationsChanged.emit()
            return False

    def _relation_options(self, key):
        nodes = self._relation_graph()["nodes"]
        return self.task_relations.related(key, "next", nodes) or self.task_relations.related(key, "together", nodes)

    @Slot(str, result=str)
    def getRelationChoices(self, key):
        nodes = self._relation_graph()["nodes"]
        next_nodes = self.task_relations.related(key, "next", nodes)
        island = self._waiting_flow_island(key)
        if island:
            lookup = {n['key']: n for n in nodes}
            following = next((t for t in island.tasks[island.current_index + 1:] if t.get('type') != 'break' and not lookup.get(t.get('relationNodeKey'), {}).get('done')), None)
            if following:
                next_nodes = [n for n in nodes if n['key'] == following.get('relationNodeKey')]
            else:
                group_key = f"group:{self.active_focus_session['groupId']}" if self.active_focus_session and self.active_focus_session.get('groupId') is not None else ''
                if group_key:
                    next_nodes += self.task_relations.related(group_key, 'next', nodes)
                    next_nodes = list({n['key']: n for n in next_nodes}.values())
        return self._json({"node": next((n for n in nodes if n["key"] == key), {}),
            "next": next_nodes,
            "together": self.task_relations.related(key, "together", nodes)})

    def _validate_flow(self, key):
        nodes = self._relation_graph()['nodes']
        node = next((n for n in nodes if n['key'] == key), {})
        group_key = key if key.startswith('group:') else node.get('parentKey', '')
        if group_key.startswith('group:'):
            group = next((g for g in self.groups_database if f"group:{g['id']}" == group_key), {})
            self._validate_group(group)
        self.task_relations.validate(nodes, key)

    @Slot(str)
    def prepareFlowNode(self, key):
        try:
            self._validate_flow(key)
            node = next((n for n in self._relation_graph()['nodes'] if n['key'] == key), None)
            if not node or node.get('done') or node.get('isBreak'):
                raise ValueError('请选择未完成的工作任务。')
            if self.active_focus_session:
                raise ValueError('已有专注正在进行，请先结束当前专注。')
            self.flowPreparationRequested.emit(key)
        except (ValueError, OSError) as error:
            self.flowInvalidRequested.emit(str(error))

    @Slot(str)
    def prepareRelationNode(self, key):
        self.prepareFlowNode(key)

    @Slot(str, float, str, bool, result=bool)
    def startRelationNode(self, key, minutes, goal, shield):
        try:
            self._validate_flow(key)
        except (ValueError, OSError) as error:
            self.flowInvalidRequested.emit(str(error))
            return False
        node = next((n for n in self._relation_graph()["nodes"] if n["key"] == key), None)
        if not node or node["done"] or node.get("isBreak") or self.active_focus_session:
            return False
        self._relation_launch_key = key
        self._journey_step = str(goal).strip() or node["title"]
        self._journey_end_reason = "stopped"
        try:
            if node['kind'] == 'group':
                return self.startGroupById(float(node['itemId']), self._json({'disableOtherApps': bool(shield)}))
            if node['kind'] == 'project':
                return self.startProjectById(float(node['itemId']), self._json({'disableOtherApps': bool(shield)}))
            if node['kind'] == 'task':
                return self.startStepFocus(float(node['itemId']), minutes, goal, shield)
            return bool(self.start_single_task(self._json({"title": node["title"], "subtitle": self._journey_step,
                "minutes": max(1, min(180, int(minutes or node["minutes"]))),
                "options": self._focus_options({"disableOtherApps": bool(shield), "keepWindowOpen": True})})))
        finally:
            self._relation_launch_key = ""
            self._journey_step = ""

    def _launch_island(self, tasks, mode, session, options=None):
        if (options or {}).get('flowConfirm'):
            session['flowOrigin'] = True
            session['flowStages'] = copy.deepcopy(tasks)
        if self._relation_launch_key:
            session["relationNodeKey"] = self._relation_launch_key
            session['flowOrigin'] = True
        return super()._launch_island(tasks, mode, session, options)

    @staticmethod
    def _session_relation_key(active):
        source = active.get("source", {})
        if source.get("relationNodeKey"):
            return source["relationNodeKey"]
        if active.get("taskId") is not None:
            return f"task:{active['taskId']}"
        for kind in ("group", "project"):
            if source.get(kind + "Id") is not None:
                return f"{kind}:{source[kind + 'Id']}"
        return ""

    @Slot(str)
    def requestRelationCompletion(self, key):
        if self.active_focus_session:
            island = next((i for i in self.island_windows.values() if not i._finished and not i._cancelled), None)
            if island and island._current_task().get('relationNodeKey') == key:
                if island.flow_waiting:
                    self.showPendingFlowStep()
                else:
                    island.finish_flow_segment()
                return
            if key == self._session_relation_key(self.focus_journey.active or {}) and self.active_focus_session.get('mode') == 'single':
                self.endStepFocus()
                return
            if key == f"group:{self.active_focus_session.get('groupId')}":
                self.messageRequested.emit('info', '任务流正在进行', '请先完成当前步骤，再结束整个任务流。')
                return
        if any(n["key"] == key for n in self._relation_graph()["nodes"]):
            self.relationCompletionRequested.emit(key, True)

    def _complete_relation_nodes(self, keys, done=True):
        from ai_library import write_state
        keys = set(keys)
        tasks, groups, projects = copy.deepcopy(self.local_database), copy.deepcopy(self.groups_database), copy.deepcopy(self.projects_database)
        now = datetime.now().isoformat(timespec="seconds")
        for task in tasks:
            if f"task:{task['id']}" in keys:
                task.update(done=bool(done), completedAt=now if done else "")
                if task.get("taskType") == "daily":
                    task["dailyStatus"] = "normal"
        for group in groups:
            for step in group.get("steps", []):
                if f"group:{group['id']}" in keys or f"step:{group['id']}:{step.get('relationId')}" in keys:
                    if step.get('taskId') is not None:
                        task = next((t for t in tasks if str(t['id']) == str(step['taskId'])), None)
                        if task:
                            task.update(done=bool(done), completedAt=now if done else '')
                    else:
                        step["relationDone"] = bool(done)
        for project in projects:
            milestones = project.get("milestones", [])
            for item in milestones:
                if f"project:{project['id']}" in keys or f"milestone:{project['id']}:{item.get('relationId')}" in keys:
                    item["done"] = bool(done)
            project["progress"] = sum(bool(m.get("done")) for m in milestones) / len(milestones) if milestones else 0
        for path, before, after, signal in ((self.tasks_file, self.local_database, tasks, self.signalTasksUpdated),
                (self.groups_file, self.groups_database, groups, self.signalGroupsUpdated),
                (self.projects_file, self.projects_database, projects, self.signalProjectsUpdated)):
            if before != after:
                write_state(path, after)
                before[:] = after
                signal.emit(self._json(after))
        self._emit_stats_and_achievements()

    @Slot(str, result=bool)
    def reopenRelationNode(self, key):
        try:
            if not any(n["key"] == key for n in self._relation_graph()["nodes"]):
                return False
            self._complete_relation_nodes([key], False)
            return True
        except OSError as error:
            self.messageRequested.emit("error", "未能重新打开任务", str(error))
            return False

    @Slot(str, bool, bool, str, result=bool)
    def confirmRelationCompletion(self, key, complete_source, together, next_key):
        try:
            nodes = self._relation_graph()["nodes"]
            self.task_relations.validate(nodes, key)
            if not any(n["key"] == key for n in nodes):
                raise ValueError("原任务已被移除。")
            if next_key and next_key not in {n["key"] for n in json.loads(self.getRelationChoices(key))['next']}:
                raise ValueError("下一项关联已经改变，请重新选择。")
            if complete_source:
                keys = [key] + ([n["key"] for n in self.task_relations.related(key, "together", nodes)] if together else [])
                if next_key in keys:
                    raise ValueError("下一项也在一起完成的任务中，请取消同时完成或选择其他下一项。")
                self._complete_relation_nodes(keys)
            island = self._waiting_flow_island(key)
            if island:
                self._pending_flow_key = ''
                latest = {n['key']: n for n in self._relation_graph()['nodes']}
                future = [t for t in island.tasks[island.current_index + 1:] if t.get('type') == 'break' or not latest.get(t.get('relationNodeKey'), {}).get('done')]
                while future and future[-1].get('type') == 'break': future.pop()
                island.tasks[island.current_index + 1:] = future
                final_stage = not any(t.get('type') != 'break' for t in island.tasks[island.current_index + 1:])
                if final_stage:
                    if self.focus_journey.active:
                        self.focus_journey.active['relationPrompted'] = True
                    island.continue_flow()
                    if next_key:
                        QTimer.singleShot(0, lambda: self.prepareFlowNode(next_key))
                elif next_key:
                    island.continue_flow()
                else:
                    self._journey_end_reason = 'stopped'
                    island.cancel_focus()
                return True
            if next_key:
                QTimer.singleShot(0, lambda: self.prepareFlowNode(next_key))
            return True
        except ValueError as error:
            self.flowInvalidRequested.emit(str(error))
            return False
        except OSError as error:
            self.messageRequested.emit("error", "未能完成关联操作", str(error))
            return False

    def _waiting_flow_island(self, key):
        if key != self._pending_flow_key or not key:
            return None
        return next((i for i in self.island_windows.values() if getattr(i, 'flow_waiting', False) and not i._cancelled and not i._finished), None)

    @Slot()
    def showPendingFlowStep(self):
        if self._pending_flow_key:
            self.relationCompletionRequested.emit(self._pending_flow_key, True)

    @Slot(float, result=str)
    def getGroupSteps(self, group_id):
        self._relation_graph()
        group = next((g for g in self.groups_database if int(g['id']) == int(group_id)), {})
        tasks = {str(t['id']): t for t in self.local_database if not t.get('archived')}
        result = []
        for step in group.get('steps', []):
            task = tasks.get(str(step.get('taskId')), {})
            done = task.get('done') if step.get('taskId') is not None else step.get('relationDone')
            if done: continue
            result.append(dict(step, title=task.get('title') or step.get('name') or step.get('title') or '步骤',
                time=step.get('duration') or step.get('time') or 25,
                relationNodeKey=f"task:{step['taskId']}" if step.get('taskId') is not None else f"step:{int(group_id)}:{step['relationId']}"))
        while result and result[0].get('type') == 'break': result.pop(0)
        while result and result[-1].get('type') == 'break': result.pop()
        return self._json(result)

    def _validate_group(self, group):
        if not str(group.get('name', '')).strip(): raise ValueError('请填写任务流名称。')
        seen = set()
        live = {str(t['id']) for t in self.local_database if not t.get('archived')}
        for step in group.get('steps', []):
            if any(step.get(k) is not None for k in ('groupId', 'projectId')):
                raise ValueError('任务流不能再嵌套整个任务流或项目，请添加具体步骤或待办。')
            if step.get('type') == 'break': continue
            ref = step.get('taskId')
            identity = ('task', str(ref)) if ref is not None else ('step', ''.join(str(step.get('name') or step.get('title') or '').split()).casefold())
            if ref is not None and str(ref) not in live: raise ValueError('关联待办已被移除，请重新选择。')
            if ref is not None and any(str(g.get('id')) != str(group.get('id')) and any(str(s.get('taskId')) == str(ref) for s in g.get('steps', [])) for g in self.groups_database):
                raise ValueError('这个待办已经加入其他任务流，请先从原任务流移除，避免重复执行。')
            if identity in seen: raise ValueError('同一任务不能在任务流中重复出现。')
            seen.add(identity)
        if not seen: raise ValueError('请添加至少一个工作步骤或已有待办。')

    @Slot(str, result=bool)
    def saveGroupJson(self, payload):
        try:
            self._relation_graph()
            group = json.loads(payload)
            self._validate_group(group)
            prepared = copy.deepcopy(self.groups_database)
            index = next((i for i, g in enumerate(prepared) if g['id'] == group['id']), None)
            if index is None: prepared.append(group)
            else: prepared[index] = group
            ensure_child_ids(prepared, 'steps')
            nodes = build_graph(self.local_database, prepared, self.projects_database, self._today_key())['nodes']
            self.task_relations.validate(nodes, f"group:{group['id']}")
            from ai_library import write_state
            write_state(self.groups_file, prepared)
            self.groups_database[:] = prepared
            self.signalGroupsUpdated.emit(self._json(prepared))
            return True
        except (ValueError, TypeError, KeyError, OSError) as error:
            self.flowInvalidRequested.emit(str(error))
            return False

    def start_group(self, group_json):
        try:
            if self.active_focus_session: raise ValueError('请先结束当前专注。')
            payload = json.loads(group_json)
            group = next((g for g in self.groups_database if int(g['id']) == int(payload['groupId'])), None)
            if not group: raise ValueError('任务流已被移除。')
            self._validate_group(group)
            self._validate_flow(f"group:{group['id']}")
            canonical = json.loads(self.getGroupSteps(group['id']))
            by_id = {s['relationId']: s for s in canonical}
            by_title = {s['title']: s for s in canonical}
            stages, seen = [], set()
            for supplied in payload.get('tasks', []):
                original = by_id.get(supplied.get('relationId')) if supplied.get('relationId') else by_title.get(supplied.get('title'))
                if original is None:
                    if supplied.get('relationId') and any(s.get('relationId') == supplied['relationId'] for s in group.get('steps', [])):
                        continue  # A task completed since the preparation page opened.
                    raise ValueError('步骤已发生变化，请重新打开启动准备。')
                key = original['relationNodeKey']
                if key in seen: raise ValueError('启动队列中存在重复步骤。')
                seen.add(key)
                stages.append(dict(original, time=supplied.get('time', original['time'])))
            if not any(s.get('type') != 'break' for s in stages): raise ValueError('任务流已完成，或没有可执行的步骤。')
            stage_ids = {s['relationId'] for s in stages}
            source_steps = {s['relationId']: s for s in group['steps']}
            prepared_group = copy.deepcopy(group)
            prepared_group['steps'] = [copy.deepcopy(s) for s in group['steps'] if s['relationId'] not in stage_ids]
            prepared_group['steps'] += [dict(source_steps[s['relationId']], duration=s['time']) for s in stages]
            if prepared_group != group and not self.saveGroupJson(self._json(prepared_group)):
                return False
            options = dict(payload.get('options') or {}, flowConfirm=True, keepWindowOpen=True)
            return super().start_group(self._json(dict(payload, tasks=stages, options=options)))
        except (ValueError, TypeError, KeyError, OSError) as error:
            self.flowInvalidRequested.emit(str(error))
            return False

    @Slot(str, result=bool)
    def updateTaskDetails(self, payload):
        try:
            from ai_library import write_state
            raw = json.loads(payload)
            task_id, title = int(raw["id"]), str(raw.get("title", "")).strip()
            if not title:
                raise ValueError("请填写任务名称。")
            prepared = copy.deepcopy(self.local_database)
            task = next((t for t in prepared if int(t.get("id", -1)) == task_id), None)
            if not task:
                raise ValueError("任务已不存在。")
            task.update(title=title[:1000], meta=str(raw.get("meta", ""))[:4000],
                        focusMinutes=max(1, min(180, int(raw.get("focusMinutes", 25)))), updatedAt=datetime.now().isoformat(timespec="seconds"))
            write_state(self.tasks_file, prepared)
            self.local_database = prepared
            self.signalTasksUpdated.emit(self.get_tasks_json())
            return True
        except (ValueError, TypeError, KeyError, OSError) as error:
            self.messageRequested.emit("warning", "任务未保存", str(error))
            return False

    @Property(int, notify=tasksChanged)
    def taskCount(self) -> int:
        return len(self._visible_tasks())

    @Property(int, notify=tasksChanged)
    def completedCount(self) -> int:
        today = self._today_key()
        return sum(
            1 for task in self.local_database
            if task.get("done") and str(task.get("scheduledDate") or task.get("dailyDate") or "") == today
        )

    @Property(int, notify=statsChanged)
    def todayFocusMinutes(self) -> int:
        return int(self._build_stats().get("todayFocusSeconds", 0) or 0) // 60

    @Property(str, notify=languageChanged)
    def todayLabel(self) -> str:
        return format_long_date(datetime.now())

    @Property(str, notify=settingsChanged)
    def dataPath(self) -> str:
        return str(self.get_current_data_path())

    @Property(float, notify=navigationContextChanged)
    def activeGroupId(self) -> float:
        return float(self._active_group_id)

    @Property(float, notify=navigationContextChanged)
    def activeProjectId(self) -> float:
        return float(self._active_project_id)

    @Slot(float)
    def setActiveGroupId(self, group_id: float) -> None:
        self._active_group_id = int(group_id)
        self.navigationContextChanged.emit()

    @Slot(float)
    def setActiveProjectId(self, project_id: float) -> None:
        self._active_project_id = int(project_id)
        self.navigationContextChanged.emit()

    @Slot()
    def reload(self) -> None:
        self.local_database = self._load_json(self.tasks_file, self.local_database)
        self.groups_database = self._load_json(self.groups_file, self.groups_database)
        self.projects_database = self._load_json(self.projects_file, self.projects_database)
        self.settings_database = self._load_json(self.settings_file, self.settings_database)
        self.stats_database = self._load_json(self.stats_file, self.stats_database)
        self.achievements_database = self._load_json(self.achievements_file, self.achievements_database)
        self.ai_state_database = self._load_json(self.ai_state_file, self.ai_state_database)
        self.long_plan_database = self._load_json(self.long_plan_file, self.long_plan_database)
        self._normalize_settings()
        self.tasksChanged.emit()
        self.groupsChanged.emit()
        self.projectsChanged.emit()
        self.settingsChanged.emit()
        self.statsChanged.emit()
        self.achievementsChanged.emit()
        self.aiStateChanged.emit()
        self.longPlanChanged.emit()

    @Slot(result=str)
    def listNotes(self) -> str:
        return self.note_manager.listNotes()

    @Slot(result=str)
    def createNote(self) -> str:
        return self.note_manager.createNote()

    @Slot(str)
    def showNote(self, note_id: str) -> None:
        self.note_manager.showNote(note_id)

    @Slot(str)
    def hideNote(self, note_id: str) -> None:
        self.note_manager.hideNote(note_id)

    @Slot(str)
    def toggleNoteCollapse(self, note_id: str) -> None:
        self.note_manager.toggleCollapse(note_id)

    @Slot(str)
    def deleteNote(self, note_id: str) -> None:
        self.note_manager.deleteNote(note_id)

    @Slot(str)
    def openNote(self, note_id: str) -> None:
        self.note_manager.openNote(note_id)

    @Slot(str, bool)
    def setNoteAlwaysOnTop(self, note_id: str, enabled: bool) -> None:
        self.note_manager.setAlwaysOnTop(note_id, enabled)

    @Slot(str, str)
    def setNoteCapsuleSide(self, note_id: str, side: str) -> None:
        self.note_manager.setCapsuleSide(note_id, side)

    @Slot()
    def showNotes(self) -> None:
        self.note_manager.showNotes()

    @Slot()
    def hideNotes(self) -> None:
        self.note_manager.hideNotes()

    @Slot(str, str)
    def addTask(self, title: str, meta: str = "") -> None:
        self.add_task(title, meta)

    @Slot(str, str, float)
    def addPomodoroTask(self, title: str, meta: str, focus_minutes: float) -> None:
        self.add_pomodoro_task(title, meta, int(focus_minutes or 25))

    @Slot(str, str, str)
    def addDailyTask(self, title: str, meta: str, reminder_time: str) -> None:
        self.add_daily_task(title, meta, reminder_time)

    @Slot(float, bool)
    def toggleTask(self, task_id: float, done: bool) -> None:
        key = f"task:{int(task_id)}"
        if done and self._relation_options(key):
            self.relationCompletionRequested.emit(key, True)
            self.tasksChanged.emit()
        else:
            self.toggle_task_status(task_id, done)

    @Slot(float)
    def deleteTask(self, task_id: float) -> None:
        self.task_relations.remove_nodes([f"task:{int(task_id)}"])
        self.delete_task(task_id)

    @Slot(str)
    def addGroup(self, group_json: str) -> None:
        self.saveGroupJson(group_json)

    @Slot(str)
    def updateGroup(self, group_json: str) -> None:
        self.saveGroupJson(group_json)

    @Slot(float)
    def deleteGroup(self, group_id: float) -> None:
        self.task_relations.remove_nodes([n["key"] for n in self._relation_graph()["nodes"]
                                         if n["collection"] == f"group:{int(group_id)}" and n['kind'] != 'task'])
        self.delete_group(group_id)

    @Slot(str)
    def addProject(self, project_json: str) -> None:
        self.add_project(project_json)

    @Slot(str)
    def updateProject(self, project_json: str) -> None:
        self.update_project(project_json)

    @Slot(float)
    def deleteProject(self, project_id: float) -> None:
        self.task_relations.remove_nodes([n["key"] for n in self._relation_graph()["nodes"]
                                         if n["collection"] == f"project:{int(project_id)}"])
        self.delete_project(project_id)

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._translator.language

    @Property("QVariantList", constant=True)
    def availableLanguages(self) -> list:
        return self._translator.languages

    @Slot(str)
    def setLanguage(self, language: str) -> None:
        """Persist the interface language and switch every live QML binding."""
        self.setSetting("language", normalize_language(language))

    @Slot(str, "QVariant")
    def setSetting(self, key: str, value) -> None:
        if key == 'customAppearance':return
        if key == 'nativeAccent' and str(value).lower() not in ('#0f6cbd','#0078d4','#107c10','#d83b01','#b146c2','#8764b8','#00b7c3','#e74856') and not self._custom_appearance_eligible():
            self.messageRequested.emit('warning','会员个性化','自定义颜色需要 Lite 或 Standard 账户。');return
        if key == "autoStart":
            self.setAutoStartEnabled(bool(value))
            return
        settings = dict(self.settings_database)
        # Changing volume/theme/etc. must not rewrite the OS startup registration.
        settings.pop("autoStart", None)
        if key == "aiServiceMode":
            from ai_service_settings import switch_service
            if value not in ("default", "custom", "official"):
                return
            settings = switch_service(settings, value)
        else:
            if key in ("_aiDefaultTest", "_aiCustom"):
                return
            if key in ("aiApiKey", "aiBaseUrl") and settings.get("aiServiceMode", "default") != "custom":
                return
            settings[key] = value
        self.save_settings(self._json(settings))
        if key == "focusMusicVolume":
            self._focus_music_audio.setVolume(max(0, min(1, self._safe_float(value, 0.25))))
        elif key == "focusMusicAutoPlay" and not value:
            self._focus_music.stop()
        if key == "language":
            self._translator.setLanguage(value)
        self.settingsChanged.emit()

    @Slot(str, str)
    def setSettingJson(self, key: str, value_json: str) -> None:
        """Store structured QML values without passing JS objects to PySide."""
        try:
            value = json.loads(value_json)
        except (TypeError, ValueError):
            value = value_json
        self.setSetting(key, value)

    @Slot(str, "QVariant", result="QVariant")
    def getSetting(self, key: str, fallback=None):
        from ai_service_settings import public_settings
        if key == "autoStart":
            return self._is_auto_start_enabled()
        return public_settings(self.settings_database).get(key, fallback)

    @Slot(bool, result=bool)
    def setAutoStartEnabled(self, enabled: bool) -> bool:
        result = json.loads(self.set_auto_start_enabled(enabled))
        self.settingsChanged.emit()
        if not result["ok"]:
            self.messageRequested.emit("error", "自启动设置失败", result.get("error", "请重试。"))
        return bool(result.get("enabled", False))

    @Property(bool, notify=aiServiceReadinessChanged)
    def aiServiceReady(self):
        if self.settings_database.get('aiServiceMode')=='official':
            cloud=getattr(self,'_cloud',None)
            return bool(cloud and cloud.logged_in() and cloud.cache.get('officialAI',{}).get('active') and cloud.cache.get('officialAI',{}).get('remaining',0))
        # Default connection secrets are intentionally absent from public settings.
        # Readiness must not depend on QML being able to retrieve those secrets.
        return bool(str(self.settings_database.get("aiApiKey") or "").strip())

    @Property(bool, constant=True)
    def windowsFeaturesAvailable(self):
        return sys.platform == "win32"

    @Property(str, constant=True)
    def systemDictationHint(self):
        if sys.platform == "darwin":
            return "macOS 系统听写 · 点击输入框，再从系统“编辑”菜单启动听写，或使用你设置的听写快捷键；不消耗 AI API 额度。"
        return "Windows 系统听写 · 无需 API 密钥，不消耗你的 AI 额度。未弹出时，点击输入框按 Win + H（需联网）。"

    @Slot()
    def chooseDataDirectory(self) -> None:
        self.open_directory_dialog()

    @Slot(result=str)
    def chooseExecutable(self) -> str:
        """Open a native picker for an application launched by a task flow."""
        path, _ = QFileDialog.getOpenFileName(
            QApplication.activeWindow(),
            tr("选择要自动打开的软件"),
            "",
            tr("应用程序 (*.exe *.lnk *.bat *.cmd);;所有文件 (*.*)"),
        )
        return path or ""

    @Slot(result=str)
    def chooseNotificationSound(self) -> str:
        """Select and persist a custom notification sound file."""
        path, _ = QFileDialog.getOpenFileName(
            QApplication.activeWindow(),
            tr("选择提醒音效"),
            "",
            tr("音频文件 (*.mp3 *.wav *.ogg *.flac);;所有文件 (*.*)"),
        )
        if path:
            self.setSetting("notificationSoundPath", path)
        return path or ""

    @Slot()
    def previewNotificationSound(self) -> None:
        preview_notification_sound()

    def save_settings(self, settings_json):
        super().save_settings(settings_json)
        self.settingsChanged.emit()

    @Slot(str, str, str, str)
    def addScheduledTask(self, title: str, meta: str, scheduled_date: str, scheduled_time: str = "") -> None:
        """Create a task and attach a lightweight calendar date/time to it."""
        task_id = self.add_task(title, meta, "normal", "")
        if task_id is None:
            return
        for task in self.local_database:
            if int(task.get("id", -1)) == int(task_id):
                task["scheduledDate"] = str(scheduled_date or self._today_key())
                task["scheduledTime"] = self._normalize_reminder_time(scheduled_time)
                break
        self._save_json(self.tasks_file, self.local_database)
        self.signalTasksUpdated.emit(self.get_tasks_json())

    @Slot(float, str, str)
    def setTaskSchedule(self, task_id: float, scheduled_date: str, scheduled_time: str = "") -> None:
        """Move an existing task to a day in the native calendar."""
        for task in self.local_database:
            if int(task.get("id", -1)) == int(task_id):
                task["scheduledDate"] = str(scheduled_date or self._today_key())
                task["scheduledTime"] = self._normalize_reminder_time(scheduled_time)
                task["updatedAt"] = datetime.now().isoformat(timespec="seconds")
                break
        self._save_json(self.tasks_file, self.local_database)
        self.signalTasksUpdated.emit(self.get_tasks_json())

    @Slot(float, result=bool)
    def startQuickFocus(self, minutes: float = 25) -> bool:
        return self._start_quick_focus(minutes, False)

    def _start_quick_focus(self, minutes: float, shield_enabled: bool) -> bool:
        """Start a focus session without binding it to a task."""
        payload = {
            "title": tr("自由专注"),
            "subtitle": tr("不绑定任务 · 专注当下"),
            "minutes": max(1, int(minutes or self.settings_database.get("focusDuration", 25))),
            "options": self._focus_options({"disableOtherApps": bool(shield_enabled)}),
        }
        try:
            ok = bool(self.start_single_task(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动专注"), str(error))
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(float, result=bool)
    def startQuickFocusWithGuard(self, minutes: float = 25) -> bool:
        return self._start_quick_focus(minutes, True)

    @Slot(float, result=bool)
    def startTask(self, task_id: float) -> bool:
        return self._start_task(task_id, False)

    def _start_task(self, task_id: float, shield_enabled: bool) -> bool:
        task = next((item for item in self._visible_tasks() if int(item.get("id", -1)) == int(task_id)), None)
        if not task:
            self.focusStartResult.emit(False, tr("任务不存在"))
            return False
        payload = {
            "taskId": task.get("id"),
            "title": task.get("title", tr("任务专注")),
            "subtitle": task.get("meta", tr("单任务专注")),
            "minutes": task.get("focusMinutes") or self.settings_database.get("focusDuration", 25),
            "options": self._focus_options({"disableOtherApps": bool(shield_enabled)}),
        }
        try:
            ok = bool(self.start_single_task(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动专注"), str(error))
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(float, result=bool)
    def startTaskWithGuard(self, task_id: float) -> bool:
        return self._start_task(task_id, True)

    @Slot(float, float, result=bool)
    def startPreparedTask(self, task_id: float, minutes: float) -> bool:
        task = next((item for item in self._visible_tasks() if int(item.get("id", -1)) == int(task_id)), None)
        if not task:
            self.focusStartResult.emit(False, tr("任务不存在"))
            return False
        payload = {
            "taskId": task.get("id"),
            "title": task.get("title", tr("任务专注")),
            "subtitle": task.get("meta", tr("单任务专注")),
            "minutes": max(1, int(minutes or self.settings_database.get("focusDuration", 25))),
        }
        try:
            ok = bool(self.start_single_task(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动专注"), str(error))
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(float)
    def startFocus(self, task_id: float) -> bool:
        return self.startTask(task_id)

    @Slot(float, str, result=bool)
    def startGroupById(self, group_id: float, options_json: str = "{}") -> bool:
        group = next((item for item in self.groups_database if int(item.get("id", -1)) == int(group_id)), None)
        if not group:
            self.focusStartResult.emit(False, tr("任务流不存在"))
            return False
        try:
            options = json.loads(options_json or "{}")
        except (TypeError, ValueError):
            options = {}
        options = self._focus_options(options)
        self._journey_end_reason = "stopped"
        self._journey_step = ""
        payload = {
            "groupId": group.get("id"),
            "tasks": json.loads(self.getGroupSteps(group_id)),
            "options": options,
        }
        try:
            ok = bool(self.start_group(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动任务流"), str(error))
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(float, str, str, result=bool)
    def startPreparedGroup(self, group_id: float, tasks_json: str, options_json: str = "{}") -> bool:
        try:
            tasks = json.loads(tasks_json or "[]")
        except (TypeError, ValueError):
            tasks = []
        try:
            options = json.loads(options_json or "{}")
        except (TypeError, ValueError):
            options = {}
        options = self._focus_options(options)
        self._journey_end_reason = "stopped"
        self._journey_step = ""
        try:
            ok = bool(self.start_group(self._json({"groupId": int(group_id), "tasks": tasks, "options": options})))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动任务流"), str(error))
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(float, str, result=bool)
    def startProjectById(self, project_id: float, options_json: str = "{}") -> bool:
        project = next((item for item in self.projects_database if int(item.get("id", -1)) == int(project_id)), None)
        if not project:
            self.focusStartResult.emit(False, tr("项目不存在"))
            return False
        try:
            options = json.loads(options_json or "{}")
        except (TypeError, ValueError):
            options = {}
        options = self._focus_options(options)
        milestones = project.get("milestones") or []
        requested = options.pop("targetMilestones", None)
        goal = str(options.pop("goal", "") or project.get("desc") or project.get("description") or tr("项目专注"))
        selected = list(requested or [])
        if not selected:
            selected = [item.get("title") or item.get("name") or tr("里程碑") for item in milestones if not item.get("done")]
        if not selected:
            selected = [item.get("title") or item.get("name") or tr("里程碑") for item in milestones]
        payload = {
            "projectId": project.get("id"),
            "goal": goal,
            "targetMilestones": selected,
            "targetMilestoneIndexes": [index for index, item in enumerate(milestones) if (item.get("title") or item.get("name")) in selected],
            "options": options,
        }
        try:
            ok = bool(self.start_project(self._json(payload)))
        except Exception as error:
            ok = False
            self.messageRequested.emit("error", tr("无法启动项目"), str(error))
        self.focusStartResult.emit(ok, "" if ok else tr("灵动岛启动失败"))
        return ok

    @Slot(str, bool)
    def requestAi(self, prompt: str, long_mode: bool = False) -> None:
        self._request_ai(prompt, long_mode, False)

    @Property(QObject, constant=True)
    def speechInput(self):
        return self._speech_input

    @Property(bool, constant=True)
    def systemMotionEnabled(self):
        return system_motion_enabled()

    @Slot(QObject, result=bool)
    def openSystemDictation(self, editor):
        if sys.platform != "win32":
            self.messageRequested.emit("info", tr("系统语音输入"), self.systemDictationHint)
            return False
        if self._dictation_pending:
            return False
        if editor is None:
            return False
        self._dictation_pending = True
        self._dictation_generation += 1
        generation = self._dictation_generation
        self._dictation_editor = editor

        def activate():
            if generation != self._dictation_generation:
                return
            self._dictation_pending = False
            opened = False
            try:
                # The page or focused field may change while the click settles.
                if editor is None or not editor.property("activeFocus"):
                    return
                window = self.native_window
                if window is not None:
                    opened = open_voice_typing(int(window.winId()))
            except RuntimeError as error:
                self.messageRequested.emit("warning", tr("系统语音输入"), str(error))
            except OSError:
                self.messageRequested.emit("warning", tr("系统语音输入"), tr("请点击文本框，再按 Win + H 打开 Windows 听写。"))
            finally:
                if not opened:
                    self._dictation_editor = None
                try:
                    self.systemDictationResult.emit(editor, opened)
                except RuntimeError:
                    pass  # A page may have been destroyed during the delay.

        QTimer.singleShot(120, activate)
        return True

    @Slot(QObject)
    def endSystemDictation(self, editor):
        if editor is not self._dictation_editor:
            return
        pending = self._dictation_pending
        self._dictation_generation += 1
        self._dictation_pending = False
        self._dictation_editor = None
        if not pending and self.native_window is not None:
            try:
                close_voice_typing(int(self.native_window.winId()))
            except (OSError, RuntimeError):
                pass

    @Slot(str)
    def organizeCapture(self, text: str) -> None:
        self._request_ai(text, False, True)

    @Slot(str, str)
    @Slot(str, str, str)
    def respondCapture(self, original, answers_json, plan_id=""):
        try:
            answers = json.loads(answers_json)
            if not isinstance(answers, list) or len(answers) > 3 or any(not isinstance(item, dict) or not isinstance(item.get("answer"), str) or len(item["answer"]) > 500 or len(str(item.get("question", ""))) > 150 for item in answers):
                raise ValueError("请简短补充这些问题。")
            prompt = str(original).strip() + "\n用户补充回答（没回答的地方请保留可调整余地）：" + self._json(answers)
            self._request_ai(prompt, False, True, {"capturePhase": "answers", "captureAnswers": answers, "captureOriginal": str(original).strip(),
                             "libraryId": plan_id or (self.ai_state_database.get("latestPlan") or {}).get("libraryId", "")})
        except (ValueError, TypeError) as error:
            self.messageRequested.emit("warning", "补充回答", str(error))
            self.aiRequestFinished.emit(False, str(error))

    @Slot(str)
    def prepareSavedAiCapture(self, plan_id):
        """Recover old task-only results without creating another plan or importing tasks."""
        from ai_library import find
        with self._ai_state_lock:
            record = copy.deepcopy(find(self.ai_state_database, plan_id))
        if not record or record.get("kind") != "capture":
            self.aiRequestFinished.emit(False, "找不到这份方案，请重新打开或准备。")
            return
        plan = record["plan"]
        original = str(plan.get("captureOriginal") or "")
        context = {"tasks": [{"title": task.get("title", ""), "meta": task.get("meta", "")}
                             for task in plan.get("tasks", [])], "answers": plan.get("captureAnswers", [])}
        prompt = original + "\n已有草稿与用户回答（不是已完成事项）：" + self._json(context)
        prompt += "\n请准备当前可开始的动作，保留全部事项与约束。按用户实际状态决定时长；已回答的问题不再询问。"
        self._request_ai(prompt, False, True, {"capturePhase": "answers", "captureOriginal": original,
            "captureAnswers": plan.get("captureAnswers", []), "libraryId": plan_id})

    @Slot(result=bool)
    def returnToGuidedFocus(self):
        active = self.focus_journey.active or {}
        if active.get("source", {}).get("kind") != "guided" or active.get("status") == "review":
            return False
        if self.active_focus_session:
            return self.enterFocusStudio(self._studio_scene)
        return self.resumeStepFocus(active.get("step", ""))

    @Slot(result=bool)
    @Slot(str, result=bool)
    def startGuidedCapture(self, plan_id=""):
        if self.active_focus_session:
            self.messageRequested.emit("info", "已有专注正在进行", "先回到当前这一段，再开始新的引导。")
            return False
        try:
            from guided_focus import validate_guidance, island_tasks
            from ai_library import find, remember
            record = find(self.ai_state_database, plan_id) if plan_id else None
            plan = copy.deepcopy(record["plan"] if record else self.ai_state_database.get("latestPlan") or {})
            guide = validate_guidance(plan.get("guidance"))
            if not guide or plan.get("questions"):
                raise ValueError("先补充关键问题，让 AI 准备适合这次的动作。")
            if not self.focusWebAvailable:
                raise ValueError("当前环境缺少沉浸场景组件，请检查安装包。")
            if plan_id and not record:
                raise ValueError("这份保存的方案找不到了。")
            if not find(self.ai_state_database, plan.get("libraryId")):
                plan["captureMode"] = True
                with self._ai_state_lock:
                    remember(self.ai_state_database, plan)
                    self._save_ai_state(latest_plan=plan)
                self.aiLibraryChanged.emit()
            self._sync_saved_ai_journey()
            tasks = island_tasks(guide)
            self._guided_error = ""
            options = self._focus_options({"keepWindowOpen": True, "guided": True})
            source = {"mode": "single", "kind": "guided", "title": guide["goal"],
                      "libraryId": plan["libraryId"],
                      "guidance": guide, "captureTasks": plan.get("tasks", []),
                      "captureFacts": plan.get("captureFacts", ""), "completedActions": [],
                      "captureOriginal": plan.get("captureOriginal", ""),
                      "captureAnswers": plan.get("captureAnswers", []), "totalTasks": len(tasks),
                      "totalSeconds": sum(task["time"] for task in tasks),
                      "focusSeconds": sum(task["time"] for task in tasks if task["type"] == "focus"),
                      "options": self._public_focus_options(options)}
            self._journey_step = tasks[0]["title"]
            self._journey_end_reason = "stopped"
            if not self._launch_island(tasks, "single", source, options):
                return False
            return self.enterFocusStudio(str(self.settings_database.get("focusScene", "tree")))
        except (ValueError, RuntimeError) as error:
            self.messageRequested.emit("error", "没有启动引导", str(error))
            return False
        finally:
            self._journey_step = ""

    def _followup_island(self, key, action):
        if action == 'flow':
            self.showPendingFlowStep()
            return
        island = self.island_windows.get(key)
        if island and island.options.get("guided") and self.active_focus_session:
            if action == "studio":
                self.enterFocusStudio(self._studio_scene)
            else:
                self.guidedFocusAction("rest" if action == "break" else "next" if action == "focus" else "end", "")
            return
        return super()._followup_island(key, action)

    def _sync_guided_island_controls(self):
        active = self.focus_journey.active or {}
        for island in list(self.island_windows.values()):
            if island.options.get("guided"):
                island._set_root_property("guidedBusy", self._guided_pending is not None)
                island._set_root_property("guidedClarification", bool(active.get("source", {}).get("pendingClarification")))
                island._set_root_property("guidedError", self._guided_error)

    @Slot(str, str)
    def guidedFocusAction(self, name, feedback):
        active = self.focus_journey.active or {}
        island = next(iter(self.island_windows.values()), None)
        if not self.active_focus_session or active.get("source", {}).get("kind") != "guided" or not island:
            return
        if name == "end":
            self._cancel_guided_request()
            self.endStepFocus()
            return
        if name not in ("next", "rest", "adjust", "progress", "answers"):
            return
        if name == "rest":
            # Rest is local and remains available during clarification or a request.
            # Changing the step invalidates the in-flight continuation's context.
            self._cancel_guided_request()
            self._guided_error = ""
        elif self._guided_pending:
            self.messageRequested.emit("info", "正在准备下一段", "准备好后可以继续，也可以先休息。")
            self.focusSessionChanged.emit()
            return
        if active["source"].get("pendingClarification") and name == "next":
            if not self.enterFocusStudio(self._studio_scene):
                self.messageRequested.emit("warning", "需要补充进度", "返回 AI 助手，补充当前进度后继续。")
            return
        needs_request = name not in ("next", "rest") or (name == "next" and island.current_index + 1 >= len(island.tasks))
        if needs_request and self._ai_request_running:
            self._guided_error = "AI 正在处理其他请求，请稍后再试。"
            self.messageRequested.emit("info", "暂时不能准备下一段", self._guided_error)
            self.focusSessionChanged.emit()
            return
        from guided_focus import rest_task, continuation_context, validate_progress, validate_replies
        if name == "answers":
            clarification = active["source"].get("pendingClarification")
            if not clarification or not island.guided_waiting:
                return
            try:
                answer_payload = json.loads(feedback)
                if answer_payload.get("questionId") != clarification["id"]:
                    return
                replies = validate_replies(answer_payload.get("answers"), clarification["questions"])
                context = dict(clarification["context"])
                context["clarificationAnswers"] = replies
                context["clarificationSkipped"] = not any(reply["answer"] for reply in replies)
                context["feedback"] = "用户补充了当前进度的问题，请根据这些回答安排下一段，不重复问已回答的问题。"
                report = dict(active["source"].get("reportedProgress", {}))
                field_limits = {"subject": 60, "paper": 80, "section": 60, "position": 120}
                for question, reply in zip(clarification["questions"], replies):
                    field = question.get("field")
                    if field in field_limits and reply["answer"] and len(reply["answer"]) <= field_limits[field]:
                        report[field] = reply["answer"]
                active["source"]["reportedProgress"] = report
                context["reportedProgress"] = report
                active["source"]["captureAnswers"] = (active["source"].get("captureAnswers", []) + replies)[-9:]
                context["answers"] = active["source"]["captureAnswers"]
                self.focus_journey.save()
                self._request_guided_context(active, island, context)
            except (ValueError, TypeError, AttributeError) as error:
                self._guided_error = "进度回答无效，请重新补充。"
                self.focusSessionChanged.emit()
            return
        if name == "progress":
            try:
                report = validate_progress(json.loads(feedback))
            except (ValueError, TypeError) as error:
                self._guided_error = str(error)
                self.focusSessionChanged.emit()
                return
            # Only user reports become progress facts; timer expiration proves no task completion.
            active["source"]["reportedProgress"] = report
            active["source"].setdefault("progressReports", []).append(report)
            active["source"]["progressReports"] = active["source"]["progressReports"][-6:]
            feedback = "用户报告了当前进度，请据此调整眼前这一段。需要澄清的地方请先提问，不猜卷子或题号。"
        if name in ("progress", "adjust"):
            active["source"].pop("pendingClarification", None)
        before = island.focus_snapshot()
        current = dict(island._current_task())
        if name == "rest" and current.get("type") == "break" and not island.guided_waiting:
            self.messageRequested.emit("info", "正在休息", "准备好了可以继续下一步。")
            return
        if not island.guided_waiting:
            island.finish_guided_segment()
        guide = active["source"]["guidance"]
        if name == "next" and current.get("type") == "focus":
            step_index = int(active.get("indexBase", 0)) + island.current_index
            acknowledged = active["source"].setdefault("acknowledgedSteps", [])
            if step_index not in acknowledged:
                acknowledged.append(step_index)
                active["source"].setdefault("completedActions", []).append(current.get("title", ""))
                self.focus_journey.save()
                self._guided_reward_seq += 1
                self._guided_reward_text = current.get("encouragement") or "这一小段，你确实做到了。"
                self.guidedReward.emit()
        if name == "rest":
            inserted = [rest_task(guide)]
            if before.get("remaining", 0) > 0 and current.get("type") == "focus":
                current["time"] = before["remaining"]
                inserted.append(current)
            island.tasks[island.current_index + 1:island.current_index + 1] = inserted
        if name == "next" and island.current_index + 1 < len(island.tasks):
            completed = island.tasks[:island.current_index + 1]
            last_rest = max((index for index, task in enumerate(completed) if task.get("type") == "break"), default=-1)
            continuous = sum(task["time"] for task in completed[last_rest + 1:] if task.get("type") == "focus")
            if continuous >= guide["restAfterMinutes"] * 60 and island.tasks[island.current_index + 1].get("type") == "focus":
                island.tasks.insert(island.current_index + 1, rest_task(guide))
        if name in ("next", "rest") and island.current_index + 1 < len(island.tasks):
            self._guided_error = ""
            island._load_and_start_task(island.current_index + 1)
            return
        context = continuation_context(active["source"], current, before, feedback or ("当前动作完成，准备下一段，别重新列全部步骤。" if current.get("type") == "focus" else "休息结束，按之前的实际进展准备下一段。"))
        context["currentActionCompleted"] = name == "next"
        self.focus_journey.save()
        self._request_guided_context(active, island, context)

    def _progress_check_minutes(self):
        value = self._safe_int(self.settings_database.get("guidedProgressCheckMinutes"), 0)
        return value if value in (0, 10, 20, 30) else 0

    def _request_guided_context(self, active, island, context):
        self._guided_request_id = uuid4().hex
        self._guided_pending = {"id": active["id"], "index": island.current_index, "context": context}
        self._guided_error = ""
        self.focusSessionChanged.emit()
        self._request_ai("这是进行中的专注引导，请根据用户实际反馈调整下一段：" + self._json(context), False, True,
                         {"capturePhase": "continue", "captureAnswers": active["source"].get("captureAnswers", []), "guidedSessionId": active["id"], "guidedRequestId": self._guided_request_id,
                          "libraryId": active["source"].get("libraryId", "")})

    def _request_ai(self, prompt, long_mode, capture, extra=None):
        if self._ai_request_running:
            self.messageRequested.emit("info", tr("AI 正在生成"), tr("请等待当前请求完成"))
            return
        if self.settings_database.get("aiServiceMode") == "official" and not self._cloud.logged_in():
            self._reject_ai_request("请先登录账户，再使用官方 AI；你的回答已保留。")
            self.accountLoginRequested.emit()
            return
        if self.settings_database.get("aiServiceMode", "default") != "custom":
            usage = json.loads(self.accountJson).get("usage", {})
            if int(usage.get("remaining") or 0) <= 0:
                self._reject_ai_request("AI 额度已用完，请接入自己的 API，或升级账号后刷新额度；你的输入已保留。")
                return
        payload = {
            "messages": [{"role": "user", "content": str(prompt or "")}],
            "longMode": bool(long_mode),
            "captureMode": bool(capture),
            "replaceOnApply": bool(self.settings_database.get("aiReplaceOnApply", True)),
        }
        payload.update(extra or {})
        if capture and payload.get("capturePhase", "intake") != "continue":
            self.ai_state_database.pop("captureFresh", None)
            from ai_library import valid_id
            if not valid_id(payload.get("libraryId")):
                payload["libraryId"] = uuid4().hex
            self.ai_state_database["captureDraftPlanId"] = payload["libraryId"]
            self.ai_state_database["captureDraftInput"] = str(payload.get("captureOriginal", prompt) or "").strip()
            self._save_ai_state()
        self._ai_request_running = True
        self.aiRequestChanged.emit()
        if not capture:
            self.messageRequested.emit(
                "info",
                tr("正在生成长期计划") if long_mode else tr("正在生成计划"),
                tr("AI 正在根据实时数据整理任务结构，请稍候"),
            )
        try:
            self.request_ai_plan(self._json(payload))
        except Exception as error:
            self._ai_request_running = False
            self._guided_request_id = ""
            self._guided_pending = None
            self.aiRequestChanged.emit()
            message = str(error)
            self.messageRequested.emit("error", tr("无法发起 AI 请求,可能是Api出错"), message)
            self.aiRequestFinished.emit(False, message)

    @Slot(str,result=bool)
    def applyAiPlan(self, plan_json: str) -> bool:
        try:
            from plan_ecosystem import apply
            raw=json.loads(plan_json)
            if isinstance(raw,dict) and isinstance(raw.get('plan'),dict):raw=raw['plan']
            added=apply(self,raw)
            self.aiStateChanged.emit();self.aiLibraryChanged.emit()
            self.messageRequested.emit('success','规划已接入',f"新增 {added['tasks']} 个待办、{added['groups']} 个任务流、{added['projects']} 个项目。带日期的任务已进入日程；已有内容会保留。")
            return True
        except Exception as error:
            self.messageRequested.emit('error','规划导入失败',str(error));return False

    @Slot()
    def clearAiMessages(self) -> None:
        self.clear_ai_messages()
        self.aiStateChanged.emit()

    @Slot(result=str)
    def clearAllUserData(self) -> str:
        """Reset application data and notes, then notify all QML consumers."""
        result = self.clear_all_user_data()
        try:
            payload = json.loads(result)
        except (TypeError, ValueError):
            payload = {"ok": False, "error": tr("清理结果无效")}

        if not payload.get("ok"):
            self.messageRequested.emit(
                "error",
                tr("清除失败"),
                str(payload.get("error") or tr("无法清除本地数据")),
            )
            return result

        self.focus_journey.clear()
        self.task_relations.clear()
        self.taskRelationsChanged.emit()
        self.focusJourneyChanged.emit()
        try:
            self.note_manager.clear_all()
        except Exception as error:
            message = f"{tr('核心数据已清除，但便签清理失败：')}{error}"
            self.messageRequested.emit("error", tr("清除未完成"), message)
            return json.dumps({"ok": False, "error": message}, ensure_ascii=False)

        self.settingsChanged.emit()
        self.longPlanChanged.emit()
        self.aiStateChanged.emit()
        self.aiLibraryChanged.emit()
        self.desktopWidgetVisibilityRequested.emit(False)
        self.messageRequested.emit(
            "success",
            tr("数据已清除"),
            tr("数据已清除，应用设置已恢复默认。"),
        )
        return result

    @Slot()
    def showDesktopWidget(self) -> None:
        self.desktopWidgetVisibilityRequested.emit(True)

    @Slot()
    def hideDesktopWidget(self) -> None:
        self.desktopWidgetVisibilityRequested.emit(False)

    @Slot(str, float)
    def requestFocusPreparation(self, kind: str, item_id: float) -> None:
        kind = str(kind or "").strip().lower()
        target_id = int(item_id)
        databases = {
            "task": self._visible_tasks(),
            "group": self.groups_database,
            "project": self.projects_database,
        }
        database = databases.get(kind)
        target = next((item for item in (database or []) if int(item.get("id", -1)) == target_id), None)
        if target is None:
            self.messageRequested.emit("error", tr("无法打开专注准备"), tr("所选内容已经不存在，请刷新小组件"))
            return
        if kind == "task" and bool(target.get("done")):
            self.messageRequested.emit("warning", tr("任务已经完成"), tr("请选择一个待完成任务"))
            return
        if kind == "group":
            self.setActiveGroupId(target_id)
        elif kind == "project":
            self.setActiveProjectId(target_id)
        self.focusPreparationRequested.emit(kind, float(target_id))

    @Slot(str)
    def startLongPlan(self, plan_json: str) -> None:
        self.start_long_plan(plan_json)
        self.longPlanChanged.emit()
        self.aiStateChanged.emit()

    @Slot()
    def abandonLongPlan(self) -> None:
        self.abandon_long_plan()
        self.longPlanChanged.emit()

    @Slot(str, result=str)
    def themePreviewUrl(self, theme_id: str) -> str:
        from pathlib import Path

        names = {
            "default": "classwidgets-default.png",
            "cw1": "classwidgets-cw1.png",
            "win10": "classwidgets-win10.png",
            "material": "classwidgets-material.png",
        }
        path = Path(__file__).resolve().parent.parent / "theme_assets" / names.get(theme_id, names["material"])
        return path.resolve().as_uri()

    @Slot(result=str)
    def getFocusGuardAppsJson(self) -> str:
        """Return the selectable Windows applications for the focus guard."""
        return self.get_focus_guard_apps_json()

    @Slot(result=str)
    def getFocusSessionJson(self) -> str:
        return self._last_focus_payload

    @Slot()
    def cancelFocus(self) -> None:
        self._journey_end_reason = "stopped"
        self.cancel_focus_session()

    @Slot()
    def shutdown(self) -> None:
        self._account_refresh.stop()
        self._supervision.shutdown()
        self._speech_input.cancel()
        self._focus_music.stop()
        self._focus_snapshot_timer.stop()
        if self._focus_weather is not None:
            self._focus_weather.shutdown()
        self.exitFocusStudio()
        if self.active_focus_session and self.focus_journey.active:
            active = self.focus_journey.active
            self.parkStepFocus(active.get("progress", ""), active.get("nextAction") or active.get("step", ""))
        self.shutdown_focus_environment()
