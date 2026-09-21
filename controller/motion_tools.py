from controller.orc_controller import OrcController
TOOL_DECLARATIONS = [
    {
        "name": "move_forward",
        "description": "Di chuyển robot tiến về phía trước trong một khoảng thời gian nhất định.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "duration": {"type": "NUMBER", "description": "Thời gian di chuyển, tính bằng giây."},
                "speed": {"type": "INTEGER", "description": "Tốc độ di chuyển, từ 0-100."}
            },
            "required": ["duration"]
         }
    },
    
    {
        "name": "move_backward",
        "description": "Di chuyển robot lùi lại.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "duration": {"type": "NUMBER", "description": "Thời gian di chuyển, tính bằng giây."},
                "speed": {"type": "INTEGER", "description": "Tốc độ 0-100."}
            },
            "required": ["duration"]
        }
    },
    {
        "name": "turn_left",
        "description": "Xoay robot sang trái tại chỗ.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "duration": {"type": "NUMBER"},
                "speed": {"type": "INTEGER"}
            },
            "required": ["duration"]
        }
    },
    {
        "name": "turn_right",
        "description": "Xoay robot sang phải tại chỗ.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "duration": {"type": "NUMBER"},
                "speed": {"type": "INTEGER"}
            },
            "required": ["duration"]
        }
    },
    {
        "name": "stop_robot",
        "description": "Dừng ngay lập tức mọi chuyển động của robot.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "wave_hello",
        "description": "Vẫy tay chào khi gặp người dùng lần đầu hoặc khi được yêu cầu chào.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "idle_pose",
        "description": "Trở về tư thế nghỉ/chờ mặc định.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "end_conversation",
        "description": "Gọi hàm này ngay lập tức khi người dùng nói lời chào tạm biệt, yêu cầu dừng trò chuyện, hoặc kêu robot đi ngủ, nghỉ ngơi.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    
]


def build_tool_handlers(orc: "OrcController"):
    def _forward(args):
        return orc.forward(duration=args.get("duration", 1.0), speed=args.get("speed", 60))
    def _backward(args):
        return orc.backward(duration=args.get("duration", 1.0), speed=args.get("speed", 60))
    def _turn_left(args):
        return orc.turn_left(duration=args.get("duration", 0.8), speed=args.get("speed", 60))
    def _turn_right(args):
        return orc.turn_right(duration=args.get("duration", 0.8), speed=args.get("speed", 60))
    return {
        "move_forward": _forward,
        "move_backward": _backward,
        "turn_left": _turn_left,
        "turn_right": _turn_right,
        "stop_robot": lambda args: orc.stop(),
        "wave_hello": lambda args: orc.hello(),
        "idle_pose": lambda args: orc.idle(),
    }