import io
import requests
from PyPDF2 import PdfReader
from typing import List, Dict, Tuple
import hashlib


def download_pdf(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def extract_text_from_pdf(pdf_content: bytes) -> str:
    pdf_file = io.BytesIO(pdf_content)
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
    chunks = []
    start = 0
    chunk_id = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk_text_content = text[start:end]
        
        if end < len(text):
            last_period = chunk_text_content.rfind('.')
            last_newline = chunk_text_content.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                end = start + break_point + 1
                chunk_text_content = text[start:end]
        
        chunks.append({
            "id": chunk_id,
            "text": chunk_text_content.strip(),
            "start": start,
            "end": end
        })
        
        chunk_id += 1
        start = end - overlap
    
    return chunks


def get_content_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def process_pdf(url: str, standard_number: str) -> Tuple[List[Dict], str]:
    pdf_content = download_pdf(url)
    content_hash = get_content_hash(pdf_content)
    text = extract_text_from_pdf(pdf_content)
    chunks = chunk_text(text)
    
    for chunk in chunks:
        chunk["standard_number"] = standard_number
        chunk["source_url"] = url
    
    return chunks, content_hash
