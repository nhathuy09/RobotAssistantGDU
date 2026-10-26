import ctypes
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from xml.sax.saxutils import escape

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class WifiError(Exception):
    """Lỗi có thông điệp tiếng Việt, hiện thẳng lên UI."""


# =====================================================================
# Bộ phân tích
# =====================================================================
def _split_nmcli(line):
    parts, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def parse_nmcli_list(text, saved):
    best = {}
    for line in text.splitlines():
        p = _split_nmcli(line)
        if len(p) < 4 or not p[1]:
            continue
        ssid = p[1]
        sig = int(p[2]) if p[2].isdigit() else 0
        old = best.get(ssid)
        in_use = p[0] == "*" or bool(old and old["in_use"])
        best[ssid] = {
            "ssid": ssid,
            "signal": max(sig, old["signal"]) if old else sig,
            "secure": p[3] not in ("", "--"),
            "auth": p[3], "enc": "",
            "in_use": in_use, "saved": ssid in saved,
        }
    return list(best.values())


def parse_netsh_networks(text):
    nets, cur, seen_bssid = {}, None, False
    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        m = re.match(r"^SSID\s+\d+\s*:\s*(.*)$", line)
        if m:
            ssid = m.group(1).strip()
            if not ssid:
                cur = None
                continue
            cur = nets.setdefault(ssid, {"ssid": ssid, "signal": 0, "auth": "", "enc": "",
                                         "in_use": False, "saved": False})
            cur["_idx"] = 0
            seen_bssid = False
            continue
        if cur is None:
            continue
        if re.match(r"^BSSID\s+\d+", line):
            seen_bssid = True
            continue
        if ":" not in line:
            continue
        _, val = line.split(":", 1)
        val = val.strip()
        if not seen_bssid:
            cur["_idx"] += 1
            if cur["_idx"] == 2:
                cur["auth"] = val
            elif cur["_idx"] == 3:
                cur["enc"] = val
        else:
            m = re.match(r"^(\d+)\s*%$", val)
            if m:
                cur["signal"] = max(cur["signal"], int(m.group(1)))
    out = []
    for n in nets.values():
        n.pop("_idx", None)
        a, e = n["auth"].strip().lower(), n["enc"].strip().lower()
        n["secure"] = not (a in ("open", "mở") or e in ("none", "không", ""))
        out.append(n)
    return out


def parse_netsh_interfaces(text):
    ssid, signal = "", 0
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^SSID\s*:\s*(.*)$", line)
        if m:
            ssid = m.group(1).strip()
            continue
        m = re.match(r"^[^:]+:\s*(\d+)\s*%$", line)
        if m:
            signal = int(m.group(1))
    return ssid, signal


def parse_netsh_profiles(text):
    names = set()
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t"):
            m = re.match(r"^\s+[^:]+:\s*(.+)$", raw)
            if m:
                names.add(m.group(1).strip())
    return names


def build_profile_xml(ssid, password, net):
    auth_raw = ((net or {}).get("auth") or "").upper()
    enc_raw = ((net or {}).get("enc") or "").upper()
    key_block = ""
    if not password:
        auth, enc = "open", "none"
    elif "ENTERPRISE" in auth_raw:
        raise WifiError("Mạng doanh nghiệp (802.1X) chưa được hỗ trợ")
    else:
        if "WPA3" in auth_raw or "SAE" in auth_raw:
            auth, enc = "WPA3SAE", "AES"
        elif "WPA2" in auth_raw or not auth_raw:
            auth, enc = "WPA2PSK", "AES"
        else:
            auth, enc = "WPAPSK", ("TKIP" if "TKIP" in enc_raw else "AES")
        key_block = ("<sharedKey><keyType>passPhrase</keyType><protected>false</protected>"
                     f"<keyMaterial>{escape(password)}</keyMaterial></sharedKey>")
    name = escape(ssid)
    is_hidden = (net or {}).get("hidden", False)
    hidden_xml = "<nonBroadcast>true</nonBroadcast>" if is_hidden else "<nonBroadcast>false</nonBroadcast>"
    
    return (
        '<?xml version="1.0"?>'
        '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">'
        f"<name>{name}</name>"
        f"<SSIDConfig><SSID><name>{name}</name></SSID>{hidden_xml}</SSIDConfig>"
        "<connectionType>ESS</connectionType><connectionMode>auto</connectionMode>"
        "<MSM><security><authEncryption>"
        f"<authentication>{auth}</authentication><encryption>{enc}</encryption>"
        "<useOneX>false</useOneX></authEncryption>"
        f"{key_block}</security></MSM></WLANProfile>"
    )


# =====================================================================
# Backends
# =====================================================================
class _NmcliBackend:
    name = "nmcli"
    scan_has_in_use = True

    def __init__(self, iface=None):
        self.iface = iface

    def _run(self, args, timeout=10):
        env = dict(os.environ, LC_ALL="C")
        try:
            p = subprocess.run(["nmcli"] + args, capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8", errors="replace", env=env)
            return p.returncode, p.stdout, p.stderr
        except FileNotFoundError:
            raise WifiError("Không tìm thấy lệnh nmcli (cần NetworkManager)")
        except subprocess.TimeoutExpired:
            return 1, "", "timeout"

    def saved(self):
        rc, out, _ = self._run(["-t", "-f", "NAME,TYPE", "connection", "show"], 8)
        names = set()
        for line in out.splitlines():
            p = _split_nmcli(line)
            if len(p) >= 2 and p[1] == "802-11-wireless":
                names.add(p[0])
        return names

    def scan(self, force_rescan=False):
        base = ["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"]
        if self.iface:
            base += ["ifname", self.iface]
        
        rescan_flag = "yes" if force_rescan else "no"
        rc, out, err = self._run(base + ["--rescan", rescan_flag], 20)
        if rc != 0 and force_rescan:
            rc, out, err = self._run(base + ["--rescan", "no"], 10)
            
        if rc != 0:
            first = (err.strip().splitlines() or ["nmcli báo lỗi"])[0]
            raise WifiError(f"Không quét được Wi-Fi: {first}")
        return parse_nmcli_list(out, self.saved())

    def current(self):
        rc, out, _ = self._run(["-t", "-f", "ACTIVE,SSID,SIGNAL", "dev", "wifi", "list",
                                "--rescan", "no"], 6)
        for line in out.splitlines():
            p = _split_nmcli(line)
            if len(p) >= 3 and p[0] == "yes":
                return p[1], int(p[2]) if p[2].isdigit() else 0
        return "", 0

    def connect(self, ssid, password, net):
        saved_before = ssid in self.saved()
        if saved_before and password is None:
            args = ["-w", "25", "connection", "up", "id", ssid]
        else:
            args = ["-w", "25", "dev", "wifi", "connect", ssid]
            if password:
                args += ["password", password]
            if net and net.get("hidden"):
                args += ["hidden", "yes"]
            if self.iface:
                args += ["ifname", self.iface]
        rc, _, err = self._run(args, 30)
        if rc == 0:
            return True, ""
        e = err.lower()
        if "secrets were required" in e or "password" in e:
            msg = "Sai mật khẩu"
        elif "no network with ssid" in e:
            msg = "Không tìm thấy SSID trong vùng phủ sóng"
        elif "timeout" in e or "timed out" in e:
            msg = "Hết thời gian chờ"
        else:
            msg = "Kết nối thất bại"
        if not saved_before:
            self._run(["connection", "delete", "id", ssid], 8)
        return False, msg

    def forget(self, ssid):
        rc, _, _ = self._run(["connection", "delete", "id", ssid], 10)
        return rc == 0


class _WindowsBackend:
    name = "netsh"
    scan_has_in_use = False

    @staticmethod
    def _oem():
        try:
            return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
        except Exception:
            return "utf-8"

    def _run_utf8(self, cmd, timeout=15):
        try:
            p = subprocess.run(f"cmd /c chcp 65001 >nul & {cmd}", capture_output=True,
                               timeout=timeout, creationflags=_NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise WifiError("netsh không phản hồi")
        return p.returncode, p.stdout.decode("utf-8", errors="replace")

    def _run_direct(self, cmd, timeout=20):
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout,
                               creationflags=_NO_WINDOW)
        except subprocess.TimeoutExpired:
            return 1, "timeout"
        return p.returncode, p.stdout.decode(self._oem(), errors="replace")

    @staticmethod
    def _check_text(text):
        low = text.lower()
        if "location" in low and ("permission" in low or "services" in low):
            raise WifiError("Windows cần bật Dịch vụ vị trí để quét Wi-Fi")
        if "wlansvc" in low or "not running" in low:
            raise WifiError("Dịch vụ WLAN AutoConfig chưa chạy")
        if "no wireless interface" in low:
            raise WifiError("Máy không có card Wi-Fi")

    def saved(self):
        _, out = self._run_utf8("netsh wlan show profiles")
        return parse_netsh_profiles(out)

    def scan(self, force_rescan=False):
        rc, out = self._run_utf8("netsh wlan show networks mode=bssid")
        self._check_text(out)
        nets = parse_netsh_networks(out)
        if rc != 0 and not nets:
            raise WifiError("netsh không đọc được danh sách Wi-Fi")
        saved = self.saved()
        for n in nets:
            n["saved"] = n["ssid"] in saved
        return nets

    def current(self):
        _, out = self._run_utf8("netsh wlan show interfaces")
        return parse_netsh_interfaces(out)

    def connect(self, ssid, password, net):
        if '"' in ssid:
            return False, 'Tên mạng chứa dấu " không hỗ trợ'
        saved_before = ssid in self.saved()
        created = False
        if password is not None or not saved_before:
            if password is None and net and net.get("secure"):
                return False, "Cần nhập mật khẩu"
            xml = build_profile_xml(ssid, password, net)
            fd, path = tempfile.mkstemp(suffix=".xml")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(xml)
                rc, out = self._run_direct(f'netsh wlan add profile filename="{path}"')
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            if rc != 0:
                return False, "Không tạo được hồ sơ Wi-Fi"
            created = not saved_before

        rc, out = self._run_direct(f'netsh wlan connect name="{ssid}"')
        if rc == 0:
            # Polling kiểm tra kết nối nhanh hơn (0.5s/lần thay vì 1s)
            for _ in range(20):
                time.sleep(0.5)
                if self.current()[0] == ssid:
                    return True, ""
        if created:
            self.forget(ssid)
        return False, "Sai mật khẩu hoặc SSID ngoài vùng phủ sóng"

    def forget(self, ssid):
        if '"' in ssid:
            return False
        rc, _ = self._run_direct(f'netsh wlan delete profile name="{ssid}"')
        return rc == 0

class WifiManager:
    STATUS_EVERY_S = 5.0
    INTERNET_EVERY_S = 20.0

    def __init__(self, iface=None):
        self._lock = threading.Lock()
        self._status = {"connected": False, "ssid": "", "signal": 0,
                        "ip": "", "internet": False}
        self._networks = []
        self._scanning = False
        self._busy = ""
        self._result = ("", True, 0.0)
        self._error = ""
        self._inet_ssid, self._inet_at, self._inet_val = "", 0.0, False
        self._stop = threading.Event()
        self._wake = threading.Event()

        if sys.platform.startswith("win"):
            self.backend = _WindowsBackend()
        elif shutil.which("nmcli"):
            self.backend = _NmcliBackend(iface)
        else:
            self.backend = None
            self._error = ("Không tìm thấy lệnh nmcli. Cài NetworkManager."
                           if sys.platform.startswith("linux")
                           else "Hệ điều hành này chưa được hỗ trợ.")

        threading.Thread(target=self._status_loop, daemon=True).start()
        self.scan(force=True)

    def snapshot(self):
        with self._lock:
            return {
                "status": dict(self._status),
                "networks": [dict(n) for n in self._networks],
                "scanning": self._scanning,
                "busy": self._busy,
                "result": self._result,
                "error": self._error,
            }

    def scan(self, force=False):
        with self._lock:
            if self._scanning or self.backend is None:
                return
            self._scanning = True
        threading.Thread(target=self._scan_worker, args=(force,), daemon=True).start()

    def connect(self, ssid, password=None):
        ssid = (ssid or "").strip()
        if not ssid:
            self._set_result("Tên SSID không được trống", False)
            return
        if self.backend is None:
            self._set_result(self._error or "Chưa có backend Wi-Fi", False)
            return
        with self._lock:
            if self._busy:
                return
            self._busy = f"Đang kết nối {ssid}"
        threading.Thread(target=self._connect_worker, args=(ssid, password),
                         daemon=True).start()

    def forget(self, ssid):
        if self.backend is not None:
            threading.Thread(target=self._forget_worker, args=(ssid,), daemon=True).start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def _set_result(self, msg, ok):
        with self._lock:
            self._result = (msg, ok, time.time())

    @staticmethod
    def _local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return ""
        finally:
            s.close()

    @staticmethod
    def _internet_ok():
        # Dùng non-blocking timeout ngắn để không giật lag
        for host in ("1.1.1.1", "8.8.8.8"):
            try:
                s = socket.create_connection((host, 53), timeout=0.8)
                s.close()
                return True
            except OSError:
                continue
        return False

    def _refresh_status(self):
        ssid, signal = "", 0
        if self.backend is not None:
            try:
                ssid, signal = self.backend.current()
            except Exception:
                ssid, signal = "", 0
        connected = bool(ssid)
        ip, internet = "", False
        if connected:
            ip = self._local_ip()
            now = time.time()
            if ssid != self._inet_ssid or now - self._inet_at > self.INTERNET_EVERY_S:
                # Chạy check internet async nếu cần để hoàn toàn giải phóng thread
                self._inet_val = self._internet_ok()
                self._inet_ssid, self._inet_at = ssid, now
            internet = self._inet_val
        else:
            self._inet_ssid = ""
        with self._lock:
            self._status = {"connected": connected, "ssid": ssid, "signal": signal,
                            "ip": ip, "internet": internet}

    def _status_loop(self):
        while not self._stop.is_set():
            try:
                self._refresh_status()
            except Exception:
                pass
            self._wake.wait(self.STATUS_EVERY_S)
            self._wake.clear()

    def _scan_worker(self, force=False):
        nets, err = None, ""
        try:
            nets = self.backend.scan(force_rescan=force)
            if not self.backend.scan_has_in_use:
                cur, _ = self.backend.current()
                for n in nets:
                    if cur and n["ssid"] == cur:
                        n["in_use"] = True
            nets.sort(key=lambda n: (not n["in_use"], -n["signal"]))
        except WifiError as e:
            err = str(e)
        except Exception as e:
            err = f"Lỗi quét Wi-Fi: {e}"
        finally:
            with self._lock:
                if nets is not None:
                    self._networks = nets
                self._error = err
                self._scanning = False

    def _connect_worker(self, ssid, password):
        ok, msg = False, ""
        try:
            with self._lock:
                net = next((dict(n) for n in self._networks if n["ssid"] == ssid), None)
            if net is None:
                net = {"ssid": ssid, "secure": bool(password), "saved": False, "hidden": True,
                       "auth": "WPA2PSK" if password else "OPEN",
                       "enc": "AES" if password else "NONE"}
            ok, msg = self.backend.connect(ssid, password, net)
        except WifiError as e:
            ok, msg = False, str(e)
        except Exception as e:
            ok, msg = False, f"Lỗi: {e}"
        finally:
            with self._lock:
                self._busy = ""
            self._set_result(f"Đã kết nối {ssid}" if ok else msg, ok)
            self._refresh_status()
            self.scan(force=False)

    def _forget_worker(self, ssid):
        try:
            ok = self.backend.forget(ssid)
        except Exception:
            ok = False
        self._set_result(f"Đã quên mạng {ssid}" if ok else "Không xoá được mạng", ok)
        self._refresh_status()
        self.scan(force=False)