# Python 베이스 이미지 사용
FROM python:3.10-slim

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 시스템 패키지 업데이트 및 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# pip 업그레이드
RUN pip install --upgrade pip

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY websocket_server.py .
COPY connection_manager.py .
COPY constants/ constants/
COPY websocket-schema/ websocket-schema/

# 포트 노출
EXPOSE 8765

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=30s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/docs || exit 1

# 서버 실행 (uvicorn 사용)
CMD ["uvicorn", "websocket_server:app", "--host", "0.0.0.0", "--port", "8765"] 