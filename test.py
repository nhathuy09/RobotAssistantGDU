import sys
from display.app_manager import AppManager


def main():
    """Điểm khởi chạy ứng dụng BD-1 Dashboard với kiến trúc module chuẩn."""
    app = AppManager(width=800, height=480)
    app.run()


if __name__ == "__main__":
    main()