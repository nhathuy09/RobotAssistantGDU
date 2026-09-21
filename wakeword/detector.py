from openwakeword.model import Model
import time
from config import WAKEWORD_THRESHOLD, COOLDOWN
class WakeWordDetector:
    def __init__(self):
        print("[WAKEWORD] Wake word detector initialized.")
        self.model=Model()
        self.last_detection_time=0.0
        print("[WAKEWORD] Wake word model loaded.")
    def detect(self,audio_data):
        current_time = time.monotonic()
        if current_time - self.last_detection_time < COOLDOWN:
            return False
        prediction=self.model.predict(audio_data)
        for model_name, score in prediction.items():
            if(model_name == "alexa" and score >= WAKEWORD_THRESHOLD):
                self.last_detection_time = current_time
                print(f"[WAKEWORD] Wake word detected with score: {score}")
                self.model.reset()
                return True
        return False
    def reset(self):
        self.model.reset()