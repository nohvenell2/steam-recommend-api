FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 빌드 도구 설치 (필요시)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 환경 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 실행 포트
EXPOSE 8000

# 서버 구동 명령
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
