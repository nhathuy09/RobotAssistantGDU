import os
import sys
import json
import sqlite3
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "BD1.db")
SETTINGS_JSON_PATH = os.path.join(os.path.dirname(DB_DIR), "robot_settings.json")
BLUETOOTH_JSON_PATH = os.path.join(os.path.dirname(DB_DIR), "bluetooth_cache.json")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def _init_db():
    """Khởi tạo toàn bộ cấu trúc bảng, chỉ mục và nạp dữ liệu mẫu."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Bảng tài khoản Admin
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Bảng vai trò và phong cách Persona 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role_description TEXT NOT NULL,
                tone_style TEXT NOT NULL,
                include_gdu_knowledge INTEGER NOT NULL DEFAULT 0 CHECK (include_gdu_knowledge IN (0, 1)),
                is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
                is_preset INTEGER NOT NULL DEFAULT 0 CHECK (is_preset IN (0, 1))
            );
        """)

        # 3. Bảng tùy biến chủ đề màu sắc khuôn mặt
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS face_themes (
                theme_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ink_color TEXT NOT NULL,
                bg_color TEXT NOT NULL,
                teeth_color TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1))
            );
        """)

        # 4. Bảng cấu hình hệ thống (Key-Value)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Bảng nhật ký hệ thống
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                component TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Bảng cache thiết bị Bluetooth
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bluetooth_devices (
                device_id TEXT PRIMARY KEY,
                mac_address TEXT,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                is_paired INTEGER DEFAULT 0,
                last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Tạo chỉ mục (Indexes)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON system_logs(created_at DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_settings_category ON system_settings(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_personas_active ON personas(is_active);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_themes_active ON face_themes(is_active);")

        conn.commit()

        # Seed dữ liệu mặc định & migrate từ JSON
        _seed_default_data(cursor)
        _migrate_from_json(cursor)

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DATABASE ERROR] Lỗi khởi tạo database: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def _seed_default_data(cursor: sqlite3.Cursor):
    """Nạp dữ liệu mẫu ban đầu nếu các bảng còn trống."""
    # 1. Preset Personas
    cursor.execute("SELECT COUNT(*) FROM personas")
    if cursor.fetchone()[0] == 0:
        personas_seed = [
            (
                "guide_gdu",
                "Hướng dẫn viên GDU",
                "Đón tiếp sinh viên, phụ huynh và khách tham quan trường Đại học Gia Định",
                "Thân thiện, ấm áp, truyền cảm hứng, phản hồi ngắn gọn 2-3 câu",
                1,  # Bật tri thức GDU
                1,  # Kích hoạt mặc định
                1,  # Is preset
            ),
            (
                "aiot",
                "Đại sứ AIoT OhStem",
                "Giới thiệu các giải pháp công nghệ giáo dục STEM và trí tuệ nhân tạo AIoT",
                "Tự tin, truyền cảm hứng, dễ hiểu, dùng ví dụ gần gũi trong đời sống",
                0,
                0,
                1,
            ),
            (
                "tech",
                "Chuyên gia Kỹ thuật",
                "Chẩn đoán sự cố phần cứng, sơ đồ mạch và hướng dẫn lập trình chuẩn xác",
                "Chính xác, khách quan, ưu tiên tuyệt đối an toàn phần cứng",
                0,
                0,
                1,
            ),
            (
                "receptionist",
                "Lễ tân Robot BD-1",
                "Trợ lý thông minh điều phối, chào đón khách và giải đáp thông tin chung",
                "Lịch thiệp, chu đáo, súc tích, tập trung đúng trọng tâm",
                0,
                0,
                1,
            ),
            (
                "custom",
                "Vai trò Tùy chỉnh",
                "Trợ lý Robot thông minh hỗ trợ người dùng theo yêu cầu",
                "Nhiệt tình, chu đáo, phản hồi tự nhiên và chính xác",
                0,
                0,
                0,
            ),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO personas 
            (id, name, role_description, tone_style, include_gdu_knowledge, is_active, is_preset)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, personas_seed)

    # 2. Preset Face Themes
    cursor.execute("SELECT COUNT(*) FROM face_themes")
    if cursor.fetchone()[0] == 0:
        themes_seed = [
            ("default", "Anime Xanh Khói (Mặc định)", "#181A20", "#CDD6E0", "#FFFFFF", 1),
            ("dark_oled", "Đêm Tối OLED", "#00E5FF", "#0F1115", "#FFFFFF", 0),
            ("forest_green", "Rừng Thông BD-1", "#1C2E24", "#E2E8E4", "#FFFFFF", 0),
            ("cyberpunk", "Cyberpunk Vàng Neon", "#121212", "#FFE600", "#FFFFFF", 0),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO face_themes 
            (theme_id, name, ink_color, bg_color, teeth_color, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, themes_seed)

    # 3. System Settings mặc định
    cursor.execute("SELECT COUNT(*) FROM system_settings")
    if cursor.fetchone()[0] == 0:
        settings_seed = [
            ("audio.target_rms", "1500", "audio", "Mức RMS mục tiêu cho thuật toán SoftAGC của Micro"),
            ("audio.speaker_volume", "80", "audio", "Âm lượng loa phát (0-100)"),
            ("ai.model_name", "gemini-3.1-flash-live-preview", "ai", "Tên model Gemini Live API"),
            ("hardware.serial_port", "/dev/ttyACM0", "hardware", "Cổng Serial kết nối Orc Hub / ESP32"),
            ("hardware.baudrate", "115200", "hardware", "Tốc độ baudrate giao tiếp Serial"),
            ("display.idle_sleep_timeout", "5.0", "display", "Thời gian IDLE trước khi robot nhắm mắt ngủ (giây)"),
        ]
        cursor.executemany("""
            INSERT OR IGNORE INTO system_settings (key, value, category, description)
            VALUES (?, ?, ?, ?)
        """, settings_seed)

    # 4. Ghi log khởi tạo ban đầu
    cursor.execute("SELECT COUNT(*) FROM system_logs")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO system_logs (level, component, message)
            VALUES ('OK', 'DATABASE', 'Khởi tạo cơ sở dữ liệu SQLite BD1.db thành công.')
        """)


def _migrate_from_json(cursor: sqlite3.Cursor):
    """Tự động nhập dữ liệu cũ từ robot_settings.json và bluetooth_cache.json nếu có."""
    # 1. Di trú Admin Accounts
    if os.path.exists(SETTINGS_JSON_PATH):
        try:
            with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            admin_data = data.get("admin", {})
            username = admin_data.get("username")
            pass_hash = admin_data.get("password_hash")
            pin_hash = admin_data.get("pin_hash")

            if username and pass_hash and pin_hash:
                cursor.execute("SELECT COUNT(*) FROM admin_accounts")
                if cursor.fetchone()[0] == 0:
                    cursor.execute("""
                        INSERT INTO admin_accounts (username, password_hash, pin_hash)
                        VALUES (?, ?, ?)
                    """, (username, pass_hash, pin_hash))
                    print(f"[DATABASE MIGRATION] Đã chuyển đổi tài khoản admin '{username}' từ robot_settings.json.")

            # Kiểm tra vai trò đang active
            persona_data = data.get("persona", {})
            sel_role = persona_data.get("selected_role")
            custom_name = persona_data.get("custom_role_name")

            if custom_name:
                cursor.execute("""
                    UPDATE personas SET name = ? WHERE id = 'custom'
                """, (custom_name,))

            if sel_role:
                cursor.execute("UPDATE personas SET is_active = 0")
                cursor.execute("""
                    UPDATE personas SET is_active = 1 WHERE id = ?
                """, (sel_role,))
        except Exception as e:
            print(f"[DATABASE MIGRATION] Lỗi đọc robot_settings.json: {e}")

    # 2. Di trú Bluetooth Cache
    if os.path.exists(BLUETOOTH_JSON_PATH):
        try:
            cursor.execute("SELECT COUNT(*) FROM bluetooth_devices")
            if cursor.fetchone()[0] == 0:
                with open(BLUETOOTH_JSON_PATH, "r", encoding="utf-8") as f:
                    devices = json.load(f)

                if isinstance(devices, list):
                    for d in devices:
                        dev_id = d.get("id") or d.get("mac")
                        if not dev_id:
                            continue
                        name = d.get("name") or "Unknown Device"
                        mac = d.get("mac") or ""
                        dev_type = d.get("type") or "Audio Device"
                        is_paired = 1 if d.get("status") in ("Connected", "Paired") else 0

                        cursor.execute("""
                            INSERT OR REPLACE INTO bluetooth_devices 
                            (device_id, mac_address, name, device_type, is_paired)
                            VALUES (?, ?, ?, ?, ?)
                        """, (dev_id, mac, name, dev_type, is_paired))
                    print(f"[DATABASE MIGRATION] Đã chuyển đổi {len(devices)} thiết bị bluetooth vào DB.")
        except Exception as e:
            print(f"[DATABASE MIGRATION] Lỗi đọc bluetooth_cache.json: {e}")


# Tự động khởi tạo bảng khi module được import
_init_db()
