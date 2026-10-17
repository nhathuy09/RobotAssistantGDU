# import asyncio
# import time
# from audio.microphone import Microphone
# from audio.speaker import Speaker
# from audio.vad import VoiceActivityDetector
# from wakeword.detector import WakeWordDetector
# from core.gemini_api import GeminiAPI
# from controller.orc_controller import OrcController
# from controller.motion_tools import build_tool_handlers
# from display.face_client import FaceClient

# LISTEN_TIMEOUT = 6.0     
# IDLE_TIMEOUT = 10.0     
# POST_WAKEWORD_SKIP = 2   
# WAKEWORD_COOLDOWN_AFTER_SESSION = 2.5
# async def main():
#     microphone = Microphone()
#     speaker = Speaker()
#     wakeword = WakeWordDetector()
#     vad = VoiceActivityDetector(start_threshold=1000, speech_threshold=1500)
#     orc = OrcController(port="/dev/ttyACM0") 
#     face = FaceClient(ip="127.0.0.1", port=5005)  
#     tool_handlers = None

#     resumption_handle = None
#     status = "WAKEWORD"
#     wakeword_cooldown = 0.0
#     gemini = None
#     connect_task = None
#     receive_task = None
#     listen_deadline = None
#     skip_count = 0
#     last_activity = None
#     pending_audio = []
    
#     async def end_session(reason: str):
#         nonlocal gemini, receive_task, status, wakeword_cooldown, resumption_handle
#         print(f"\n[SYSTEM] {reason} -- ngắt kết nối, quay lại chờ 'Alexa'.")
#         if receive_task and not receive_task.done():
#             receive_task.cancel()
#             try:
#                 await receive_task
#             except asyncio.CancelledError:
#                 pass
#         if gemini:
#             # nonlocal resumption_handle
#             if gemini.resumption_handle and "ngủ" not in reason.lower() and "im lặng" not in reason.lower():
#                 resumption_handle = gemini.resumption_handle
#                 print("[SYSTEM] Đã lưu ngữ cảnh phiên -- lần gọi 'Alexa' tiếp theo sẽ nhớ tiếp.")
#             else:
#                 resumption_handle = None
#                 print("[SYSTEM] Không lưu ngữ cảnh phiên -- lần gọi 'Alexa' tiếp theo sẽ bắt đầu mới.")
#             await gemini.close()
#         gemini = None
#         receive_task = None
#         status = "WAKEWORD"
#         wakeword.reset()
#         wakeword_cooldown = time.monotonic() + WAKEWORD_COOLDOWN_AFTER_SESSION

#     try:
#         if not orc.connect():
#             print("[SYSTEM] Không kết nối được Orc Hub -- robot sẽ chạy không có motor.")
#         tool_handlers = build_tool_handlers(orc)
#         # face.start_stream()
#         microphone.start_stream()
#         speaker.start_stream()
#         while True:
#             try:
#                 audio_data = await asyncio.get_running_loop().run_in_executor(None, microphone.read)
                
#                 # ------------------- TRẠNG THÁI 1: CHỜ WAKEWORD -------------------
#                 if status == "WAKEWORD":
#                     # if time.monotonic() < wakeword_cooldown:
#                     #     continue
#                     detected = await asyncio.get_running_loop().run_in_executor(None, wakeword.detect, audio_data)
#                     if time.monotonic() < wakeword_cooldown:
#                         wakeword.reset()
#                         continue
#                     if detected:
#                         print("\n[MIC] Đã nghe 'Alexa'! Đang kết nối Gemini (nền)...")
#                         face.send_state("LISTENING")
#                         gemini = GeminiAPI(
#                             speaker,
#                             resumption_handle=resumption_handle,
#                             tool_handlers=tool_handlers, 
#                             face_client=face
#                         )
#                         connect_task = asyncio.create_task(gemini.connect())
#                         # listen_deadline = time.monotonic() + LISTEN_TIMEOUT
#                         status = "CONNECTING"
#                         # skip_count = POST_WAKEWORD_SKIP
#                         # listen_deadline = time.monotonic() + LISTEN_TIMEOUT

#                 # ------------------- TRẠNG THÁI 2: ĐANG KẾT NỐI (NỀN) -------------------
#                 elif status == "CONNECTING":
#                     pending_audio.append(audio_data)
#                     if connect_task.done():
#                         exc = connect_task.exception()
#                         if exc:
#                             raise exc
#                         receive_task = asyncio.create_task(gemini.receive_audio())
#                         print("[SYSTEM] Gemini đã sẵn sàng. Mời bạn nói...")
#                         status = "LISTENING"
#                         skip_count = POST_WAKEWORD_SKIP 
#                         listen_deadline = time.monotonic() + LISTEN_TIMEOUT
#                         buffered = pending_audio
#                         pending_audio = []
#                         for i, chunk in enumerate(buffered):
#                             if i < POST_WAKEWORD_SKIP:
#                                 continue
#                             if status == "LISTENING" and vad.calculate_rms(chunk) > vad.start_threshold:
#                                 print("[MIC] Phát hiện giọng nói đã nói trong lúc đang kết nối -- gửi bù...")
#                                 status = "ACTIVE"
#                                 last_activity = time.monotonic()
#                                 skip_count = 0
#                             if status == "ACTIVE":
#                                 await gemini.send_audio(chunk)
#                     # if time.monotonic() > listen_deadline:
#                     #     raise TimeoutError("Kết nối hoặc chờ giọng nói quá lâu")

#                 # ------------------- TRẠNG THÁI 3: CHỜ BẮT ĐẦU NÓI -------------------
#                 elif status == "LISTENING":
#                     if receive_task.done():
#                         exc = receive_task.exception()
#                         raise exc if exc else RuntimeError("WebSocket bị ngắt đột ngột!")
#                     if skip_count > 0:
#                         skip_count -= 1
#                         continue 
#                     if time.monotonic() > listen_deadline:
#                         await end_session("Không nói gì")
#                         continue
#                     if vad.calculate_rms(audio_data) > vad.start_threshold:
#                         print("[MIC] Đang thu âm và truyền lên Gemini...")
#                         status = "ACTIVE"
#                         last_activity = time.monotonic()
#                         await gemini.send_audio(audio_data)

#                 # ------------------- TRẠNG THÁI 4: GIAO TIẾP HAI CHIỀU -------------------
#                 elif status == "ACTIVE":
#                     if receive_task.done():
#                         exc = receive_task.exception()
#                         raise exc if exc else RuntimeError("WebSocket bị ngắt đột ngột!")
#                     if gemini.go_away_event.is_set():
#                         await end_session("Server sắp ngắt kết nối (goAway)")
#                         continue
#                     if not gemini.mic_should_be_muted():
#                         await gemini.send_audio(audio_data)
#                         if vad.calculate_rms(audio_data) > vad.start_threshold:
#                             last_activity = time.monotonic()
#                     if gemini.ai_speaking:
#                         last_activity = time.monotonic()
#                     if gemini.turn_complete.is_set() and not speaker.is_busy():
#                         gemini.turn_complete.clear()
#                         last_activity = time.monotonic()
#                         print("\n[GEMINI] Trả lời xong. Bạn có thể nói tiếp...")
#                         if gemini.force_sleep.is_set():
#                             await end_session("Nhận lệnh đi ngủ từ người dùng")
#                             continue
#                     if time.monotonic() - last_activity > IDLE_TIMEOUT:
#                         await end_session("Kết thúc phiên hội thoại do im lặng")

#             except Exception as e:
#                 print(f"\n[SYSTEM] Sự cố: {e}")
#                 await end_session("Lỗi trong phiên")
#                 await asyncio.sleep(1.0) 

#     except KeyboardInterrupt:
#         pass
#     finally:
#         if receive_task and not receive_task.done():
#             receive_task.cancel()
#             try:
#                 await receive_task
#             except asyncio.CancelledError:
#                 pass
#         if gemini:
#             await gemini.close()
#         orc.disconnect()
#         face.close()
#         microphone.stop_stream()
#         speaker.stop_stream()
#         print("\n[SYSTEM] Đã đóng mic & loa.")


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("\n Đã tắt Robot.")




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

LISTEN_TIMEOUT = 6.0        # chờ người dùng bắt đầu nói sau khi Gemini sẵn sàng
IDLE_TIMEOUT = 10.0         # im lặng thật sự (không ai nói, AI không nói, robot không cử động)
POST_WAKEWORD_SKIP = 2      # bỏ qua vài chunk đầu để tránh dư âm của chữ "Alexa"
WAKEWORD_COOLDOWN_AFTER_SESSION = 2.5
THINK_DELAY = 0.8           # người dùng ngừng nói bao lâu thì mặt chuyển sang THINKING
THINK_TIMEOUT = 5.0         # THINKING quá lâu mà AI không đáp -> về LISTENING
FORCE_SLEEP_GRACE = 8.0     # chờ tối đa bao lâu cho câu tạm biệt trước khi ép đóng phiên
MIC_MAX_ERRORS = 3          # số lần đọc mic lỗi liên tiếp trước khi khởi động lại stream


def split_frame(frame):
    """Tương thích cả microphone.read() trả 1 mảng lẫn (detect_audio, stream_audio)."""
    if isinstance(frame, tuple):
        return frame
    return frame, frame


async def main():
    loop = asyncio.get_running_loop()

    microphone = Microphone()
    speaker = Speaker()
    wakeword = WakeWordDetector()
    vad = VoiceActivityDetector(start_threshold=1000, speech_threshold=1500)
    orc = OrcController(port="/dev/ttyACM0")
    face = FaceClient(ip="127.0.0.1", port=5005)
    tool_handlers = None

    resumption_handle = None
    status = "WAKEWORD"
    wakeword_cooldown = 0.0
    gemini = None
    connect_task = None
    receive_task = None
    listen_deadline = 0.0
    last_activity = 0.0
    frames_since_wake = 0
    pending_audio = []
    mic_errors = 0

    # Theo dõi lượt nói trong ACTIVE
    last_voice = 0.0
    awaiting_reply = False
    thinking_sent = False
    force_sleep_since = None

    async def cancel_task(task):
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        elif task and task.done() and not task.cancelled():
            task.exception()  # đánh dấu đã đọc, tránh cảnh báo "exception was never retrieved"

    async def end_session(reason: str, keep_context: bool = True):
        """Điểm thoát duy nhất của mọi phiên. keep_context quyết định lần gọi sau có nhớ tiếp không."""
        nonlocal gemini, connect_task, receive_task, status, wakeword_cooldown
        nonlocal resumption_handle, pending_audio, awaiting_reply, thinking_sent, force_sleep_since

        print(f"\n[SYSTEM] {reason} -- ngắt kết nối, quay lại chờ 'Alexa'.")
        await cancel_task(connect_task)
        await cancel_task(receive_task)

        if gemini:
            if keep_context and gemini.resumption_handle:
                resumption_handle = gemini.resumption_handle
                print("[SYSTEM] Đã lưu ngữ cảnh phiên -- lần gọi 'Alexa' tiếp theo sẽ nhớ tiếp.")
            else:
                resumption_handle = None
                print("[SYSTEM] Không lưu ngữ cảnh phiên -- lần gọi 'Alexa' tiếp theo sẽ bắt đầu mới.")
            try:
                await gemini.close()
            except Exception as e:
                print(f"[SYSTEM] Lỗi khi đóng Gemini: {e}")

        gemini = None
        connect_task = None
        receive_task = None
        pending_audio = []
        awaiting_reply = False
        thinking_sent = False
        force_sleep_since = None
        status = "WAKEWORD"
        wakeword.reset()
        wakeword_cooldown = time.monotonic() + WAKEWORD_COOLDOWN_AFTER_SESSION
        face.send_state("IDLE")

    async def read_mic():
        """Đọc mic, tự phục hồi stream nếu lỗi liên tiếp. Trả None nếu lần đọc này thất bại."""
        nonlocal mic_errors
        try:
            frame = await loop.run_in_executor(None, microphone.read)
            mic_errors = 0
            return frame
        except Exception as e:
            mic_errors += 1
            print(f"[MIC] Lỗi đọc mic ({mic_errors}/{MIC_MAX_ERRORS}): {e}")
            if mic_errors >= MIC_MAX_ERRORS:
                print("[MIC] Khởi động lại stream mic...")
                try:
                    await loop.run_in_executor(None, microphone.stop_stream)
                    await loop.run_in_executor(None, microphone.start_stream)
                    mic_errors = 0
                except Exception as e2:
                    print(f"[MIC] Không khởi động lại được: {e2}")
            await asyncio.sleep(0.2)
            return None

    try:
        if not await loop.run_in_executor(None, orc.connect):
            print("[SYSTEM] Không kết nối được Orc Hub -- robot sẽ chạy không có motor.")
        tool_handlers = build_tool_handlers(orc)
        microphone.start_stream()
        speaker.start_stream()
        face.send_state("IDLE")
        print("[SYSTEM] Sẵn sàng. Nói 'Alexa' để bắt đầu.")

        while True:
            frame = await read_mic()
            if frame is None:
                continue
            detect_audio, stream_audio = split_frame(frame)
            now = time.monotonic()

            try:
                # ------------------- TRẠNG THÁI 1: CHỜ WAKEWORD -------------------
                if status == "WAKEWORD":
                    detected = await loop.run_in_executor(None, wakeword.detect, detect_audio)
                    if now < wakeword_cooldown:
                        continue
                    if detected:
                        print("\n[MIC] Đã nghe 'Alexa'! Đang kết nối Gemini (nền)...")
                        face.send_state("LISTENING")
                        gemini = GeminiAPI(
                            speaker,
                            resumption_handle=resumption_handle,
                            tool_handlers=tool_handlers,
                            face_client=face,
                        )
                        connect_task = asyncio.create_task(gemini.connect())
                        pending_audio = []
                        frames_since_wake = 0
                        status = "CONNECTING"

                # ------------------- TRẠNG THÁI 2: ĐANG KẾT NỐI (NỀN) -------------------
                elif status == "CONNECTING":
                    pending_audio.append((detect_audio, stream_audio))
                    frames_since_wake += 1
                    if connect_task.done():
                        exc = connect_task.exception()
                        if exc:
                            raise exc
                        receive_task = asyncio.create_task(gemini.receive_audio())
                        print("[SYSTEM] Gemini đã sẵn sàng. Mời bạn nói...")
                        status = "LISTENING"
                        listen_deadline = time.monotonic() + LISTEN_TIMEOUT

                        buffered, pending_audio = pending_audio, []
                        for i, (d_chunk, s_chunk) in enumerate(buffered):
                            if i < POST_WAKEWORD_SKIP:
                                continue
                            if status == "LISTENING" and vad.calculate_rms(d_chunk) > vad.start_threshold:
                                print("[MIC] Phát hiện giọng nói trong lúc đang kết nối -- gửi bù...")
                                status = "ACTIVE"
                                last_activity = last_voice = time.monotonic()
                                awaiting_reply = True
                                thinking_sent = False
                            if status == "ACTIVE":
                                await gemini.send_audio(s_chunk)

                # ------------------- TRẠNG THÁI 3: CHỜ BẮT ĐẦU NÓI -------------------
                elif status == "LISTENING":
                    if receive_task.done():
                        exc = receive_task.exception()
                        raise exc if exc else RuntimeError("WebSocket bị ngắt đột ngột!")
                    frames_since_wake += 1
                    if frames_since_wake <= POST_WAKEWORD_SKIP:
                        continue
                    if now > listen_deadline:
                        await end_session("Không nói gì")
                        continue
                    if vad.calculate_rms(detect_audio) > vad.start_threshold:
                        print("[MIC] Đang thu âm và truyền lên Gemini...")
                        status = "ACTIVE"
                        last_activity = last_voice = now
                        awaiting_reply = True
                        thinking_sent = False
                        await gemini.send_audio(stream_audio)

                # ------------------- TRẠNG THÁI 4: GIAO TIẾP HAI CHIỀU -------------------
                elif status == "ACTIVE":
                    if receive_task.done():
                        exc = receive_task.exception()
                        raise exc if exc else RuntimeError("WebSocket bị ngắt đột ngột!")
                    if gemini.go_away_event.is_set():
                        await end_session("Server sắp ngắt kết nối (goAway)")
                        continue

                    muted = gemini.mic_should_be_muted()
                    if muted:
                        # AI đang nói / robot đang cử động / đang cooldown = vẫn là "hoạt động",
                        # không được tính là im lặng (tránh bị ngắt giữa chuỗi hành động dài).
                        last_activity = now
                        awaiting_reply = False
                        thinking_sent = False
                    else:
                        await gemini.send_audio(stream_audio)
                        if vad.calculate_rms(detect_audio) > vad.start_threshold:
                            last_activity = last_voice = now
                            awaiting_reply = True
                            thinking_sent = False

                    # Phản hồi trực quan: người dùng nói xong mà AI chưa đáp -> mặt "đang nghĩ"
                    if awaiting_reply and not muted:
                        silent_for = now - last_voice
                        if not thinking_sent and silent_for > THINK_DELAY:
                            face.send_state("THINKING")
                            thinking_sent = True
                        elif thinking_sent and silent_for > THINK_TIMEOUT:
                            face.send_state("LISTENING")
                            awaiting_reply = False
                            thinking_sent = False

                    if gemini.turn_complete.is_set() and not speaker.is_busy():
                        gemini.turn_complete.clear()
                        last_activity = now
                        awaiting_reply = False
                        thinking_sent = False
                        print("\n[GEMINI] Trả lời xong. Bạn có thể nói tiếp...")
                        if gemini.force_sleep.is_set():
                            await end_session("Nhận lệnh đi ngủ từ người dùng", keep_context=False)
                            continue
                        face.send_state("LISTENING")

                    # Lưới an toàn: đã yêu cầu đi ngủ nhưng không thấy turnComplete
                    if gemini.force_sleep.is_set():
                        if force_sleep_since is None:
                            force_sleep_since = now
                        elif now - force_sleep_since > FORCE_SLEEP_GRACE:
                            await end_session("Nhận lệnh đi ngủ (quá thời gian chờ câu tạm biệt)", keep_context=False)
                            continue

                    if now - last_activity > IDLE_TIMEOUT:
                        await end_session("Kết thúc phiên hội thoại do im lặng", keep_context=False)

            except Exception as e:
                print(f"\n[SYSTEM] Sự cố: {e}")
                # Lỗi ngay lúc kết nối: bỏ handle cũ, tránh kẹt vòng lặp nếu handle hết hạn/bị từ chối
                await end_session("Lỗi trong phiên", keep_context=(status != "CONNECTING"))
                await asyncio.sleep(1.0)

    except KeyboardInterrupt:
        pass
    finally:
        await cancel_task(connect_task)
        await cancel_task(receive_task)
        for name, fn in (
            ("gemini", lambda: gemini and asyncio.ensure_future(gemini.close())),
            ("orc", orc.disconnect),
            ("face", face.close),
            ("mic", microphone.stop_stream),
            ("speaker", speaker.stop_stream),
        ):
            try:
                result = fn()
                if asyncio.isfuture(result):
                    await result
            except Exception as e:
                print(f"[SYSTEM] Lỗi khi đóng {name}: {e}")
        print("\n[SYSTEM] Đã đóng toàn bộ thiết bị.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Đã tắt Robot.")