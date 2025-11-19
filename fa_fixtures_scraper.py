"""
FA Full-Time Fixtures Scraper
Handles scraping fixture data from FA Full-Time website, including CAPTCHA challenges
"""

import re
import time
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from fa_fixture_parser import FAFixtureParser

logger = logging.getLogger(__name__)


class FAFixturesScraper:
    """Scraper for FA Full-Time fixtures pages"""
    
    def __init__(self, headless: bool = True, wait_for_captcha: bool = True):
        """
        Initialize the scraper
        
        Args:
            headless: Whether to run browser in headless mode
            wait_for_captcha: Whether to wait for CAPTCHA to be solved manually
        """
        self.headless = headless
        self.wait_for_captcha = wait_for_captcha
        self.parser = FAFixtureParser()
        self.driver = None
        
    def __enter__(self):
        """Context manager entry"""
        self.setup_driver()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
        
    def setup_driver(self):
        """Setup Selenium WebDriver"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless=new')  # Use new headless mode
        else:
            # Non-headless: ensure browser stays open and visible
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_experimental_option("detach", True)  # Keep browser open
        
        # Add options to avoid detection
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Additional options for better compatibility
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            # Execute script to avoid detection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            if not self.headless:
                logger.info("Selenium WebDriver initialized in VISIBLE mode - browser window will open for CAPTCHA solving")
            else:
                logger.info("Selenium WebDriver initialized in HEADLESS mode")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def cleanup(self):
        """Cleanup WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.warning(f"Error closing WebDriver: {e}")
    
    def wait_for_page_load(self, timeout: int = 30):
        """Wait for page to load completely"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)  # Additional wait for dynamic content
        except TimeoutException:
            logger.warning("Page load timeout")
    
    def detect_captcha(self) -> bool:
        """Detect if CAPTCHA is present on the page"""
        try:
            # Check page source for CAPTCHA indicators
            page_source = self.driver.page_source.lower()
            page_url = self.driver.current_url.lower()
            
            # Check for various CAPTCHA indicators
            captcha_indicators = [
                "recaptcha" in page_source,
                "captcha" in page_source and ("solve" in page_source or "verify" in page_source),
                "cloudflare" in page_source and ("challenge" in page_source or "checking" in page_source),
                "i'm not a robot" in page_source,
                "verify you're human" in page_source,
                "blocked" in page_source or "blocked" in page_url,
                "access denied" in page_source or "access denied" in page_url
            ]
            
            if any(captcha_indicators):
                return True
            
            # Check for CAPTCHA iframes and elements
            captcha_selectors = [
                "iframe[src*='recaptcha']",
                "iframe[src*='challenges.cloudflare.com']",
                "div[class*='recaptcha']",
                "div[id*='captcha']",
                "div[class*='cf-challenge']"
            ]
            
            for selector in captcha_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"Error detecting CAPTCHA: {e}")
            return False
    
    def handle_captcha(self, timeout: int = 60):
        """
        Handle CAPTCHA challenge
        
        Args:
            timeout: Maximum time to wait for CAPTCHA to be solved (in seconds)
            
        Returns:
            bool: True if CAPTCHA was solved or not present, False if still present after timeout
        """
        if not self.wait_for_captcha:
            logger.info("CAPTCHA handling disabled, proceeding without wait")
            return True
        
        try:
            # Wait a moment for page to load
            time.sleep(2)
            
            # Check if CAPTCHA is present
            if not self.detect_captcha():
                logger.info("No CAPTCHA detected, proceeding")
                return True
            
            logger.warning("⚠️ CAPTCHA detected on FA website!")
            
            # In headless mode, try to solve using CAPTCHA solving service or fail gracefully
            if self.headless:
                logger.warning("🔍 Running in headless mode - attempting automatic CAPTCHA solving...")
                
                # Try to use CAPTCHA solving service (if configured)
                captcha_solved = self._try_solve_captcha_headless()
                
                if not captcha_solved:
                    logger.error("❌ Could not solve CAPTCHA automatically in headless mode.")
                    logger.info("💡 Solutions:")
                    logger.info("   1. Try running again - sometimes CAPTCHA doesn't appear")
                    logger.info("   2. Use non-headless mode to manually solve CAPTCHA")
                    logger.info("   3. Use the 'Paste FA Data' method instead")
                    raise Exception("CAPTCHA detected in headless mode and could not be solved automatically. Please use non-headless mode or the 'Paste FA Data' method.")
                
                return True
            
            # Non-headless mode - open browser and wait for user to solve
            logger.info("🌐 Opening browser window for manual CAPTCHA solving...")
            logger.info("📋 Instructions:")
            logger.info("   1. A browser window will open showing the FA website")
            logger.info("   2. Solve the CAPTCHA in the browser window")
            logger.info("   3. Wait for the page to load after solving")
            logger.info("   4. The scraper will automatically detect when CAPTCHA is solved")
            logger.info(f"⏳ Waiting up to {timeout} seconds for you to solve the CAPTCHA...")
            
            # Make sure browser window is visible and focused
            try:
                self.driver.maximize_window()
                # Bring window to front (platform-specific)
                import platform
                if platform.system() == 'Darwin':  # macOS
                    self.driver.execute_script("window.focus();")
            except:
                pass
            
            start_time = time.time()
            last_log_time = start_time
            check_interval = 3
            
            while time.time() - start_time < timeout:
                try:
                    # Check if CAPTCHA is still present
                    if not self.detect_captcha():
                        # Wait a bit more to ensure page fully loads
                        time.sleep(3)
                        if not self.detect_captcha():
                            elapsed = time.time() - start_time
                            logger.info(f"✅ CAPTCHA appears to be solved! (took {elapsed:.1f} seconds)")
                            return True
                    
                    # Log progress every 15 seconds
                    elapsed = time.time() - start_time
                    if elapsed - (last_log_time - start_time) >= 15:
                        remaining = int(timeout - elapsed)
                        logger.info(f"⏳ Still waiting for CAPTCHA to be solved... ({remaining} seconds remaining)")
                        logger.info(f"   Current URL: {self.driver.current_url}")
                        last_log_time = time.time()
                    
                except Exception as e:
                    logger.debug(f"Error checking CAPTCHA status: {e}")
                
                time.sleep(check_interval)
            
            # Timeout reached
            elapsed = time.time() - start_time
            logger.warning(f"⏱️ Timeout after {timeout} seconds.")
            
            # Final check
            if not self.detect_captcha():
                logger.info("✅ CAPTCHA appears to be solved on final check")
                return True
            
            logger.error("❌ CAPTCHA still present after timeout")
            logger.info("💡 The browser window may still be open. You can:")
            logger.info("   1. Solve the CAPTCHA now and the scraper will continue")
            logger.info("   2. Or try running the import again")
            raise Exception(f"CAPTCHA was not solved within {timeout} seconds. Please solve it in the browser window or try again.")
                
        except Exception as e:
            logger.error(f"Error handling CAPTCHA: {e}")
            raise
    
    def _try_solve_captcha_headless(self) -> bool:
        """
        Attempt to solve CAPTCHA in headless mode using external services
        
        Returns:
            bool: True if CAPTCHA was solved, False otherwise
        """
        try:
            # Option 1: Try using 2captcha or similar service (if API key configured)
            api_key = os.environ.get('CAPTCHA_API_KEY') or os.environ.get('2CAPTCHA_API_KEY')
            
            if api_key:
                logger.info("🔑 CAPTCHA API key found, attempting automatic solving...")
                return self._solve_with_captcha_service(api_key)
            
            # Option 2: Try waiting a bit - sometimes CAPTCHA auto-solves
            logger.info("⏳ Waiting 10 seconds to see if CAPTCHA auto-solves...")
            time.sleep(10)
            
            if not self.detect_captcha():
                logger.info("✅ CAPTCHA appears to have been auto-solved")
                return True
            
            # Option 3: Try using stealth mode or other techniques
            logger.info("🔍 Attempting alternative CAPTCHA bypass methods...")
            
            # Refresh page - sometimes helps
            try:
                self.driver.refresh()
                self.wait_for_page_load()
                time.sleep(5)
                if not self.detect_captcha():
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.debug(f"Error in automatic CAPTCHA solving: {e}")
            return False
    
    def _solve_with_captcha_service(self, api_key: str) -> bool:
        """
        Solve CAPTCHA using 2captcha or similar service
        
        Args:
            api_key: API key for CAPTCHA solving service
            
        Returns:
            bool: True if solved, False otherwise
        """
        try:
            # Look for reCAPTCHA site key
            site_key = None
            try:
                recaptcha_iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
                if recaptcha_iframe:
                    iframe_src = recaptcha_iframe.get_attribute('src')
                    import re
                    match = re.search(r'k=([^&]+)', iframe_src)
                    if match:
                        site_key = match.group(1)
            except:
                pass
            
            if not site_key:
                logger.warning("Could not find reCAPTCHA site key")
                return False
            
            logger.info(f"Found reCAPTCHA site key: {site_key[:20]}...")
            logger.info("Submitting to CAPTCHA solving service...")
            
            # Here you would integrate with 2captcha API
            # For now, this is a placeholder - you'd need to:
            # 1. Submit CAPTCHA to 2captcha API
            # 2. Poll for result
            # 3. Inject solution token into page
            
            # Placeholder - actual implementation would use 2captcha API
            logger.warning("CAPTCHA solving service integration not yet implemented")
            return False
            
        except Exception as e:
            logger.debug(f"Error using CAPTCHA service: {e}")
            return False
    
    def scrape_fixtures_page(self, url: str, team_name: Optional[str] = None) -> List[Dict]:
        """
        Scrape fixtures from FA Full-Time page
        
        Args:
            url: URL of the FA fixtures page
            team_name: Optional team name for filtering/validation
            
        Returns:
            List of fixture dictionaries
        """
        if not self.driver:
            self.setup_driver()
        
        logger.info(f"Scraping fixtures from: {url}")
        
        try:
            # Navigate to the page
            logger.info("Navigating to FA website...")
            self.driver.get(url)
            self.wait_for_page_load()
            
            # Handle CAPTCHA if needed - this will raise an exception if CAPTCHA can't be solved
            captcha_solved = self.handle_captcha(timeout=120)  # 2 minute timeout
            
            if not captcha_solved:
                raise Exception("CAPTCHA was not solved. Please try again or use the 'Paste FA Data' import method.")
            
            # Wait a bit more for any JavaScript to load content
            time.sleep(3)
            
            # Get page source
            page_source = self.driver.page_source
            
            # Final check if we were blocked or CAPTCHA not solved
            page_lower = page_source.lower()
            if any([
                "blocked" in page_lower and ("captcha" in page_lower or "challenge" in page_lower),
                "access denied" in page_lower,
                "captcha" in page_lower and ("solve" in page_lower or "verify" in page_lower or "robot" in page_lower)
            ]):
                # Double-check with detection method
                if self.detect_captcha():
                    raise Exception("CAPTCHA detected on final check. The page may still be showing a CAPTCHA challenge. Please try the 'Paste FA Data' import method instead.")
            
            # Parse fixtures from page
            fixtures = self.parse_fixtures_from_html(page_source, team_name)
            
            logger.info(f"Successfully scraped {len(fixtures)} fixtures")
            return fixtures
            
        except Exception as e:
            logger.error(f"Error scraping fixtures: {e}")
            raise
    
    def parse_fixtures_from_html(self, html: str, team_name: Optional[str] = None) -> List[Dict]:
        """
        Parse fixtures from HTML content
        
        Args:
            html: HTML content of the fixtures page
            team_name: Optional team name for validation
            
        Returns:
            List of fixture dictionaries
        """
        fixtures = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for fixture tables or lists
        # FA Full-Time typically uses tables for fixtures
        fixture_tables = soup.find_all('table', class_=re.compile(r'fixture|match|game', re.I))
        
        if not fixture_tables:
            # Try finding by other common selectors
            fixture_tables = soup.find_all(['table', 'div'], class_=re.compile(r'fixture|result', re.I))
        
        if not fixture_tables:
            logger.warning("No fixture tables found in HTML, trying alternative parsing")
            # Try parsing all table rows
            all_tables = soup.find_all('table')
            for table in all_tables:
                rows = table.find_all('tr')
                if len(rows) > 3:  # Likely a fixture table
                    fixture_tables.append(table)
        
        for table in fixture_tables:
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                try:
                    # Try to extract fixture information
                    # FA Full-Time format varies, so we'll try multiple approaches
                    
                    # Method 1: Look for text content that matches fixture patterns
                    row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                    
                    # Try parsing with existing FA fixture parser
                    parsed = self.parser.parse_single_fa_line(row_text)
                    if parsed:
                        # Add source information
                        parsed['source'] = 'fa_scraper'
                        parsed['scraped_at'] = datetime.utcnow().isoformat()
                        fixtures.append(parsed)
                    else:
                        # Method 2: Try manual parsing of table cells
                        fixture_data = self._parse_table_row(cells, row_text)
                        if fixture_data:
                            fixture_data['source'] = 'fa_scraper'
                            fixture_data['scraped_at'] = datetime.utcnow().isoformat()
                            fixtures.append(fixture_data)
                            
                except Exception as e:
                    logger.debug(f"Error parsing row: {e}")
                    continue
        
        # If no fixtures found in tables, try extracting from text content
        if not fixtures:
            logger.info("No fixtures found in tables, trying text extraction")
            page_text = soup.get_text('\n')
            # Extract lines that look like fixtures
            lines = page_text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line looks like a fixture (has date, teams, etc.)
                if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line):  # Date pattern
                    parsed = self.parser.parse_single_fa_line(line)
                    if parsed:
                        parsed['source'] = 'fa_scraper'
                        parsed['scraped_at'] = datetime.utcnow().isoformat()
                        fixtures.append(parsed)
        
        return fixtures
    
    def _parse_table_row(self, cells: List, row_text: str) -> Optional[Dict]:
        """
        Parse a table row into fixture data
        
        Args:
            cells: List of table cells
            row_text: Full text of the row
            
        Returns:
            Fixture dictionary or None
        """
        # This is a simplified parser - may need adjustment based on actual FA page structure
        try:
            fixture = {}
            
            # Look for date patterns
            date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', row_text)
            if date_match:
                day, month, year = date_match.groups()
                year = int(year) if len(year) == 4 else 2000 + int(year)
                try:
                    fixture['date'] = datetime(int(year), int(month), int(day))
                except:
                    pass
            
            # Look for time patterns
            time_match = re.search(r'(\d{1,2}):(\d{2})', row_text)
            if time_match:
                hour, minute = time_match.groups()
                fixture['kickoff_time'] = f"{hour}:{minute}"
            
            # Look for team names (usually in specific columns)
            if len(cells) >= 3:
                # Common patterns: Home Team vs Away Team
                for cell in cells:
                    text = cell.get_text(strip=True)
                    if 'vs' in text.lower() or 'v' in text.lower():
                        parts = re.split(r'\s+[vV][sS]?\s+', text)
                        if len(parts) == 2:
                            fixture['home_team'] = parts[0].strip()
                            fixture['away_team'] = parts[1].strip()
                    elif text and len(text) > 3 and not re.match(r'^\d+[/:-]\d+', text):
                        # Could be a team name
                        if 'home_team' not in fixture:
                            fixture['home_team'] = text
                        elif 'away_team' not in fixture:
                            fixture['away_team'] = text
            
            # Only return if we have essential data
            if 'home_team' in fixture or 'away_team' in fixture:
                return fixture
                
        except Exception as e:
            logger.debug(f"Error in _parse_table_row: {e}")
        
        return None


def scrape_team_fixtures(url: str, team_name: Optional[str] = None, headless: bool = True) -> List[Dict]:
    """
    Convenience function to scrape fixtures for a team
    
    Args:
        url: FA fixtures page URL
        team_name: Optional team name
        headless: Whether to run browser in headless mode
        
    Returns:
        List of fixture dictionaries
    """
    with FAFixturesScraper(headless=headless) as scraper:
        return scraper.scrape_fixtures_page(url, team_name)

