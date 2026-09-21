import asyncio
import json
import logging
import time
import base64
import websockets
from config import URL, MODEL_NAME
from controller.motion_tools import TOOL_DECLARATIONS
CONNECT_TIMEOUT = 10
CONTEXT_COMPRESSION_TRIGGER_TOKENS = 25000
CONTEXT_COMPRESSION_WINDOW_TOKENS = 8000
class GeminiAPI:
    MUTE_COOLDOWN = 0.6
    def __init__(self, speaker, resumption_handle=None, tool_handlers=None, face_client=None):
        self.ws = None
        self.speaker = speaker
        self.turn_complete = asyncio.Event()
        self.ai_speaking = False
        self.mic_reopen_at = 0.0
        # Quản lý phiên
        self.resumption_handle = resumption_handle
        self.go_away_event = asyncio.Event()
        self.go_away_time_left = None
        
        self.force_sleep = asyncio.Event()
        self.tool_handlers = tool_handlers or {}
        self.face_client = face_client
        
        self.cmd_queue = asyncio.Queue()
        self.hardware_worker_task = None
        self._queue_free_at = time.monotonic() 
    async def connect(self):
        self.ws = await asyncio.wait_for(websockets.connect(URL), timeout=CONNECT_TIMEOUT)
        print("[GEMINI] Connected to Gemini API.")
        await self.setup()
        self.hardware_worker_task = asyncio.create_task(self._hardware_worker())

    async def setup(self):
        if self.resumption_handle:
            print("[GEMINI] Đang thử tiếp tục ngữ cảnh phiên trước đó...")
        else:
            print("[GEMINI] Bắt đầu phiên hội thoại mới.")
    
        setup_msg = {
            "setup": {
                "model": f"models/{MODEL_NAME}",
                "tools":[{
                    "functionDeclarations": TOOL_DECLARATIONS
                }],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}
                    }
                },
                "realtimeInputConfig": {
                    "automaticActivityDetection": {
                        "disabled": False,
                        "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
                        "endOfSpeechSensitivity": "END_SENSITIVITY_LOW",
                        "prefixPaddingMs": 100,
                        "silenceDurationMs": 600
                    }
                },
                # Kéo dài phiên vô thời hạn (audio-only mặc định giới hạn ~15 phút nếu không nén)
                "contextWindowCompression": {
                    "slidingWindow": {
                        "targetTokens": CONTEXT_COMPRESSION_WINDOW_TOKENS
                    },
                    "triggerTokens": CONTEXT_COMPRESSION_TRIGGER_TOKENS
                },
                # Cho phép nối lại đúng ngữ cảnh cũ nếu resumption_handle còn hiệu lực (trong 2 giờ)
                "sessionResumption": {
                    "handle": self.resumption_handle
                },
                "systemInstruction": {
                    "parts": [
                        {
                            "text": """Bạn là Alexa, trợ lý ảo do sinh viên trường Đại học Gia Định (GDU) phát triển. Bạn có thể trò chuyện, trả lời bắt cứ câu hỏi , và điều khiển robot GDU Assistant. 

[QUY TẮC GIAO TIẾP & HÀNH ĐỘNG]
1. Giao tiếp: Phản hồi bằng giọng nói cực kỳ ngắn gọn, tự nhiên (tối đa 2-3 câu). Luôn xưng hô thân thiện, hỏi tên người dùng trong lần đầu tương tác
2. Vận động (quan trọng): Chỉ gọi tool di chuyển/biểu diễn khi người dùng ra lệnh trực tiếp. Không tự ý gọi tool nếu không có lý do rõ ràng.
3. Nguyên tắc dữ liệu: Tuyệt đối chỉ dùng thông tin được cung cấp bên dưới để tư vấn về GDU. Nếu người dùng hỏi ngoài phạm vi dữ liệu, hãy khéo léo hẹn họ liên hệ phòng tuyển sinh.
4. Về phần kiến thức nội bộ  về GDU: bạn chỉ đề cập tới thông tin này khi nguời dùng yêu cầu, hoặc khi người dùng hỏi về GDU. Không được tự ý nhắc tới kiến thức nội bộ về GDU nếu không có ngữ cảnh. Nếu người dùng hỏi ngoài phạm vi dữ liệu, hãy khéo léo hẹn họ liên hệ phòng tuyển sinh.
[KIẾN THỨC NỘI BỘ VỀ GDU]

--- 1. THÔNG TIN CHUNG ---
- Tên trường: Trường Đại học Gia Định (Gia Dinh University - GDU).
- Lịch sử: Là ĐH tư thục tại TP.HCM, thành lập năm 2007 (tiền thân là ĐH Tư thục Công nghệ - Thông tin Gia Định). Năm 2026 kỷ niệm 19 năm phát triển.
- Triết lý giáo dục: "Chọn lọc (kiến thức trọng tâm) – Ứng dụng (chú trọng thực hành) – Đại chúng (cơ hội học tập với mức phí phù hợp)".
- Địa điểm: Cơ sở Tân Sơn Nhất (371 Nguyễn Kiệm, Phường Hạnh Thông, TP.HCM) - vị trí trung tâm, gần sân bay.
- Chất lượng: Đạt chuẩn kiểm định quốc gia ở cả cấp cơ sở và cấp chương trình đào tạo.

--- 2. CHƯƠNG TRÌNH ĐÀO TẠO ---
- Quy mô: Đa ngành, đa lĩnh vực với 6 Khoa chính:
  + Khoa Công nghệ thông tin (CNTT, IoT, AI, Kỹ thuật phần mềm...)
  + Khoa Quản trị - Marketing
  + Khoa Tài chính - Thương mại
  + Khoa Khoa học Xã hội & Ngôn ngữ Quốc tế
  + Khoa Truyền thông số
  + Khoa Khoa học Sức khỏe
- Lợi thế cạnh tranh: Thời gian đào tạo tinh gọn (từ 3 năm). Lộ trình: "Học -> làm dự án -> thực tập -> đi làm".
- Trải nghiệm: Sinh viên có 2 học kỳ thực tế tại doanh nghiệp.

--- 3. HỌC PHÍ ---
- Mức phí tham khảo: Từ khoảng 1,1 triệu VNĐ/tín chỉ.
- Lưu ý: Học phí linh hoạt thay đổi tùy thuộc vào chương trình, số tín chỉ và từng khóa cụ thể."""
                        }
                    ]
                }
            }
        }
        await asyncio.wait_for(self.ws.send(json.dumps(setup_msg)), timeout=CONNECT_TIMEOUT)
        await asyncio.wait_for(self.ws.recv(), timeout=CONNECT_TIMEOUT)
        print("[GEMINI] Setup completed.")

    async def send_audio(self, audio_data):
        audio_b64 = base64.b64encode(audio_data.tobytes()).decode("utf-8")
        msg = {"realtimeInput": {"audio": {"mimeType": "audio/pcm;rate=16000", "data": audio_b64}}}
        await self.ws.send(json.dumps(msg))

    def mic_should_be_muted(self):
        return self.ai_speaking or time.monotonic() < self.mic_reopen_at
    # async def _auto_return_idle(self, seq: int, delay: float):
    #     await asyncio.sleep(delay)
    #     if seq != self._action_seq:
    #         return  
    #     idle_handler = self.tool_handlers.get("idle_pose")
    #     if idle_handler is None:
    #         return
    #     loop = asyncio.get_running_loop()
    #     print("[TOOL] Tự động quay về idle_pose sau động tác biểu diễn.")
    #     try:
    #         await loop.run_in_executor(None, idle_handler, {})
    #     except Exception as e:
    #         logging.error(f"[TOOL] Lỗi khi tự động về idle: {e}")
    def _estimate_action_duration(self, name: str, args: dict) -> float:
        dur = float(args.get("duration", 0))
        if dur > 0:
            return dur
        return 2.0 if name in ["wave_hello"] else 0.5        
    async def _handle_tool_call(self, tool_call):
        responses = []
        calls = tool_call.get("functionCalls", [])
        start_at = max(self._queue_free_at, time.monotonic())
        total_duration = 0.0
        for fc in calls:
            name = fc.get("name")
            args = fc.get("args", {}) or {}
            call_id = fc.get("id")
            if name == "end_conversation":
                self.force_sleep.set()
                responses.append({"id": fc.get("id"), "name": name, "response": {"status": "ok"}})
                continue
            if name not in self.tool_handlers:
                print(f"[TOOL] Cảnh báo: Gemini gọi tool không tồn tại '{name}'")
                responses.append({"id": call_id, "name": name,
                                "response": {"status": "error", "detail": f"Không có handler cho '{name}'"}})
                continue
            self.cmd_queue.put_nowait((name, args))
            print(f"[AI] Đã xếp '{name}' vào hàng đợi.")
            dur = self._estimate_action_duration(name, args)
            start_at = start_at + dur
            total_duration += dur
            responses.append({"id": call_id, "name": name, "response": {"status": "ok"}})
            if name in ["wave_hello"]:
                self.cmd_queue.put_nowait(("idle_pose", {}))
                print("[SYSTEM] Tự động chèn 'idle_pose' vào để thu tay về.")
                total_duration += 0.5
        self._queue_free_at = start_at
        self.mic_reopen_at = max(self.mic_reopen_at, time.monotonic() + total_duration + 0.5)
        await self.ws.send(json.dumps({"toolResponse": {"functionResponses": responses}}))
    
    async def _hardware_worker(self):
        loop = asyncio.get_running_loop()
        while True:
            try:
                name, args = await self.cmd_queue.get()
                
                print(f"[WORKER] Bắt đầu thực thi phần cứng: {name}({args})")
                
                if self.face_client:
                    self.face_client.send_state("ACTING")

                handler = self.tool_handlers.get(name)
                if handler:
                    try:
                        await loop.run_in_executor(None, handler, args)
                        dur = self._estimate_action_duration(name, args)
                        await asyncio.sleep(dur + 0.1)    
                    except Exception as e:
                        logging.error(f"[WORKER] Lỗi điều khiển {name}: {e}")
                if self.face_client:
                    self.face_client.send_state("IDLE")
                self.cmd_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[WORKER] Vòng lặp gặp lỗi: {e}")
    async def receive_audio(self):
        loop = asyncio.get_running_loop()
        try:
            async for message in self.ws:
                response = json.loads(message)

                if "goAway" in response:
                    self.go_away_time_left = response["goAway"].get("timeLeft")
                    print(f"[GEMINI] GoAway nhận được, còn lại: {self.go_away_time_left}")
                    self.go_away_event.set()
                    continue
                if "sessionResumptionUpdate" in response:
                    update = response["sessionResumptionUpdate"]
                    if update.get("resumable") and update.get("newHandle"):
                        self.resumption_handle = update["newHandle"]
                    continue

                if "toolCall" in response:
                    await self._handle_tool_call(response["toolCall"])
                    continue

                if "toolCallCancellation" in response:
                    print("[GEMINI] Tool call bị huỷ do người dùng ngắt lời.")
                    continue

                if "serverContent" not in response:
                    continue
                server_content = response["serverContent"]

                # if server_content.get("interrupted", False):
                #     print("[GEMINI] Interrupted by user.")
                #     self.ai_speaking = False
                #     self.mic_reopen_at = time.monotonic() + self.MUTE_COOLDOWN
                #     await loop.run_in_executor(None, self.speaker.flush)
                #     continue

                model_turn = server_content.get("modelTurn", {})
                if model_turn:
                    for part in model_turn.get("parts", []):
                        if "text" in part:
                            print(part["text"], end="", flush=True)
                        if "inlineData" in part:
                            audio_b64 = part["inlineData"].get("data", "")
                            if audio_b64:
                                if not self.ai_speaking:
                                # self.ai_speaking = True
                                    if self.face_client:
                                        self.face_client.send_state("SPEAKING")
                                self.ai_speaking = True
                                raw_audio = base64.b64decode(audio_b64)
                                await loop.run_in_executor(None, self.speaker.play, raw_audio)

                if server_content.get("turnComplete", False):
                    print("\n[GEMINI] Turn complete.")
                    self.mic_reopen_at = time.monotonic() + self.MUTE_COOLDOWN
                    self.ai_speaking = False
                    if self.face_client:
                        self.face_client.send_state("IDLE")
                    self.turn_complete.set()
        except asyncio.CancelledError:
            print("[GEMINI] Receive audio task cancelled.")
            raise
        except Exception as e:
            logging.error(f"[GEMINI] Error receiving audio: {e}")

    async def close(self):
        if self.hardware_worker_task and not self.hardware_worker_task.done():
            self.hardware_worker_task.cancel()
            try:
                await self.hardware_worker_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
            print("[GEMINI] Connection closed.")