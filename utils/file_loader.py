# utils/file_loader.py
import os
import cv2
import numpy as np
import fitz  # PyMuPDF
from core.logger import logger


def load_file_as_images(file_path: str):
    """
    Input:  Đường dẫn file (PDF hoặc ảnh)
    Output: List ảnh dạng numpy array (BGR OpenCV) để đưa vào OCR.
    
    Tối ưu hóa Windows & Linux: Sử dụng trực tiếp PyMuPDF (fitz) để render PDF thành ảnh trong RAM.
    Hoàn toàn KHÔNG phụ thuộc vào Poppler (không cần cài thêm binary trên Windows/Linux).
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return []

    file_ext = os.path.splitext(file_path)[1].lower()
    images = []

    try:
        # =========================
        # TRƯỜNG HỢP 1: FILE PDF
        # =========================
        if file_ext == ".pdf":
            logger.info(f"Loading PDF via PyMuPDF: {file_path}")
            doc = fitz.open(file_path)

            if len(doc) == 0:
                logger.error("Empty PDF file.")
                return []

            for page_idx in range(len(doc)):
                page = doc[page_idx]
                # dpi=200 cho độ phân giải sắc nét tối ưu cho OCR
                pix = page.get_pixmap(dpi=200)

                # Convert pixmap buffer trực tiếp sang numpy array
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

                # Chuyển đổi định dạng màu sang BGR OpenCV
                if pix.n == 4:  # RGBA
                    img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:  # RGB
                    img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                elif pix.n == 1:  # Grayscale
                    img_cv = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
                else:
                    img_cv = img_array

                images.append(img_cv)

            doc.close()

        # =========================
        # TRƯỜNG HỢP 2: FILE ẢNH
        # =========================
        elif file_ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]:
            logger.info(f"Loading image file: {file_path}")

            # Đọc bằng np.fromfile để tránh lỗi đường dẫn tiếng Việt có dấu trên Windows
            img_cv = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img_cv is None:
                logger.error("OpenCV cannot decode image file")
                return []

            images.append(img_cv)

        # =========================
        # TRƯỜNG HỢP KHÁC
        # =========================
        else:
            logger.error(f"Unsupported file format: {file_ext}")
            return []

    except Exception as e:
        logger.error(f"Error loading file {file_path}: {e}")
        return []

    return images
