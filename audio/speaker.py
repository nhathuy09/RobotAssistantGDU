
import queue
import threading
import time

import pyaudio

from config import SPEAKER_RATE, SPEAKER_CHANNELS

SLICE_MS = 40


class Speaker:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None

        self._queue = queue.Queue()
        self._worker = None
        self._running = False

        # Bảo vệ thao tác với stream.
        self._io_lock = threading.Lock()

        # Bảo vệ thông tin lượt phát.
        self._meta_lock = threading.Lock()
        self._gen = 0
        self._play_end = 0.0

    # ---------- Vòng đời ----------

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
            start=False,
        )

        self._running = True

        self._worker = threading.Thread(
            target=self._playback_worker,
            daemon=True,
        )
        self._worker.start()

        print(
            f"[SPEAKER] Stream started: "
            f"{SPEAKER_RATE} Hz, {SPEAKER_CHANNELS} channel(s)."
        )

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
                except Exception as e:
                    print(f"[SPEAKER] Lỗi đóng stream: {e}")
                finally:
                    self.stream = None

        with self._meta_lock:
            self._play_end = 0.0

        print("[SPEAKER] Speaker stream stopped.")

    def close(self):
        self.stop_stream()

        if self.audio is not None:
            self.audio.terminate()
            self.audio = None

    # ---------- Đưa âm thanh vào hàng đợi ----------

    def play(self, audio_data):
        """Không chặn: đưa PCM vào hàng đợi phát."""
        if not self._running or not audio_data:
            return

        # PCM paInt16 yêu cầu mỗi mẫu chiếm 2 byte.
        pcm = audio_data[:len(audio_data) // 2 * 2]

        if not pcm:
            return

        sample_count = len(pcm) // 2
        duration = sample_count / (
            SPEAKER_RATE * SPEAKER_CHANNELS
        )

        with self._meta_lock:
            self._play_end = (
                max(self._play_end, time.monotonic()) + duration
            )
            gen = self._gen

        self._queue.put((gen, pcm))

    def is_busy(self):
        """Ước tính còn âm thanh đang chờ hoặc đang phát."""
        with self._meta_lock:
            return time.monotonic() < self._play_end

    # ---------- Ngắt âm thanh ----------

    def flush(self):
        """Bỏ chunk đang chờ và khởi động lại buffer phát."""
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

    # ---------- Worker phát âm thanh ----------

    def _playback_worker(self):
        bytes_per_frame = 2 * SPEAKER_CHANNELS
        slice_bytes = (
            int(SPEAKER_RATE * SLICE_MS / 1000)
            * bytes_per_frame
        )

        while self._running:
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                # Tạm dừng stream khi không có âm thanh để chống rè / underrun
                with self._io_lock:
                    if self.stream is not None and self.stream.is_active() and not self.is_busy():
                        try:
                            self.stream.stop_stream()
                        except Exception:
                            pass
                continue

            if item is None:
                break

            gen, pcm = item

            with self._meta_lock:
                if gen != self._gen:
                    continue

            # Kích hoạt lại stream nếu đang tạm dừng
            with self._io_lock:
                if self.stream is not None and self.stream.is_stopped():
                    try:
                        self.stream.start_stream()
                    except Exception as e:
                        print(f"[SPEAKER] Lỗi khởi động lại stream: {e}")

            # Phát trực tiếp, không resampling.
            for i in range(0, len(pcm), slice_bytes):
                with self._meta_lock:
                    if gen != self._gen:
                        break

                if not self._running:
                    break

                chunk = pcm[i:i + slice_bytes]

                with self._io_lock:
                    if self.stream is None:
                        break

                    try:
                        self.stream.write(chunk)
                    except Exception as e:
                        print(f"[SPEAKER] Lỗi phát âm thanh: {e}")
                        break