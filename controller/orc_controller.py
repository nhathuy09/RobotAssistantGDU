import serial,time
import threading
import queue
class OrcController:
    def __init__(self,port="/dev/ttyACM0",baudrate=115200,timeout=0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial=None    
        self.connected=False
        
        self._queue = queue.Queue()
        self._worker_thread = None
        self._stop_event = threading.Event()
    def connect(self):
        if self.serial is None:
            try:
                self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                )
                time.sleep(2)
                self.connected = True
                print(f"[ORC] Connected: {self.port}")
                print(f"[ORC] Baudrate: {self.baudrate}")
                return True
            except serial.SerialException as e:
                print(f"[ORC] Connection failed: {e}")
                self.serial = None
                self.connected = False
                return False
    def disconnect(self):
        if self.serial is not None:
            try:
                self.serial.close()
            except serial.SerialException as e:
                print(f"[ORC] Error while closing serial: {e}")
            self.serial = None
            self.connected = False
            print(f"[ORC] Disconnected: {self.port}")
    def send_command(self, command):
        if not self.connected  or self.serial is None:
            print("[ORC] Not connected. Cannot send command.")
            return None
        command_str = command.strip() + "\n"
        if not command_str:
            return None
        try:
            self.serial.reset_input_buffer()
            self.serial.write(command_str.encode('utf-8'))
            print(f"[ORC] Sent command: {command_str}")
            response = self.serial.readline().decode('utf-8', errors='ignore').strip()
            if not response:
                print("[ORC] No response received (có thể ESP32 chưa kịp phản hồi).")
                return None
            print(f"[ORC] Received response: {response}")
            return response
        except serial.SerialException as e:
            print(f"[ORC] Error sending command: {e}")
            self.connected = False
            return None
        
    def ping(self):
        response = self.send_command("PING")
        if response == "PONG":
            print("[ORC] Ping successful.")
            return True
        else:
            print("[ORC] Ping failed.")
            return False
    def _validate_motion(self, duration, speed):
        if duration <= 0:
            raise ValueError("Duration must be > 0")
        if speed < 0 or speed > 100:
            raise ValueError("Speed must be between 0 and 100")
    def turn_left(self, duration=1.0, speed=50):
        self._validate_motion(duration, speed)
        return self.send_command(f"Q {duration} {speed}")

    def turn_right(self, duration=1.0, speed=50):
        self._validate_motion(duration, speed)
        return self.send_command(f"E {duration} {speed}")
        
    def forward(self, duration=1.0, speed=50):
        self._validate_motion(duration, speed)
        return self.send_command(f"W {duration} {speed}")

    def backward(self, duration=1.0, speed=50):
        self._validate_motion(duration, speed)
        return self.send_command(f"S {duration} {speed}")
    # def rightArm(self, angle=90, speed=100):
    #     self._validate_motion(angle, speed)
    #     return self.send_command(f"R {angle} {speed}")
    # def leftArm(self, angle=90, speed=100):
    #     self._validate_motion(angle, speed)
    #     return self.send_command(f"L {angle} {speed}")
    def stop(self):
        return self.send_command("X")
    def hello(self):
        return self.send_command("H")
    def idle(self):
        return self.send_command("B")
        