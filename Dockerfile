# 1️⃣ Python 3.9을 기반으로 사용
FROM python:3.9

# 2️⃣ 작업 디렉토리 설정
WORKDIR /

# 3️⃣ 필수 패키지 설치
COPY requirements.txt requirements.txt
RUN apt update && apt install -y \
  apt-utils \
  python3-venv \
  libnss3 \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libxcomposite1 \
  libxrandr2 \
  libxdamage1 \
  libxkbcommon-x11-0 \
  libgbm1 \
  libasound2 \
  libgtk-3-0 \
  libxfixes3 \
  xdg-utils \
  libvulkan1 \
  fonts-liberation \
  libnspr4 \
  wget \
  unzip \
  curl \
  && python -m venv /venv \
  && /venv/bin/pip install --upgrade pip \
  && /venv/bin/pip install -r requirements.txt \
  && ln -s /venv/bin/gunicorn /usr/local/bin/gunicorn \
  && ln -s /venv/bin/celery /usr/local/bin/celery \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# 4️⃣ Google Chrome 수동 다운로드 및 설치
RUN wget -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
  && apt install -y /tmp/google-chrome.deb \
  && rm /tmp/google-chrome.deb

# 5️⃣ 최신 Chrome 버전에 맞는 ChromeDriver 다운로드
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}') \
  && LATEST_DRIVER=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/ | grep -o "https://storage.googleapis.com/chrome-for-testing-public/$CHROME_VERSION/linux64/chromedriver-linux64.zip" | head -n 1) \
  && wget -q -O /tmp/chromedriver.zip "$LATEST_DRIVER" \
  && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
  && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \ 
  && rm -rf /usr/local/bin/chromedriver-linux64 \ 
  && rm /tmp/chromedriver.zip \
  && chmod +x /usr/local/bin/chromedriver

# 🔹 추가: 실행 환경 경로 설정
ENV PATH="/venv/bin:$PATH"

# 6️⃣ 프로젝트 파일 복사
COPY . .

# 7️⃣ 웹 서버 및 워커 실행을 위한 엔트리포인트 설정
ENTRYPOINT ["/bin/sh", "-c"]

CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "app:app"]