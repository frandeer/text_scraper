from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth
import time
import os
import logging
import random
import json
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("wishket_scraper")

def setup_chrome_options():
    """
    Chrome 브라우저 옵션을 설정하는 함수
    
    Returns:
        Options: 설정된 Chrome 옵션 객체
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 봇 감지 우회를 위한 설정
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36", 
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    return chrome_options

def save_page_source(driver, url, output_dir="page_sources"):
    """
    현재 페이지의 HTML 소스를 파일로 저장합니다.
    
    Args:
        driver: Selenium WebDriver 인스턴스
        url: 스크랩한 URL
        output_dir: HTML 소스를 저장할 디렉토리
    
    Returns:
        str: 저장된 파일 경로
    """
    # 디렉토리가 없으면 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 파일명에 사용할 타임스탬프 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # URL에서 기사 ID 추출 (URL 형식: https://yozm.wishket.com/magazine/detail/NUMBER/)
    try:
        article_id = url.strip('/').split('/')[-1]
    except:
        article_id = "unknown"
    
    # 파일명 생성
    filename = f"{output_dir}/article_{article_id}_{timestamp}.html"
    
    # HTML 소스 저장
    with open(filename, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    logger.info(f"HTML 소스가 {filename}에 저장되었습니다.")
    return filename

def clean_content(content):
    """
    추출된 콘텐츠에서 불필요한 텍스트 제거
    
    Args:
        content: 원본 콘텐츠 텍스트
    
    Returns:
        str: 정리된 콘텐츠 텍스트
    """
    # 제거할 문구 목록
    phrases_to_remove = [
        "요즘IT가 PICK 한 뉴스레터를 매주 목요일 에 만나보세요.",
        "개인정보 수집·이용 에 동의해 주세요. 무료로 구독하기",
        "요즘IT",
        "이메일 주소를 입력해주세요.",
        "현재 글",
        "관련 글 보기",
        "목록으로",
        "복사 완료!"
    ]
    
    for phrase in phrases_to_remove:
        content = content.replace(phrase, "")
    
    # 다중 공백 및 불필요한 줄바꿈 정리
    content = ' '.join(content.split())
    
    # 문단 구분을 위한 줄바꿈 추가
    content = content.replace(". ", ".\n\n")
    
    return content.strip()

def extract_article_content(driver):
    """
    여러 방법으로 기사 내용을 추출하는 함수
    
    Args:
        driver: Selenium WebDriver 인스턴스
    
    Returns:
        dict: 추출된 기사 내용, 제목, 추출 방법 정보
    """
    result = {}
    extraction_methods = {}
    
    # 제목 추출
    try:
        title = driver.find_element(By.CSS_SELECTOR, "h1.article-title").text
        result['title_method'] = "h1.article-title"
    except Exception as e:
        logger.warning(f"h1.article-title로 제목 추출 실패: {e}")
        try:
            title = driver.find_element(By.TAG_NAME, "h1").text
            result['title_method'] = "h1 태그"
        except Exception as e:
            logger.error(f"h1 태그로 제목 추출 실패: {e}")
            title = "제목을 찾을 수 없습니다"
            result['title_method'] = "찾을 수 없음"
    
    result['title'] = title
    
    # 방법 1: 원본 코드 방식 - p 태그 추출
    try:
        article_container = driver.find_element(By.CSS_SELECTOR, "div.article-body-container")
        paragraphs = article_container.find_elements(By.TAG_NAME, "p")
        p_content = "\n\n".join([p.text for p in paragraphs if p.text])
        extraction_methods['p_tags'] = {
            'content': p_content,
            'length': len(p_content),
            'element_count': len(paragraphs)
        }
    except Exception as e:
        logger.warning(f"p 태그 추출 실패: {e}")
        extraction_methods['p_tags'] = {'error': str(e)}
    
    # 방법 2: 강화된 방식 - 여러 태그 혼합
    try:
        article_container = driver.find_element(By.CSS_SELECTOR, "div.article-body-container")
        
        # 내용 요소 수집
        content_elements = []
        
        # p 태그 추출
        p_tags = article_container.find_elements(By.TAG_NAME, "p")
        for p in p_tags:
            if p.text.strip():
                content_elements.append(p.text)
        
        # div 태그 (내용이 있는 것만)
        div_tags = article_container.find_elements(By.TAG_NAME, "div")
        for div in div_tags:
            div_text = div.text.strip()
            if div_text and len(div_text) > 50:  # 실질적인 내용이 있는 div만
                # 이미 추출된 내용과 중복되지 않는지 확인
                is_duplicate = False
                for existing in content_elements:
                    if div_text in existing or existing in div_text:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    content_elements.append(div_text)
        
        # 모든 내용을 합쳐서 하나의 텍스트로
        enhanced_content = "\n\n".join(content_elements)
        extraction_methods['enhanced'] = {
            'content': enhanced_content,
            'length': len(enhanced_content),
            'element_count': len(content_elements)
        }
    except Exception as e:
        logger.warning(f"강화된 방식 추출 실패: {e}")
        extraction_methods['enhanced'] = {'error': str(e)}
    
    # 방법 3: 컨테이너 텍스트 전체
    try:
        article_container = driver.find_element(By.CSS_SELECTOR, "div.article-body-container")
        container_text = article_container.text
        extraction_methods['container_text'] = {
            'content': container_text,
            'length': len(container_text)
        }
    except Exception as e:
        logger.warning(f"컨테이너 텍스트 추출 실패: {e}")
        extraction_methods['container_text'] = {'error': str(e)}
    
    # 방법 4: Article 태그 전체
    try:
        article = driver.find_element(By.TAG_NAME, "article")
        article_text = article.text
        extraction_methods['article_tag'] = {
            'content': article_text,
            'length': len(article_text)
        }
    except Exception as e:
        logger.warning(f"article 태그 추출 실패: {e}")
        extraction_methods['article_tag'] = {'error': str(e)}
    
    # 가장 긴 내용을 제공하는 방법 선택
    best_method = None
    max_length = 0
    
    for method, data in extraction_methods.items():
        if 'length' in data and data['length'] > max_length:
            max_length = data['length']
            best_method = method
    
    if best_method:
        logger.info(f"최적 추출 방법: {best_method} ({max_length} 글자)")
        content = extraction_methods[best_method]['content']
        # 불필요한 텍스트 제거
        content = clean_content(content)
        result['content'] = content
        result['extraction_method'] = best_method
    else:
        logger.error("모든 추출 방법이 실패했습니다.")
        result['content'] = "내용을 찾을 수 없습니다."
        result['extraction_method'] = "실패"
    
    result['extraction_methods'] = extraction_methods
    
    return result

def scrape_wishket_article(url):
    """
    Selenium을 이용하여 Wishket 사이트의 기사 내용을 스크랩핑하는 함수

    Args:
        url (str): 스크랩핑할 기사의 URL

    Returns:
        dict: 제목, 내용을 포함한 딕셔너리
    """
    logger.info(f"스크랩 시작: {url}")
    
    # Chrome 옵션 설정
    chrome_options = setup_chrome_options()
    
    try:
        # Chrome WebDriver 설정
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Selenium Stealth 적용 (봇 감지 회피)
        stealth(
            driver,
            languages=["ko-KR", "ko", "en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True
        )
        
        # 자동화 스크립트 감지 방지
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # 웹 페이지 로드
        driver.get(url)
        
        # 페이지가 완전히 로드될 때까지 대기
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
            logger.info("기사 컨텐츠 로드 완료")
        except Exception as e:
            logger.warning(f"기사 콘텐츠 로드 대기 시간 초과: {e}")
        
        # 추가 대기 (JavaScript가 모두 로드되도록)
        time.sleep(3)
        
        # 페이지 소스 저장
        page_source_file = save_page_source(driver, url)
        
        # 콘텐츠 추출
        article_data = extract_article_content(driver)
        
        # 추출 데이터에 URL 및 소스 파일 정보 추가
        article_data['url'] = url
        article_data['page_source_file'] = page_source_file
        article_data['timestamp'] = datetime.now().isoformat()
        
        # 웹드라이버 종료
        driver.quit()
        
        # 메타데이터 저장
        metadata_file = f"metadata/{os.path.basename(page_source_file).replace('.html', '.json')}"
        os.makedirs("metadata", exist_ok=True)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            # 콘텐츠 크기 제한 (JSON 파일 크기 관리)
            metadata = article_data.copy()
            for method, data in metadata['extraction_methods'].items():
                if 'content' in data and len(data['content']) > 500:
                    data['content'] = data['content'][:500] + '...(생략)'
            
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"스크랩 완료: {url}")
        return {
            'title': article_data['title'],
            'content': article_data['content'],
            'extraction_method': article_data['extraction_method'],
            'page_source_file': page_source_file
        }
    
    except Exception as e:
        logger.error(f"스크랩 과정에서 오류 발생: {e}", exc_info=True)
        if 'driver' in locals():
            try:
                # 오류 발생 시에도 페이지 소스 저장 시도
                save_page_source(driver, url, "error_pages")
                driver.quit()
            except:
                pass
        return None

def save_to_file(data, filename="wishket_article.txt"):
    """
    스크랩핑한 내용을 파일로 저장

    Args:
        data (dict): 제목과 내용이 포함된 딕셔너리
        filename (str): 저장할 파일명
    """
    if data:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"제목: {data['title']}\n\n")
                f.write(data['content'])
            logger.info(f"파일이 성공적으로 저장되었습니다: {os.path.abspath(filename)}")
        except Exception as e:
            logger.error(f"파일 저장 중 오류 발생: {e}")
    else:
        logger.warning("저장할 데이터가 없습니다.")

if __name__ == "__main__":
    # 타겟 URL
    url = "https://yozm.wishket.com/magazine/detail/3005/"
    
    try:
        # 스크랩핑 실행
        article_data = scrape_wishket_article(url)
        
        # 결과 출력
        if article_data:
            print(f"제목: {article_data['title']}")
            print(f"추출 방법: {article_data['extraction_method']}")
            print(f"HTML 소스 저장 위치: {article_data['page_source_file']}")
            
            print("\n== 내용 미리보기 ==")
            preview = article_data['content'][:300] + "..." if len(article_data['content']) > 300 else article_data['content']
            print(preview)
            
            # 파일로 저장
            save_to_file(article_data)
        else:
            print("기사를 스크랩핑하지 못했습니다.")
    except Exception as e:
        logger.critical(f"예상치 못한 오류 발생: {e}", exc_info=True)
        print(f"오류가 발생했습니다: {e}")