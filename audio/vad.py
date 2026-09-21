import time
import numpy as np 
class VoiceActivityDetector:
    def __init__(self,start_threshold=800, speech_threshold=1800,silence_timeout=2.0,max_record_time=15.0):
        self.start_threshold = start_threshold
        self.speech_threshold = speech_threshold
        self.silence_timeout = silence_timeout
        self.max_record_time = max_record_time

        self.speech_started = False
        self.last_speech_time = None
        self.start_time = None
        
    def calculate_rms(self, audio_data):
        samples=audio_data.astype(np.float32)
        if len(samples) ==0:
            return 0
        rms=np.sqrt(np.mean(samples**2))
        return rms
    def process(self,audio_data):
        now=time.monotonic()
        rms=self.calculate_rms(audio_data)
        if not self.speech_started:
            if rms > self.start_threshold:
                self.speech_started = True
                self.last_speech_time = now
                self.start_time = now
                print("[VAD] Speech started")
                return "START"
            return "SILENCE"
        if rms > self.speech_threshold:
            self.last_speech_time = now
            return "SPEECH"
        silence_duration = now - self.last_speech_time
        if silence_duration > self.silence_timeout:
            print("[VAD] Silence detected, stopping speech")
            self.reset()
            return "END"
        record_duration = now - self.start_time
        if record_duration > self.max_record_time:
            print("[VAD] Max record time exceeded, stopping speech")
            self.reset()
            return "END"
        return "SILENCE"
    def reset(self):
        self.speech_started = False
        self.last_speech_time = None
        self.start_time = None