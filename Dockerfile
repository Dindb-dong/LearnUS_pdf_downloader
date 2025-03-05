# 1️⃣ Python 3.9을 기반으로 사용
FROM python:3.9

# 2️⃣ 작업 디렉토리 설정
WORKDIR /app

# 3️⃣ 필요한 패키지 설치
COPY requirements.txt requirements.txt
RUN apt update && apt install -y apt-utils python3-venv libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 libxrandr2 libxdamage1 libxkbcommon-x11-0 libgbm1 google-chrome-stable && \
  python -m venv /venv && \
  /venv/bin/pip install --upgrade pip && \
  /venv/bin/pip install -r requirements.txt &&\
  ln -s /venv/bin/gunicorn /usr/local/bin/gunicorn  
# Gunicorn을 실행 가능하도록 설정

# PATH 설정 추가
ENV PATH="/venv/bin:$HOME/.local/bin:$PATH"

ARG DEBIAN_FRONTEND=noninteractive

# 4️⃣ Chrome 및 ChromeDriver 설치 (Selenium 실행용)

RUN apt-get update && apt-get install -y wget unzip \
  && wget -q -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$(curl -s https://chromedriver.storage.googleapis.com/LATEST_RELEASE)/chromedriver_linux64.zip \
  && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
  && rm /tmp/chromedriver.zip \
  && chmod +x /usr/local/bin/chromedriver

# 5️⃣ 프로젝트 파일 복사
COPY . .

# 6️⃣ Gunicorn 실행 (최적화된 워커 설정)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "app:app"]