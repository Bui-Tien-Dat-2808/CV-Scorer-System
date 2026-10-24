import cv2
import numpy as np

def preprocess_column(column_gray, is_dark_bg=False):
    """Áp dụng Adaptive Thresholding cho cột ảnh CV"""
    if is_dark_bg:
        col_inverted = cv2.bitwise_not(column_gray)
        col_processed = cv2.adaptiveThreshold(col_inverted, 255,
                                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY, 11, 2)
    else:
        col_processed = cv2.adaptiveThreshold(column_gray, 255,
                                              cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY, 11, 2)
    return col_processed

def split_cv_columns(gray_image):
    """Phát hiện layout 2 cột và cắt ảnh"""
    height, width = gray_image.shape
    left_check_area = gray_image[:, :int(width * 0.40)]
    right_check_area = gray_image[:, int(width * 0.60):]
    
    mean_left = np.mean(left_check_area)
    mean_right = np.mean(right_check_area)
    DIFFERENCE_THRESHOLD = 80
    
    is_dark_left = False
    is_dark_right = False

    if abs(mean_left - mean_right) > DIFFERENCE_THRESHOLD:
        if mean_left < mean_right: 
            is_dark_left = True
        else: 
            is_dark_right = True
        
    split_info = {
        "is_split": is_dark_left or is_dark_right,
        "is_dark_left": is_dark_left,
        "is_dark_right": is_dark_right,
        "width": width
    }
    return split_info
