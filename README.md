# BÁO CÁO PHÂN TÍCH THIẾT KẾ KIẾN TRÚC HỆ THỐNG ROBOT ASSISTANT (GDU)
**Tài liệu Phân Tích Luồng Hoạt Động, Sơ Đồ Tuần Tự (Sequence Diagram) và Sơ Đồ Trạng Thái (State Diagram)**

---

## 1. TỔNG QUAN HỆ THỐNG (SYSTEM OVERVIEW)

Dự án **Robot Assistant** (Trợ lý ảo robot trường Đại học Gia Định - GDU) là hệ thống nhúng thông minh tích hợp trí tuệ nhân tạo tạo sinh đa phương thức thời gian thực (Multimodal Generative AI Realtime). Hệ thống hoạt động dựa trên mô hình xử lý phân tán bất đồng bộ kết hợp giữa phần cứng biên (Raspberry Pi/Edge Device, vi điều khiển Orc Hub điều khiển động cơ) và hạ tầng điện toán đám mây (Google Gemini Live WebSocket API).

### 1.1. Các thành phần cốt lõi trong Source Code

1. **Vòng lặp điều phối trung tâm (`main.py`)**:
   - Quản trị luồng bất đồng bộ chính (`asyncio.run(main())`).
   - Quản lý máy trạng thái cấp cao: `WAKEWORD` $\rightarrow$ `CONNECTING` $\rightarrow$ `ACTIVE`.
   - Vận hành worker thu âm liên tục không nghẽn (`mic_reader_worker`) qua hàng đợi kích thước giới hạn `audio_queue(maxsize=20)`.
   - Quản lý vòng đời phiên (Session Lifecycle), timeout im lặng (`IDLE_TIMEOUT = 12.0s`), thời gian chờ kích hoạt lại wakeword (`WAKEWORD_COOLDOWN_AFTER_SESSION = 2.5s`).

2. **Module Gemini Live API (`core/gemini_api.py`)**:
   - Thiết lập kết nối hai chiều Full-duplex WebSocket (`wss://generativelanguage.googleapis.com/...`) sử dụng model `gemini-3.1-flash-live-preview`.
   - Hỗ trợ **Session Resumption** (`resumption_handle`) để ghi nhớ ngữ cảnh hội thoại xuyên suốt các lượt gọi thức dậy.
   - Cơ chế Server-side VAD (Voice Activity Detection tự động ngắt câu với độ nhạy cấu hình).
   - Cơ chế **Mic Muting Logic** (`mic_should_be_muted`, `MUTE_COOLDOWN = 0.6s`) nhằm triệt tiêu hiện tượng dội âm (Acoustic Echo Feedback) khi loa đang phát câu trả lời của AI.
   - Hàng đợi bất đồng bộ điều khiển phần cứng riêng biệt (`cmd_queue` và task `_hardware_worker`) giúp tách rời thời gian thực thi của động cơ ra khỏi luồng xử lý audio/network.

3. **Module Điều khiển Chuyển động & Phần cứng (`controller/orc_controller.py` & `controller/motion_tools.py`)**:
   - Giao tiếp nối tiếp UART/Serial (`/dev/ttyACM0`, 115200 baud) với vi điều khiển Orc Hub.
   - Điều khiển chuyển động (`W`: Tiến, `S`: Lùi, `Q`: Xoay trái, `E`: Xoay phải, `X`: Dừng, `H`: Vẫy tay, `B`: Tư thế nghỉ).
   - Cơ chế Thread-safe Serial với `threading.Lock()` bảo vệ dữ liệu truyền nhận.
   - Ánh xạ Function Calling (Tool Declarations) từ Gemini Live: `move_forward`, `move_backward`, `turn_left`, `turn_right`, `stop_robot`, `wave_hello`, `idle_pose`, `end_conversation`.

4. **Module Hiển thị Biểu cảm (`display/face_client.py`)**:
   - Giao tiếp phi khóa (Non-blocking UDP Socket) gửi gói tin trạng thái biểu cảm tới màn hình (`gdupi3.local:5005`).
   - Phân giải sẵn địa chỉ IP (`_resolve_ip`) tránh nghẽn luồng xử lý do DNS lookup.
   - 4 trạng thái biểu cảm: `IDLE` (Chờ/Nghỉ), `LISTENING` (Đang nghe), `SPEAKING` (Đang nói), `ACTING` (Đang vận động).

5. **Module Âm thanh & Nhận diện WakeWord (`audio/`, `wakeword/`)**:
   - **Microphone (`audio/microphone.py`)**: Thu âm 48kHz Stereo 32-bit, bộ lọc High-pass (40Hz cắt ù DC), SoftAGC (tự động điều biến độ lợi mượt mà chống méo âm), Low-pass chống gấp dải phổ (anti-aliasing) và Downsample về 16kHz Mono 16-bit PCM.
   - **Speaker (`audio/speaker.py`)**: Phát âm thanh 24kHz 16-bit PCM với hàng đợi non-blocking thread-safe `queue.Queue(maxsize=150)` và luồng playback riêng biệt; hỗ trợ `flush()` tức thì khi bị gián đoạn.
   - **WakeWordDetector (`wakeword/detector.py`)**: Sử dụng mô hình `openwakeword` nhận diện từ khóa "Alexa" cục bộ với ngưỡng tin cậy $0.85$ và cơ chế Cooldown chống kích hoạt trùng lặp.

---

## 2. THIẾT KẾ SƠ ĐỒ TUẦN TỰ (SEQUENCE DIAGRAMS)

### 2.1. Sơ đồ 1: Khởi động hệ thống và Kích hoạt WakeWord ("Alexa")

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant Main as Main Loop (main.py)
    participant MicWorker as Mic Reader Worker
    participant Mic as Microphone (I2S/USB)
    participant WW as WakeWord Detector (openwakeword)
    participant Face as Face Client (UDP)
    participant Gem as GeminiAPI

    Main->>Main: Khởi tạo Orc, Mic, Speaker, Face, WakeWord
    Main->>Face: send_state("IDLE")
    Main->>Mic: start_stream()
    Main->>MicWorker: asyncio.create_task(mic_reader_worker)
    
    loop Đọc âm thanh liên tục (Non-blocking)
        MicWorker->>Mic: read() (48kHz -> Filter -> AGC -> 16kHz)
        MicWorker->>Main: audio_queue.put(chunk)
    end

    Note over Main: Trạng thái: WAKEWORD (Chờ kích hoạt)
    User->>Mic: Phát âm: "Alexa..."
    Main->>WW: detect(audio_data)
    WW-->>Main: True (score >= 0.85)
    
    Note over Main: Phát hiện WakeWord thành công
    Main->>Face: send_state("LISTENING")
    Main->>Gem: GeminiAPI(speaker, resumption_handle, tool_handlers, face)
    Main->>Gem: create_task(gemini.connect())
    Main->>Main: Chuyển trạng thái sang CONNECTING
    Main->>Main: Bật đồng hồ timeout (CONNECT_TIMEOUT = 10s)
```

---

### 2.2. Sơ đồ 2: Kết nối WebSocket Gemini Live & Thiết lập Phiên (Bắt tay & Session Resumption)

```mermaid
sequenceDiagram
    autonumber
    participant Main as Main Loop (main.py)
    participant Gem as GeminiAPI
    participant WS as Google Gemini Live Server (WSS)
    participant HW as Hardware Worker Task

    Note over Main,Gem: Trạng thái: CONNECTING (Tích lũy audio vào pending_audio)
    Gem->>WS: websockets.connect(URL)
    WS-->>Gem: WebSocket Handshake 101 Switching Protocols
    
    Gem->>Gem: setup()
    Gem->>WS: Gửi JSON setup_msg (Model, VoiceConfig, Tools, Server VAD, resumption_handle)
    WS-->>Gem: Setup Completed Response
    Gem->>HW: create_task(_hardware_worker())
    Gem-->>Main: connect_task hoàn tất thành công

    Main->>Gem: create_task(gemini.receive_audio())
    Main->>Main: Chuyển trạng thái sang ACTIVE
    Main->>Main: Gửi bù âm thanh từ pending_audio (bỏ qua POST_WAKEWORD_SKIP khung)
    
    loop Gửi bù Buffer
        Main->>Gem: send_audio(chunk)
        Gem->>WS: realtimeInput (audio/pcm b64)
    end
```

---

### 2.3. Sơ đồ 3: Giao tiếp Thoại hai chiều Full-Duplex & Quản lý Chống dội âm (Mute Logic)

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant Main as Main Loop (main.py)
    participant Gem as GeminiAPI
    participant WS as Google Gemini Live Server
    participant Spk as Speaker Playback Thread
    participant Face as Face Client (UDP)

    Note over Main,WS: Trạng thái: ACTIVE (Hội thoại liên tục)
    
    rect rgb(235, 245, 255)
        Note over User,WS: GIAI ĐOẠN 1: NGƯỜI DÙNG NÓI
        User->>Main: Giọng nói: "Trường Đại học Gia Định có những ngành nào?"
        Main->>Gem: mic_should_be_muted()?
        Gem-->>Main: False (Loa đang rảnh, AI chưa nói)
        Main->>Gem: send_audio(audio_data)
        Gem->>WS: realtimeInput (audio/pcm rate=16000)
    end

    rect rgb(240, 255, 240)
        Note over WS,Spk: GIAI ĐOẠN 2: GEMINI PHẢN HỒI STREAMING VÀ PHÁT LOA
        WS-->>Gem: serverContent (modelTurn: inlineData audio chunk)
        Gem->>Gem: Đặt ai_speaking = True
        Gem->>Face: send_state("SPEAKING")
        Gem->>Spk: speaker.play(raw_audio) (đưa vào Queue phát non-blocking)
        Spk->>Spk: Phát âm thanh qua I2S/Audio Out (24kHz)
        
        Note over Main,Gem: Trong lúc loa phát: mic_should_be_muted() = True -> Main DROP audio đầu vào
    end

    rect rgb(255, 248, 230)
        Note over WS,Main: GIAI ĐOẠN 3: HOÀN TẤT LƯỢT NÓI (TURN COMPLETE) VÀ MỞ LẠI MIC
        WS-->>Gem: serverContent (turnComplete = True)
        Gem->>Gem: turn_complete.set()
        Gem->>Gem: mic_reopen_at = time.now() + 0.6s (MUTE_COOLDOWN)
        
        loop Kiểm tra trạng thái loa xả hết Buffer
            Main->>Spk: speaker.is_playing()?
            Spk-->>Main: False (Buffer đã phát hết)
        end

        Main->>Gem: turn_complete.clear() & ai_speaking = False
        Main->>Face: send_state("LISTENING")
        Main->>Main: Reset last_activity (Gia hạn IDLE_TIMEOUT)
    end
```

---

### 2.4. Sơ đồ 4: Thực thi Gọi Hàm Phần Cứng (Function Calling / Tool Execution)

```mermaid
sequenceDiagram
    autonumber
    actor User as Người dùng
    participant WS as Gemini Live Server
    participant Gem as GeminiAPI
    participant Queue as asyncio.Queue (cmd_queue)
    participant Worker as Hardware Worker Task
    participant Tools as Motion Handlers (motion_tools.py)
    participant Orc as Orc Controller (Serial UART)
    participant Face as Face Client (UDP)

    User->>WS: "Chào mọi người và tiến lên 2 mét đi robot"
    WS-->>Gem: response { toolCall: { functionCalls: [ {name: "wave_hello"}, {name: "move_forward", args: {duration: 2, speed: 60}} ] } }
    
    Gem->>Gem: _handle_tool_call()
    Gem->>Queue: put_nowait(("wave_hello", {}))
    Gem->>Queue: put_nowait(("idle_pose", {})) (Tự động chèn để thu tay)
    Gem->>Queue: put_nowait(("move_forward", {duration: 2, speed: 60}))
    
    Gem->>Gem: Tính toán ước lượng thời gian chạy động cơ
    Gem->>Gem: Kéo dài mic_reopen_at = now + total_duration + 0.5s
    Gem->>WS: Gửi toolResponse (status: ok) để Gemini tiếp tục sinh lời nói đồng thời
    
    par Luồng Hardware Worker thực thi tuần tự các lệnh cơ khí
        Worker->>Queue: get() -> ("wave_hello", {})
        Worker->>Face: send_state("ACTING")
        Worker->>Tools: wave_hello handler
        Tools->>Orc: hello() -> send_command("H")
        Orc-->>Worker: UART Response từ vi điều khiển
        Worker->>Worker: asyncio.sleep(2.0 + 0.1s)
        Worker->>Face: send_state("IDLE")

        Worker->>Queue: get() -> ("idle_pose", {})
        Worker->>Tools: idle_pose handler
        Tools->>Orc: idle() -> send_command("B")
        Worker->>Worker: asyncio.sleep(0.5 + 0.1s)

        Worker->>Queue: get() -> ("move_forward", {duration: 2, speed: 60})
        Worker->>Face: send_state("ACTING")
        Worker->>Tools: move_forward handler
        Tools->>Orc: forward(duration=2.0, speed=60) -> send_command("W 2.0 60")
        Orc-->>Worker: UART Response
        Worker->>Worker: asyncio.sleep(2.0 + 0.1s)
        Worker->>Face: send_state("IDLE")
    and Luồng Gemini vừa nói vừa diễn
        WS-->>Gem: serverContent (modelTurn: audio stream "Dạ em chào mọi người...")
        Gem->>Face: send_state("SPEAKING")
    end
```

---

### 2.5. Sơ đồ 5: Luồng Kết Thúc Phiên Hội Thoại (Session Teardown)

```mermaid
sequenceDiagram
    autonumber
    participant Main as Main Loop (main.py)
    participant Gem as GeminiAPI
    participant WS as Gemini Live Server
    participant WW as WakeWord Detector
    participant Face as Face Client (UDP)

    alt Kịch bản A: Người dùng ra lệnh "Đi ngủ / Tạm biệt"
        WS-->>Gem: toolCall { name: "end_conversation" }
        Gem->>Gem: force_sleep.set()
        Gem->>WS: toolResponse { status: "ok" }
        Note over Main: Khi lượt nói kết thúc trọn vẹn:
        Main->>Main: end_session("Nhận lệnh đi ngủ từ người dùng")
    else Kịch bản B: Im lặng quá hạn (Silence Timeout)
        Note over Main: time.monotonic() - last_activity > 12.0s
        Main->>Main: end_session("Kết thúc phiên hội thoại do im lặng")
    else Kịch bản C: Server gửi tín hiệu sắp ngắt (GoAway)
        WS-->>Gem: response { goAway: { timeLeft: "..." } }
        Gem->>Gem: go_away_event.set()
        Main->>Main: end_session("Server sắp ngắt kết nối (goAway)")
    end

    rect rgb(255, 235, 235)
        Note over Main,Face: TIẾN TRÌNH DỌN DẸP & LƯU NGỮ CẢNH
        Main->>Main: Cancel & await connect_task, receive_task
        
        alt Nếu ngắt bình thường (không phải lệnh ngủ/im lặng)
            Main->>Main: Lưu resumption_handle = gemini.resumption_handle
        else Lệnh ngủ hoặc im lặng
            Main->>Main: resumption_handle = None (Xóa ngữ cảnh để phiên sau tươi mới)
        end

        Main->>Gem: gemini.close() (Đóng WS, huỷ hardware_worker)
        Main->>Face: send_state("IDLE")
        Main->>WW: set_cooldown(2.5s) (Ngăn mic nhận diện lại chính tiếng vang cũ)
        Main->>Main: status = "WAKEWORD" (Quay lại vòng chờ ban đầu)
    end
```

---

## 3. THIẾT KẾ SƠ ĐỒ TRẠNG THÁI (STATE DIAGRAMS)

### 3.1. Sơ đồ Trạng thái Tổng thể Hệ thống (System High-Level FSM)

Máy trạng thái của chương trình chính (`main.py`) điều khiển toàn bộ chu kỳ sống từ lúc khởi động cho tới khi chạy hội thoại và dọn dẹp.

```mermaid
stateDiagram-v2
    [*] --> SYSTEM_INIT: Khởi chạy main()

    state SYSTEM_INIT {
        [*] --> InitHardware
        InitHardware --> InitAudio: Kết nối Orc Serial (/dev/ttyACM0)
        InitAudio --> StartMicWorker: Mở luồng PyAudio (Mic + Speaker)
        StartMicWorker --> [*]: Tạo mic_reader_worker (Queue 20)
    }

    SYSTEM_INIT --> WAKEWORD: Hoàn tất khởi tạo (status = "WAKEWORD")

    state WAKEWORD {
        [*] --> CheckCooldown
        CheckCooldown --> SleepWait: is_in_cooldown() == True
        SleepWait --> CheckCooldown: Chờ hết cooldown (2.5s)
        CheckCooldown --> Detecting: is_in_cooldown() == False
        Detecting --> Detecting: score < 0.85 (Tiếp tục nghe)
    }

    WAKEWORD --> CONNECTING: WakeWord "Alexa" phát hiện (score >= 0.85) / Face = "LISTENING"

    state CONNECTING {
        [*] --> OpenWebSocket
        OpenWebSocket --> SendSetup: WS Connected
        SendSetup --> WaitResponse: Gửi setup_msg (tools, voice, resumption)
        WaitResponse --> BufferAudio: Lắng nghe âm thanh đầu vào đưa vào pending_audio
        BufferAudio --> Ready: Nhận Setup Completed
    }

    CONNECTING --> WAKEWORD: Timeout kết nối (>10s) hoặc Lỗi WS / end_session()
    CONNECTING --> ACTIVE: Kết nối & Setup thành công / Tạo receive_audio task

    state ACTIVE {
        [*] --> DuplexConversation
        state DuplexConversation {
            state "USER_SPEAKING / STREAMING" as UserSpeak
            state "GEMINI_THINKING / ACTING" as AiThink
            state "AI_SPEAKING" as AiSpeak
            state "TURN_COMPLETE_DRAIN" as TurnDrain

            [*] --> UserSpeak
            UserSpeak --> AiThink: Gemini Server VAD kích hoạt ngắt câu
            AiThink --> AiSpeak: Nhận inlineData PCM
            AiSpeak --> TurnDrain: serverContent.turnComplete == True
            TurnDrain --> UserSpeak: Loa xả hết buffer & Hết MUTE_COOLDOWN (0.6s)
        }
    }

    ACTIVE --> WAKEWORD: IDLE_TIMEOUT (12s) / "end_conversation" / Server GoAway / Gặp lỗi
    
    WAKEWORD --> SHUTDOWN: Nhận tín hiệu KeyboardInterrupt (Ctrl+C)
    CONNECTING --> SHUTDOWN: Nhận tín hiệu KeyboardInterrupt
    ACTIVE --> SHUTDOWN: Nhận tín hiệu KeyboardInterrupt

    state SHUTDOWN {
        [*] --> CancelTasks
        CancelTasks --> CloseGemini: Hủy mic_task, receive_task, connect_task
        CloseGemini --> DisconnectHardware: Đóng WS
        DisconnectHardware --> [*]: Ngắt Orc Serial, Tắt Face UDP, Đóng Loa & Mic
    }

    SHUTDOWN --> [*]
```

---

### 3.2. Sơ đồ Trạng thái Chi tiết: Vòng lặp Âm thanh & Triệt tiêu Dội âm (Audio & Acoustic Echo Muting State Machine)

Logic điều khiển Micro trong `core/gemini_api.py` và `main.py` là hạt nhân quyết định khả năng đàm thoại tự nhiên mượt mà mà không bị tiếng loa phản hồi vào mic.

```mermaid
stateDiagram-v2
    [*] --> MIC_OPEN: Bắt đầu trạng thái ACTIVE

    state MIC_OPEN {
        [*] --> Capture16k
        Capture16k --> SendToGemini: Mic thu -> Filter -> AGC -> Downsample 16k
        SendToGemini --> Capture16k: Gửi realtimeInput qua WebSocket
    }

    MIC_OPEN --> AI_SPEAKING_MUTED: Nhận gói audio phản hồi đầu tiên (inlineData) từ Gemini

    state AI_SPEAKING_MUTED {
        [*] --> PlayChunk
        PlayChunk --> FeedSpeakerQueue: Đưa dữ liệu PCM 24k vào Speaker Queue
        FeedSpeakerQueue --> DropMicFrames: Khóa Mic (mic_should_be_muted = True)
        DropMicFrames --> DropMicFrames: Loại bỏ toàn bộ khung âm từ Mic nhằm chống phản hồi
    }

    AI_SPEAKING_MUTED --> DRAINING_SPEAKER: Nhận cờ serverContent.turnComplete = True từ Gemini

    state DRAINING_SPEAKER {
        [*] --> CheckSpeakerBuffer
        CheckSpeakerBuffer --> WaitForSpeaker: speaker.is_playing() == True
        WaitForSpeaker --> CheckSpeakerBuffer: Loa đang phát các gói audio dở dang
        CheckSpeakerBuffer --> CooldownGuard: speaker.is_playing() == False
        CooldownGuard --> CooldownGuard: Đợi time >= mic_reopen_at (now + 0.6s)
    }

    DRAINING_SPEAKER --> MIC_OPEN: Loa đã im lặng hoàn toàn và hết thời gian đệm Cooldown
```

---

### 3.3. Sơ đồ Trạng thái Màn hình Biểu cảm Robot (Face Display State Machine)

Module `FaceClient` liên tục phát tín hiệu trạng thái tới Raspberry Pi qua UDP Socket để hiển thị khuôn mặt động:

```mermaid
stateDiagram-v2
    [*] --> IDLE: Khởi động hệ thống

    IDLE --> LISTENING: Phát hiện WakeWord "Alexa" hoặc Gemini bắt đầu mở Mic
    LISTENING --> SPEAKING: Nhận audio từ Gemini Live (AI bắt đầu nói)
    LISTENING --> ACTING: Hardware Worker bắt đầu thực thi lệnh Motor/Tay
    
    SPEAKING --> LISTENING: Hoàn tất lượt nói (Turn Complete & Speaker rảnh)
    SPEAKING --> ACTING: Vừa nói vừa gọi chuyển động (Chuyển đổi trạng thái)
    
    ACTING --> IDLE: Hoàn tất lệnh động cơ (move/wave/turn) trong Hardware Worker
    ACTING --> SPEAKING: Vẫn còn audio đang phát sau khi động cơ dừng
    
    LISTENING --> IDLE: Hết phiên hội thoại (Timeout / Lệnh đi ngủ / Ngắt kết nối)
    SPEAKING --> IDLE: Lỗi phiên hoặc ngắt phiên đột ngột
```

---

## 4. BẢNG MA TRẬN CHUYỂN TRẠNG THÁI CHI TIẾT (STATE TRANSITION TABLE)

| STT | Trạng thái hiện tại | Sự kiện kích hoạt (Event / Trigger) | Điều kiện biên (Guard Condition) | Hành động thực hiện (Actions) | Trạng thái tiếp theo |
|:---:|:---|:---|:---|:---|:---|
| **1** | `SYSTEM_INIT` | Ứng dụng khởi động | Cổng Serial mở thành công hoặc bỏ qua lỗi | Khởi tạo Microphone, Speaker, Orc, FaceClient, WakeWord. Bật luồng đọc Mic ngầm. | `WAKEWORD` |
| **2** | `WAKEWORD` | Âm thanh từ Mic đổ về hàng đợi | `wakeword.is_in_cooldown() == True` | Bỏ qua khung âm, không chạy model nhằm tiết kiệm CPU và tránh kích hoạt nhầm. | `WAKEWORD` |
| **3** | `WAKEWORD` | Đọc âm thanh | `wakeword.detect(chunk) == True` (Score $\ge 0.85$) | Đổi Face sang `"LISTENING"`, tạo `GeminiAPI`, khởi tạo `gemini.connect()` task, đặt deadline timeout 10s. | `CONNECTING` |
| **4** | `CONNECTING` | Âm thanh đổ về liên tục | Đang đợi handshake | Tích lũy âm thanh vào danh sách tạm `pending_audio`. | `CONNECTING` |
| **5** | `CONNECTING` | `time.monotonic() > connect_deadline` | Quá 10s không nhận phản hồi từ Gemini | Báo lỗi `TimeoutError`, dọn dẹp kết nối, đặt Face `"IDLE"`. | `WAKEWORD` |
| **6** | `CONNECTING` | `connect_task.done()` | Không có Exception | Tạo task `receive_audio`, chuyển Face `"LISTENING"`, gửi bù âm thanh đã buffer (bỏ 2 frame đầu). | `ACTIVE` |
| **7** | `ACTIVE` | Người dùng nói vào Mic | `mic_should_be_muted() == False` | Mã hóa Base64 PCM 16kHz, gửi bản tin `realtimeInput` qua WebSocket. | `ACTIVE` |
| **8** | `ACTIVE` | Nhận phản hồi `inlineData` | `serverContent.modelTurn` có audio | Đặt `ai_speaking = True`, đổi Face `"SPEAKING"`, đưa dữ liệu thô vào `speaker.play()`. | `ACTIVE` |
| **9** | `ACTIVE` | Loa đang phát hoặc `ai_speaking == True` | `mic_should_be_muted()` được gọi | Trả về `True`, tính lại mốc `mic_reopen_at = now + 0.6s`, chặn không gửi Mic lên Gemini. | `ACTIVE` |
| **10** | `ACTIVE` | Nhận `toolCall` từ Gemini | Hàm có trong `tool_handlers` | Đẩy `(name, args)` vào `cmd_queue`, ước lượng thời gian chạy động cơ, phản hồi ngay `toolResponse` (status: ok). | `ACTIVE` |
| **11** | `ACTIVE` | `cmd_queue` có phần tử | `_hardware_worker` đang chạy | Đổi Face `"ACTING"`, chạy hàm điều khiển Orc Serial trong thread pool, sau đó đổi lại Face `"IDLE"`. | `ACTIVE` |
| **12** | `ACTIVE` | Nhận `serverContent.turnComplete` | Server báo kết thúc câu trả lời | Đặt cờ `turn_complete.set()`, gia hạn thời gian bảo vệ chống dội âm `mic_reopen_at`. | `ACTIVE` |
| **13** | `ACTIVE` | Loa phát xong (`is_playing() == False`) | `time.monotonic() >= gemini.mic_reopen_at` | Xóa cờ `turn_complete`, đặt `ai_speaking = False`, đổi Face `"LISTENING"`, cập nhật `last_activity`. | `ACTIVE` |
| **14** | `ACTIVE` | Nhận tool `end_conversation` | Người dùng nói chào tạm biệt/đi ngủ | Đặt `force_sleep.set()`, đợi nói xong câu chào rồi gọi `end_session("Nhận lệnh đi ngủ")`. | `WAKEWORD` |
| **15** | `ACTIVE` | `time.monotonic() - last_activity > 12.0s` | Không có tương tác âm thanh từ cả 2 phía | Gọi `end_session("Kết thúc phiên do im lặng")`, xóa `resumption_handle`. | `WAKEWORD` |
| **16** | `ACTIVE` | Nhận bản tin `goAway` | Server chuẩn bị ngắt WebSocket | Đọc `timeLeft`, gọi `end_session("Server sắp ngắt")`. | `WAKEWORD` |
| **17** | `ACTIVE` | Đứt cáp mạng / WebSocket Error | `receive_task.exception()` khác `None` | Bắt ngoại lệ, gọi `end_session("Lỗi trong phiên")`, chờ 1.0s. | `WAKEWORD` |
| **18** | `BẤT KỲ` | Người dùng nhấn Ctrl+C | `KeyboardInterrupt` | Hủy toàn bộ Task nền, đóng Serial Orc Hub, giải phóng PyAudio Mic/Speaker, tắt Socket UDP. | `TERMINATED` |

---

## 5. CÁC ĐIỂM SÁNG KIẾN VÀ KỸ THUẬT TỐI ƯU TRONG SOURCE CODE

1. **Pipeline xử lý âm thanh số hóa chất lượng cao (DSP Audio Pipeline)**:
   - Thay vì thu âm trực tiếp ở 16kHz dễ bị méo hài trên phần cứng Raspberry Pi, hệ thống thu ở tần số tiêu chuẩn **48kHz Stereo 32-bit**, lọc thông cao 40Hz loại bỏ tạp âm rung sàn và DC offset, áp dụng thuật toán nén dải động **SoftAGC** thích ứng nhanh (`attack=0.7`, `release=0.98`), sau đó lọc chống gấp tần (Anti-aliasing Lowpass) rồi mới Downsample về **16kHz Mono 16-bit**.
2. **Kiến trúc Producer-Consumer cách ly hoàn toàn IO phần cứng**:
   - `mic_reader_worker` sử dụng `run_in_executor` để việc đọc phần cứng PyAudio không chặn Event Loop của asyncio. Hàng đợi có cơ chế tự drop frame cũ khi đầy (`Queue.full()`), đảm bảo độ trễ âm thanh luôn ở mức thời gian thực (< 50ms).
   - Tương tự, `_hardware_worker` tách các lệnh động cơ có độ trễ lớn (chạy 1-2 giây) vào hàng đợi riêng, cho phép mô hình AI vừa nói vừa ra lệnh mà không làm nghẽn luồng xử lý WebSocket.
3. **Cơ chế chống Acoustic Echo Feedback tự trị (Zero-Cost AEC)**:
   - Không cần dùng bộ AEC phức tạp tốn tài nguyên phần cứng, hệ thống phối hợp giữa kiểm tra trạng thái bộ đệm loa (`speaker.is_playing()`) và thời gian hạ nhiệt Cooldown (`MUTE_COOLDOWN = 0.6s`), triệt tiêu triệt để tình trạng AI tự nghe thấy giọng của chính mình rồi ngắt lời giữa chừng.
4. **Quản lý ngữ cảnh thông minh (Smart Context Persistence)**:
   - Hệ thống biết phân biệt lý do kết thúc phiên: Nếu kết thúc vì "đi ngủ" hoặc "im lặng quá lâu", `resumption_handle` sẽ bị xóa để phiên tiếp theo mở đầu mới mẻ. Nếu kết thúc do ngắt kết nối kỹ thuật, handle được lưu lại để duy trì trí nhớ của cuộc trò chuyện.

---

## 6. KẾT LUẬN

Hệ thống mã nguồn của **Robot Assistant** được thiết kế mạch lạc theo mô hình **Sự kiện - Bất đồng bộ (Event-driven Asynchronous Architecture)**. Việc kết hợp chặt chẽ giữa các máy trạng thái cấp ứng dụng và máy trạng thái xử lý tín hiệu âm thanh giúp robot vận hành ổn định, độ trễ thấp và đem lại trải nghiệm tương tác tự nhiên.
