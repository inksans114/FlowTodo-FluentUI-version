import io
import json
import math
import struct
import unittest
import urllib.error
import wave
from speech_input import encode_wav, endpoint, transcribe

class SpeechContracts(unittest.TestCase):
    def test_stereo_to_mono_wav(self):
        raw = b''.join(struct.pack('<ff', math.sin(i / 8) * 0.1, math.sin(i / 8) * 0.1) for i in range(16000))
        audio = wave.open(io.BytesIO(encode_wav(raw,16000,2,'float')))
        self.assertEqual((audio.getnchannels(), audio.getsampwidth(), audio.getnframes()), (1,2,16000))

    def test_silence_and_short_recordings_are_not_uploaded(self):
        for raw in (b'\0' * 32000, b'\0' * 30):
            with self.assertRaises(ValueError): encode_wav(raw,16000,1,'int16')

    def test_endpoints_and_https(self):
        self.assertEqual(endpoint('https://host/v1/chat/completions'), 'https://host/v1/audio/transcriptions')
        self.assertEqual(endpoint('http://localhost:8000/v1'), 'http://localhost:8000/v1/audio/transcriptions')
        with self.assertRaises(ValueError): endpoint('http://external/v1')

    def test_upload_preserves_corrections_and_sends_only_audio_vocabulary(self):
        def fake(request, timeout):
            self.assertIn(b'filename="voice.wav"', request.data)
            self.assertIn('课程甲'.encode(), request.data)
            self.assertNotIn(b'SECRET_TASK', request.data)
            return io.BytesIO(json.dumps({'text':'明天下午，不对，下周二交。不要买猫粮。'},ensure_ascii=False).encode())
        text = transcribe(b'WAV', {'aiBaseUrl':'https://host/v1', 'aiApiKey':'secret', 'speechVocabulary':'课程甲', 'tasks':'SECRET_TASK'}, fake)
        self.assertIn('不要买猫粮', text)

    def test_unsupported_provider_does_not_leak_error_body(self):
        def fail(request, timeout):
            raise urllib.error.HTTPError(request.full_url,404,'error',{},io.BytesIO(b'secret'))
        with self.assertRaisesRegex(RuntimeError, '不支持语音'):
            transcribe(b'WAV', {'aiApiKey':'secret'}, fail)

if __name__ == '__main__': unittest.main()
