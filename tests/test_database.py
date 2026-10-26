import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo đường dẫn import đúng thư mục gốc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import DB_PATH, get_connection
from database.repositories import (
    AdminRepository,
    PersonaRepository,
    FaceThemeRepository,
    SettingsRepository,
    SystemLogRepository,
    BluetoothDeviceRepository,
)

def run_tests():
    print(f"[TEST] Đường dẫn DB: {DB_PATH}")
    assert os.path.exists(DB_PATH), "File BD1.db chưa được tạo!"

    # 1. Kiểm tra AdminRepository
    print("\n--- 1. Kiểm tra AdminRepository ---")
    is_reg = AdminRepository.is_registered()
    print(f"Admin is registered: {is_reg}")
    admin = AdminRepository.get_admin()
    if admin:
        print(f"Admin username: {admin['username']}")
        # Test verify_pin
        test_pin_ok = AdminRepository.verify_pin("123456")
        print(f"Verify pin test: {test_pin_ok}")

    # 2. Kiểm tra PersonaRepository
    print("\n--- 2. Kiểm tra PersonaRepository ---")
    all_personas = PersonaRepository.get_all_personas()
    print(f"Tổng số personas: {len(all_personas)}")
    for p in all_personas:
        print(f" - [{p['id']}] {p['name']} (Active: {p['is_active']}, GDU Knowledge: {p['include_gdu_knowledge']})")

    active_p = PersonaRepository.get_active_persona()
    print(f"\nPersona đang kích hoạt: {active_p['name']}")
    instruction = PersonaRepository.get_system_instruction()
    print(f"Chiều dài System Instruction tạo tự động: {len(instruction)} ký tự")
    assert "QUY TẮC GIAO TIẾP & VẬN ĐỘNG CỐ ĐỊNH" in instruction
    if active_p.get("include_gdu_knowledge"):
        assert "KIẾN THỨC NỘI BỘ VỀ TRƯỜNG ĐẠI HỌC GIA ĐỊNH" in instruction
        print("-> Đã nạp thành công kiến thức GDU vì vai trò này yêu cầu.")
    else:
        assert "KIẾN THỨC NỘI BỘ VỀ TRƯỜNG ĐẠI HỌC GIA ĐỊNH" not in instruction
        print("-> Không nạp kiến thức GDU (vai trò phổ thông).")

    # 3. Kiểm tra FaceThemeRepository
    print("\n--- 3. Kiểm tra FaceThemeRepository ---")
    active_theme = FaceThemeRepository.get_active_theme()
    print(f"Active Theme: {active_theme['name']} ({active_theme['theme_id']})")
    print(f"Ink RGB: {active_theme['ink_rgb']}, BG RGB: {active_theme['bg_rgb']}, Teeth RGB: {active_theme['teeth_rgb']}")
    assert isinstance(active_theme['ink_rgb'], tuple) and len(active_theme['ink_rgb']) == 3

    all_themes = FaceThemeRepository.get_all_themes()
    print(f"Tổng số themes trong DB: {len(all_themes)}")
    for t in all_themes:
        print(f" - [{t['theme_id']}] {t['name']}: Ink={t['ink_color']}, BG={t['bg_color']}")

    # 4. Kiểm tra SettingsRepository
    print("\n--- 4. Kiểm tra SettingsRepository ---")
    serial_port = SettingsRepository.get("hardware.serial_port")
    baudrate = SettingsRepository.get_int("hardware.baudrate")
    print(f"hardware.serial_port: {serial_port}")
    print(f"hardware.baudrate: {baudrate}")
    assert baudrate == 115200

    # 5. Kiểm tra SystemLogRepository
    print("\n--- 5. Kiểm tra SystemLogRepository ---")
    SystemLogRepository.log("INFO", "TEST", "Kiểm thử ghi log thành công vào database.")
    logs = SystemLogRepository.get_recent_logs(limit=5)
    print(f"Số lượng logs lấy được: {len(logs)}")
    for l in logs:
        print(f" [{l['time_str']}] [{l['level']}] [{l['component']}] {l['message']}")

    # 6. Kiểm tra BluetoothDeviceRepository
    print("\n--- 6. Kiểm tra BluetoothDeviceRepository ---")
    cached_bt = BluetoothDeviceRepository.get_cached_devices()
    print(f"Số thiết bị bluetooth trong DB: {len(cached_bt)}")
    if cached_bt:
        print(f"Thiết bị mẫu: {cached_bt[0]['name']} (MAC: {cached_bt[0]['mac']}, Type: {cached_bt[0]['type']})")

    print("\n==========================================")
    print("🎉 TẤT CẢ CÁC BÀI KIỂM THỬ DATABASE ĐỀU THÀNH CÔNG!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
