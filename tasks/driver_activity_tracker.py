# driver_activity_tracker.py

import time
import threading

class DriverTracker:
    def __init__(self):
        self.driver = None
        self.last_used = time.time()
        self.lock = threading.Lock()

    def set_driver(self, driver_instance):
        with self.lock:
            self.driver = driver_instance
            self.last_used = time.time()

    def update_usage(self):
        with self.lock:
            self.last_used = time.time()

    def get_driver(self):
        with self.lock:
            self.last_used = time.time()
            return self.driver

    def is_idle(self, idle_threshold=10):
        with self.lock:
            return (time.time() - self.last_used) > idle_threshold

    def quit_driver(self):
        with self.lock:
            if self.driver:
                try:
                    self.driver.quit()
                    print("🚪 유휴 드라이버 종료 완료")
                except Exception as e:
                    print(f"⚠️ 드라이버 종료 실패: {e}")
                finally:
                    self.driver = None