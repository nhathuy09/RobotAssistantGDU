import asyncio
import time
import logging
from audio.microphone import Microphone
from audio.speaker import Speaker
from audio.vad import VoiceActivityDetector
from wakeword.detector import WakeWordDetector
from core.gemini_api import GeminiAPI
from core.reconnect import RECONNECT_DELAYS, GeminiDisconnected, is_retryable_connection_error
from controller.orc_controller import OrcController
from controller.motion_tools import build_tool_handlers
from display.face_client import FaceClient

try:
    from database.repositories import PersonaRepository
except ImportError:
    PersonaRepository = None

GREETING_TIMEOUT = 30.0
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
    greeting_pending = False
    greeting_deadline = None
    
    retry_count = 0
    retry_at = 0.0
    cleanup_task = None
    handled_tool_calls = set()

    def start_connection():
        nonlocal gemini, connect_task
        gemini = GeminiAPI(
            speaker, resumption_handle=resumption_handle,
            tool_handlers=tool_handlers, face_client=face,
            handled_tool_calls=handled_tool_calls,
        )
        connect_task = asyncio.create_task(gemini.connect())

    async def begin_connected_session():
        nonlocal receive_task, status, greeting_pending, greeting_deadline
        nonlocal skip_count, listen_deadline, last_activity
        receive_task = asyncio.create_task(gemini.receive_audio())
        if greeting_pending:
            # Mark before send: a failed send may already have reached the server.
            # Do not automatically send a duplicate opening after reconnect.
            greeting_pending = False
            status = "GREETING"
            greeting_deadline = time.monotonic() + GREETING_TIMEOUT
            face.send_state("THINKING")
            await gemini.send_greeting()
            print("[SYSTEM] Đã yêu cầu Gemini chào chủ động. Vui lòng chờ lời chào.")
        else:
            status = "LISTENING"
            skip_count = POST_WAKEWORD_SKIP
            listen_deadline = time.monotonic() + LISTEN_TIMEOUT
            last_activity = time.monotonic()
            face.send_state("LISTENING")
            print("[SYSTEM] Đã kết nối lại. Bạn có thể nói tiếp, không cần gọi Alexa.")

    async def close_current_connection():
        nonlocal gemini, connect_task, receive_task, resumption_handle
        old_gemini = gemini
        tasks = [t for t in (connect_task, receive_task) if t is not None]
        gemini = connect_task = receive_task = None
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if old_gemini:
            resumption_handle = old_gemini.resumption_handle
            try:
                await old_gemini.close()
            except Exception:
                logging.exception("[SYSTEM] Lỗi đóng kết nối Gemini cũ")
        await asyncio.get_running_loop().run_in_executor(None, speaker.flush)

    async def finish_cleanup():
        nonlocal cleanup_task
        if cleanup_task:
            await cleanup_task
            cleanup_task = None

    async def end_session(reason: str):
        nonlocal status, wakeword_cooldown, resumption_handle, retry_count, greeting_pending
        print(f"\n[SYSTEM] {reason} -- ngắt kết nối, quay lại chờ 'Alexa'.")
        await finish_cleanup()
        await close_current_connection()
        if "ngủ" in reason.lower() or "im lặng" in reason.lower():
            resumption_handle = None
        if resumption_handle is None:
            handled_tool_calls.clear()
        retry_count = 0
        greeting_pending = False
        status = "WAKEWORD"
        wakeword.reset()
        wakeword_cooldown = time.monotonic() + WAKEWORD_COOLDOWN_AFTER_SESSION
        face.send_state("SLEEP" if "ngủ" in reason.lower() else "IDLE")

    async def schedule_reconnect(error):
        nonlocal status, retry_count, retry_at, cleanup_task
        # An explicit sleep request must not be undone by a network failure.
        if gemini and gemini.force_sleep.is_set():
            await end_session("Nhận lệnh đi ngủ từ người dùng")
            return
        if retry_count >= len(RECONNECT_DELAYS):
            await end_session("Không thể kết nối lại sau 3 lần thử")
            return
        delay = RECONNECT_DELAYS[retry_count]
        retry_count += 1
        status = "RECONNECTING"
        retry_at = time.monotonic() + delay
        # Cleanup runs in the background so the loop keeps draining the mic.
        cleanup_task = asyncio.create_task(close_current_connection())
        face.send_state("THINKING")
        print(f"[SYSTEM] {type(error).__name__}: {error}")
        print(f"[SYSTEM] Đang kết nối lại {retry_count}/{len(RECONNECT_DELAYS)} "
              f"sau {delay:g}s. Vui lòng chờ trước khi nói tiếp.")

    try:
        if not orc.connect():
            print("[SYSTEM] Không kết nối được Orc Hub -- robot sẽ chạy không có motor.")
        tool_handlers = build_tool_handlers(orc)
        # face.start_stream()
        microphone.start_stream()
        speaker.start_stream()
        while not (stop_event and stop_event.is_set()):
            try:
                network_operation = False
                # Nếu người dùng đang ở các màn hình cài đặt (Persona, WiFi, PIN, System...)
                # Tạm dừng lắng nghe WakeWord để nhường trọn CPU và chống nhiễu rè loa
                if app_manager and getattr(app_manager, "current_screen_name", "face") != "face":
                    if status != "WAKEWORD" or gemini or cleanup_task:
                        await end_session("Tạm dừng hội thoại khi mở cài đặt")
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

                        retry_count = 0
                        greeting_pending = True
                        if resumption_handle is None:
                            handled_tool_calls.clear()
                        start_connection()
                        status = "CONNECTING"

                elif status == "RECONNECTING":
                    # Discard audio captured while offline; never replay it.
                    if cleanup_task:
                        if not cleanup_task.done():
                            continue
                        await finish_cleanup()
                    if connect_task is None:
                        if time.monotonic() >= retry_at:
                            if resumption_handle is None:
                                handled_tool_calls.clear()
                            start_connection()
                        continue
                    if not connect_task.done():
                        continue
                    network_operation = True
                    await connect_task
                    connect_task = None
                    await begin_connected_session()

                elif status == "CONNECTING":
                    # Greeting-first: discard capture during setup rather than
                    # replaying speech/noise that could interrupt the opening.
                    if connect_task.done():
                        network_operation = True
                        await connect_task
                        connect_task = None
                        await begin_connected_session()

                elif status == "GREETING":
                    network_operation = True
                    if receive_task.done():
                        await receive_task
                        raise GeminiDisconnected("Luồng nhận Gemini đã kết thúc.")
                    if gemini.go_away_event.is_set():
                        await schedule_reconnect(GeminiDisconnected("Gemini gửi goAway"))
                        continue
                    # Continue draining the mic, but do not send any audio until
                    # the opening has finished playing and the mute cooldown ends.
                    if gemini.turn_complete.is_set() and not gemini.mic_should_be_muted():
                        gemini.turn_complete.clear()
                        status = "LISTENING"
                        skip_count = POST_WAKEWORD_SKIP
                        listen_deadline = time.monotonic() + LISTEN_TIMEOUT
                        last_activity = time.monotonic()
                        retry_count = 0
                        face.send_state("LISTENING")
                        print("[SYSTEM] Đã chào xong. Mời bạn nói...")
                    elif time.monotonic() >= greeting_deadline:
                        await end_session("Hết thời gian chờ lời chào Gemini")

                # ------------------- TRẠNG THÁI 3: CHỜ BẮT ĐẦU NÓI -------------------
                elif status == "LISTENING":
                    network_operation = True
                    if receive_task.done():
                        await receive_task
                        raise GeminiDisconnected("Luồng nhận Gemini đã kết thúc.")
                    if gemini.go_away_event.is_set():
                        await schedule_reconnect(GeminiDisconnected("Gemini gửi goAway"))
                        continue
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
                    network_operation = True
                    if receive_task.done():
                        await receive_task
                        raise GeminiDisconnected("Luồng nhận Gemini đã kết thúc.")
                    if gemini.go_away_event.is_set():
                        await schedule_reconnect(GeminiDisconnected("Gemini gửi goAway"))
                        continue
                    if not gemini.mic_should_be_muted():
                        await gemini.send_audio(audio_data)
                        if vad.calculate_rms(audio_data) > vad.start_threshold:
                            last_activity = time.monotonic()
                    if gemini.ai_speaking:
                        last_activity = time.monotonic()
                    if gemini.turn_complete.is_set() and not speaker.is_busy():
                        gemini.turn_complete.clear()
                        # Reset the budget only after a completed turn, not setup:
                        # repeated immediate disconnects must exhaust retries.
                        retry_count = 0
                        last_activity = time.monotonic()
                        print("\n[GEMINI] Trả lời xong. Bạn có thể nói tiếp...")
                        if gemini.force_sleep.is_set():
                            await end_session("Nhận lệnh đi ngủ từ người dùng")
                            continue
                    if time.monotonic() - last_activity > IDLE_TIMEOUT:
                        await end_session("Kết thúc phiên hội thoại do im lặng")

            except (asyncio.CancelledError, KeyboardInterrupt):
                break
            except Exception as e:
                if stop_event and stop_event.is_set():
                    break
                if isinstance(e, RuntimeError) and (
                    "cannot schedule new futures" in str(e) or "Event loop is closed" in str(e)
                ):
                    break
                if network_operation and is_retryable_connection_error(e):
                    # Traceback retains the original socket error and its cause.
                    logging.exception("[SYSTEM] Kết nối Gemini bị gián đoạn")
                    await schedule_reconnect(e)
                else:
                    logging.exception("[SYSTEM] Lỗi không tự động thử lại")
                    await end_session("Lỗi trong phiên")
                    await asyncio.sleep(1.0)

    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        try:
            await finish_cleanup()
            await close_current_connection()
        except Exception:
            logging.exception("[SYSTEM] Lỗi dọn phiên khi thoát")
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



