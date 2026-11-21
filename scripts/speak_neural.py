#!/usr/bin/env python3
"""Private stdin text to local Kokoro synthesis and optional native playback."""
import json
import signal
import subprocess
from pathlib import Path
import sys
import tempfile
import wave

import numpy as np
from kokoro_onnx import Kokoro

ROOT = Path(__file__).resolve().parents[1]
request = json.load(sys.stdin)
text = request['text'].strip()[:600]
if not text:
    raise ValueError('No speech text')
model = Kokoro(str(ROOT/'models/voice/kokoro-v1.0.onnx'), str(ROOT/'models/voice/voices-v1.0.bin'))
# kokoro-onnx 0.4.7 sends integer speed for newer exports. Respect the
# model's declared input type without modifying the installed dependency.
class ModelSession:
    def __init__(self, session): self.session = session
    def get_inputs(self): return self.session.get_inputs()
    def run(self, outputs, inputs):
        inputs = dict(inputs)
        speed = next(i for i in self.get_inputs() if i.name == 'speed')
        if speed.type == 'tensor(float)':
            inputs['speed'] = np.asarray(inputs['speed'], dtype=np.float32)
        return self.session.run(outputs, inputs)
model.sess = ModelSession(model.sess)
audio, rate = model.create(text, voice='bm_lewis', speed=1.18, lang='en-gb')
with tempfile.NamedTemporaryFile(suffix='.wav', dir=ROOT/'artifacts', delete=False) as file:
    output = Path(file.name)
with wave.open(str(output), 'wb') as stream:
    stream.setnchannels(1)
    stream.setsampwidth(2)
    stream.setframerate(rate)
    stream.writeframes((np.clip(audio, -1, 1)*32767).astype('<i2').tobytes())
if request.get('save_only'):
    print(output)
else:
    # Keep ownership of playback so Stop speech can terminate it and remove
    # the generated audio, including when the app exits during playback.
    player = subprocess.Popen(['/usr/bin/afplay', str(output)])
    def stop_player(_signal, _frame):
        player.terminate()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop_player)
    try:
        player.wait()
    finally:
        if player.poll() is None:
            player.terminate()
            player.wait(timeout=2)
        output.unlink(missing_ok=True)
