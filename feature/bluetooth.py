import os
import re
import sys
import json
import time
import shutil
import threading
import subprocess
from typing import List, Dict, Optional

# Cấu hình Win32 API cho Windows
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    try:
        import ctypes
        from ctypes import wintypes
        ole32 = ctypes.WinDLL("ole32")
        bthprops = ctypes.WinDLL(r"C:\Windows\System32\bthprops.cpl")

        CLSIDFromString = ole32.CLSIDFromString
        CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
        CLSIDFromString.restype = wintypes.DWORD

        bthprops.BluetoothFindFirstDevice.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        bthprops.BluetoothFindFirstDevice.restype = wintypes.HANDLE

        bthprops.BluetoothFindNextDevice.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        bthprops.BluetoothFindNextDevice.restype = wintypes.BOOL

        bthprops.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]
        bthprops.BluetoothFindDeviceClose.restype = wintypes.BOOL

        bthprops.BluetoothSetServiceState.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
        bthprops.BluetoothSetServiceState.restype = wintypes.DWORD

        HAS_WIN32_BT = True
    except Exception as _e:
        HAS_WIN32_BT = False
else:
    HAS_WIN32_BT = False


def safe_log(msg: str):
    """Ghi log an toàn không bị lỗi bảng mã trên Windows console cp1258/ascii."""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


class BluetoothManager:
    """
    Quản lý kết nối thiết bị Bluetooth thực tế cho Robot.
    - Trên Linux (Raspberry Pi): Sử dụng công cụ chuẩn `bluetoothctl`
    - Trên Windows: Sử dụng Win32 Bluetooth API (bthprops.cpl) & PnP để kết nối AudioSink / Handsfree thực tế
    """

    # CACHE_FILE đã được loại bỏ - dữ liệu nay lưu trong SQLite (BluetoothDeviceRepository)

    # GUID dịch vụ âm thanh Bluetooth chuẩn quốc tế
    GUID_A2DP = "{0000110b-0000-1000-8000-00805f9b34fb}"
    GUID_HFP  = "{0000111e-0000-1000-8000-00805f9b34fb}"

    IGNORE_PATTERNS = [
        "enumerator", "adapter", "service", "generic", "radio",
        "protocol", "transport", "pse", "tdi", "device information",
        "microsoft bluetooth", "intel", "realtek", "mediatek"
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self.scanning = False
        self.connecting_id: Optional[str] = None
        self.is_linux = IS_LINUX
        self.is_windows = IS_WINDOWS
        self.has_bluetoothctl = bool(shutil.which("bluetoothctl"))
        self.devices: List[Dict] = []
        self._connected_ids = set()

        # Nạp cache trước để hiển thị tức thì
        self._load_cache()

        # Quét mới ở chế độ nền
        self.scan()

    def _load_cache(self):
        """Nạp danh sách thiết bị đã có từ SQLite (BluetoothDeviceRepository)."""
        try:
            from database.repositories import BluetoothDeviceRepository
            cached = BluetoothDeviceRepository.get_cached_devices()
            if cached:
                self.devices = cached
        except Exception:
            pass

    def _save_cache(self, devices: List[Dict]):
        """Lưu danh sách thiết bị vào SQLite (BluetoothDeviceRepository)."""
        try:
            from database.repositories import BluetoothDeviceRepository
            BluetoothDeviceRepository.save_devices(devices)
        except Exception:
            pass

    def snapshot(self) -> Dict:
        """Trả về bản sao trạng thái quét và danh sách thiết bị hiện tại."""
        with self._lock:
            return {
                "scanning": self.scanning,
                "connecting_id": self.connecting_id,
                "devices": [dict(d) for d in self.devices],
            }

    def scan(self):
        """Khởi chạy quét thiết bị Bluetooth thực tế trong background thread."""
        with self._lock:
            if self.scanning:
                return
            self.scanning = True

        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        try:
            if self.is_linux and self.has_bluetoothctl:
                found_devices = self._scan_linux()
            elif self.is_windows:
                found_devices = self._scan_windows()
            else:
                found_devices = list(self.devices)

            with self._lock:
                self.devices = found_devices
            self._save_cache(found_devices)
        except Exception as exc:
            safe_log(f"[BLUETOOTH] Quét thiết bị lỗi: {exc}")
        finally:
            with self._lock:
                self.scanning = False

    def _classify_device_type(self, name: str) -> str:
        """Phân loại thiết bị dựa vào tên thiết bị."""
        lower = name.lower()
        if any(k in lower for k in ("headphone", "earphone", "buds", "air", "encok", "headset", "wh-", "wf-")):
            return "Headphones"
        elif any(k in lower for k in ("speaker", "soundmax", "nanomax", "loa", "flip", "jbl", "xiqeer", "boombox", "charge")):
            return "Bluetooth Speaker"
        elif any(k in lower for k in ("mouse", "chuột", "keyboard", "phím")):
            return "Peripheral"
        elif any(k in lower for k in ("phone", "iphone", "samsung", "xiaomi", "nhathuy", "galaxy")):
            return "Smartphone Audio"
        return "Audio Device"

    def _scan_windows(self) -> List[Dict]:
        """Quét danh sách thiết bị Bluetooth thực tế trên Windows thông qua Win32 API & PnP."""
        # 1. Quét trạng thái Connected thực tế qua Win32 API nếu khả dụng
        win32_connected_names = set()
        win32_connected_macs = set()

        if HAS_WIN32_BT:
            try:
                self._query_win32_devices(win32_connected_names, win32_connected_macs)
            except Exception as e:
                print(f"[BLUETOOTH] Win32 query error: {e}")

        # 2. Quét qua PnP PowerShell để lấy danh sách đầy đủ tất cả thiết bị
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-PnpDevice -Class Bluetooth | Select-Object -Property FriendlyName, Status, InstanceId | ConvertTo-Json"
        ]

        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        res = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", creationflags=flags)

        raw = res.stdout.strip()
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except Exception:
            return []

        if isinstance(data, dict):
            data = [data]

        seen_names = set()
        devices = []

        for item in data:
            name = (item.get("FriendlyName") or "").strip()
            if not name:
                continue

            lower = name.lower()
            if any(p in lower for p in self.IGNORE_PATTERNS):
                continue

            if name in seen_names:
                continue
            seen_names.add(name)

            dev_id = item.get("InstanceId") or name
            dev_type = self._classify_device_type(name)

            # Trích xuất MAC address nếu có trong InstanceId
            mac = ""
            m = re.search(r"DEV_([0-9A-Fa-f]{12})", dev_id)
            if m:
                hex_str = m.group(1).upper()
                mac = ":".join(hex_str[i:i+2] for i in range(0, 12, 2))

            # Xác định trạng thái kết nối thực tế
            is_connected = (
                (dev_id in self._connected_ids) or
                (name in win32_connected_names) or
                (mac and mac in win32_connected_macs)
            )

            signal = 94 if is_connected else 80
            status_text = "Connected" if is_connected else ("Paired" if item.get("Status") == "OK" else "Ready")

            devices.append({
                "id": dev_id,
                "mac": mac,
                "name": name,
                "type": dev_type,
                "status": status_text,
                "connected": is_connected,
                "signal": signal,
            })

        # Sắp xếp thiết bị đã kết nối lên đầu, sau đó đến Audio
        devices.sort(key=lambda d: (not d["connected"], d["type"] == "Peripheral", d["name"]))
        return devices

    def _query_win32_devices(self, out_connected_names: set, out_connected_macs: set):
        """Dùng Win32 Bluetooth API để đọc trạng thái kết nối thực tế."""
        ptr_size = ctypes.sizeof(ctypes.c_void_p)
        search_params_size = 24 + ptr_size * 2
        dev_info_size = 560

        search_params = (ctypes.c_ubyte * search_params_size)()
        ctypes.memmove(search_params, (ctypes.c_uint * 1)(search_params_size), 4)
        ctypes.memmove(ctypes.byref(search_params, 4), (ctypes.c_uint * 1)(1), 4)
        ctypes.memmove(ctypes.byref(search_params, 8), (ctypes.c_uint * 1)(1), 4)

        dev_info = (ctypes.c_ubyte * dev_info_size)()
        ctypes.memmove(dev_info, (ctypes.c_uint * 1)(dev_info_size), 4)

        h_find = bthprops.BluetoothFindFirstDevice(ctypes.byref(search_params), ctypes.byref(dev_info))
        if not h_find:
            return

        try:
            while True:
                name_raw = ctypes.wstring_at(ctypes.byref(dev_info, 64), 248)
                dev_name = name_raw.split('\x00')[0]

                addr_val = ctypes.c_ulonglong.from_buffer_copy(bytes(dev_info[8:16])).value
                addr_hex = f"{addr_val:012X}"
                mac = ":".join(addr_hex[i:i+2] for i in range(0, 12, 2))

                # fConnected nằm ở offset 20 (wintypes.BOOL = 4 bytes)
                f_connected = ctypes.c_int.from_buffer_copy(bytes(dev_info[20:24])).value != 0

                if f_connected:
                    out_connected_names.add(dev_name)
                    out_connected_macs.add(mac)

                if not bthprops.BluetoothFindNextDevice(h_find, ctypes.byref(dev_info)):
                    break
        finally:
            bthprops.BluetoothFindDeviceClose(h_find)

    def _scan_linux(self) -> List[Dict]:
        """Quét danh sách thiết bị Bluetooth thực tế trên Linux / Raspberry Pi bằng bluetoothctl."""
        try:
            subprocess.run(["bluetoothctl", "--timeout", "5", "scan", "on"], capture_output=True, timeout=6)
        except Exception:
            pass

        res = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, errors="ignore")
        paired_res = subprocess.run(["bluetoothctl", "paired-devices"], capture_output=True, text=True, errors="ignore")

        paired_macs = set()
        for line in paired_res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                paired_macs.add(parts[1])

        devices = []
        for line in res.stdout.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) >= 3 and parts[0] == "Device":
                mac = parts[1]
                name = parts[2].strip()

                info_res = subprocess.run(["bluetoothctl", "info", mac], capture_output=True, text=True, errors="ignore")
                info_text = info_res.stdout

                is_connected = ("Connected: yes" in info_text) or (mac in self._connected_ids)
                is_paired = mac in paired_macs or "Paired: yes" in info_text
                status_text = "Connected" if is_connected else ("Paired" if is_paired else "Ready")

                dev_type = self._classify_device_type(name)

                devices.append({
                    "id": mac,
                    "mac": mac,
                    "name": name,
                    "type": dev_type,
                    "status": status_text,
                    "connected": is_connected,
                    "signal": 88 if is_connected else 72,
                })

        devices.sort(key=lambda d: (not d["connected"], d["name"]))
        return devices

    def connect(self, device_id: str):
        """Kết nối thực tế thiết bị Bluetooth (chạy nền không block UI)."""
        with self._lock:
            if self.connecting_id:
                safe_log(f"[BLUETOOTH] Đang trong tiến trình kết nối thiết bị khác: {self.connecting_id}")
                return
            self.connecting_id = device_id
            for d in self.devices:
                if d["id"] == device_id or d.get("mac") == device_id or d.get("name") == device_id:
                    d["status"] = "Connecting..."

        threading.Thread(target=self._connect_worker, args=(device_id,), daemon=True).start()

    def _connect_worker(self, device_id: str):
        success = False
        target_device = None

        with self._lock:
            for d in self.devices:
                if d["id"] == device_id or d.get("mac") == device_id or d.get("name") == device_id:
                    target_device = dict(d)
                    break

        if not target_device:
            safe_log(f"[BLUETOOTH] Không tìm thấy thông tin thiết bị: {device_id}")
            with self._lock:
                self.connecting_id = None
            return

        name = target_device.get("name", "")
        mac = target_device.get("mac", "")

        safe_log(f"[BLUETOOTH] Bắt đầu kết nối thực tế tới '{name}' (ID: {device_id}, MAC: {mac})...")

        try:
            if self.is_linux and self.has_bluetoothctl:
                # 1. Kết nối trên Linux
                success = self._connect_linux_device(mac or device_id)
            elif self.is_windows:
                # 2. Kết nối trên Windows qua Win32 API
                success = self._connect_windows_device(name, mac)
            else:
                # Môi trường khác: giả lập
                time.sleep(1.2)
                success = True
        except Exception as exc:
            safe_log(f"[BLUETOOTH] Ngoại lệ khi kết nối: {exc}")
            success = False

        with self._lock:
            self.connecting_id = None
            if success:
                self._connected_ids.add(device_id)
                if mac:
                    self._connected_ids.add(mac)
                if name:
                    self._connected_ids.add(name)

                for d in self.devices:
                    if d["id"] == device_id or d.get("mac") == mac or d.get("name") == name:
                        d["connected"] = True
                        d["status"] = "Connected"
                    else:
                        d["connected"] = False
                        if d["status"] == "Connected":
                            d["status"] = "Paired"
            else:
                for d in self.devices:
                    if d["id"] == device_id or d.get("mac") == mac or d.get("name") == name:
                        d["connected"] = False
                        d["status"] = "Failed"

            self._save_cache(self.devices)

        safe_log(f"[BLUETOOTH] Kết nối '{name}': {'THÀNH CÔNG' if success else 'THẤT BẠI'}")

    def _connect_linux_device(self, mac: str) -> bool:
        """Thực hiện kết nối Bluetooth trên Linux / Raspberry Pi."""
        try:
            # Đảm bảo thiết bị được trust
            subprocess.run(["bluetoothctl", "trust", mac], capture_output=True, timeout=5)
            # Kết nối
            res = subprocess.run(["bluetoothctl", "connect", mac], capture_output=True, text=True, timeout=12)
            out = res.stdout
            if "Connection successful" in out:
                return True

            # Kiểm tra lại info
            info = subprocess.run(["bluetoothctl", "info", mac], capture_output=True, text=True, timeout=5)
            return "Connected: yes" in info.stdout
        except Exception as exc:
            safe_log(f"[BLUETOOTH] Linux connect error: {exc}")
            return False

    def _connect_windows_device(self, name: str, mac: str) -> bool:
        """Thực hiện kết nối Bluetooth Audio trên Windows qua Win32 API."""
        if not HAS_WIN32_BT:
            safe_log("[BLUETOOTH] Win32 Bluetooth API không khả dụng")
            return False

        dev_buf, real_name = self._win32_find_device(name, mac)
        if not dev_buf:
            safe_log(f"[BLUETOOTH] Không tìm thấy thiết bị Windows: {name} (MAC: {mac})")
            return False

        # Bật Hands-Free và AudioSink (A2DP)
        hf_res = self._win32_toggle_service(dev_buf, self.GUID_HFP, True)
        as_res = self._win32_toggle_service(dev_buf, self.GUID_A2DP, True)
        safe_log(f"[BLUETOOTH] Kết quả Win32: HFP={hf_res}, AudioSink={as_res}")

        return (as_res == "ok") or (hf_res == "ok")

    def disconnect(self, device_id: str):
        """Ngắt kết nối thực tế thiết bị Bluetooth."""
        with self._lock:
            target_device = None
            for d in self.devices:
                if d["id"] == device_id or d.get("mac") == device_id or d.get("name") == device_id:
                    target_device = dict(d)
                    d["status"] = "Disconnecting..."
                    break

        threading.Thread(target=self._disconnect_worker, args=(device_id, target_device), daemon=True).start()

    def _disconnect_worker(self, device_id: str, target_device: Optional[Dict]):
        name = target_device.get("name", "") if target_device else ""
        mac = target_device.get("mac", "") if target_device else ""

        safe_log(f"[BLUETOOTH] Ngắt kết nối thực tế '{name}' (ID: {device_id})...")

        try:
            if self.is_linux and self.has_bluetoothctl:
                subprocess.run(["bluetoothctl", "disconnect", mac or device_id], capture_output=True, timeout=8)
            elif self.is_windows and HAS_WIN32_BT:
                dev_buf, _ = self._win32_find_device(name, mac)
                if dev_buf:
                    self._win32_toggle_service(dev_buf, self.GUID_HFP, False)
                    self._win32_toggle_service(dev_buf, self.GUID_A2DP, False)
        except Exception as exc:
            safe_log(f"[BLUETOOTH] Lỗi khi ngắt kết nối: {exc}")

        with self._lock:
            self._connected_ids.discard(device_id)
            if mac:
                self._connected_ids.discard(mac)
            if name:
                self._connected_ids.discard(name)

            for d in self.devices:
                if d["id"] == device_id or d.get("mac") == mac or d.get("name") == name:
                    d["connected"] = False
                    d["status"] = "Paired"

            self._save_cache(self.devices)

        safe_log(f"[BLUETOOTH] Đã ngắt kết nối '{name}'")

    # =========================================================================
    # CÁC HÀM TRỢ GIÚP WIN32 BLUETOOTH
    # =========================================================================
    def _win32_find_device(self, target_name: str, target_mac: str):
        if not HAS_WIN32_BT:
            return None, None

        ptr_size = ctypes.sizeof(ctypes.c_void_p)
        search_params_size = 24 + ptr_size * 2
        dev_info_size = 560

        search_params = (ctypes.c_ubyte * search_params_size)()
        ctypes.memmove(search_params, (ctypes.c_uint * 1)(search_params_size), 4)
        ctypes.memmove(ctypes.byref(search_params, 4), (ctypes.c_uint * 1)(1), 4)
        ctypes.memmove(ctypes.byref(search_params, 8), (ctypes.c_uint * 1)(1), 4)

        dev_info = (ctypes.c_ubyte * dev_info_size)()
        ctypes.memmove(dev_info, (ctypes.c_uint * 1)(dev_info_size), 4)

        h_find = bthprops.BluetoothFindFirstDevice(ctypes.byref(search_params), ctypes.byref(dev_info))
        if not h_find:
            return None, None

        clean_mac = target_mac.replace(":", "").replace("-", "").upper() if target_mac else ""
        matched_buf = None
        matched_name = None

        try:
            while True:
                name_raw = ctypes.wstring_at(ctypes.byref(dev_info, 64), 248)
                dev_name = name_raw.split('\x00')[0]

                addr_val = ctypes.c_ulonglong.from_buffer_copy(bytes(dev_info[8:16])).value
                addr_hex = f"{addr_val:012X}"

                match_name = target_name and (target_name.lower() in dev_name.lower() or dev_name.lower() in target_name.lower())
                match_mac = clean_mac and (clean_mac in addr_hex)

                if match_name or match_mac:
                    matched_buf = (ctypes.c_ubyte * dev_info_size)()
                    ctypes.memmove(matched_buf, dev_info, dev_info_size)
                    matched_name = dev_name
                    break

                if not bthprops.BluetoothFindNextDevice(h_find, ctypes.byref(dev_info)):
                    break
        finally:
            bthprops.BluetoothFindDeviceClose(h_find)

        return matched_buf, matched_name

    def _win32_toggle_service(self, dev_info_buf, guid_str: str, toggle_on: bool, max_retries: int = 8) -> str:
        """Kích hoạt hoặc tắt một service Bluetooth trên Windows bằng Win32 API."""
        if not HAS_WIN32_BT:
            return "fail"

        guid_buf = (ctypes.c_ubyte * 16)()
        res = CLSIDFromString(guid_str, ctypes.byref(guid_buf))
        if res != 0:
            return f"fail:guid_error_{res}"

        desired = 1 if toggle_on else 0
        current_toggle = desired
        last_hr = 0

        for _ in range(max_retries):
            hr = bthprops.BluetoothSetServiceState(
                None,
                ctypes.byref(dev_info_buf),
                ctypes.byref(guid_buf),
                current_toggle
            )
            last_hr = hr

            if hr == 0:
                if current_toggle == desired:
                    return "ok"
                current_toggle = 1 if current_toggle == 0 else 0
            elif hr in (87, 0x80070057):
                if current_toggle == desired and desired == 0:
                    return "ok"
                current_toggle = 1 if current_toggle == 0 else 0
            elif hr == 1060:
                return "absent"
            elif hr == 1168 and desired == 0 and guid_str.lower() == self.GUID_HFP.lower():
                return "absent"

            time.sleep(0.3)

        return f"fail:0x{last_hr:08X}"
