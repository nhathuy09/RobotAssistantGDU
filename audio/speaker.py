import pyaudio
from config import SPEAKER_RATE, SPEAKER_CHANNELS


class Speaker:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None

    def start_stream(self):
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=SPEAKER_CHANNELS,
            rate=SPEAKER_RATE,
            output=True,
        )
        print("[SPEAKER] Speaker stream started.")

    def play(self, audio_data):
        if self.stream:
            self.stream.write(audio_data)

    def flush(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
        self.start_stream()

    def stop_stream(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            print("[SPEAKER] Speaker stream stopped.")