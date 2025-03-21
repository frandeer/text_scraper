import streamlit as st
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
import random
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import glob
import re
import json
import platform
import subprocess
import shutil
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("article_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("article_scraper")

# Streamlit 페이지 설정
st.set_page_config(page_title="기사 콘텐츠 스크래퍼", page_icon="🔍", layout="wide")
st.title("기사 콘텐츠 스크래퍼")
st.markdown("다양한 사이트의 기사 내용을 추출합니다.")

def detect_site_type(url):
    """URL을 기반으로 사이트 유형을 감지합니다."""
    if "yozm.wishket.com" in url:
        return "wishket"
    elif "brunch.co.kr" in url:
        return "brunch"
    elif "medium.com" in url:
        return "medium"
    elif "velog.io" in url:
        return "velog"
    else:
        return "unknown"

def get_compatible_chromedriver():
    """
    Streamlit Cloud와 호환되는 ChromeDriver를 설정하는 함수
    
    Returns:
        Service: Chrome WebDriver 서비스 객체
    """
    try:
        # 환경 감지
        is_streamlit_cloud = os.environ.get('IS_STREAMLIT_CLOUD') == 'true'
        
        if is_streamlit_cloud:
            logger.info("Streamlit Cloud 환경 감지됨")
            
            # Streamlit Cloud에서는 이미 Chrome이 설치되어 있으므로 해당 경로 사용
            CHROME_PATH = "/usr/bin/google-chrome"
            
            # Chrome 버전 확인
            chrome_version = ""
            try:
                chrome_version_cmd = subprocess.run(
                    [CHROME_PATH, "--version"], 
                    capture_output=True, 
                    text=True
                )
                chrome_version = chrome_version_cmd.stdout.strip().split(" ")[-1]
                logger.info(f"감지된 Chrome 버전: {chrome_version}")
            except Exception as e:
                logger.error(f"Chrome 버전 확인 실패: {e}")
                chrome_version = "114.0.5735.90"  # 기본 버전
            
            # ChromeDriver 다운로드 경로 설정
            chrome_major_version = chrome_version.split('.')[0]
            driver_path = Path("/tmp/chromedriver")
            
            # 환경에 맞는 ChromeDriver 설치
            if not driver_path.exists():
                logger.info(f"ChromeDriver 설치 중 (Chrome {chrome_major_version}용)")
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.utils import ChromeType
                driver_path = ChromeDriverManager(version=chrome_major_version, chrome_type=ChromeType.GOOGLE).install()
            
            logger.info(f"ChromeDriver 경로: {driver_path}")
            return Service(executable_path=driver_path)
        else:
            # 로컬 환경에서는 webdriver-manager 사용
            logger.info("로컬 환경 감지됨, webdriver-manager 사용")
            return Service(ChromeDriverManager().install())
    
    except Exception as e:
        logger.error(f"ChromeDriver 설정 중 오류 발생: {e}", exc_info=True)
        # 오류 발생 시 기본 ChromeDriverManager 사용
        return Service(ChromeDriverManager().install())

def setup_chrome_options():
    """Chrome 브라우저 옵션을 설정하는 함수"""
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
    """현재 페이지의 HTML 소스를 파일로 저장합니다."""
    # 디렉토리가 없으면 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 파일명에 사용할 타임스탬프 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 사이트 유형 감지
    site_type = detect_site_type(url)
    
    # URL에서 기사 ID 추출
    try:
        # URL의 마지막 부분을 ID로 사용
        article_id = url.strip('/').split('/')[-1]
        # 쿼리 파라미터 제거
        if '?' in article_id:
            article_id = article_id.split('?')[0]
    except:
        article_id = "unknown"
    
    # 파일명 생성
    filename = f"{output_dir}/{site_type}_article_{article_id}_{timestamp}.html"
    
    # HTML 소스 저장
    with open(filename, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    logger.info(f"HTML 소스가 {filename}에 저장되었습니다.")
    return filename

def extract_content_from_html(html_file):
    """저장된 HTML 파일에서 내용을 추출합니다."""
    logger.info(f"HTML 파일에서 내용 추출: {html_file}")
    
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 파일명에서 사이트 유형 추출
        file_basename = os.path.basename(html_file)
        site_type = "unknown"
        site_types = ["wishket", "brunch", "medium", "velog"]
        for st in site_types:
            if st in file_basename:
                site_type = st
                break
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 (사이트별 선택자)
        title_elem = None
        if site_type == "brunch":
            title_elem = soup.select_one('h1.cover_title') or soup.select_one('h1.article_title')
        elif site_type == "medium":
            title_elem = soup.select_one('h1[data-testid="article-title"]') or soup.select_one('h1.pw-post-title')
        elif site_type == "velog":
            title_elem = soup.select_one('h1.head-title')
        
        # 일반적인 제목 선택자 (다른 사이트용)
        if not title_elem:
            for selector in ['h1.article-title', 'h1.post-title', 'h1.entry-title', 'h1.title']:
                title_elem = soup.select_one(selector)
                if title_elem:
                    break
        
        # 그래도 찾지 못한 경우 첫 번째 h1 태그 사용
        if not title_elem:
            title_elem = soup.select_one('h1')
        
        title = title_elem.text.strip() if title_elem else "제목을 찾을 수 없습니다"
        
        # 여러 컨테이너 후보 탐색 (사이트별 특화)
        containers = []
        
        # 브런치 특화 컨테이너
        if site_type == "brunch":
            containers.extend([
                soup.select_one('div.wrap_body_frame'),  # 브런치 메인 컨텐츠
                soup.select_one('div.article_body'),     # 브런치 본문
                soup.select_one('div.wrap_item')         # 브런치 아이템 래퍼
            ])
        
        # 미디엄 특화 컨테이너
        elif site_type == "medium":
            containers.extend([
                soup.select_one('article'),              # 미디엄 아티클
                soup.select_one('div[data-testid="postContent"]')  # 미디엄 포스트 콘텐츠
            ])
            
        # 벨로그 특화 컨테이너
        elif site_type == "velog":
            containers.extend([
                soup.select_one('div.atom-one'),         # 벨로그 본문
                soup.select_one('div.sc-gZMcBi')         # 벨로그 컨텐츠
            ])
        
        # Wishket 특화 컨테이너
        elif site_type == "wishket":
            containers.extend([
                soup.select_one('div.article-body-container'),  # 위시켓 기본 선택자
                soup.select_one('div.content-body')             # 위시켓 대체 선택자
            ])
        
        # 일반 컨테이너 (대부분의 사이트에 적용 가능)
        containers.extend([
            soup.select_one('article'),                  # 일반 아티클 태그
            soup.select_one('main'),                     # 메인 태그
            soup.select_one('div.article-content'),      # 일반 아티클 콘텐츠
            soup.select_one('div.entry-content'),        # 일반 엔트리 콘텐츠
            soup.select_one('div.post-content'),         # 일반 포스트 콘텐츠
            soup.select_one('div.content')               # 일반 콘텐츠
        ])
        
        # 유효한 컨테이너 필터링
        valid_containers = [c for c in containers if c is not None]
        
        if not valid_containers:
            # 컨테이너를 찾을 수 없는 경우, 대체 방법 시도
            logger.warning("HTML에서 주요 컨테이너를 찾을 수 없습니다. 대체 방법 시도...")
            
            # 전체 텍스트에서 가장 긴 텍스트 블록 찾기
            all_tags = soup.find_all(["p", "div", "article", "section", "main", "span"])
            text_blocks = [(tag, " ".join(tag.text.split())) 
                        for tag in all_tags if tag.text.strip()]
            
            # 길이순 정렬
            text_blocks.sort(key=lambda x: len(x[1]), reverse=True)
            
            if text_blocks:
                # 가장 긴 블록 사용
                content = text_blocks[0][1]
                content = clean_content(content, site_type)
                
                logger.info(f"대체 방법으로 {len(content)}자 추출됨")
                return {
                    'title': title,
                    'content': content,
                    'site_type': site_type
                }
            else:
                return {
                    'title': title, 
                    'content': "내용을 찾을 수 없습니다. HTML 구조가 변경되었을 수 있습니다.",
                    'site_type': site_type
                }
        
        # 가장 많은 텍스트를 포함한 컨테이너 선택
        article_container = max(valid_containers, key=lambda c: len(c.text.strip()))
        
        logger.info(f"선택된 컨테이너: {article_container.name}.{' '.join(article_container.get('class', []))}")
        
        # 다양한 태그에서 내용 추출
        content_elements = []
        
        # p 태그 추출 (길이 제한 없음)
        p_tags = article_container.select('p')
        for p in p_tags:
            p_text = p.text.strip()
            if p_text:
                content_elements.append(p_text)
        
        # div 태그 추출 (길이 제한 낮춤: 20자)
        div_tags = article_container.select('div')
        for div in div_tags:
            div_text = div.text.strip()
            if div_text and len(div_text) > 20:  # 실질적인 내용이 있는 div만
                # 이미 추출된 내용과 중복되지 않는지 확인
                is_duplicate = False
                for existing in content_elements:
                    if div_text in existing or existing in div_text:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    content_elements.append(div_text)
        
        # span 태그도 추가 (길이가 긴 것만)
        span_tags = article_container.select('span')
        for span in span_tags:
            span_text = span.text.strip()
            if span_text and len(span_text) > 30:  # 실질적인 내용이 있는 span만
                # 이미 추출된 내용과 중복되지 않는지 확인
                is_duplicate = False
                for existing in content_elements:
                    if span_text in existing or existing in span_text:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    content_elements.append(span_text)
        
        # li 태그도 추가 (길이 제한 없음)
        li_tags = article_container.select('li')
        for li in li_tags:
            li_text = li.text.strip()
            if li_text:
                # 중복 검사
                is_duplicate = False
                for existing in content_elements:
                    if li_text in existing or existing in li_text:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    content_elements.append(li_text)
        
        # 브런치 특화 처리: figure 태그 내의 figcaption 추가
        if site_type == "brunch":
            for fig in article_container.select('figure'):
                caption = fig.select_one('figcaption')
                if caption and caption.text.strip():
                    content_elements.append(f"[이미지] {caption.text.strip()}")
        
        # 내용이 추출되지 않은 경우 컨테이너 전체 텍스트 사용
        if not content_elements:
            logger.warning("개별 요소에서 내용을 추출할 수 없습니다. 컨테이너 전체 텍스트를 사용합니다.")
            content = article_container.text.strip()
        else:
            # 모든 내용을 합쳐서 하나의 텍스트로
            content = "\n\n".join(content_elements)
        
        # 불필요한 텍스트 제거
        content = clean_content(content, site_type)
        
        logger.info(f"HTML 파일에서 {len(content)}자 추출됨")
        return {
            'title': title,
            'content': content,
            'site_type': site_type
        }
    
    except Exception as e:
        logger.error(f"HTML 파일에서 내용 추출 실패: {e}", exc_info=True)
        return {
            'error': f"HTML 파일에서 내용 추출 중 오류 발생: {str(e)}"
        }

def get_saved_html_files():
    """저장된 HTML 파일 목록을 가져옵니다."""
    page_sources = glob.glob("page_sources/*.html")
    error_pages = glob.glob("error_pages/*.html")
    return sorted(page_sources + error_pages, key=os.path.getmtime, reverse=True)

def clean_content(content, site_type="unknown"):
    """추출된 콘텐츠에서 불필요한 텍스트 제거"""
    # ©️ 문자열 기준으로 내용 잘라내기
    for copyright_marker in ["©️", "©", "ⓒ", "Copyright", "저작권"]:
        if copyright_marker in content:
            content = content.split(copyright_marker)[0]
            break
    
    # 사이트별 제거할 문구 목록
    common_phrases = [
        "목록으로",
        "복사 완료!",
        "공유하기",
        "좋아요",
        "댓글",
        "신고",
        "구독하기"
    ]
    
    site_specific_phrases = {
        "wishket": [
            "요즘IT가 PICK 한 뉴스레터를 매주 목요일 에 만나보세요.",
            "개인정보 수집·이용 에 동의해 주세요. 무료로 구독하기",
            "요즘IT",
            "이메일 주소를 입력해주세요.",
            "현재 글",
            "관련 글 보기"
        ],
        "brunch": [
            "이 글이 좋으셨다면 추천을 눌러주세요",
            "선택한 텍스트를 드래그하여 하이라이트 해보세요",
            "공유하기",
            "브런치에서 보기",
            "작가의 글을 공유하세요",
            "작가의 글에 공감하시면 ♡를 누르세요",
            "작가정보",
            "You can make anything by writing",
            "C.S.Lewis",
            "브런치스토리 홈",
            "브런치스토리 나우",
            "브런치스토리 책방",
            "계정을 잊어버리셨나요?",
            "로그인 회원가입"
        ],
        "medium": [
            "Medium is an open platform where",
            "Read more from",
            "More from",
            "Recommended from Medium",
            "Get the Medium app",
            "A button that says 'Download on the App Store'"
        ],
        "velog": [
            "댓글 작성하기",
            "댓글을 작성하려면",
            "로그인",
            "태그",
            "시리즈에 추가",
            "이 블로그 구독하기"
        ]
    }
    
    # 사이트별 특화 문구 제거
    phrases_to_remove = common_phrases + site_specific_phrases.get(site_type, [])
    
    for phrase in phrases_to_remove:
        content = content.replace(phrase, "")
    
    # 다중 공백 정리
    content = ' '.join(content.split())
    
    # 문단 구분을 위한 줄바꿈 추가
    content = content.replace(". ", ".\n\n")
    
    return content.strip()

def scrape_article(url):
    """여러 사이트의 기사 내용을 스크랩하는 함수"""
    # 사이트 타입 감지
    site_type = detect_site_type(url)
    logger.info(f"스크랩 시작: {url} (사이트 유형: {site_type})")
    
    # Chrome 옵션 설정
    chrome_options = setup_chrome_options()
    
    try:
        with st.spinner('웹 페이지 로딩 중...'):
            # ChromeDriverManager 대신 get_compatible_chromedriver 함수 사용
            service = get_compatible_chromedriver()
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
            
            driver.get(url)
            
            # 사이트별 페이지 로드 대기 설정
            wait_selectors = {
                "wishket": "article",
                "brunch": "div.wrap_body_frame, div.article_body",
                "medium": "article, div[data-testid='postContent']",
                "velog": "div.atom-one, h1.head-title",
                "unknown": "article, main, div.content" 
            }
            
            selector = wait_selectors.get(site_type, wait_selectors["unknown"])
            
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                logger.info("기사 컨텐츠 로드 완료")
            except Exception as e:
                logger.warning(f"기사 콘텐츠 로드 대기 시간 초과: {e}")
            
            # 추가 대기 (동적 로딩 콘텐츠 대기)
            time.sleep(3)
            
            # 페이지 소스 저장
            page_source_file = save_page_source(driver, url)
            st.info(f"HTML 소스 저장됨: {page_source_file}")

        # 사이트별 제목 추출 선택자
        title_selectors = {
            "wishket": ["h1.article-title", "h1"],
            "brunch": ["h1.cover_title", "h1.article_title", "h1"],
            "medium": ["h1[data-testid='article-title']", "h1.pw-post-title", "h1"],
            "velog": ["h1.head-title", "h1"]
        }
        
        selectors = title_selectors.get(site_type, ["h1.article-title", "h1.post-title", "h1.entry-title", "h1"])
        
        # 제목 추출
        title = "제목을 찾을 수 없습니다"
        for selector in selectors:
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, selector)
                title = title_elem.text.strip()
                if title:
                    break
            except Exception:
                continue
                
        # 사이트별 내용 컨테이너 선택자
        content_selectors = {
            "wishket": ["div.article-body-container", "div.content-body"],
            "brunch": ["div.wrap_body_frame", "div.article_body"],
            "medium": ["article", "div[data-testid='postContent']"],
            "velog": ["div.atom-one", "div.sc-gZMcBi"],
            "unknown": ["article", "main", "div.content"]
        }
        
        selectors = content_selectors.get(site_type, content_selectors["unknown"])
        
        # 내용 추출
        content = None
        article_container = None
        
        for selector in selectors:
            try:
                article_container = driver.find_element(By.CSS_SELECTOR, selector)
                if article_container:
                    break
            except Exception:
                continue
                
        if article_container:
            try:
                # 내용 요소 추출
                content_elements = []
                
                # p 태그 추출
                p_tags = article_container.find_elements(By.TAG_NAME, "p")
                for p in p_tags:
                    if p.text.strip():
                        content_elements.append(p.text)
                        
                # div 태그 추출 (중복 방지를 위한 최소 길이 확인)
                div_tags = article_container.find_elements(By.TAG_NAME, "div")
                for div in div_tags:
                    div_text = div.text.strip()
                    # 브런치는 div에 중요 내용이 많으므로 길이 제한 완화
                    min_length = 20 if site_type == "brunch" else 50
                    if div_text and len(div_text) > min_length:
                        # 이미 추출된 내용과 중복되지 않는지 확인
                        is_duplicate = False
                        for existing in content_elements:
                            if div_text in existing or existing in div_text:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            content_elements.append(div_text)
                
                # 브런치 특화: figcaption 처리
                if site_type == "brunch":
                    try:
                        figcaptions = article_container.find_elements(By.TAG_NAME, "figcaption")
                        for caption in figcaptions:
                            if caption.text.strip():
                                content_elements.append(f"[이미지] {caption.text.strip()}")
                    except Exception:
                        pass
                
                # 모든 내용을 합쳐서 하나의 텍스트로
                content = "\n\n".join(content_elements)
                # 불필요한 텍스트 제거
                content = clean_content(content, site_type)
                
            except Exception as e:
                logger.error(f"내용 추출 실패: {e}")
                content = None
        
        # 내용 추출 실패 시 저장된 HTML 파일에서 추출 시도
        if not content:
            st.warning("웹 페이지에서 직접 내용 추출에 실패했습니다. 저장된 HTML 파일에서 추출을 시도합니다...")
            
            html_result = extract_content_from_html(page_source_file)
            if 'error' not in html_result:
                content = html_result['content']
                if title == "제목을 찾을 수 없습니다":
                    title = html_result['title']
                st.success("HTML 파일에서 내용을 성공적으로 추출했습니다!")
            else:
                content = "내용을 찾을 수 없습니다."
                st.error(f"HTML 파일 추출도 실패: {html_result['error']}")
        
        # 드라이버 종료
        driver.quit()
        
        return {
            'title': title,
            'content': content,
            'page_source_file': page_source_file,
            'site_type': site_type
        }

    except Exception as e:
        error_msg = f"스크랩 과정에서 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.error(error_msg)
        
        # 오류 발생 시에도 페이지 소스 저장 시도
        if 'driver' in locals():
            try:
                page_source_file = save_page_source(driver, url, "error_pages")
                st.info(f"오류 상태의 HTML 소스가 {page_source_file}에 저장되었습니다.")
                driver.quit()
            except Exception as e2:
                logger.error(f"오류 처리 중 추가 예외 발생: {e2}")
        
        return {'error': str(e)}

def create_copy_button(text, button_text="복사하기"):
    """클립보드에 복사하는 버튼 생성"""
    import json
    from streamlit.components.v1 import html
    
    # 텍스트를 이스케이프하여 JavaScript에서 안전하게 사용할 수 있도록 함
    escaped_text = json.dumps(text)
    
    # 복사 버튼 HTML/JavaScript 코드
    copy_button_html = f"""
    <script>
    function copyToClipboard() {{
        const text = {escaped_text};
        navigator.clipboard.writeText(text)
            .then(() => {{
                const btn = document.getElementById('copyButton');
                btn.innerHTML = '복사 완료!';
                setTimeout(() => {{
                    btn.innerHTML = '{button_text}';
                }}, 2000);
            }})
            .catch(err => {{
                console.error('클립보드 복사 실패:', err);
                alert('클립보드 복사에 실패했습니다.');
            }});
    }}
    </script>
    <button id="copyButton" onclick="copyToClipboard()" 
        style="background-color: #4CAF50; color: white; border: none; 
        padding: 8px 16px; text-align: center; text-decoration: none; 
        display: inline-block; font-size: 14px; margin: 4px 2px; cursor: pointer; 
        border-radius: 4px;">
        {button_text}
    </button>
    """
    
    # HTML 컴포넌트로 렌더링
    html(copy_button_html, height=50)

# 메인 UI
st.sidebar.title("옵션")
mode = st.sidebar.radio("작업 모드 선택", ["웹 스크래핑", "저장된 HTML 파일 읽기"])

if mode == "웹 스크래핑":
    # URL 입력 필드 (기본값 제거)
    url = st.text_input("스크랩핑할 기사 URL 입력", "")
    
    # 사이트 예시 제공
    st.caption("지원 사이트 예시: 브런치(brunch.co.kr), 미디엄(medium.com), 벨로그(velog.io) 등")
    
    # 결과 저장 변수 초기화
    if 'results' not in st.session_state:
        st.session_state.results = None

    # 스크랩 버튼
    if st.button("스크랩 실행"):
        if url:
            with st.spinner('기사 스크랩 중...'):
                st.session_state.results = scrape_article(url)
        else:
            st.warning("URL을 입력해주세요.")
else:  # 저장된 HTML 파일 읽기 모드
    html_files = get_saved_html_files()
    
    if not html_files:
        st.warning("저장된 HTML 파일이 없습니다. 먼저 웹 스크래핑 모드에서 기사를 스크랩해주세요.")
    else:
        selected_file = st.selectbox("분석할 HTML 파일 선택", html_files, format_func=lambda x: f"{os.path.basename(x)} ({datetime.fromtimestamp(os.path.getmtime(x)).strftime('%Y-%m-%d %H:%M:%S')})")
        
        if st.button("HTML 파일 분석"):
            with st.spinner('HTML 파일에서 내용 추출 중...'):
                st.session_state.results = extract_content_from_html(selected_file)
                st.session_state.results['page_source_file'] = selected_file
                st.success("HTML 파일 분석 완료!")
            
# 결과 표시
if st.session_state and 'results' in st.session_state and st.session_state.results:
    if 'error' in st.session_state.results:
        st.error(f"오류가 발생했습니다: {st.session_state.results['error']}")
        
        # 오류 발생 시에도 HTML 소스가 저장되었다고 알림
        if 'page_source_file' in st.session_state.results and st.session_state.results['page_source_file']:
            html_path = st.session_state.results['page_source_file']
            st.info(f"오류 페이지 HTML이 저장되었습니다: {html_path}")
    else:
        # 사이트 유형 표시
        site_type = st.session_state.results.get('site_type', 'unknown')
        st.info(f"사이트 유형: {site_type}")
        
        # 제목 표시
        st.subheader(f"제목: {st.session_state.results['title']}")
        
        # HTML 소스 파일 정보
        if 'page_source_file' in st.session_state.results:
            html_path = st.session_state.results['page_source_file']
            st.info(f"HTML 소스: {html_path}")
        
        # 콘텐츠 표시
        st.markdown("### 추출된 내용")
        # 텍스트 영역으로 표시 (원본 그대로 표시)
        st.text_area("전체 내용", st.session_state.results['content'], 
                   height=400, disabled=False, key="content")
        
        st.caption(f"추출된 내용 길이: {len(st.session_state.results['content'])} 글자")
        
        # 복사 기능
        st.markdown("### 내용 복사하기")
        create_copy_button(st.session_state.results['content'], "본문 복사하기")

# HTML 디버깅을 위한 함수 추가
st.sidebar.markdown("---")
st.sidebar.subheader("HTML 디버깅")
debug_mode = st.sidebar.checkbox("HTML 구조 디버깅 모드")

if debug_mode and 'results' in st.session_state and st.session_state.results and 'page_source_file' in st.session_state.results:
    st.sidebar.markdown("#### HTML 요소 검사")
    html_file = st.session_state.results['page_source_file']
    
    if os.path.exists(html_file):
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 사이트 유형별 선택자 설정
        site_type = st.session_state.results.get('site_type', 'unknown')
        
        # 사이트별 주요 컨테이너 선택자
        container_selectors = {
            "wishket": "div.article-body-container, div.content-body",
            "brunch": "div.wrap_body_frame, div.article_body",
            "medium": "article, div[data-testid='postContent']",
            "velog": "div.atom-one, div.sc-gZMcBi",
            "unknown": "div.article-body-container, div.content-body, article, main, div.article-content, div.content"
        }
        
        selector = container_selectors.get(site_type, container_selectors["unknown"])
        
        # 주요 구조 분석
        st.sidebar.markdown(f"##### 주요 HTML 구조 ({site_type})")
        main_containers = soup.select(selector)
        
        if main_containers:
            st.sidebar.success(f"{len(main_containers)}개의 주요 컨테이너 찾음")
            container_selector = st.sidebar.selectbox(
                "분석할 컨테이너 선택", 
                options=range(len(main_containers)),
                format_func=lambda i: f"{main_containers[i].name}.{' '.join(main_containers[i].get('class', []))} ({len(main_containers[i].text)}자)"
            )
            
            selected_container = main_containers[container_selector]
            
            # 요소별 분석
            st.sidebar.markdown("##### 내부 요소 분석")
            
            # P 태그 분석
            p_tags = selected_container.select("p")
            st.sidebar.text(f"P 태그 수: {len(p_tags)}")
            if p_tags:
                p_content = "\n".join([f"{i+1}. ({len(p.text)}자) {p.text[:50]}..." for i, p in enumerate(p_tags) if p.text.strip()])
                st.sidebar.text_area("P 태그 미리보기", p_content, height=100)
            
            # DIV 태그 분석 (내용이 있는 것만)
            div_tags = [div for div in selected_container.select("div") if div.text.strip() and len(div.text.strip()) > 20]
            st.sidebar.text(f"의미있는 DIV 태그 수: {len(div_tags)}")
            if div_tags:
                div_content = "\n".join([f"{i+1}. ({len(div.text)}자) {div.text[:50]}..." for i, div in enumerate(div_tags)])
                st.sidebar.text_area("DIV 태그 미리보기", div_content, height=100)
            
            # 테스트 추출
            if st.sidebar.button("선택 컨테이너로 추출 테스트"):
                test_elements = []
                # P 태그 추출 (길이 제한 없음)
                for p in selected_container.select("p"):
                    if p.text.strip():
                        test_elements.append(p.text.strip())
                
                # DIV 태그 추출 (길이 제한 낮춤: 20자)
                for div in selected_container.select("div"):
                    div_text = div.text.strip()
                    if div_text and len(div_text) > 20:
                        # 중복 방지
                        is_duplicate = False
                        for existing in test_elements:
                            if div_text in existing or existing in div_text:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            test_elements.append(div_text)
                
                # SPAN 태그도 추가 (길이가 길면)
                for span in selected_container.select("span"):
                    span_text = span.text.strip()
                    if span_text and len(span_text) > 30:
                        # 중복 방지
                        is_duplicate = False
                        for existing in test_elements:
                            if span_text in existing or existing in span_text:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            test_elements.append(span_text)
                
                test_content = "\n\n".join(test_elements)
                test_content = clean_content(test_content)
                
                st.text_area("테스트 추출 결과", test_content, height=300)
                st.caption(f"추출된 내용 길이: {len(test_content)} 글자")
        else:
            st.sidebar.error("주요 컨테이너를 찾을 수 없습니다")
            
            # 대체 방법 제안
            st.sidebar.markdown("##### 대체 방법 제안")
            
            # 전체 텍스트에서 가장 긴 텍스트 블록 찾기
            all_tags = soup.find_all(["p", "div", "article", "section", "main", "span"])
            text_blocks = [(tag.name, " ".join(tag.text.split()), len(" ".join(tag.text.split()))) 
                          for tag in all_tags if tag.text.strip()]
            
            # 길이순 정렬
            text_blocks.sort(key=lambda x: x[2], reverse=True)
            
            # 상위 5개 보여주기
            st.sidebar.text("가장 긴 텍스트 블록:")
            for i, (tag_name, text, length) in enumerate(text_blocks[:5]):
                st.sidebar.text(f"{i+1}. {tag_name}: {length}자 - {text[:50]}...")
                
            # 가장 긴 블록으로 테스트
            if st.sidebar.button("가장 긴 블록으로 테스트"):
                if text_blocks:
                    longest_text = text_blocks[0][1]
                    st.text_area("가장 긴 블록 내용", longest_text, height=300)
                    st.caption(f"블록 길이: {len(longest_text)} 글자")
    else:
        st.sidebar.error(f"HTML 파일을 찾을 수 없습니다: {html_file}")