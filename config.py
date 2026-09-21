import os
from dotenv import load_dotenv
import pyaudio
load_dotenv()  
#==============================================================
#==================== GEMINI CONFIG ===========================
#==============================================================
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY is None:
    raise RuntimeError(
        "Chưa thiết lập GEMINI_API_KEY. "
        "Hãy export GEMINI_API_KEY='YOUR_KEY'"
    )

MODEL_NAME = "gemini-3.1-flash-live-preview"
URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"
#==============================================================
#==================== MICROPHONE CONFIG =======================
#==============================================================
FORMAT= pyaudio.paInt32
CHANNELS= 2
RATE=48000
TARGET_RATE=16000
DOWNSAMPLE=int(RATE / TARGET_RATE)
CHUNK_SIZE=1280 * DOWNSAMPLE
#==============================================================
#====================== SPEAKER CONFIG ========================
#==============================================================
SPEAKER_RATE = 24000
SPEAKER_CHANNELS = 1
#==============================================================
#====================== WAKEWORD CONFIG =======================
#==============================================================
WAKEWORD_THRESHOLD = 0.85
COOLDOWN = 2.0
