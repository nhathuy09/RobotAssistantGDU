import time
from audio.microphone import Microphone

mic = Microphone()
mic.start_stream()
try:
    print("10 giây đầu: GIỮ YÊN LẶNG. Sau đó nói bình thường, rồi nói to.")
    t0 = time.time()
    while time.time() - t0 < 30:
        mic.read()
        print(f"rms_in={mic.last_rms_in:7.1f}  gain={mic.last_gain:5.2f}  clipped={mic.last_clipped}")
finally:
    mic.stop_stream()