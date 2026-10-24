import re

def clean_ocr_errors_smart(text: str) -> str:
    if not text: return ""
    # Sửa lỗi OCR số 0 vs chữ O, số 1 vs chữ l/I khi đứng cạnh số
    text = re.sub(r'(\d)o', r'\g<1>0', text, flags=re.IGNORECASE)
    text = re.sub(r'o(\d)', r'0\g<1>', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d)[lI]', r'\g<1>1', text)
    text = re.sub(r'[lI](\d)', r'1\g<1>', text)
    return text

def clean_text(text: str) -> str:
    if not text: return ""
    text = re.sub(r'[\r\n]+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def preprocess_text_for_matching(text: str) -> str:
    if not text: return ""
    text = text.lower()
    text = re.sub(r'[^a-zA-Z0-9#\+\.\-,\n\s]', ' ', text)
    return text.strip()