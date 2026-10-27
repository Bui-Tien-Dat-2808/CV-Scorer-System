# ==========================================
# Dockerfile: TalentMatch Enterprise AI Platform
# ==========================================
FROM python:3.11-slim

# Ngăn Python tạo bytecode .pyc và bật stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV, PaddleOCR và PyTorch
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements.txt trước để tận dụng Docker layer cache
COPY requirements.txt .

# Cài đặt Python packages.
# torch được lấy từ chỉ mục CPU: wheel mặc định trên PyPI kèm CUDA (~5GB) trong khi
# container này chỉ chạy suy luận CPU. `==2.9.1` vẫn khớp bản `2.9.1+cpu`.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.1 && \
    pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn backend, frontend và core services vào container
COPY core/ core/
COPY models/ models/
COPY schemas/ schemas/
COPY services/ services/
COPY utils/ utils/
COPY backend/ backend/
COPY frontend/ frontend/
# Sao chép test để `docker compose exec cv-scorer pytest` chạy được trong container
COPY tests/ tests/

# Tạo các thư mục dữ liệu và cache mặc định
RUN mkdir -p /app/data /app/data/sample_cvs /root/.cache /root/.paddleocr

# Expose duy nhất port 8000 cho Enterprise Web UI & REST API
EXPOSE 8000

# Healthcheck kiểm tra FastAPI service
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Khởi chạy trực tiếp FastAPI Server qua uvicorn
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
