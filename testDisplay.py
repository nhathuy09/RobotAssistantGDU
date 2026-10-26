import pyaudio

p = pyaudio.PyAudio()

for rate in [48000, 44100, 16000]:
    try:
        print(f"\nTesting {rate} Hz...")
        stream = p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=rate,
            input=True,
            input_device_index=0,
            frames_per_buffer=1280
        )

        data = stream.read(1280, exception_on_overflow=False)
        print(f"OK: {rate} Hz, received {len(data)} bytes")

        stream.stop_stream()
        stream.close()

    except Exception as e:
        print(f"FAILED: {rate} Hz: {e}")

p.terminate()