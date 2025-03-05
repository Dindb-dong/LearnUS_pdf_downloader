# 1️⃣ Python 3.9을 기반으로 사용
FROM python:3.9

# 2️⃣ 작업 디렉토리 설정
WORKDIR /app

# 3️⃣ 필요한 패키지 설치
COPY requirements.txt requirements.txt
RUN python -m venv /venv && \
  /venv/bin/pip install --upgrade pip && \
  /venv/bin/pip install -r requirements.txt

# 환경 변수 설정 (venv 활성화)
ENV PATH="/app/venv/bin:$PATH"

# 4️⃣ 프로젝트 파일 복사
COPY . .

# 5️⃣ Gunicorn 실행 (최적화된 워커 설정)
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "4", "app:app"]