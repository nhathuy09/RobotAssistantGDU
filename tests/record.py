import sys
import wave
from audio.microphone import Microphone
from config import TARGET_RATE
 
def record(seconds=5.0, out_path="test_recording.wav"):
    mic = Microphone()
    mic.start_stream()
    print(f"[TEST] Bắt đầu ghi {seconds}s... nói vào mic bây giờ.")
 
    chunks = []
    import time
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        chunk = mic.read()  # int16, đã DC-removal + anti-alias + downsample 16kHz
        chunks.append(chunk.tobytes())
 
    mic.stop_stream()
 
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(TARGET_RATE)
        wf.writeframes(b"".join(chunks))
 
    print(f"[TEST] Đã ghi xong -> {out_path}")
    print("[TEST] Copy file này ra máy khác / dùng tai nghe để nghe lại, TRÁNH mở loa cùng phòng lúc mic đang chạy.")
 
if __name__ == "__main__":
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    record(secs)