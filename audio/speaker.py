import queue
import threading
import time

import numpy as np
import pyaudio

from config import SPEAKER_RATE, SPEAKER_CHANNELS, GEMINI_SPEAKER_RATE

SLICE_MS = 40  


class Speaker:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None

        self._queue = queue.Queue()
        self._worker = None
        self._running = False

        self._io_lock = threading.Lock()    # bảo vệ stream: write / flush / close
        self._meta_lock = threading.Lock()  # bảo vệ _gen và _play_end
        self._gen = 0                       # tăng mỗi lần flush -> chunk cũ bị bỏ
        self._play_end = 0.0                # thời điểm (monotonic) ước tính phát xong

        self._in_rate = GEMINI_SPEAKER_RATE or SPEAKER_RATE
        self._step = self._in_rate / SPEAKER_RATE
        self._rs_gen = 0
        self._reset_resampler()

    # ---------- resampler tuyến tính (mono), giữ trạng thái giữa các chunk ----------
    def _reset_resampler(self):
        self._prev = 0.0
        self._pos = 1.0

    def _resample(self, pcm):
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        n = len(x)
        if n == 0:
            return b""
        ext = np.concatenate(([self._prev], x))
        count = int(np.ceil((n - self._pos) / self._step)) if n > self._pos else 0
        pos = self._pos + self._step * np.arange(count)
        i0 = np.minimum(np.floor(pos).astype(np.int64), n - 1)
        frac = np.clip(pos - i0, 0.0, 1.0)
        y = ext[i0] * (1.0 - frac) + ext[i0 + 1] * frac
        self._pos = self._pos + self._step * count - n
        self._prev = float(ext[-1])
        return np.clip(y, -32768, 32767).astype(np.int16).tobytes()

    # ---------- vòng đời ----------
    def start_stream(self):
        if self._running:
            return
        self._drain_queue()
        with self._meta_lock:
            self._gen += 1
            self._play_end = 0.0
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=SPEAKER_CHANNELS,
            rate=SPEAKER_RATE,
            output=True,
            frames_per_buffer=1024,
        )
        self._running = True
        self._worker = threading.Thread(target=self._playback_worker, daemon=True)
        self._worker.start()
        print("[SPEAKER] Speaker stream started.")

    def stop_stream(self):
        if not self._running:
            return
        self._running = False
        self._queue.put(None)
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1.0)
        self._worker = None
        with self._io_lock:
            if self.stream is not None:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
        print("[SPEAKER] Speaker stream stopped.")

    def close(self):
        self.stop_stream()
        if self.audio is not None:
            self.audio.terminate()
            self.audio = None

    # ---------- phát ----------
    def play(self, audio_data):
        """Không chặn: nhét vào hàng đợi. Gọi từ bất kỳ thread nào."""
        if not self._running or not audio_data:
            return
        pcm = audio_data[: len(audio_data) // 2 * 2]
        if not pcm:
            return
        duration = len(pcm) / 2 / self._in_rate
        with self._meta_lock:
            self._play_end = max(self._play_end, time.monotonic()) + duration
            gen = self._gen
        self._queue.put((gen, pcm))

    def is_busy(self):
        """True nếu còn audio chưa phát xong (ước tính theo tổng thời lượng đã nhận)."""
        return time.monotonic() < self._play_end

    def flush(self):
        """Dừng ngay: bỏ toàn bộ audio đang chờ và xả bộ đệm phần cứng."""
        with self._meta_lock:
            self._gen += 1
            self._play_end = 0.0
        self._drain_queue()
        with self._io_lock:
            if self.stream is not None:
                try:
                    self.stream.stop_stream()
                    self.stream.start_stream()
                except Exception as e:
                    print(f"[SPEAKER] Lỗi khi flush: {e}")

    def _drain_queue(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _playback_worker(self):
        slice_bytes = int(SPEAKER_RATE * SLICE_MS / 1000) * 2 * SPEAKER_CHANNELS
        while self._running:
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                break
            gen, pcm = item
            if gen != self._gen:
                continue  # chunk của lượt đã bị ngắt
            if gen != self._rs_gen:
                self._reset_resampler()
                self._rs_gen = gen
            out = pcm if self._in_rate == SPEAKER_RATE else self._resample(pcm)
            for i in range(0, len(out), slice_bytes):
                if gen != self._gen or not self._running:
                    break
                with self._io_lock:
                    if self.stream is None:
                        break
                    try:
                        self.stream.write(out[i:i + slice_bytes])
                    except Exception as e:
                        print(f"[SPEAKER] Lỗi phát âm thanh: {e}")
                        break