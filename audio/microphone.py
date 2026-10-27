import pyaudio
import numpy as np
import threading
import queue
from scipy.signal import butter, lfilter, lfilter_zi
from config import (
    FORMAT,
    CHANNELS,
    RATE,
    DOWNSAMPLE,
    CHUNK_SIZE,
    TARGET_RATE,
 )
SHIFT_BITS = 16
class SoftAGC:
    """Tự động khuếch đại/nén tín hiệu về quanh target_rms một cách êm ái, tránh bơm nhiễu nền."""
    def __init__(self, target_rms=1500, max_gain=20.0, min_gain=0.1,
                 attack=0.7, release=0.98):
        self.gain = 1.0
        self.target_rms = target_rms
        self.max_gain = max_gain
        self.min_gain = min_gain
        self.attack = attack     # gain giảm NHANH khi tín hiệu to -> tránh clip
        self.release = release   # gain tăng TỪ TỪ khi tín hiệu nhỏ -> tránh bơm nhiễu nền

    def process(self, samples_float):
        rms = np.sqrt(np.mean(samples_float ** 2, dtype=np.float32)) + 1e-6
        desired_gain = float(np.clip(self.target_rms / rms, self.min_gain, self.max_gain))
        if desired_gain < self.gain:
            self.gain = self.attack * self.gain + (1.0 - self.attack) * desired_gain
        else:
            self.gain = self.release * self.gain + (1.0 - self.release) * desired_gain
        return samples_float * self.gain
class Microphone:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None 
        self.device_index = None

        self._hp_b, self._hp_a = butter(2, 40, fs=RATE, btype='high')
        self._hp_b = self._hp_b.astype(np.float32)
        self._hp_a = self._hp_a.astype(np.float32)
        self._hp_zi = (lfilter_zi(self._hp_b, self._hp_a) * 0.0).astype(np.float32)

        self._lp_b, self._lp_a = butter(4, TARGET_RATE / 2 * 0.9, fs=RATE, btype='low')
        self._lp_b = self._lp_b.astype(np.float32)
        self._lp_a = self._lp_a.astype(np.float32)
        self._lp_zi = (lfilter_zi(self._lp_b, self._lp_a) * 0.0).astype(np.float32)

        self.agc = SoftAGC(target_rms=1500, max_gain=20.0)

    def find_device(self):
        default_input = None
        for i in range(self.audio.get_device_count()):
            try:
                info = self.audio.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    if default_input is None:
                        default_input = i
                    name = info.get("name", "").lower()
                    if "snd_rpi" in name or "googlevoicehat" in name or "i2s" in name:
                        self.device_index = i
                        print(f"[MICROPHONE] Tìm thấy microphone I2S: {info['name']} (Index {i})")
                        return self.device_index
            except Exception:
                continue

        if default_input is not None:   
            self.device_index = default_input
            print(f"[MICROPHONE] Cảnh báo: Không thấy card I2S đặc thù, dùng input device mặc định index {default_input}")
            return self.device_index

        raise RuntimeError("Không tìm thấy bất kỳ thiết bị Microphone input nào trên hệ thống!")

    def start_stream(self):
        if self.device_index is None:
            self.find_device()
        self.stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=self.device_index,
        )
        print("[MICROPHONE] Microphone stream started.")
    def read(self):
        pcm_data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
        # audio_np_32 = np.frombuffer(pcm_data, dtype=np.int32)
        # mono_32 = audio_np_32[::2].astype(np.float32)
        audio_np=np.frombuffer(pcm_data, dtype=np.int32)
        stereo=audio_np.reshape(-1, 2).astype(np.float32)
        mono=(stereo[:, 0] + stereo[:, 1]) * 0.5
        dc_removed, self._hp_zi = lfilter(self._hp_b, self._hp_a, mono, zi=self._hp_zi)
        base_scaled = dc_removed / 65536.0
        agc_out = self.agc.process(base_scaled)
        pre_filter = np.clip(agc_out, -32768.0, 32767.0)
        filtered, self._lp_zi = lfilter(self._lp_b, self._lp_a, pre_filter, zi=self._lp_zi)
        mono_16k = filtered[::DOWNSAMPLE]
        return np.clip(mono_16k, -32768.0, 32767.0).astype(np.int16)

    def read_debug(self):
        pcm_data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
        audio_np_32 = np.frombuffer(pcm_data, dtype=np.int32)
        mono_32 = audio_np_32[::2].astype(np.float32)
        dc_removed, self._hp_zi = lfilter(self._hp_b, self._hp_a, mono_32, zi=self._hp_zi)
        print(f"[RAW] abs_max={np.abs(mono_32).max():.0f}, mean={mono_32.mean():.0f}")
        print(f"[DC-removed] abs_max={np.abs(dc_removed).max():.0f}")

    def stop_stream(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            print("[MICROPHONE] Microphone stream stopped.")

        
