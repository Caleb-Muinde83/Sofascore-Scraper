import re
import time
import random
import traceback
from datetime import datetime
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException,
    WebDriverException
)
from selenium.webdriver.common.action_chains import ActionChains

from .logger import get_logger
from .config import ScrapingConfig
from .utils import parse_datetime_from_text, retry
from .persistence import load_data, save_data

logger = get_logger(__name__, log_file="scraper.log", level=logging.DEBUG)


class SofaScoreEPLScraper:
    def __init__(self, headless=True, implicit_wait=10):
        self.base_url = "https://www.sofascore.com/tournament/football/england/premier-league/17"
        self.headless = headless
        self.implicit_wait = implicit_wait
        self.driver = None
        self.wait = None
        self.original_tab = None
        self.all_match_data = load_data()
        self.logger = logger
        self.config = ScrapingConfig

        logger.info("SofaScoreEPLScraper initialized.")


    # --- Driver Management & Utilities ---
    def setup_driver(self):
        logger.info("Setting up Selenium WebDriver...")
        opts = Options()
        if self.headless:
            logger.info("Running Chrome in headless mode.")
            opts.add_argument("--headless=new")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-software-rasterizer")
            opts.add_argument("--enable-unsafe-webgpu")
            opts.add_argument("--enable-unsafe-swiftshader")
            opts.add_argument("--incognito")
            opts.add_argument("--disable-cache")
            opts.add_argument("--disable-application-cache")
            opts.add_argument("--disk-cache-size=0")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--disable-blink-features=AutomationControlled")

        self.driver = webdriver.Chrome(options=opts)
        self.driver.implicitly_wait(self.implicit_wait)
        self.wait = WebDriverWait(self.driver, 15)
        self.original_tab = self.driver.current_window_handle
        logger.info("WebDriver setup complete.")

    def quit(self):
        if self.driver:
            try:
                if hasattr(self.driver, "session_id") and self.driver.session_id is not None:
                    logger.info("Quitting WebDriver...")
                    self.driver.quit()
                    logger.info("WebDriver quit successfully.")
                else:
                    logger.info("WebDriver session already closed.")
            except Exception as e:
                logger.warning(f"Error during driver.quit(): {e}")

    @retry(retries=3, backoff=1)
    def dismiss_cookies(self):
        logger.info("Attempting to dismiss cookie consent popups...")
        selectors = [
            (By.ID, "onetrust-accept-btn-handler"),
            (By.CSS_SELECTOR, "button.css-1ohyq2v"),
            (By.CSS_SELECTOR, "div.ot-sdk-row button.ot-accept-btn"),
            (By.XPATH, "//button[contains(., 'Accept All') or contains(., 'Consent')]"),
            (By.XPATH, "//button[contains(., 'Accept cookies') or contains(., 'Allow all')]"),
        ]
        for by, sel in selectors:
            try:
                btn = self.wait.until(EC.element_to_be_clickable((by, sel)))
                btn.click()
                logger.info(f"Clicked cookie button: {by} {sel}")
                time.sleep(1)
                return True
            except Exception:
                continue
        logger.warning("No cookie popups found or clickable.")
        return False

    def safe_click(self, elt, retries=3):
        for i in range(retries):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elt)
                time.sleep(0.2)
                elt.click()
                logger.info("Clicked element successfully.")
                return True
            except (ElementClickInterceptedException, StaleElementReferenceException) as e:
                logger.warning(f"Click interception on attempt {i+1}: {e}")
                try:
                    self.driver.execute_script("arguments[0].click();", elt)
                    logger.info("Clicked element using JS fallback.")
                    return True
                except Exception as e2:
                    logger.warning(f"JS click failed: {e2}")
                    time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Unexpected click error: {e}")
                time.sleep(0.5)
        logger.error("Failed to click element after retries.")
        return False

    def safe_find(self, by, sel, timeout=30):
        logger.debug(f"Looking for element: {by} {sel}")
        try:
            elt = self.wait.until(EC.presence_of_element_located((by, sel)))
            logger.debug("Element found.")
            return elt
        except TimeoutException:
            logger.warning(f"Element not found: {by} {sel}")
            return None

    def safe_find_all(self, by, sel, timeout=30):
        logger.debug(f"Looking for multiple elements: {by} {sel}")
        try:
            self.wait.until(EC.presence_of_all_elements_located((by, sel)))
            elements = self.driver.find_elements(by, sel)
            logger.debug(f"Found {len(elements)} elements.")
            return elements
        except TimeoutException:
            logger.warning(f"No elements found: {by} {sel}")
            return []

    # --- Page Navigation & Interaction ---
    def _is_season_selected(self, season):
        elt = self.safe_find(By.CSS_SELECTOR, ScrapingConfig.CURRENT_SEASON_TEXT_SELECTOR)
        result = elt and elt.text.strip() == season
        logger.info(f"Season {season} is currently selected: {result}")
        return result

    def select_season(self, season="24/25"):
        logger.info(f"Selecting season {season}...")
        if self._is_season_selected(season):
            logger.info(f"Season {season} already selected.")
            return True

        btn = self.safe_find(By.CSS_SELECTOR, ScrapingConfig.SEASON_DROPDOWN_SELECTOR)
        if not btn or not self.safe_click(btn):
            logger.warning("Failed to open season dropdown.")
            return False
        time.sleep(ScrapingConfig.DROPDOWN_WAIT_TIME)

        xpath = ScrapingConfig.SEASON_OPTION_XPATH.format(season=season)
        opt = self.safe_find(By.XPATH, xpath, timeout=30)
        if not opt or not self.safe_click(opt):
            logger.warning(f"Failed to select season option {season}.")
            return False

        time.sleep(ScrapingConfig.PAGE_RELOAD_WAIT)
        logger.info(f"Season {season} selected successfully.")
        return True

    def _extract_round(self):
        elt = self.safe_find(By.CSS_SELECTOR, ScrapingConfig.ROUND_TEXT_SELECTOR)
        if not elt:
            logger.warning("Could not extract current round.")
            return None
        m = re.search(r"Round (\d+)", elt.text.strip())
        round_num = int(m.group(1)) if m else None
        logger.info(f"Detected current round: {round_num}")
        return round_num

    def navigate_to_round(self, target):
        logger.info(f"Navigating to round {target}...")
        current = self._extract_round()
        if current == target:
            logger.info(f"Already on round {target}.")
            return True

        btn = self.safe_find(By.CSS_SELECTOR, ScrapingConfig.ROUND_DROPDOWN_BUTTON)
        if btn and self.safe_click(btn):
            time.sleep(ScrapingConfig.DROPDOWN_WAIT_TIME)
            xpath = f"//ul[@role='listbox']//li[@role='option' and text()='Round {target}']"
            opt = self.safe_find(By.XPATH, xpath, timeout=30)
            if opt and self.safe_click(opt):
                time.sleep(ScrapingConfig.PAGE_RELOAD_WAIT)
                logger.info(f"Round {target} selected via dropdown.")
                return True

        diff = target - (current or 0)
        selector = ScrapingConfig.NEXT_ROUND_ARROW if diff > 0 else ScrapingConfig.PREV_ROUND_ARROW
        for _ in range(abs(diff)):
            arrow = self.safe_find(By.CSS_SELECTOR, selector)
            if not arrow or not self.safe_click(arrow):
                logger.error(f"Failed to navigate using arrows to round {target}.")
                return False
            time.sleep(ScrapingConfig.SCROLL_PAUSE_TIME)
        time.sleep(ScrapingConfig.PAGE_RELOAD_WAIT)
        logger.info(f"Successfully navigated to round {target}.")
        return True

    def get_match_links(self):
        logger.info("Extracting match links...")
        elems = self.safe_find_all(By.CSS_SELECTOR, ScrapingConfig.MATCH_LINK_SELECTOR)
        links = []
        for e in elems:
            href = e.get_attribute('href') or ''
            if '/football/match/' in href:
                full = href if href.startswith('http') else f"https://www.sofascore.com{href}"
                mid = re.search(r'#id:(\d+)', href)
                match_id = mid.group(1) if mid else href.rstrip('/').split('/')[-1]
                links.append({'url': full, 'match_id': match_id})
        logger.info(f"Found {len(links)} match links.")
        return links

    # --- Main Scraping Logic ---
    def scrape_match(self, url, matchday=None):
        if matchday is None:
            matchday = self._extract_round()
        logger.info(f"Scraping match page: {url} (Matchday {matchday})")

        data = {}
        try:
            # Open new tab and navigate
            self.driver.execute_script("window.open('');")
            tab = self.driver.window_handles[-1]
            self.driver.switch_to.window(tab)
            time.sleep(ScrapingConfig.TAB_OPEN_WAIT)
            self.driver.get(url)
            time.sleep(3)

            # --- Main match data extraction ---
            data = {
                'matchday': matchday,
                'date_time_info': self._get_date_time(),
                'teams': self._get_teams(),
                'venue': self._get_venue(),
                'referee': self._get_referee(),
                'odds': self._get_odds(),
                'crowd_voting': self._get_crowd_voting(),
                'statistics': self._get_stats(),
                #'commentary': self._get_commentary()  # ✅ Added here
            }

            logger.info(f"Scraping complete for {url} (Matchday {matchday})")

        except KeyboardInterrupt:
            logger.warning("Scraping manually interrupted!")
            raise
        except WebDriverException as e:
            logger.error(f"Failed to load page {url}: {e}")
            logger.debug(traceback.format_exc())
            data = {}
        except Exception as e:
            logger.error(f"Unexpected error while scraping {url}: {e}")
            logger.debug(traceback.format_exc())
            data = {}

        finally:
            # Close tab and return to original
            try:
                if (
                    hasattr(self.driver, "session_id")
                    and self.driver.session_id is not None
                    and self.driver.window_handles
                ):
                    self.driver.close()
                    self.driver.switch_to.window(self.original_tab)
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"Error closing tab or switching window: {e}")

        return data
    
    # --- Data Extraction Helpers (private methods) ---
    def _get_date_time(self):
        logger.info("Extracting date and time...")
        cnt = self.safe_find(By.CSS_SELECTOR, ScrapingConfig.MATCH_DATE_TIME_CONTAINER)
        if cnt:
            spans = cnt.find_elements(By.TAG_NAME, "span")
            if len(spans) >= 2:
                dt = spans[1].text.strip().split('\n')
                if len(dt) >= 2:
                    result = {'date_time': f"{dt[0]} {dt[1]}", 'date': dt[0], 'time': dt[1]}
                    logger.info(f"Date & time extracted: {result}")
                    return result

        text = self.driver.find_element(By.TAG_NAME, 'body').text
        parsed = parse_datetime_from_text(text)
        logger.info(f"Fallback date & time parsed: {parsed}")
        return parsed or {'date_time': 'Not found', 'date': 'Not found', 'time': 'Not found'}

    def _get_teams(self):
        logger.info("Extracting team names...")
        imgs = self.safe_find_all(By.CSS_SELECTOR, ScrapingConfig.TEAM_SELECTOR)
        home = imgs[0].get_attribute('alt').strip() if len(imgs) > 0 else "N/A"
        away = imgs[1].get_attribute('alt').strip() if len(imgs) > 1 else "N/A"
        logger.info(f"Teams: Home = {home}, Away = {away}")
        return {'home_team': home, 'away_team': away}

    def _get_venue(self):
        self.logger.info("Extracting venue info...")
        try:
            name = "N/A"
            location = "N/A"

            venue_blocks = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div[class*='bg_surface'][class*='elevation_2']"
            )

            for block in venue_blocks:
                block_text = block.text

                if "Name" in block_text or "Location" in block_text:
                    name_elements = block.find_elements(
                        By.XPATH,
                        ".//span[preceding-sibling::span[contains(text(), 'Name')]]"
                    )
                    if name_elements:
                        name = name_elements[0].text.strip()

                    location_elements = block.find_elements(
                        By.XPATH,
                        ".//span[preceding-sibling::span[contains(text(), 'Location')]]"
                    )
                    if location_elements:
                        location = location_elements[0].text.strip()

                    if name != "N/A" or location != "N/A":
                        break

            if name == "N/A":
                name_candidates = self.driver.find_elements(
                    By.XPATH,
                    "//span[contains(text(), 'Stadium') or contains(text(), 'Arena') or contains(text(), 'Ground')]"
                )
                if name_candidates:
                    name = name_candidates[0].text.strip()

            self.logger.info(f"Venue found: {name}, {location}")

            return {
                "name": name,
                "location": location
            }

        except Exception as e:
            self.logger.warning(f"Failed to extract venue info: {e}")
            return {
                "name": "N/A",
                "location": "N/A"
            }

    def _get_referee(self):
        self.logger.info("Extracting referee info...")
        try:
            referee_name = "N/A"
            avg_red_cards = "N/A"
            avg_yellow_cards = "N/A"
            attendance = "N/A"

            blocks = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div[class*='bg_surface'][class*='elevation_2']"
            )

            for block in blocks:
                block_text = block.text

                if "Attendance" in block_text:
                    attendance_elements = block.find_elements(
                        By.XPATH,
                        ".//span[preceding-sibling::span[contains(text(), 'Attendance')]]"
                    )
                    if attendance_elements:
                        attendance = attendance_elements[0].text.strip()

                if "Referee" in block_text:
                    referee_elements = block.find_elements(
                        By.XPATH,
                        ".//span[preceding-sibling::span[contains(text(), 'Referee')]]"
                    )
                    if referee_elements:
                        nested_span = referee_elements[0].find_elements(By.XPATH, ".//span[1]")
                        referee_name = (
                            nested_span[0].text.strip()
                            if nested_span
                            else referee_elements[0].text.strip()
                        )

                if "Avg. cards" in block_text:
                    red_cards, yellow_cards = self.extract_card_stats_from_text(block_text)
                    if red_cards is not None:
                        avg_red_cards = str(red_cards)
                    if yellow_cards is not None:
                        avg_yellow_cards = str(yellow_cards)

                if referee_name != "N/A":
                    break

            self.logger.info(
                f"Referee: {referee_name}, Red: {avg_red_cards}, Yellow: {avg_yellow_cards}, Attendance: {attendance}"
            )

            return {
                "name": referee_name,
                "avg_red_cards": avg_red_cards,
                "avg_yellow_cards": avg_yellow_cards,
                "attendance": attendance
            }

        except Exception as e:
            self.logger.warning(f"Failed to extract referee info: {e}")
            return {
                "name": "N/A",
                "avg_red_cards": "N/A",
                "avg_yellow_cards": "N/A",
                "attendance": "N/A"
            }

    def _get_odds(self):
        logger.info("Extracting odds info...")
        out = {'1': 'N/A', 'X': 'N/A', '2': 'N/A'}
        elems = self.safe_find_all(By.CSS_SELECTOR, ScrapingConfig.ODDS_SELECTOR, timeout=30)
        if len(elems) >= 3:
            out['1'], out['X'], out['2'] = [e.text.strip() for e in elems[:3]]
            logger.info(f"Odds: {out}")
        return out

    def _get_crowd_voting(self):
        self.logger.info("Extracting crowd voting...")
        try:
            home_pct = "N/A"
            draw_pct = "N/A"
            away_pct = "N/A"
            total_votes = "N/A"

            voting_sections = self.driver.find_elements(
                By.XPATH,
                "//span[contains(text(), 'Who will win?')]/ancestor::div[contains(@class, 'bg_surface')]"
            )

            if not voting_sections:
                self.logger.warning("No crowd voting section found.")
                return {
                    "home": home_pct,
                    "draw": draw_pct,
                    "away": away_pct,
                    "total_votes": total_votes
                }

            block = voting_sections[0]

            percent_elems = block.find_elements(By.CSS_SELECTOR, "div.Text.gHLcGU")
            if len(percent_elems) >= 3:
                home_pct = self.extract_percentage(percent_elems[0].text)
                draw_pct = self.extract_percentage(percent_elems[1].text)
                away_pct = self.extract_percentage(percent_elems[2].text)

            vote_spans = block.find_elements(
                By.XPATH,
                ".//span[contains(text(), 'Total votes')]"
            )
            if vote_spans:
                total_votes = self.extract_total_votes(vote_spans[0].text)

            self.logger.info(
                f"Crowd voting: home={home_pct}%, draw={draw_pct}%, away={away_pct}%, total_votes={total_votes}"
            )

            return {
                "home": home_pct,
                "draw": draw_pct,
                "away": away_pct,
                "total_votes": total_votes
            }

        except Exception as e:
            self.logger.warning(f"Failed to extract crowd voting: {e}")
            return {
                "home": "N/A",
                "draw": "N/A",
                "away": "N/A",
                "total_votes": "N/A"
            }

    def _scroll_container(self, elt, max_scrolls=5):
        logger.debug("Scrolling stats container...")
        last = self.driver.execute_script("return arguments[0].scrollHeight", elt)
        for _ in range(max_scrolls):
            self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", elt)
            time.sleep(ScrapingConfig.SCROLL_PAUSE_TIME)
            new = self.driver.execute_script("return arguments[0].scrollHeight", elt)
            if new == last:
                break
            last = new

    def _extract_stats_view(self):
        self.logger.info("Extracting stats view...")
        stats = []

        self.logger.debug("Scrolling page to trigger lazy loading of stats container...")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1.5)

        cont = None
        for i in range(3):
            cont = self.safe_find(By.CSS_SELECTOR, "div.Box.Flex.gQxTzO")
            if cont:
                break
            self.logger.info(f"Stats container not found, retrying ({i+1}/3)...")
            self.driver.execute_script("window.scrollBy(0, 400);")
            time.sleep(2)

        if cont:
            self._scroll_container(cont)
        else:
            self.logger.warning("Stats container could not be found after scrolling attempts.")

        rows = []
        for i in range(3):
            rows = self.safe_find_all(By.CSS_SELECTOR, "div.Box.Flex.heNsMA.bnpRyo", timeout=30)
            if rows:
                break
            self.logger.info(f"No stat rows found, retrying ({i+1}/3)...")
            time.sleep(2)

        self.logger.debug(f"Found {len(rows)} stat rows.")

        for r in rows:
            try:
                home_span = r.find_elements(By.CSS_SELECTOR, "bdi.Box.iQnHnj span.Text")
                home_value = home_span[0].text.strip() if home_span else "N/A"

                name_span = r.find_elements(By.CSS_SELECTOR, "span.Text.lluFbU, span.Text.eSKwCR, span.Text.llXWMP")
                name = name_span[0].text.strip() if name_span else "N/A"

                away_span = r.find_elements(By.CSS_SELECTOR, "bdi.Box.fdyVPU span.Text")
                away_value = away_span[0].text.strip() if away_span else "N/A"

                stats.append({
                    "name": name,
                    "home_value": home_value,
                    "away_value": away_value
                })

                self.logger.debug(f"Stat extracted: {name}: {home_value} - {away_value}")
            except Exception as e:
                self.logger.warning(f"Error extracting stat row: {e}")

        self.logger.info(f"Total stats extracted: {len(stats)}")
        return stats

    def wait_for_stat_rows(self, min_rows=10, timeout=20, poll_freq=0.5, return_rows=False):
        self.logger.debug(f"Waiting for at least {min_rows} stat rows...")
        end_time = time.time() + timeout
        while time.time() < end_time:
            rows = self.safe_find_all(By.CSS_SELECTOR, "div.Box.Flex.heNsMA.bnpRyo")
            if rows and len(rows) >= min_rows:
                self.logger.debug(f"Found {len(rows)} stat rows.")
                return rows if return_rows else True
            time.sleep(poll_freq)
        self.logger.warning(f"Timeout: Less than {min_rows} stat rows found.")
        return [] if return_rows else False

    def _get_stats(self):
        self.logger.info("Extracting all statistics sections...")
        out = {
            "overall": [],
            "first_half": [],
            "second_half": []
        }

        # Extract overall stats
        out["overall"] = self._extract_stats_view()

        def extract_with_retries(tab_id, label):
            for attempt in range(3):
                self.logger.info(f"Attempt {attempt + 1} to extract {label} stats...")
                tab = self.safe_find(By.CSS_SELECTOR, f"div[data-tabid='{tab_id}']")
                if tab and self.safe_click(tab):
                    if self.wait_for_stat_rows(min_rows=10):
                        return self._extract_stats_view()
                time.sleep(2)
            self.logger.warning(f"Failed to extract {label} stats after 3 attempts.")
            return []

        out["first_half"] = extract_with_retries(tab_id=2, label="first half")
        out["second_half"] = extract_with_retries(tab_id=3, label="second half")

        self.logger.info("Stats extraction complete.")
        return out

    # --- Generic Data Extraction Helpers (for specific data points from text) ---
    def extract_card_stats_from_text(self, text):
        """Extract red and yellow card averages from text"""
        import re
        try:
            card_pattern = r'Avg\.\s*cards.?(\d+\.?\d)[^\d](\d+\.?\d)'
            match = re.search(card_pattern, text, re.IGNORECASE | re.DOTALL)
            
            if match:
                red_cards = float(match.group(1))
                yellow_cards = float(match.group(2))
                return red_cards, yellow_cards

            numbers = re.findall(r'\d+\.\d+', text)
            if len(numbers) >= 2:
                return float(numbers[0]), float(numbers[1])
                
        except Exception as e:
            self.logger.debug(f"Error extracting card stats: {e}")
        
        return None, None

    def extract_percentage(self, text):
        """Extract percentage from text like '83%'"""
        import re
        try:
            match = re.search(r'(\d+)%', text)
            return int(match.group(1)) if match else "N/A"
        except:
            return "N/A"

    def extract_total_votes(self, text):
        """
        Extracts the number of votes from strings like:
        'Total votes: 12,345' or 'Total votes: 121k'
        """
        import re
        try:
            m = re.search(r"Total votes[:\s]*([\d.,]+)([kM]?)", text, re.IGNORECASE)
            if m:
                number = m.group(1).replace(",", "")
                suffix = m.group(2).lower()

                if suffix == 'k':
                    return str(int(float(number) * 1000))
                elif suffix == 'm':
                    return str(int(float(number) * 1_000_000))
                else:
                    return number
        except Exception as e:
            self.logger.warning(f"Failed to extract total votes: {e}")
        return "N/A"
    
    @staticmethod
    def classify_event_type(text):
        """
        Classify commentary text into a type based on keywords.
        """
        lowered = text.lower()
        if "goal" in lowered:
            return "goal"
        elif "substitution" in lowered or "subbed" in lowered or "substituted" in lowered:
            return "substitution"
        elif "yellow card" in lowered or "booked" in lowered:
            return "yellow_card"
        elif "red card" in lowered or "sent off" in lowered:
            return "red_card"
        elif "corner" in lowered:
            return "corner"
        elif "foul" in lowered:
            return "foul"
        elif "offside" in lowered:
            return "offside"
        elif "penalty" in lowered:
            return "penalty"
        elif "attempt" in lowered or "shot" in lowered:
            return "attempt"
        elif "free kick" in lowered:
            return "free_kick"
        elif "kick-off" in lowered or "kick off" in lowered:
            return "kick_off"
        elif "half time" in lowered or "half-time" in lowered:
            return "half_time"
        elif "full time" in lowered or "full-time" in lowered:
            return "full_time"
        elif "var" in lowered:
            return "var"
        elif "injury" in lowered:
            return "injury"
        else:
            return "other"

    def navigate_to_commentary_section(self):
        """Navigate to the commentary section of the match"""
        self.logger.info("Navigating to commentary section...")
        
        try:
            # Try to find and click commentary tab/section
            commentary_selectors = [
                "//span[contains(text(), 'Commentary')]",
                "//a[contains(text(), 'Commentary')]",
                "//button[contains(text(), 'Commentary')]",
                "div[data-tabid='commentary']",
                "a[href*='commentary']"
            ]
            
            for selector in commentary_selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        self.safe_click(elements[0])
                        time.sleep(2)  # Wait for content to load
                        self.logger.info("Successfully navigated to commentary section")
                        return True
                except Exception as e:
                    self.logger.debug(f"Failed to click commentary selector {selector}: {e}")
                    continue
            
            self.logger.warning("Could not find commentary section")
            return False
            
        except Exception as e:
            self.logger.warning(f"Error navigating to commentary section: {e}")
            return False

    def _get_commentary(self):
        """Extract full commentary with improved error handling and multiple selector approaches"""
        self.logger.info("Extracting full commentary...")
        commentary = []
        seen_texts = set()

        try:
            # First, try to navigate to commentary section
            if not self.navigate_to_commentary_section():
                self.logger.warning("Could not navigate to commentary section, trying to extract from current page")

            # Step 1: Load all commentary by clicking "Show more" buttons
            max_clicks = 25  # Increased max clicks
            attempts = 0
            consecutive_no_change = 0
            previous_count = 0

            while attempts < max_clicks and consecutive_no_change < 3:
                show_more_found = False
                
                # Try multiple selectors for "Show more" button
                for selector in self.config.LOAD_MORE_SELECTORS:
                    try:
                        if selector.startswith("//"):
                            show_more_elements = self.driver.find_elements(By.XPATH, selector)
                        else:
                            show_more_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if show_more_elements:
                            show_more = show_more_elements[0]
                            if show_more.is_displayed() and show_more.is_enabled():
                                if self.safe_click(show_more):
                                    show_more_found = True
                                    time.sleep(1.5)  # Wait for content to load
                                    break
                    except Exception as e:
                        self.logger.debug(f"Error with selector {selector}: {e}")
                        continue

                if not show_more_found:
                    self.logger.info("No more 'Show more' buttons found")
                    break

                # Check if new content was loaded
                containers = self.get_commentary_containers()
                current_count = len(containers)
                
                if current_count == previous_count:
                    consecutive_no_change += 1
                    self.logger.debug(f"No change in commentary count ({consecutive_no_change}/3)")
                else:
                    consecutive_no_change = 0
                    self.logger.debug(f"Commentary entries increased from {previous_count} to {current_count}")
                
                previous_count = current_count
                attempts += 1

            # Step 2: Extract commentary entries
            containers = self.get_commentary_containers()
            self.logger.info(f"Found {len(containers)} commentary containers")

            for i, entry in enumerate(containers):
                try:
                    entry_data = self._get_commentary_entry(entry)
                    if entry_data and entry_data["text"] not in seen_texts:
                        seen_texts.add(entry_data["text"])
                        commentary.append(entry_data)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse commentary entry {i}: {e}")

            self.logger.info(f"Successfully extracted {len(commentary)} commentary entries")
            return commentary

        except Exception as e:
            self.logger.error(f"Failed to extract commentary: {e}")
            return []

    def get_commentary_containers(self):
        """Get all commentary containers using multiple selector approaches"""
        containers = []
        
        # Try primary selector
        try:
            containers = self.driver.find_elements(By.CSS_SELECTOR, self.config.COMMENTARY_ENTRY_CONTAINER)
            if containers:
                return containers
        except:
            pass
        
        # Try alternative selectors
        alternative_selectors = [
            "div[class*='commentary-entry']",
            "div[class*='event-entry']", 
            "div[class*='match-event']",
            "div.d_flex.ai_center",
            "div[class*='timeline-entry']"
        ]
        
        for selector in alternative_selectors:
            try:
                containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if containers:
                    # Filter to only include elements that look like commentary
                    filtered_containers = []
                    for container in containers:
                        if self.looks_like_commentary(container):
                            filtered_containers.append(container)
                    
                    if filtered_containers:
                        return filtered_containers
            except:
                continue
        
        return containers

    def looks_like_commentary(self, element):
        """Check if an element looks like a commentary entry"""
        try:
            text = element.text.strip()
            # Commentary entries typically have some text and might contain time stamps
            return (len(text) > 5 and 
                (any(char.isdigit() for char in text) or
                any(keyword in text.lower() for keyword in ['goal', 'card', 'corner', 'foul', 'attempt'])))
        except:
            return False

    def _get_commentary_entry(self, entry):
        """Extract time and text from a single commentary entry"""
        try:
            # Extract time using multiple approaches
            time_text = self.extract_time_from_entry(entry)
            
            # Extract commentary text using multiple approaches  
            commentary_text = self.extract_text_from_entry(entry)
            
            if commentary_text and commentary_text != "N/A":
                event_type = self.classify_event_type(commentary_text)
                
                return {
                    "time": time_text,
                    "text": commentary_text,
                    "type": event_type
                }
        except Exception as e:
            self.logger.debug(f"Error extracting commentary entry: {e}")
        
        return None

    def extract_time_from_entry(self, entry):
        """Extract time from commentary entry using multiple selectors"""
        time_selectors = [
            "span.textStyle_assistive.default",
            "span[class*='time']",
            "span[class*='minute']", 
            "div[class*='time']",
            ".time",
            ".minute"
        ]
        
        for selector in time_selectors:
            try:
                time_elements = entry.find_elements(By.CSS_SELECTOR, selector)
                if time_elements:
                    time_text = time_elements[0].text.strip()
                    if time_text and "'" in time_text:  # Looks like a time stamp
                        return time_text
            except:
                continue
        
        # Look for time patterns in the text
        try:
            entry_text = entry.text
            time_match = re.search(r"(\d{1,3}(?:\+\d+)?)'", entry_text)
            if time_match:
                return time_match.group(1) + "'"
        except:
            pass
        
        return "N/A"

    def extract_text_from_entry(self, entry):
        """Extract commentary text from entry using multiple selectors"""
        text_selectors = [
            "span.textStyle_body.small",
            "span[class*='text']",
            "div[class*='description']",
            "span[class*='body']",
            ".text",
            ".description"
        ]
        
        for selector in text_selectors:
            try:
                text_elements = entry.find_elements(By.CSS_SELECTOR, selector)
                if text_elements:
                    text = text_elements[0].text.strip()
                    if text and len(text) > 3:  # Reasonable text length
                        return text
            except:
                continue
        
        # Fallback to full entry text, but clean it up
        try:
            full_text = entry.text.strip()
            if full_text:
                # Remove time stamps from beginning
                clean_text = re.sub(r"^\d{1,3}(?:\+\d+)?'\s*", "", full_text)
                return clean_text if clean_text else full_text
        except:
            pass
        
        return "N/A"