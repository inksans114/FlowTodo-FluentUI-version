"""Explicit microphone capture and compatible transcription; audio stays in RAM."""
import io
import json
import math
import struct
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave

from PySide6.QtCore import QObject, Property, Signal, Slot, QBuffer, QIODevice, QTimer, Qt
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSource, QMediaDevices

def endpoint(base):
    base = str(base or '').strip().rstrip('/')
    for suffix in ('/chat/completions', '/audio/transcriptions'):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('请设置有效的语音 API 地址。')
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('远程语音 API 请使用 HTTPS。')
    return base + '/audio/transcriptions'

def encode_wav(raw, rate, channels, kind):
    formats = {'int16': ('h', 2, 32768), 'int32': ('i', 4, 2147483648), 'float': ('f', 4, 1), 'uint8': ('B', 1, 128)}
    code, size, divisor = formats[kind]
    frame_size = size * channels
    raw = raw[:len(raw) // frame_size * frame_size]
    if len(raw) < rate * frame_size // 2:
        raise ValueError('录音太短，请至少说半秒后再结束。')
    samples = struct.iter_unpack('<' + code * channels, raw)
    pcm = bytearray()
    square, count = 0.0, 0
    for frame in samples:
        value = sum((x - 128 if kind == 'uint8' else x) / divisor for x in frame) / channels
        if not math.isfinite(value):
            value = 0
        value = max(-1, min(1, value))
        square += value * value
        count += 1
        pcm.extend(struct.pack('<h', round(value * 32767)))
    if math.sqrt(square / max(1, count)) < 0.001:
        raise ValueError('没有检测到清晰声音，请检查麦克风后重试。')
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm)
    return output.getvalue()

def transcribe(wav, settings, opener=urllib.request.urlopen):
    base = settings.get('speechBaseUrl') or settings.get('aiBaseUrl') or 'https://api.openai.com/v1'
    url = endpoint(base)
    key = str(settings.get('speechApiKey') or settings.get('aiApiKey') or '').strip()
    if not key:
        raise ValueError('请先在 AI 服务设置中填写语音 API Key。')
    fields = {'model': str(settings.get('speechModel') or 'gpt-4o-transcribe').strip(),
              'response_format': 'json', 'language': 'zh',
              'prompt': '中文日常任务口述，简体中文。保留原话、人名、数字、时间、否定和改口。FlowTodo，待办，番茄钟，专注。'}
    # A tiny vocabulary may help names; never send task history to the ASR service.
    vocabulary = str(settings.get('speechVocabulary') or '').strip()[:200]
    if vocabulary:
        fields['prompt'] += '可能出现的专名：' + vocabulary
    boundary = 'flowtodo-' + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode('utf-8'))
    parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="voice.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(), wav, f'\r\n--{boundary}--\r\n'.encode()]
    request = urllib.request.Request(url, data=b''.join(parts), method='POST',
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    try:
        with opener(request, timeout=90) as response:
            result = json.loads(response.read(1024 * 1024).decode('utf-8'))
    except urllib.error.HTTPError as error:
        if error.code in (404, 405):
            raise RuntimeError('该接口不支持语音识别，请在设置中配置支持 /audio/transcriptions 的服务。') from None
        raise RuntimeError(f'语音识别失败（HTTP {error.code}），请检查语音模型、密钥或服务额度。') from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('语音识别连接失败或超时，请检查网络后重录；也可直接打字。') from None
    text = str(result.get('text') or '').strip()
    if not text:
        raise ValueError('没有识别到文字，请重试或直接输入。')
    if len(text) > 8000:
        raise ValueError('识别文字过长，请分段录音。')
    return text

class SpeechInput(QObject):
    changed = Signal()
    textReady = Signal(str)
    failed = Signal(str)
    _finished = Signal(int, str, str)

    def __init__(self, backend):
        super().__init__(backend)
        self.backend = backend
        self._state, self._seconds, self._revision = 'idle', 0, 0
        self._audio = self._buffer = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._finished.connect(self._accept, Qt.ConnectionType.QueuedConnection)

    @Property(str, notify=changed)
    def state(self):
        return self._state

    @Property(int, notify=changed)
    def seconds(self):
        return self._seconds

    @Slot(result=bool)
    def start(self):
        if self._state != 'idle':
            return False
        try:
            self._settings = dict(self.backend.settings_database)
            endpoint(self._settings.get('speechBaseUrl') or self._settings.get('aiBaseUrl') or 'https://api.openai.com/v1')
            if not (self._settings.get('speechApiKey') or self._settings.get('aiApiKey')):
                raise ValueError('请先配置 AI 服务的语音密钥，再开始录音。')
            device = QMediaDevices.defaultAudioInput()
            if device.isNull():
                raise ValueError('没有可用麦克风，请检查 Windows 麦克风权限与输入设备。')
            audio_format = QAudioFormat()
            audio_format.setSampleRate(16000)
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if not device.isFormatSupported(audio_format):
                audio_format = device.preferredFormat()
            self._format = audio_format
            self._buffer = QBuffer(self)
            self._buffer.open(QIODevice.OpenModeFlag.ReadWrite)
            self._audio = QAudioSource(device, audio_format, self)
            self._audio.stateChanged.connect(self._audio_state)
            self._revision += 1
            self._seconds, self._state = 0, 'recording'
            self._audio.start(self._buffer)
            if self._audio.error() != QAudio.Error.NoError:
                raise ValueError('麦克风启动失败，请检查权限与占用情况。')
            self._timer.start()
            self.changed.emit()
            return True
        except Exception as error:
            self.cancel()
            self.failed.emit(str(error))
            return False

    def _audio_state(self, state):
        if state == QAudio.State.StoppedState and self._state == 'recording' and self._audio and self._audio.error() != QAudio.Error.NoError:
            self.cancel()
            self.failed.emit('录音设备已断开或不可用，请检查麦克风。')

    def _tick(self):
        self._seconds += 1
        self.changed.emit()
        if self._seconds >= 90:
            self.stop()

    def _release(self):
        self._timer.stop()
        if self._audio:
            self._audio.stop()
            self._audio.deleteLater()
            self._audio = None
        if self._buffer:
            self._buffer.close()
            self._buffer.deleteLater()
            self._buffer = None

    @Slot()
    def stop(self):
        if self._state != 'recording':
            return
        self._state = 'transcribing'
        self._audio.stop()
        raw = bytes(self._buffer.data())
        fmt = self._format
        self._release()
        revision, settings = self._revision, self._settings
        self.changed.emit()
        def work():
            try:
                kind = {QAudioFormat.SampleFormat.Int16: 'int16', QAudioFormat.SampleFormat.Int32: 'int32', QAudioFormat.SampleFormat.Float: 'float', QAudioFormat.SampleFormat.UInt8: 'uint8'}[fmt.sampleFormat()]
                text = transcribe(encode_wav(raw, fmt.sampleRate(), fmt.channelCount(), kind), settings)
                self._finished.emit(revision, text, '')
            except Exception as error:
                self._finished.emit(revision, '', str(error))
        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def cancel(self):
        self._revision += 1
        self._state = 'idle'
        self._release()
        self.changed.emit()

    @Slot(int, str, str)
    def _accept(self, revision, text, error):
        if revision != self._revision:
            return
        self._state = 'idle'
        self.changed.emit()
        if error:
            self.failed.emit(error)
        else:
            self.textReady.emit(text)
