import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from app.core.config import settings


def get_page_content(url: str) -> Optional[str]:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def parse_standards_page(html_content: str, base_url: str) -> List[Dict]:
    soup = BeautifulSoup(html_content, 'html.parser')
    standards = []
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '.pdf' in href.lower():
            text = link.get_text(strip=True)
            
            if not text:
                continue
                
            if not href.startswith('http'):
                if href.startswith('/'):
                    href = base_url + href
                else:
                    href = base_url + '/' + href
            
            standard_info = {
                'title': text,
                'pdf_url': href,
                'standard_number': extract_standard_number(text, href)
            }
            standards.append(standard_info)
    
    return standards


def extract_standard_number(title: str, url: str) -> str:
    import os
    filename = os.path.basename(url).replace('.pdf', '').replace('.PDF', '')
    if filename and len(filename) > 3:
        return filename[:100]
    
    clean_title = re.sub(r'[^\w\s-]', '', title)[:50]
    return clean_title.strip() if clean_title.strip() else url[-50:]


def get_pdf_last_modified(url: str) -> Optional[datetime]:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.head(url, timeout=10, headers=headers)
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            return datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z')
    except Exception:
        pass
    return None


def scrape_lvvta_standards() -> List[Dict]:
    pages_to_scrape = [
        ("https://lvvta.org.nz/documents.html", "https://lvvta.org.nz"),
        (f"{settings.LVVTA_BASE_URL}/standards/", settings.LVVTA_BASE_URL),
        (f"{settings.LVVTA_BASE_URL}/operating-requirements/", settings.LVVTA_BASE_URL),
    ]
    
    all_standards = []
    seen_urls = set()
    
    for page_url, base_url in pages_to_scrape:
        html = get_page_content(page_url)
        if html:
            standards = parse_standards_page(html, base_url)
            for std in standards:
                if std['pdf_url'] not in seen_urls:
                    seen_urls.add(std['pdf_url'])
                    std['source_page'] = page_url
                    std['last_modified'] = get_pdf_last_modified(std['pdf_url'])
                    all_standards.append(std)
    
    return all_standards


def categorize_by_topic(title: str) -> str:
    title_lower = title.lower()
    
    category_keywords = {
        "Brakes": ["brake", "braking", "abs", "disc", "drum"],
        "Suspension & Steering": ["suspension", "steering", "spring", "shock", "strut", "coil", "leaf"],
        "Engine & Drivetrain": ["engine", "motor", "drivetrain", "transmission", "gearbox", "turbo", "supercharger"],
        "Lighting & Electrical": ["light", "lighting", "electrical", "wiring", "headlight", "indicator"],
        "Body & Structure": ["body", "structure", "chassis", "frame", "roll", "cage"],
        "Wheels & Tyres": ["wheel", "tyre", "tire", "rim"],
        "Exhaust & Emissions": ["exhaust", "emission", "muffler", "catalytic"],
        "Fuel Systems": ["fuel", "tank", "lpg", "cng"],
        "Certification Process": ["certification", "form", "guide", "process", "schedule"],
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in title_lower for keyword in keywords):
            return category
    
    return "General Compliance"
