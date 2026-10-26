import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from database.db import get_connection

# ==============================================================================
# HẰNG SỐ QUY TẮC CỐ ĐỊNH & KIẾN THỨC NỘI BỘ (HARDCODED)
# ==============================================================================
HARDCODED_MOTION_RULES = """
[QUY TẮC GIAO TIẾP & VẬN ĐỘNG CỐ ĐỊNH]
1. Giao tiếp: Phản hồi bằng giọng nói cực kỳ ngắn gọn, tự nhiên (tối đa 2-3 câu). Luôn xưng hô thân thiện, hỏi tên người dùng trong lần đầu tương tác nếu chưa biết.
2. Vận động (tuyệt đối tuân thủ): Chỉ gọi tool di chuyển/biểu diễn khi người dùng ra lệnh trực tiếp (tiến, lùi, quay trái, quay phải, vẫy tay chào). Tuyệt đối không tự ý gọi tool vận động nếu không có yêu cầu rõ ràng.
"""

HARDCODED_GDU_KNOWLEDGE = """
[KIẾN THỨC NỘI BỘ VỀ TRƯỜNG ĐẠI HỌC GIA ĐỊNH - GDU]
[NGUYÊN TẮC QUAN TRỌNG VỀ DỮ LIỆU GDU]
- Chỉ đề cập tới thông tin trường Gia Định khi người dùng hỏi hoặc yêu cầu. Tuyệt đối không tự ý nhắc tới kiến thức nội bộ nếu không có ngữ cảnh.
- Tuyệt đối chỉ dùng thông tin được cung cấp bên dưới để tư vấn về GDU. Nếu người dùng hỏi ngoài phạm vi dữ liệu, hãy khéo léo hẹn họ liên hệ phòng tuyển sinh.

--- 1. THÔNG TIN CHUNG ---
- Tên trường: Trường Đại học Gia Định (Gia Dinh University - GDU).
- Lịch sử: Là ĐH tư thục tại TP.HCM, thành lập năm 2007 (tiền thân là ĐH Tư thục Công nghệ - Thông tin Gia Định). Năm 2026 kỷ niệm 19 năm phát triển.
- Triết lý giáo dục: "Chọn lọc (kiến thức trọng tâm) – Ứng dụng (chú trọng thực hành) – Đại chúng (cơ hội học tập với mức phí phù hợp)".
- Địa điểm: Cơ sở Tân Sơn Nhất (371 Nguyễn Kiệm, Phường Hạnh Thông, Q. Gò Vấp, TP.HCM) - vị trí trung tâm, gần sân bay.
- Chất lượng: Đạt chuẩn kiểm định quốc gia ở cả cấp cơ sở và cấp chương trình đào tạo.

--- 2. CHƯƠNG TRÌNH ĐÀO TẠO ---
- Quy mô: Đa ngành với 6 Khoa chính:
  + Khoa Công nghệ thông tin (CNTT, IoT, AI, Kỹ thuật phần mềm...)
  + Khoa Quản trị - Marketing
  + Khoa Tài chính - Thương mại
  + Khoa Khoa học Xã hội & Ngôn ngữ Quốc tế
  + Khoa Truyền thông số
  + Khoa Khoa học Sức khỏe
- Lợi thế cạnh tranh: Thời gian đào tạo tinh gọn từ 3 năm. Lộ trình: "Học -> làm dự án -> thực tập -> đi làm". Sinh viên có 2 học kỳ thực tế tại doanh nghiệp.

--- 3. HỌC PHÍ ---
- Mức phí tham khảo: Từ khoảng 1,1 triệu VNĐ/tín chỉ (linh hoạt theo ngành và khóa).
"""


def _hash_sha256(text: str) -> str:
    """Mã hóa chuỗi dạng SHA-256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ==============================================================================
# 1. ADMIN REPOSITORY
# ==============================================================================
class AdminRepository:
    """Quản lý tài khoản đăng nhập Admin và mã PIN bảo mật."""

    @staticmethod
    def get_admin() -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM admin_accounts LIMIT 1").fetchone()
            return dict(row) if row else None

    @staticmethod
    def is_registered() -> bool:
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM admin_accounts").fetchone()[0]
            return count > 0

    @staticmethod
    def create_or_update_admin(username: str, password_hash: str, pin_hash: str) -> bool:
        with get_connection() as conn:
            admin = conn.execute("SELECT id FROM admin_accounts LIMIT 1").fetchone()
            if admin:
                conn.execute("""
                    UPDATE admin_accounts 
                    SET username = ?, password_hash = ?, pin_hash = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (username, password_hash, pin_hash, admin["id"]))
            else:
                conn.execute("""
                    INSERT INTO admin_accounts (username, password_hash, pin_hash)
                    VALUES (?, ?, ?)
                """, (username, password_hash, pin_hash))
            conn.commit()
            return True

    @staticmethod
    def verify_password(password: str) -> bool:
        admin = AdminRepository.get_admin()
        if not admin:
            return False
        return admin["password_hash"] == _hash_sha256(password)

    @staticmethod
    def verify_pin(pin: str) -> bool:
        admin = AdminRepository.get_admin()
        if not admin:
            return False
        hashed = _hash_sha256(pin)
        return admin["pin_hash"] == hashed or admin["password_hash"] == hashed


# ==============================================================================
# 2. PERSONA REPOSITORY (DYNAMIC PROMPT ASSEMBLY)
# ==============================================================================
class PersonaRepository:
    """Quản lý các vai trò Persona và tự động ghép nối System Instruction cho Gemini."""

    @staticmethod
    def get_active_persona() -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM personas WHERE is_active = 1 LIMIT 1").fetchone()
            if row:
                return dict(row)
            # Mặc định nếu chưa có role nào active
            row = conn.execute("SELECT * FROM personas LIMIT 1").fetchone()
            return dict(row) if row else {
                "id": "default",
                "name": "Trợ lý BD-1",
                "role_description": "Trợ lý robot thông minh",
                "tone_style": "Thân thiện, súc tích",
                "include_gdu_knowledge": 0,
            }

    @staticmethod
    def get_system_instruction() -> str:
        """Tự động lắp ráp prompt hoàn chỉnh để gửi tới Gemini Live API."""
        persona = PersonaRepository.get_active_persona()

        instruction = (
            f"Bạn là alexa, một trợ lý robot thông minh.\n"
            f"- Vai trò hiện tại của bạn: {persona['name']}.\n"
            f"- Trách nhiệm chính: {persona['role_description']}.\n"
            f"- Phong cách trò chuyện: {persona['tone_style']}.\n\n"
        )

        # 1. Ghép các quy tắc vận động & giao tiếp cốt lõi
        instruction += HARDCODED_MOTION_RULES

        # 2. Ghép kiến thức Đại học Gia Định nếu vai trò này kích hoạt cờ GDU
        if persona.get("include_gdu_knowledge"):
            instruction += "\n" + HARDCODED_GDU_KNOWLEDGE

        return instruction

    @staticmethod
    def get_all_personas() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM personas ORDER BY is_preset DESC, id ASC").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def set_active_persona(persona_id: str) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE personas SET is_active = 0")
            cursor = conn.execute("UPDATE personas SET is_active = 1 WHERE id = ?", (persona_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def save_persona(
        persona_id: str,
        name: str,
        role_description: str,
        tone_style: str,
        include_gdu_knowledge: int = 0,
        is_preset: int = 0,
        is_active: int = 0
    ) -> bool:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO personas 
                (id, name, role_description, tone_style, include_gdu_knowledge, is_active, is_preset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    role_description = excluded.role_description,
                    tone_style = excluded.tone_style,
                    include_gdu_knowledge = excluded.include_gdu_knowledge
            """, (persona_id, name, role_description, tone_style, include_gdu_knowledge, is_active, is_preset))
            conn.commit()
            return True

    @staticmethod
    def delete_persona(persona_id: str) -> bool:
        with get_connection() as conn:
            # Không cho phép xóa các vai trò mẫu hệ thống (preset)
            cursor = conn.execute("DELETE FROM personas WHERE id = ? AND is_preset = 0", (persona_id,))
            conn.commit()
            return cursor.rowcount > 0


# ==============================================================================
# 3. FACE THEME REPOSITORY (COLOR PALETTE & PYGAME RGB)
# ==============================================================================
class FaceThemeRepository:
    """Quản lý các chủ đề màu sắc cho khuôn mặt robot và chuyển đổi RGB cho Pygame."""

    @staticmethod
    def hex_to_rgb(hex_color: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
        """Chuyển đổi chuỗi Hex '#RRGGBB' thành Tuple Pygame RGB (R, G, B)."""
        hex_color = hex_color.strip().lstrip("#")
        if len(hex_color) == 6:
            try:
                return (
                    int(hex_color[0:2], 16),
                    int(hex_color[2:4], 16),
                    int(hex_color[4:6], 16),
                )
            except ValueError:
                return default
        return default

    @staticmethod
    def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
        """Chuyển đổi RGB sang chuỗi HEX #RRGGBB."""
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    @classmethod
    def get_active_theme(cls) -> Dict[str, Any]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM face_themes WHERE is_active = 1 LIMIT 1").fetchone()
            if not row:
                row = conn.execute("SELECT * FROM face_themes LIMIT 1").fetchone()

            data = dict(row) if row else {
                "theme_id": "default",
                "name": "Mặc định",
                "ink_color": "#181A20",
                "bg_color": "#CDD6E0",
                "teeth_color": "#FFFFFF",
                "is_active": 1,
            }

            # Thêm trường RGB tiện dụng cho Pygame
            data["ink_rgb"] = cls.hex_to_rgb(data["ink_color"], (24, 26, 32))
            data["bg_rgb"] = cls.hex_to_rgb(data["bg_color"], (205, 214, 224))
            data["teeth_rgb"] = cls.hex_to_rgb(data["teeth_color"], (255, 255, 255))
            return data

    @classmethod
    def get_all_themes(cls) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM face_themes ORDER BY is_active DESC, theme_id ASC").fetchall()
            themes = []
            for r in rows:
                item = dict(r)
                item["ink_rgb"] = cls.hex_to_rgb(item["ink_color"])
                item["bg_rgb"] = cls.hex_to_rgb(item["bg_color"])
                item["teeth_rgb"] = cls.hex_to_rgb(item["teeth_color"])
                themes.append(item)
            return themes

    @staticmethod
    def set_active_theme(theme_id: str) -> bool:
        with get_connection() as conn:
            conn.execute("UPDATE face_themes SET is_active = 0")
            cursor = conn.execute("UPDATE face_themes SET is_active = 1 WHERE theme_id = ?", (theme_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def save_theme(
        theme_id: str,
        name: str,
        ink_color: str,
        bg_color: str,
        teeth_color: str,
        is_active: int = 0
    ) -> bool:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO face_themes (theme_id, name, ink_color, bg_color, teeth_color, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(theme_id) DO UPDATE SET
                    name = excluded.name,
                    ink_color = excluded.ink_color,
                    bg_color = excluded.bg_color,
                    teeth_color = excluded.teeth_color
            """, (theme_id, name, ink_color, bg_color, teeth_color, is_active))
            conn.commit()
            return True

    @staticmethod
    def delete_theme(theme_id: str) -> bool:
        if theme_id == "default":
            return False  # Chặn xóa theme gốc mặc định
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM face_themes WHERE theme_id = ?", (theme_id,))
            conn.commit()
            return cursor.rowcount > 0


# ==============================================================================
# 4. SYSTEM SETTINGS REPOSITORY
# ==============================================================================
class SettingsRepository:
    """Quản lý tham số cấu hình động dưới dạng Key-Value."""

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        with get_connection() as conn:
            row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        val = SettingsRepository.get(key)
        try:
            return int(val) if val is not None else default
        except ValueError:
            return default

    @staticmethod
    def get_float(key: str, default: float = 0.0) -> float:
        val = SettingsRepository.get(key)
        try:
            return float(val) if val is not None else default
        except ValueError:
            return default

    @staticmethod
    def set(key: str, value: Any, category: str = "general", description: str = "") -> bool:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO system_settings (key, value, category, description, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, str(value), category, description))
            conn.commit()
            return True

    @staticmethod
    def get_by_category(category: str) -> Dict[str, str]:
        with get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM system_settings WHERE category = ?", (category,)).fetchall()
            return {r["key"]: r["value"] for r in rows}


# ==============================================================================
# 5. SYSTEM LOG REPOSITORY
# ==============================================================================
class SystemLogRepository:
    """Ghi nhận và trích xuất nhật ký hoạt động / chẩn đoán hệ thống."""

    @staticmethod
    def log(level: str, component: str, message: str) -> bool:
        try:
            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO system_logs (level, component, message)
                    VALUES (?, ?, ?)
                """, (level.upper(), component.upper(), message))
                conn.commit()
                return True
        except Exception:
            return False

    @staticmethod
    def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT id, level, component, message, 
                       strftime('%H:%M:%S', created_at, 'localtime') as time_str,
                       created_at
                FROM system_logs 
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            # Đảo ngược lại thứ tự thời gian tăng dần để dễ hiển thị giao diện console
            return [dict(r) for r in reversed(rows)]

    @staticmethod
    def export_logs_to_file(filepath: str) -> bool:
        """Xuất toàn bộ nhật ký sự kiện ra file text để chẩn đoán sự cố."""
        try:
            with get_connection() as conn:
                rows = conn.execute("""
                    SELECT strftime('%Y-%m-%d %H:%M:%S', created_at, 'localtime') as ts,
                           level, component, message
                    FROM system_logs ORDER BY id ASC
                """).fetchall()

            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("=== BD-1 ROBOT SYSTEM EVENT LOGS ===\n")
                f.write(f"Exported at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for r in rows:
                    f.write(f"[{r['ts']}] [{r['level']:4}] [{r['component']:8}] {r['message']}\n")
            return True
        except Exception as e:
            print(f"[EXPORT ERROR] Không thể xuất file log: {e}")
            return False


# ==============================================================================
# 6. BLUETOOTH DEVICE REPOSITORY
# ==============================================================================
class BluetoothDeviceRepository:
    """Lưu trữ và phục hồi bộ nhớ đệm thiết bị Bluetooth."""

    @staticmethod
    def save_devices(devices: List[Dict[str, Any]]) -> bool:
        with get_connection() as conn:
            for d in devices:
                dev_id = d.get("id") or d.get("mac")
                if not dev_id:
                    continue
                name = d.get("name") or "Unknown"
                mac = d.get("mac") or ""
                dev_type = d.get("type") or "Audio Device"
                is_paired = 1 if d.get("connected") or d.get("status") in ("Connected", "Paired") else 0

                conn.execute("""
                    INSERT INTO bluetooth_devices (device_id, mac_address, name, device_type, is_paired, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(device_id) DO UPDATE SET
                        name = excluded.name,
                        device_type = excluded.device_type,
                        is_paired = excluded.is_paired,
                        last_seen_at = CURRENT_TIMESTAMP
                """, (dev_id, mac, name, dev_type, is_paired))
            conn.commit()
            return True

    @staticmethod
    def get_cached_devices() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT device_id as id, mac_address as mac, name, device_type as type,
                       CASE WHEN is_paired = 1 THEN 'Paired' ELSE 'Ready' END as status,
                       0 as connected,
                       80 as signal
                FROM bluetooth_devices
                ORDER BY is_paired DESC, last_seen_at DESC
            """).fetchall()
            return [dict(r) for r in rows]
