# epl_scraper/config.py

JSON_FILE_PATH = 'epl_matches_.json'

class ScrapingConfig:
    # Timing & retry
    DROPDOWN_WAIT_TIME = 1.5
    SCROLL_PAUSE_TIME = 0.5
    PAGE_RELOAD_WAIT = 4
    RECOVERY_WAIT = 5
    BASE_RETRY_DELAY = 2
    TAB_OPEN_WAIT = 1
    SCROLL_TO_END_TIMEOUT = 30

    # Season/Round selectors
    SEASON_DROPDOWN_SELECTOR = 'div.Dropdown.kdhXwd button.DropdownButton.jQruaf'
    CURRENT_SEASON_TEXT_SELECTOR = 'div.Dropdown.kdhXwd button.DropdownButton.jQruaf div.Text.nZQAT'
    SEASON_OPTION_XPATH = '//ul[@role="listbox"]//li[@role="option" and normalize-space(text())="{season}"]'
    ROUND_DROPDOWN_BUTTON = "div[data-panelid='round'] .DropdownButton"
    ROUND_TEXT_SELECTOR = 'div[data-panelid="round"] div.Dropdown.gSFIyj button.DropdownButton.jQruaf div.Text.nZQAT'
    NEXT_ROUND_ARROW = "div.Wrapper.d_flex.ai_center button.Button.iCnTrv:last-child"
    PREV_ROUND_ARROW = "div.Wrapper.d_flex.ai_center button.Button.iCnTrv:first-child"

    # Match list
    MATCH_LINK_SELECTOR = "a[class*='event-hl-']"

    # Match header
    MATCH_DATE_TIME_CONTAINER = "div.d_flex.ai_center.gap_sm.px_lg.py_sm"
    # Match date & time (XPath version is now preferred)
    MATCH_DATE_TIME_XPATH = "//span[preceding-sibling::span[contains(text(), 'Date and time')]]"
    TEAM_SELECTOR = "img.Img.jmRURX[alt]"
    
    # Venue selectors - Updated based on HTML structure
    VENUE_SECTION = "div.bg_surface\\.s1.md\\:bg_surface\\.s1.br_lg.md\\:br_xl.elevation_2.md\\:elevation_2.pos_relative"
    VENUE_NAME_SELECTOR = "span.textStyle_body\\.medium.c_neutrals\\.nLv1.ov_hidden"
    VENUE_LOCATION_SELECTOR = "span.textStyle_body\\.medium.c_neutrals\\.nLv1.ov_hidden"

    # ✅ XPath-based selectors for venue details (for stable dynamic scraping)
    VENUE_NAME_XPATH = "//span[text()='Name']/following-sibling::span[1]"
    VENUE_LOCATION_XPATH = "//span[text()='Location']/following-sibling::span[1]"
    
    # Alternative venue selectors (fallback)
    VENUE_SECTION_ALT = "div[class*='bg_surface'][class*='elevation_2']"
    VENUE_NAME_ALT = "//span[preceding-sibling::span[text()='Name']]"
    VENUE_LOCATION_ALT = "//span[preceding-sibling::span[text()='Location']]"

    # Referee and attendance selectors - Updated
    ATTENDANCE_SELECTOR = "//span[preceding-sibling::span[text()='Attendance']]"
    REFEREE_NAME_SELECTOR = "//span[preceding-sibling::span[text()='Referee']]"  
    REFEREE_LINK_SELECTOR = "a[href*='/referee/']"
    
    # Card statistics - Updated selectors
    RED_CARD_STATS_SELECTOR = "svg[fill*='error-default'] + text(), svg[fill*='error'] + text()"
    YELLOW_CARD_STATS_SELECTOR = "svg[fill*='score-rating'] + text(), svg[fill*='rating-s65'] + text()"
    
    # Alternative card stats approach
    CARD_STATS_CONTAINER = "//span[contains(text(), 'Avg. cards')]"
    CARD_STATS_TEXT_PATTERN = r"(\d+\.?\d*)"

    # Referee & attendance section XPaths
    ATTENDANCE_XPATH = "//span[text()='Attendance']/following-sibling::span[1]"
    REFEREE_NAME_XPATH = "//span[text()='Referee']/following-sibling::span[1]//span[1]"
    #REFEREE_CARD_STATS_XPATH = "//span[contains(text(), 'Avg. cards')]/parent::span"
    REFEREE_CARD_STATS_XPATH = "//span[contains(text(), 'Avg. cards')]"
    
    # Crowd voting selectors - Updated based on HTML
    CROWD_VOTING_CONTAINER = "//span[text()='Who will win?']/ancestor::div[contains(@class, 'jTWvec')]"
    HOME_VOTE_PERCENTAGE = "(//div[@class='Text gHLcGU'])[1]"
    DRAW_VOTE_PERCENTAGE = "(//div[@class='Text gHLcGU'])[2]"
    AWAY_VOTE_PERCENTAGE = "(//div[@class='Text gHLcGU'])[3]"
    TOTAL_VOTES_SELECTOR = "//span[contains(text(), 'Total votes')]"
    
    # Odds selectors
    ODDS_SELECTOR = "span.textStyle_display\\.micro"

    # config.py
    # Finds all odds blocks (the <a> elements for 1, X, 2)
    ODDS_BLOCK_XPATH = "//a[.//span[text()='1' or text()='X' or text()='2']]"

    # Finds the label (1, X, 2)
    ODDS_LABEL_XPATH = ".//span[contains(@class,'cTGrSw')]"

    # Finds the odds value
    ODDS_VALUE_XPATH = ".//span[contains(@class,'FSvfQ')]"

    # Statistics
    STAT_ROW = "div.Box.Flex.heNsMA.bnpRyo"
    STAT_NAME = "span.Text.lluFbU"
    STAT_VALUE = "span.Text"
    FIRST_HALF_TAB = "div[data-tabid='2']"
    SECOND_HALF_TAB = "div[data-tabid='3']"

    # Date/time patterns
    DATE_PATTERNS = [
        r'\d{1,2}/\d{1,2}/\d{4}',
        r'\d{1,2}-\d{1,2}-\d{4}',
        r'\d{4}-\d{1,2}-\d{1,2}',
        r'\d{1,2}\.\d{1,2}\.\d{4}',
        r'(\d{1,2}/\d{1,2}/\d{4})[^\d]*(\d{1,2}:\d{2})',
        r'(\d{1,2} [A-Za-z]{3,}\.? \d{4})',
    ]
    TIME_PATTERNS = [
        r'\d{1,2}:\d{2}',
        r'\d{1,2}:\d{2}:\d{2}',
        r'\d{1,2}\.\d{2}',
    ]
    CALENDAR_ICONS = [
        "svg.SvgWrapper",
        "svg[viewBox='0 0 24 24'] path[d^='M22,2 L22,12.11']",
        "svg[data-icon='calendar']",
        "*[class*='calendar'] svg",
    ]

    # Additional selectors for comprehensive data extraction
    MATCH_HEADER_CONTAINER = "div[class*='match-header'], div[class*='event-header']"
    TEAM_LOGO_SELECTOR = "img[alt*='team'], img[src*='/team/']"
    
    # Backup selectors for robustness
    BACKUP_SELECTORS = {
        'venue_name': [
            "span:contains('Name') + span",
            "//span[text()='Name']/following-sibling::span",
            "div:contains('Venue') span.textStyle_body\\.medium"
        ],
        'venue_location': [
            "span:contains('Location') + span", 
            "//span[text()='Location']/following-sibling::span",
            "img[alt='EN'] + div span.textStyle_body\\.medium"
        ],
        'attendance': [
            "span:contains('Attendance') + span",
            "//span[text()='Attendance']/following-sibling::span",
            "svg[viewBox*='16 16'] + div span:nth-child(2)"
        ],
        'referee': [
            "span:contains('Referee') + span",
            "a[href*='/referee/'] span.textStyle_body\\.medium",
            "//span[text()='Referee']/following-sibling::span//span[1]"
        ]
    }
    
    # Commentary selectors for Sofascore new layout
    COMMENTARY_ENTRY_CONTAINER = "div.fPSBzf.bYPztT"
    COMMENTARY_TIME_SPAN = "span.eIsWjS.cTGrSw"
    COMMENTARY_EVENT_TYPE_SPAN = "span.bGAxYH.fdnFeu"
    COMMENTARY_TEXT_SPAN = "span.gnTBMP.fdnFeu"
    COMMENTARY_SUB_PLAYER_SPAN = "span.gnTBMP.fdnFeu"

    # Add new load more selector for the Sofascore button
    LOAD_MORE_SELECTORS = [
        "//button[contains(., 'Show more')]",
        "//button[contains(., 'Load more')]",
        "//button[contains(., 'View more')]",
        "//a[contains(., 'Show more')]",
        "button[class*='load-more']",
        "button[class*='show-more']",
        "button.ervFBh"
    ]
    
    def __init__(self, driver, config):
        self.driver = driver
        self.config = config
        self.logger = ...

    # Helper function to extract card statistics from text
    def extract_card_stats(text):
        """Extract red and yellow card averages from referee text"""
        import re

        numbers = re.findall(r'\d+\.?\d*', text)
        if len(numbers) >= 2:
            red_cards = float(numbers[0]) if numbers[0] else 0.0
            yellow_cards = float(numbers[1]) if numbers[1] else 0.0
            return red_cards, yellow_cards
        
        return None, None

    # Helper function to extract vote percentages
    def extract_vote_percentage(text):
        """Extract percentage from voting text like '83%'"""
        import re
        match = re.search(r'(\d+)%', text)
        return int(match.group(1)) if match else None

    # Helper function to extract total votes
    def extract_total_votes(text):
        """Extract total votes from text like 'Total votes: 121k'"""
        import re

        match = re.search(r'Total votes:\s*(\d+(?:\.\d+)?)(k|K|m|M)?', text)
        if match:
            number = float(match.group(1))
            multiplier = match.group(2)

            if multiplier and multiplier.lower() == 'k':
                return int(number * 1000)
            elif multiplier and multiplier.lower() == 'm':
                return int(number * 1_000_000)
            else:
                return int(number)
        
        return None
    

