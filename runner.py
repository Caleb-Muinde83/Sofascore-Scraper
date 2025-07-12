# epl_scraper/runner.py

import logging
import random
import time
import sys

from .scraper import SofaScoreEPLScraper
from .persistence import save_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main(start_matchday=1, end_matchday=38, season="24/25", headless=True):
    scraper = SofaScoreEPLScraper(headless=headless)

    try:
        scraper.setup_driver()
        scraper.driver.get(scraper.base_url)
        scraper.dismiss_cookies()

        if not scraper.select_season(season):
            logger.critical(f"Failed to select season {season}. Exiting.")
            return

        scraped_ids = {m['match_id'] for m in scraper.all_match_data}
        logger.info(f"Already have {len(scraped_ids)} matches loaded.")

        for md in range(start_matchday, end_matchday + 1):
            logger.info(f"=== Matchday {md} ===")
            if not scraper.navigate_to_round(md):
                logger.error(f"Couldn’t navigate to matchday {md}, skipping.")
                continue

            links = scraper.get_match_links()
            logger.info(f"Found {len(links)} matches on MD {md}.")

            for link in links:
                mid = link['match_id']
                if mid in scraped_ids:
                    logger.info(f"Skipping already scraped match {mid}.")
                    continue

                logger.info(f"Scraping match {mid}...")

                try:
                    data = scraper.scrape_match(link['url'], matchday=md)
                except KeyboardInterrupt:
                    logger.warning("Scraper interrupted by user (Ctrl + C) while scraping match.")
                    raise
                except Exception as e:
                    logger.exception(f"Unexpected error scraping match {mid}: {e}")
                    data = None

                if data:
                    data['match_id'] = mid
                    data['source_url'] = link['url']
                    scraper.all_match_data.append(data)
                    save_data(scraper.all_match_data)
                    scraped_ids.add(mid)
                else:
                    logger.error(f"Failed to scrape match {mid}.")

                time.sleep(random.uniform(1, 3))

    except KeyboardInterrupt:
        logger.warning("Scraper manually stopped via Ctrl + C.")
    except Exception as e:
        logger.exception(f"Unhandled error in scraping process: {e}")
    finally:
        scraper.quit()
        logger.info("Scraper shut down cleanly.")

if __name__ == "__main__":
    main()
