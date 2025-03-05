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

# Celery 설정
celery = Celery("tasks", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0")

# 저장 폴더 설정
SAVE_DIR = "static"
IMG_DIR = os.path.join(SAVE_DIR, "downloaded_pages")
UPSCALE_DIR = os.path.join(SAVE_DIR, "upscaled_pages")

os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(UPSCALE_DIR, exist_ok=True)

@celery.task(bind=True)
def process_pdf(self, pdf_url, file_name):
    """런어스에서 PDF를 PNG로 변환, 업스케일 후 PDF로 저장"""
    try:
        # 1️⃣ Selenium 설정
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # GUI 없이 실행
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        service = Service("/usr/local/bin/chromedriver")  # ChromeDriver 경로 지정
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # 2️⃣ PDF 뷰어 페이지 열기
        driver.get(pdf_url)
        print(f"📄 페이지 로드 중: {pdf_url}")

        # 3️⃣ iframe이 있으면 전환
        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            driver.switch_to.frame(iframe)
            print("🔄 iframe 내부로 이동 완료")
        except:
            print("⚠️ iframe이 감지되지 않음 (무시하고 진행)")

        # 4️⃣ PDF 뷰어 내의 스크롤 가능한 div 찾기
        try:
            scroll_container = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "contents"))  # ID로 찾기
            )
            print("✅ PDF 뷰어 요소 찾음!")
        except:
            print("❌ PDF 뷰어 요소를 찾을 수 없음!")
            driver.quit()
            return {"error": "PDF 뷰어를 찾을 수 없음"}

        # 5️⃣ 자동 스크롤하여 모든 페이지 로드
        scroll_attempts = 0
        prev_image_count = 0
        max_scrolls = 30  # 최대 30번 스크롤 시도

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

        # 6️⃣ 이미지 URL 추출 및 다운로드
        image_elements = driver.find_elements(By.TAG_NAME, "img")
        driver.quit()

        if not image_elements:
            return {"error": "이미지를 찾을 수 없음"}

        base_url = None
        page_count = 0
        downloaded_images = []

        for img in image_elements:
            img_id = img.get_attribute("id")
            src = img.get_attribute("src")

            if img_id and img_id.startswith("page"):
                if img_id == "page0":
                    base_url = src.rsplit("/", 1)[0]
                page_count += 1

        if not base_url or page_count == 0:
            return {"error": "이미지 URL을 찾을 수 없음"}

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

        # 7️⃣ 업스케일링 (4배 해상도)
        def upscale_image(input_path, output_path, scale_factor=4):
            try:
                img = Image.open(input_path)
                new_size = (img.width * scale_factor, img.height * scale_factor)
                upscaled_img = img.resize(new_size, Image.LANCZOS)
                upscaled_img.save(output_path)
                return output_path
            except Exception as e:
                print(f"❌ 업스케일 실패: {input_path}, 오류: {e}")
                return None

        upscaled_images = []
        for img_path in downloaded_images:
            img_name = os.path.basename(img_path)
            upscaled_path = os.path.join(UPSCALE_DIR, img_name)
            upscaled_img = upscale_image(img_path, upscaled_path)

            if upscaled_img:
                upscaled_images.append(upscaled_img)

        # 8️⃣ 업스케일된 PNG → PDF 변환
        def convert_images_to_pdf(image_files, output_pdf):
            images = [Image.open(img).convert("RGB") for img in image_files]
            if images:
                images[0].save(output_pdf, save_all=True, append_images=images[1:])
                print(f"📄 PDF 변환 완료: {output_pdf}")
            else:
                print("❌ 변환할 이미지가 없음")

        final_pdf_path = os.path.join(SAVE_DIR, f"{file_name}.pdf")
        convert_images_to_pdf(upscaled_images, final_pdf_path)

        # ✅ 임시 파일 삭제
        for file_path in downloaded_images + upscaled_images:
            os.remove(file_path)  # PNG 파일 삭제

        return {"pdf_url": f"/download/{file_name}.pdf"}

    except Exception as e:
        return {"error": str(e)}