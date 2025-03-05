# 1️⃣ Python 3.9을 기반으로 사용
FROM python:3.9

# 2️⃣ 작업 디렉토리 설정
WORKDIR /app

# 3️⃣ 필요한 패키지 설치
COPY requirements.txt requirements.txt
RUN apt update && apt install -y apt-utils python3-venv && \
  python -m venv /venv && \
  /venv/bin/pip install --upgrade pip && \
  /venv/bin/pip install -r requirements.txt &&\
  ln -s /venv/bin/gunicorn /usr/local/bin/gunicorn  
# Gunicorn을 실행 가능하도록 설정

# PATH 설정 추가
ENV PATH="/venv/bin:$HOME/.local/bin:$PATH"

ARG DEBIAN_FRONTEND=noninteractive

# 4️⃣ Chrome 및 ChromeDriver 설치 (Selenium 실행용)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
  && apt update \
  && apt install -y google-chrome-stable \
  && wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$(curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE)/chromedriver_linux64.zip \
  && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
  && rm /tmp/chromedriver.zip

# 5️⃣ 프로젝트 파일 복사
COPY . .

# 6️⃣ Gunicorn 실행 (최적화된 워커 설정)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "app:app"]