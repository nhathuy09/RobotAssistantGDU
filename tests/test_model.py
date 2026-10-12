import websockets
import asyncio
import json
import pyaudio
import numpy as np
import base64
from openwakeword.model import Model

# ================= CẤU HÌNH =================
API_KEY = "YOUR_API_KEY_HERE"  # Thay bằng API Key của bạn từ Google Cloud Console
MODEL_NAME = "gemini-3.1-flash-live-preview"
URL = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}"

# Cấu hình phần cứng Micro
FORMAT = pyaudio.paInt32
CHANNELS = 2
RATE = 48000
TARGET_RATE = 16000
DOWNSAMPLE = int(RATE / TARGET_RATE)
CHUNK = 1280 * DOWNSAMPLE

app_state = {"status": "WAKEWORD"}
# ============================================

async def setup_gemini(ws):
    setup_msg = {
        "setup": {
            "model": f"models/{MODEL_NAME}",
            "generationConfig": {
                "responseModalities": ["AUDIO"] 
            }
        }
    }
    await ws.send(json.dumps(setup_msg))
    await ws.recv() 
    print("[] Đã kết nối trí tuệ Gemini!")

# Thêm tham số out_stream để phát âm thanh
async def receive_from_gemini(ws, out_stream):
    loop = asyncio.get_running_loop()
    try:
        async for message in ws:
            response = json.loads(message)
            if "serverContent" in response:
                model_turn = response["serverContent"].get("modelTurn", {})
                if model_turn:
                    for part in model_turn.get("parts", []):
                        # 1. In văn bản ra màn hình
                        if "text" in part:
                            print(part["text"], end="", flush=True)
                            
                        # 2. XUẤT ÂM THANH RA LOA
                        if "inlineData" in part:
                            audio_b64 = part["inlineData"].get("data", "")
                            if audio_b64:
                                raw_audio = base64.b64decode(audio_b64)
                                # Dùng executor để luồng phát loa không làm đứng kết nối mạng
                                await loop.run_in_executor(None, out_stream.write, raw_audio)

                if response["serverContent"].get("turnComplete"):
                    print("\n\n[🤖] (Gemini đã trả lời xong)")
                    app_state["status"] = "WAKEWORD"
                    print("\n[🎙️] Tiếp tục chờ gọi 'Alexa'...")
    except Exception as e:
        print(f"\n[❌] Lỗi nhận dữ liệu Gemini: {e}")

async def audio_processing_loop(ws, in_stream, oww_model):
    loop = asyncio.get_running_loop()
    record_chunks = 0
    MAX_RECORD_CHUNKS = 60 

    while True:
        pcm_data = await loop.run_in_executor(None, in_stream.read, CHUNK, False)

        audio_np_32 = np.frombuffer(pcm_data, dtype=np.int32)
        mono_32 = audio_np_32[::2]
        mono_16k_32 = mono_32[::DOWNSAMPLE]
        audio_np_16 = (mono_16k_32 >> 16).astype(np.int16)

        if app_state["status"] == "WAKEWORD":
            prediction = oww_model.predict(audio_np_16)
            for mdl_name, score in prediction.items():
                if score > 0.5:
                    print(f"\n[🔥] Kích hoạt bởi '{mdl_name.upper()}'! (Điểm: {score:.2f})")
                    print("[🔴] ĐANG GHI ÂM (Mời bạn nói trong 5 giây)...\n")
                    app_state["status"] = "LISTENING"
                    record_chunks = 0
                    oww_model.reset()
                    break

        elif app_state["status"] == "LISTENING":
            audio_b64 = base64.b64encode(audio_np_16.tobytes()).decode("utf-8")
            
            # CẬP NHẬT CHUẨN MỚI: Dùng "audio" thay vì "mediaChunks"
            msg = {
                "realtimeInput": {
                    "audio": {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": audio_b64
                    }
                }
            }
            await ws.send(json.dumps(msg))
            record_chunks += 1

            if record_chunks >= MAX_RECORD_CHUNKS:
                print("\n[⏳] Đang gửi lên cho não bộ xử lý...")
                await ws.send(json.dumps({"clientContent": {"turnComplete": True}}))
                app_state["status"] = "WAITING_AI"

        elif app_state["status"] == "WAITING_AI":
            pass

async def main():
    print("[⏳] Khởi động động cơ WakeWord...")
    oww_model = Model() 
    print("[✅] Khởi động thành công!")

    audio = pyaudio.PyAudio()
    target_index = None
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0 and ("snd_rpi" in info["name"] or "googlevoicehat" in info["name"]):
            target_index = i

    # Luồng IN (Thu âm từ Micro I2S)
    in_stream = audio.open(format=FORMAT,
                           channels=CHANNELS,
                           rate=RATE,
                           input=True,
                           frames_per_buffer=CHUNK,
                           input_device_index=target_index)
                           
    # Luồng OUT (Phát âm thanh ra Loa - Tần số 24000Hz của Gemini)
    out_stream = audio.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=24000,
                            output=True)
                            
    print(f"[✅] Hệ thống Audio đã bật")

    async with websockets.connect(URL) as ws:
        await setup_gemini(ws)
        print("\n=========================================")
        print("🎉 ROBOT ĐÃ SẴN SÀNG! HÃY GỌI 'ALEXA'")
        print("=========================================\n")

        # Truyền out_stream vào luồng nhận dữ liệu
        receive_task = asyncio.create_task(receive_from_gemini(ws, out_stream))
        audio_task = asyncio.create_task(audio_processing_loop(ws, in_stream, oww_model))

        await asyncio.gather(receive_task, audio_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[🛑] Đã tắt Robot.")