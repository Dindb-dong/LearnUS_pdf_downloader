import os
import time
import threading
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from celery import Celery
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
from driver_activity_tracker import DriverTracker

# ✅ 드라이버 상태 추적 객체
driver_tracker = DriverTracker()

# ✅ .env 파일 로드
load_dotenv()
EC2_IP = os.getenv("EC2_IP")

# ✅ Chrome 실행 상태 확인
def is_chrome_running():
    try:
        response = requests.get("http://127.0.0.1:9223/json", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

# ✅ 드라이버 가져오기
def get_driver(self=None):
    if self:
        self.update_state(state="PROGRESS", meta="🧭 크롬 인스턴스에 접근 중입니다...")

    # ✅ 기존 드라이버 존재 시 재사용
    existing_driver = driver_tracker.get_driver()
    if existing_driver:
        print(f"✅ 기존 Chrome 드라이버와 연결 중...")
        driver_tracker.update_usage()
        return existing_driver

    # ✅ 새 드라이버 생성
    print("🚀 ChromeDriver 시작 중...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-address=0.0.0.0")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--disable-gpu-process")
    chrome_options.debugger_address = f"{EC2_IP}:9223"

    # ✅ Chrome 실행 중 확인
    retries = 5
    for _ in range(retries):
        if is_chrome_running():
            try:
                print(f"✅ 기존 Chrome 인스턴스({EC2_IP})와 연결 중...")
                driver = webdriver.Chrome(options=chrome_options)
                driver_tracker.set_driver(driver)
                return driver
            except Exception as e:
                print(f"⚠️ 연결 실패: {e}")
        time.sleep(2)

    print("🚀 Chrome이 실행되지 않음, 새로운 ChromeDriver 실행")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver_tracker.set_driver(driver)
    return driver

# ✅ Chrome 실행 대기
def wait_for_chrome(timeout=10, interval=2):
    start = time.time()
    while time.time() - start < timeout:
        if is_chrome_running():
            print("🚀 Chrome 실행 확인됨!")
            return True
        print("⏳ Chrome 실행 대기 중...")
        time.sleep(interval)
    print("❌ Chrome이 실행되지 않음. 종료.")
    return False

# ✅ Celery 설정
celery = Celery("tasks", broker="redis://127.0.0.1:6379/0", backend="redis://127.0.0.1:6379/0")
celery.conf.update(
    task_track_started=True,  # 작업 시작 상태를 추적
    result_extended=True,  # 추가적인 결과 정보 저장
    task_ignore_result=False,  # 작업 결과 무시 방지
)

# ✅ 디렉토리 생성
SAVE_DIR = "static"
IMG_DIR = os.path.join(SAVE_DIR, "downloaded_pages")
UPSCALE_DIR = os.path.join(SAVE_DIR, "upscaled_pages")
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(UPSCALE_DIR, exist_ok=True)

# ✅ PDF 이미지 다운로드
def download_pdf_images(self, pdf_url):
    try:
        if not wait_for_chrome(timeout=10, interval=2):
            return []

        driver = get_driver(self)
        driver_tracker.update_usage()

        driver.get(pdf_url)
        print(f"📄 페이지 로드 중: {pdf_url}")

        try:
            iframe = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            driver.switch_to.frame(iframe)
            print("🔄 iframe 내부로 이동 완료")
        except:
            print("⚠️ iframe이 감지되지 않음 (무시하고 진행)")

        try:
            scroll_container = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "contents")))
            print("✅ PDF 뷰어 요소 찾음!")
        except:
            print("❌ PDF 뷰어 요소를 찾을 수 없음!")
            return []

        scroll_attempts = 0
        prev_image_count = 0

        for _ in range(30):
            images = driver.find_elements(By.TAG_NAME, "img")
            count = len(images)
            driver.execute_script("arguments[0].scrollBy(0, 2000);", scroll_container)
            time.sleep(3)
            print(f"🔄 스크롤 중... (현재 이미지 개수: {count})")

            if count == prev_image_count:
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    break
            else:
                scroll_attempts = 0
            prev_image_count = count

        print("✅ 모든 페이지 스크롤 완료!")
        image_data = [(img.get_attribute("id"), img.get_attribute("src")) for img in driver.find_elements(By.TAG_NAME, "img")]
        if not image_data:
            print("❌ 이미지 요소를 찾을 수 없음")
            return []

        base_url, page_count = None, 0
        for img_id, src in image_data:
            if img_id and img_id.startswith("page"):
                if img_id == "page0":
                    base_url = src.rsplit("/", 1)[0]
                page_count += 1

        if not base_url or page_count == 0:
            return []

        print(f"🌟 감지된 페이지 개수: {page_count}")
        downloaded_images = []
        for i in range(page_count):
            img_url = f"{base_url}/{i+1}.png"
            img_path = os.path.join(IMG_DIR, f"{i+1}.png")
            try:
                res = requests.get(img_url, stream=True, timeout=10)
                if res.status_code == 200:
                    with open(img_path, 'wb') as f:
                        f.write(res.content)
                    print(f"✅ 다운로드 완료: {img_path}")
                    downloaded_images.append(img_path)
                else:
                    print(f"⚠️ 다운로드 실패: {img_url}")
            except requests.exceptions.RequestException as e:
                print(f"❌ 요청 오류: {e}")
        return downloaded_images
    except Exception as e:
        print(f"❌ 다운로드 오류: {str(e)}")
        return []

# ✅ 이미지 업스케일
def upscale_images(image_files, scale_factor=4):
    upscaled = []
    for img_path in image_files:
        img_name = os.path.basename(img_path)
        upscaled_path = os.path.join(UPSCALE_DIR, img_name)
        try:
            img = Image.open(img_path)
            new_size = (img.width * scale_factor, img.height * scale_factor)
            img.resize(new_size, Image.LANCZOS).save(upscaled_path)
            upscaled.append(upscaled_path)
            print(f"✅ 업스케일 완료: {upscaled_path}")
        except Exception as e:
            print(f"❌ 업스케일 실패: {img_path}, 오류: {e}")
    return upscaled

# ✅ PDF로 변환
def convert_images_to_pdf(image_files, file_name):
    output_pdf = os.path.join(SAVE_DIR, f"{file_name}.pdf")
    try:
        images = [Image.open(img).convert("RGB") for img in image_files]
        if images:
            images[0].save(output_pdf, save_all=True, append_images=images[1:])
            print(f"📄 PDF 변환 완료: {output_pdf}")
            return output_pdf
        print("❌ 변환할 이미지 없음")
        return None
    except Exception as e:
        print(f"❌ PDF 변환 실패: {e}")
        return None

# ✅ 메인 태스크
@celery.task(bind=True)
def process_pdf(self, pdf_url, file_name):
    try:
        self.update_state(state="PROGRESS", meta="📄 PDF 다운로드 중...")
        imgs = download_pdf_images(self, pdf_url)
        if not imgs:
            return {"error": "PDF 다운로드 실패"}

        self.update_state(state="PROGRESS", meta="🖼️ 이미지 업스케일링 중...")
        upscaled = upscale_images(imgs)
        if not upscaled:
            return {"error": "업스케일 실패"}

        self.update_state(state="PROGRESS", meta="📄 PDF 변환 중...")
        pdf = convert_images_to_pdf(upscaled, file_name)
        if not pdf:
            return {"error": "PDF 변환 실패"}

        self.update_state(state="PROGRESS", meta="🗑️ 임시 파일 삭제 중...")
        for f in imgs + upscaled:
            try:
                os.remove(f)
                print(f"🗑️ 삭제 완료: {f}")
            except Exception as e:
                print(f"⚠️ 파일 삭제 실패: {f}, 오류: {e}")

        return {"pdf_url": f"/download/{file_name}.pdf"}

    except Exception as e:
        return {"error": str(e)}

# ✅ 유휴 감지 스레드
def monitor_idle(threshold=10, interval=5):
    while True:
        time.sleep(interval)
        if driver_tracker.is_idle(threshold):
            print("⏳ 유휴 드라이버 감지됨 → 종료 시도")
            driver_tracker.quit_driver()

threading.Thread(target=monitor_idle, daemon=True).start()

if __name__ == "__main__":
    celery.start()