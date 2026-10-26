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

try:
    from database.repositories import PersonaRepository
except ImportError:
    PersonaRepository = None

LISTEN_TIMEOUT = 6.0     
IDLE_TIMEOUT = 10.0     
POST_WAKEWORD_SKIP = 2   
WAKEWORD_COOLDOWN_AFTER_SESSION = 2.5
async def main(app_manager=None, stop_event=None):
    microphone = Microphone()
    speaker = Speaker()
    wakeword = WakeWordDetector()
    vad = VoiceActivityDetector(start_threshold=1000, speech_threshold=1500)
    orc = OrcController(port="/dev/ttyACM0") 
    face = FaceClient(app_manager=app_manager) if app_manager else FaceClient(ip="127.0.0.1", port=5005)
    tool_handlers = None

    current_persona_id = None
    if PersonaRepository:
        try:
            active_p = PersonaRepository.get_active_persona()
            current_persona_id = active_p.get("id") if active_p else None
        except Exception:
            pass

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
        face.send_state("SLEEP" if "ngủ" in reason.lower() else "IDLE")

    try:
        if not orc.connect():
            print("[SYSTEM] Không kết nối được Orc Hub -- robot sẽ chạy không có motor.")
        tool_handlers = build_tool_handlers(orc)
        # face.start_stream()
        microphone.start_stream()
        speaker.start_stream()
        while not (stop_event and stop_event.is_set()):
            try:
                # Nếu người dùng đang ở các màn hình cài đặt (Persona, WiFi, PIN, System...)
                # Tạm dừng lắng nghe WakeWord để nhường trọn CPU và chống nhiễu rè loa
                if app_manager and getattr(app_manager, "current_screen_name", "face") != "face":
                    await asyncio.sleep(0.1)
                    continue

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

                        if PersonaRepository:
                            try:
                                active_p = PersonaRepository.get_active_persona()
                                new_p_id = active_p.get("id") if active_p else None
                                if current_persona_id is not None and new_p_id != current_persona_id:
                                    print(f"[SYSTEM] Vai trò Persona đã đổi ({current_persona_id} -> {new_p_id}). Làm mới phiên hội thoại!")
                                    resumption_handle = None
                                current_persona_id = new_p_id
                            except Exception:
                                pass

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
                    if gemini.turn_complete.is_set() and not speaker.is_busy():
                        gemini.turn_complete.clear()
                        last_activity = time.monotonic()
                        print("\n[GEMINI] Trả lời xong. Bạn có thể nói tiếp...")
                        if gemini.force_sleep.is_set():
                            await end_session("Nhận lệnh đi ngủ từ người dùng")
                            continue
                    if time.monotonic() - last_activity > IDLE_TIMEOUT:
                        await end_session("Kết thúc phiên hội thoại do im lặng")

            except (asyncio.CancelledError, KeyboardInterrupt):
                break
            except RuntimeError as e:
                # Nếu event loop hoặc executor đang shutdown
                if "cannot schedule new futures" in str(e) or "Event loop is closed" in str(e):
                    break
                if stop_event and stop_event.is_set():
                    break
                print(f"\n[SYSTEM] Sự cố Runtime: {e}")
                await end_session("Lỗi trong phiên")
                await asyncio.sleep(1.0)
            except Exception as e:
                if stop_event and stop_event.is_set():
                    break
                print(f"\n[SYSTEM] Sự cố: {e}")
                await end_session("Lỗi trong phiên")
                await asyncio.sleep(1.0) 

    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except (asyncio.CancelledError, Exception):
                pass
        if gemini:
            try:
                await gemini.close()
            except Exception:
                pass
        try:
            orc.disconnect()
        except Exception:
            pass
        try:
            face.close()
        except Exception:
            pass
        try:
            microphone.stop_stream()
        except Exception:
            pass
        try:
            speaker.stop_stream()
        except Exception:
            pass
        print("\n[SYSTEM] Đã đóng mic, loa và phần cứng.")


if __name__ == "__main__":
    import argparse
    import threading

    parser = argparse.ArgumentParser(description="Robot Assistant BD-1")
    parser.add_argument("--no-gui", action="store_true", help="Chạy chế độ Headless / CLI không có giao diện màn hình")
    args = parser.parse_args()

    def run_brain(app_manager=None, stop_event=None):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        main_task = loop.create_task(main(app_manager, stop_event))

        def _monitor_stop():
            if stop_event:
                stop_event.wait()
                if not main_task.done():
                    loop.call_soon_threadsafe(main_task.cancel)

        monitor_thread = threading.Thread(target=_monitor_stop, daemon=True, name="BrainStopMonitor")
        monitor_thread.start()

        try:
            loop.run_until_complete(main_task)
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except Exception as e:
            if not (stop_event and stop_event.is_set()):
                print(f"[BRAIN] Lỗi luồng AI: {e}")
        finally:
            try:
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for t in pending:
                    t.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            except Exception:
                pass

    if args.no_gui:
        print("[SYSTEM] Khởi chạy Robot ở chế độ Headless (CLI only)...")
        stop_evt = threading.Event()
        try:
            run_brain(app_manager=None, stop_event=stop_evt)
        except KeyboardInterrupt:
            print("\nĐã tắt Robot.")
        finally:
            stop_evt.set()
    else:
        print("[SYSTEM] Khởi chạy Robot Assistant (GUI AppManager + AI Brain)...")
        try:
            from display.app_manager import AppManager
            app = AppManager(width=800, height=480)

            stop_evt = threading.Event()
            brain_thread = threading.Thread(
                target=run_brain, 
                args=(app, stop_evt), 
                daemon=False,
                name="AIBrainThread"
            )
            brain_thread.start()

            # Chạy Pygame event loop trên main thread
            app.run()
        except KeyboardInterrupt:
            print("\nNhận tín hiệu dừng.")
        finally:
            stop_evt.set()
            if 'brain_thread' in locals() and brain_thread.is_alive():
                brain_thread.join(timeout=2.5)
            print("[SYSTEM] Đã tắt hoàn tất.")



