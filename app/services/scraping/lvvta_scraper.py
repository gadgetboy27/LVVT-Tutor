import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from app.core.config import settings


def get_page_content(url: str) -> Optional[str]:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def parse_standards_page(html_content: str) -> List[Dict]:
    soup = BeautifulSoup(html_content, 'html.parser')
    standards = []
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '.pdf' in href.lower():
            text = link.get_text(strip=True)
            
            if not href.startswith('http'):
                href = settings.LVVTA_BASE_URL + href
            
            standard_info = {
                'title': text,
                'pdf_url': href,
                'standard_number': extract_standard_number(text, href)
            }
            standards.append(standard_info)
    
    return standards


def extract_standard_number(title: str, url: str) -> str:
    import re
    patterns = [
        r'(\d{2,3}-\d{2})',
        r'Standard\s+(\d+)',
        r'LVV\s+(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1)
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return title[:20] if title else "unknown"


def get_pdf_last_modified(url: str) -> Optional[datetime]:
    try:
        response = requests.head(url, timeout=10)
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            return datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
    except:
        pass
    return None


def scrape_lvvta_standards() -> List[Dict]:
    pages_to_scrape = [
        f"{settings.LVVTA_BASE_URL}/standards/",
        f"{settings.LVVTA_BASE_URL}/operating-requirements/",
    ]
    
    all_standards = []
    
    for page_url in pages_to_scrape:
        html = get_page_content(page_url)
        if html:
            standards = parse_standards_page(html)
            for std in standards:
                std['source_page'] = page_url
                std['last_modified'] = get_pdf_last_modified(std['pdf_url'])
            all_standards.extend(standards)
    
    return all_standards
