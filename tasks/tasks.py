import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from celery import Celery
from webdriver_manager.chrome import ChromeDriverManager  # ✅ 자동 다운로드 추가
from dotenv import load_dotenv  # ✅ .env 파일 로드

# ✅ .env 파일 로드
load_dotenv()

# ✅ 환경 변수에서 EC2 IP 가져오기
EC2_IP = os.getenv("EC2_IP")

def is_chrome_running():
    """✅ Chrome 디버깅 포트(9223)가 정상 응답을 반환하는지 확인"""
    try:
        response = requests.get("http://127.0.0.1:9223/json", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False  # 포트가 닫혀 있거나 응답이 없음

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # ✅ headless 모드 유지
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # ✅ 9223 포트의 DevTools 프로토콜을 명시적으로 사용
    chrome_options.debugger_address = f"{EC2_IP}:9223"

    # ✅ Chrome이 실행 중인지 확인
    if is_chrome_running():
        try:
            print(f"✅ 기존 Chrome 인스턴스({EC2_IP})와 연결 중...")
            driver = webdriver.Chrome(options=chrome_options)
            print("🚀 기존 Chrome 인스턴스와 연결 성공!")
            return driver
        except Exception as e:
            print(f"⚠️ 기존 Chrome 연결 실패, 새로운 Chrome 실행: {e}")

    print("🚀 기존 Chrome이 실행되지 않음, 새로운 ChromeDriver 실행")

    # ✅ ChromeDriver 자동 다운로드 및 실행
    service = Service(ChromeDriverManager().install())  # ✅ 자동 다운로드
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver


def wait_for_chrome(timeout=10, interval=2):
    """✅ Chrome이 실행될 때까지 최대 timeout초 대기"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if is_chrome_running():
            print("🚀 Chrome 실행 확인됨!")
            return True
        print("⏳ Chrome 실행 대기 중...")
        time.sleep(interval)
    
    print("❌ Chrome이 실행되지 않음. 종료.")
    return False

# Celery 설정
celery = Celery("tasks", broker="redis://127.0.0.1:6379/0", backend="redis://127.0.0.1:6379/0")
celery.conf.update(
    task_track_started=True,  # 작업 시작 상태를 추적
    result_extended=True,  # 추가적인 결과 정보 저장
    task_ignore_result=False,  # 작업 결과 무시 방지
)

# 저장 폴더 설정
SAVE_DIR = "static"
IMG_DIR = os.path.join(SAVE_DIR, "downloaded_pages")
UPSCALE_DIR = os.path.join(SAVE_DIR, "upscaled_pages")

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(UPSCALE_DIR, exist_ok=True)


def download_pdf_images(pdf_url):
    """PDF 뷰어에서 이미지를 다운로드하여 로컬에 저장"""
    try:
        # ✅ Chrome이 실행될 때까지 최대 10초 대기
        if not wait_for_chrome(timeout=10, interval=2):
            return []

        driver = get_driver()  # ✅ 기존 Chrome 인스턴스(9223)과 연결

        driver.get(pdf_url)
        print(f"📄 페이지 로드 중: {pdf_url}")

        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            driver.switch_to.frame(iframe)
            print("🔄 iframe 내부로 이동 완료")
        except:
            print("⚠️ iframe이 감지되지 않음 (무시하고 진행)")

        try:
            scroll_container = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "contents"))
            )
            print("✅ PDF 뷰어 요소 찾음!")
        except:
            print("❌ PDF 뷰어 요소를 찾을 수 없음!")
            driver.quit()
            return []

        scroll_attempts = 0
        prev_image_count = 0
        max_scrolls = 30

        for _ in range(max_scrolls):
            image_elements = driver.find_elements(By.TAG_NAME, "img")
            current_image_count = len(image_elements)

            driver.execute_script("arguments[0].scrollBy(0, 2000);", scroll_container)
            time.sleep(3)

            print(f"🔄 스크롤 중... (현재 이미지 개수: {current_image_count})")

            if current_image_count == prev_image_count:
                scroll_attempts += 1
                if scroll_attempts >= 3:
                    break
            else:
                scroll_attempts = 0

            prev_image_count = current_image_count

        print("✅ 모든 페이지 스크롤 완료!")
        # 🚀 **driver.quit() 하기 전에 필요한 정보를 먼저 저장**
        image_data = [(img.get_attribute("id"), img.get_attribute("src")) for img in driver.find_elements(By.TAG_NAME, "img")]

        driver.quit()
        print("🚪 브라우저 종료")
        # ✅ `image_data`에서 필요한 정보 추출
        if not image_data:
            print("❌ 이미지 요소를 찾을 수 없음")
            return []

        base_url = None
        page_count = 0
        downloaded_images = []

        for img_id, src in image_data:
            if img_id and img_id.startswith("page"):
                if img_id == "page0":
                    base_url = src.rsplit("/", 1)[0]  # ✅ base_url 저장
                page_count += 1

        if not base_url or page_count == 0:
            return []

        print(f"🌟 감지된 페이지 개수: {page_count}")

        for i in range(page_count):
            img_url = f"{base_url}/{i+1}.png"
            img_path = os.path.join(IMG_DIR, f"{i+1}.png")

            try:
                response = requests.get(img_url, stream=True, timeout=10)
                if response.status_code == 200:
                    with open(img_path, 'wb') as file:
                        file.write(response.content)
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
    finally:
        if driver:
            driver.quit()  # 🔹 예외 발생 여부와 상관없이 항상 driver 종료
            print("🚪 브라우저 종료")


def upscale_images(image_files, scale_factor=4):
    """이미지를 업스케일하여 새로운 폴더에 저장"""
    upscaled_images = []
    
    for img_path in image_files:
        img_name = os.path.basename(img_path)
        upscaled_path = os.path.join(UPSCALE_DIR, img_name)

        try:
            img = Image.open(img_path)
            new_size = (img.width * scale_factor, img.height * scale_factor)
            upscaled_img = img.resize(new_size, Image.LANCZOS)
            upscaled_img.save(upscaled_path)
            upscaled_images.append(upscaled_path)
            print(f"✅ 업스케일 완료: {upscaled_path}")
        except Exception as e:
            print(f"❌ 업스케일 실패: {img_path}, 오류: {e}")

    return upscaled_images


def convert_images_to_pdf(image_files, file_name):
    """업스케일된 PNG 파일을 PDF로 변환"""
    output_pdf = os.path.join(SAVE_DIR, f"{file_name}.pdf")
    
    try:
        images = [Image.open(img).convert("RGB") for img in image_files]
        if images:
            images[0].save(output_pdf, save_all=True, append_images=images[1:])
            print(f"📄 PDF 변환 완료: {output_pdf}")
            return output_pdf
        else:
            print("❌ 변환할 이미지가 없음")
            return None
    except Exception as e:
        print(f"❌ PDF 변환 실패: {e}")
        return None


@celery.task(bind=True)
def process_pdf(self, pdf_url, file_name):
    """PDF 다운로드 → 이미지 변환 → 업스케일링 → PDF 변환"""
    try:
        # 1️⃣ PDF 뷰어에서 이미지 다운로드 과정
        self.update_state(state="PROGRESS", meta="📄 PDF 다운로드 중...")
        downloaded_images = download_pdf_images(pdf_url)

        if not downloaded_images:
            return {"error": "PDF 다운로드 실패"}

        # 2️⃣ 업스케일 상태 업데이트
        self.update_state(state="PROGRESS", meta="🖼️ 이미지 업스케일링 중...")
        upscaled_images = upscale_images(downloaded_images)

        if not upscaled_images:
            return {"error": "업스케일 실패"}

        # 3️⃣ PDF 변환 상태 업데이트
        self.update_state(state="PROGRESS", meta="📄 PDF 변환 중...")
        final_pdf_path = convert_images_to_pdf(upscaled_images, file_name)

        if not final_pdf_path:
            return {"error": "PDF 변환 실패"}

        # ✅ 4️⃣ 임시 파일 삭제
        self.update_state(state="PROGRESS", meta="🗑️ 임시 파일 삭제 중...")
        for file_path in downloaded_images + upscaled_images:
            try:
                os.remove(file_path)
                print(f"🗑️ 삭제 완료: {file_path}")
            except Exception as e:
                print(f"⚠️ 파일 삭제 실패: {file_path}, 오류: {e}")

        return {"pdf_url": f"/download/{file_name}.pdf"}

    except Exception as e:
        return {"error": str(e)}
    
if __name__ == "__main__":
    celery.start()