import asyncio
import time
from audio.microphone import Microphone
from audio.speaker import Speaker
from audio.vad import VoiceActivityDetector
from wakeword.detector import WakeWordDetector
from core.gemini_api import GeminiAPI
from controller.orc_controller import OrcController
from controller.motion_tools import build_tool_handlers
from display.face_client import FaceClient

LISTEN_TIMEOUT = 6.0     
IDLE_TIMEOUT = 10.0     
POST_WAKEWORD_SKIP = 2   
WAKEWORD_COOLDOWN_AFTER_SESSION = 2.5
async def main():
    microphone = Microphone()
    speaker = Speaker()
    wakeword = WakeWordDetector()
    vad = VoiceActivityDetector(start_threshold=1000, speech_threshold=1500)
    orc = OrcController(port="/dev/ttyACM0") 
    face = FaceClient(ip="gdupi3.local", port=5005)  
    tool_handlers = None

    resumption_handle = None
    status = "WAKEWORD"
    wakeword_cooldown = 0.0
    gemini = None
    connect_task = None
    receive_task = None
    listen_deadline = None
    skip_count = 0
    last_activity = None
    pending_audio = []
    async def end_session(reason: str):
        nonlocal gemini, receive_task, status, wakeword_cooldown, resumption_handle
        print(f"\n[SYSTEM] {reason} -- ngắt kết nối, quay lại chờ 'Alexa'.")
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        if gemini:
            # nonlocal resumption_handle
            if gemini.resumption_handle and "ngủ" not in reason.lower() and "im lặng" not in reason.lower():
                resumption_handle = gemini.resumption_handle
                print("[SYSTEM] Đã lưu ngữ cảnh phiên -- lần gọi 'Alexa' tiếp theo sẽ nhớ tiếp.")
            else:
                resumption_handle = None
                print("[SYSTEM] Không lưu ngữ cảnh phiên -- lần gọi 'Alexa' tiếp theo sẽ bắt đầu mới.")
            await gemini.close()
        gemini = None
        receive_task = None
        status = "WAKEWORD"
        wakeword.reset()
        wakeword_cooldown = time.monotonic() + WAKEWORD_COOLDOWN_AFTER_SESSION

    try:
        if not orc.connect():
            print("[SYSTEM] Không kết nối được Orc Hub -- robot sẽ chạy không có motor.")
        tool_handlers = build_tool_handlers(orc)
        # face.start_stream()
        microphone.start_stream()
        speaker.start_stream()
        while True:
            try:
                audio_data = await asyncio.get_running_loop().run_in_executor(None, microphone.read)
                
                # ------------------- TRẠNG THÁI 1: CHỜ WAKEWORD -------------------
                if status == "WAKEWORD":
                    # if time.monotonic() < wakeword_cooldown:
                    #     continue
                    detected = await asyncio.get_running_loop().run_in_executor(None, wakeword.detect, audio_data)
                    if time.monotonic() < wakeword_cooldown:
                        wakeword.reset()
                        continue
                    if detected:
                        print("\n[MIC] Đã nghe 'Alexa'! Đang kết nối Gemini (nền)...")
                        face.send_state("LISTENING")
                        gemini = GeminiAPI(
                            speaker,
                            resumption_handle=resumption_handle,
                            tool_handlers=tool_handlers, 
                            face_client=face
                        )
                        connect_task = asyncio.create_task(gemini.connect())
                        # listen_deadline = time.monotonic() + LISTEN_TIMEOUT
                        status = "CONNECTING"
                        # skip_count = POST_WAKEWORD_SKIP
                        # listen_deadline = time.monotonic() + LISTEN_TIMEOUT

                # ------------------- TRẠNG THÁI 2: ĐANG KẾT NỐI (NỀN) -------------------
                elif status == "CONNECTING":
                    pending_audio.append(audio_data)
                    if connect_task.done():
                        exc = connect_task.exception()
                        if exc:
                            raise exc
                        receive_task = asyncio.create_task(gemini.receive_audio())
                        print("[SYSTEM] Gemini đã sẵn sàng. Mời bạn nói...")
                        status = "LISTENING"
                        skip_count = POST_WAKEWORD_SKIP 
                        listen_deadline = time.monotonic() + LISTEN_TIMEOUT
                        buffered = pending_audio
                        pending_audio = []
                        for i, chunk in enumerate(buffered):
                            if i < POST_WAKEWORD_SKIP:
                                continue
                            if status == "LISTENING" and vad.calculate_rms(chunk) > vad.start_threshold:
                                print("[MIC] Phát hiện giọng nói đã nói trong lúc đang kết nối -- gửi bù...")
                                status = "ACTIVE"
                                last_activity = time.monotonic()
                                skip_count = 0
                            if status == "ACTIVE":
                                await gemini.send_audio(chunk)
                    # if time.monotonic() > listen_deadline:
                    #     raise TimeoutError("Kết nối hoặc chờ giọng nói quá lâu")

                # ------------------- TRẠNG THÁI 3: CHỜ BẮT ĐẦU NÓI -------------------
                elif status == "LISTENING":
                    if receive_task.done():
                        exc = receive_task.exception()
                        raise exc if exc else RuntimeError("WebSocket bị ngắt đột ngột!")
                    if skip_count > 0:
                        skip_count -= 1
                        continue 
                    if time.monotonic() > listen_deadline:
                        await end_session("Không nói gì")
                        continue
                    if vad.calculate_rms(audio_data) > vad.start_threshold:
                        print("[MIC] Đang thu âm và truyền lên Gemini...")
                        status = "ACTIVE"
                        last_activity = time.monotonic()
                        await gemini.send_audio(audio_data)

                # ------------------- TRẠNG THÁI 4: GIAO TIẾP HAI CHIỀU -------------------
                elif status == "ACTIVE":
                    if receive_task.done():
                        exc = receive_task.exception()
                        raise exc if exc else RuntimeError("WebSocket bị ngắt đột ngột!")
                    if gemini.go_away_event.is_set():
                        await end_session("Server sắp ngắt kết nối (goAway)")
                        continue
                    if not gemini.mic_should_be_muted():
                        await gemini.send_audio(audio_data)
                        if vad.calculate_rms(audio_data) > vad.start_threshold:
                            last_activity = time.monotonic()
                    if gemini.ai_speaking:
                        last_activity = time.monotonic()
                    if gemini.turn_complete.is_set():
                        gemini.turn_complete.clear()
                        last_activity = time.monotonic()
                        print("\n[GEMINI] Trả lời xong. Bạn có thể nói tiếp...")
                        if gemini.force_sleep.is_set():
                            await end_session("Nhận lệnh đi ngủ từ người dùng")
                            continue
                    if time.monotonic() - last_activity > IDLE_TIMEOUT:
                        await end_session("Kết thúc phiên hội thoại do im lặng")

            except Exception as e:
                print(f"\n[SYSTEM] Sự cố: {e}")
                await end_session("Lỗi trong phiên")
                await asyncio.sleep(1.0) 

    except KeyboardInterrupt:
        pass
    finally:
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        if gemini:
            await gemini.close()
        orc.disconnect()
        face.close()
        microphone.stop_stream()
        speaker.stop_stream()
        print("\n[SYSTEM] Đã đóng mic & loa.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Đã tắt Robot.")