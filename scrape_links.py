import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

class LinkScraper:
    def __init__(self, headless=False, slow_mo=50):
        self.setup_browser(headless, slow_mo)
        self.setup_session()
        
    def setup_browser(self, headless=True, slow_mo=50):
        print("Starting Playwright...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo
        )
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        print("Browser launched successfully.")
    
    def setup_session(self):
        print("Setting up HTTP session...")
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        print("HTTP session configured.")
    
    def __del__(self):
        if hasattr(self, 'browser'):
            try:
                print("Closing browser...")
                self.browser.close()
                self.playwright.stop()
                print("Browser closed.")
            except Exception as e:
                print(f"Error during browser shutdown: {e}")
    
    def get_price(self, url, nav_timeout, selector_timeout):
        for attempt in range(2):  # Allow up to 2 attempts
            try:
                page = self.context.new_page()
                print(f"Navigating to {url} (Attempt {attempt + 1})")
                page.goto(url, wait_until='load', timeout=nav_timeout)  # Navigation timeout
                
                # Wait for price element
                price_selector = '.price--currentPriceText--V8_y_b5'
                print(f"Waiting for price selector: {price_selector}")
                page.wait_for_selector(price_selector, timeout=selector_timeout)  # Selector timeout
                
                # Extract current price
                price_element = page.query_selector(price_selector)
                price = price_element.text_content().strip() if price_element else None
                print(f"Current Price: {price}")
                
                # Extract original price if available
                original_price = None
                original_selector = '.price--originalText--gxVO5_d'
                original_element = page.query_selector(original_selector)
                if original_element:
                    try:
                        original_price = original_element.text_content().strip()
                        print(f"Original Price: {original_price}")
                    except:
                        print("Original price element found but failed to retrieve text.")
                
                page.close()
                return {
                    'current_price': price,
                    'original_price': original_price,
                    'error': None
                }
            
            except Exception as e:
                print(f"Error on attempt {attempt + 1} for {url}: {e}")
                try:
                    page.close()
                except:
                    pass
                if 'Timeout' in str(e) and attempt == 0:
                    print("Retrying...")
                    continue  # Retry once
                else:
                    return {
                        'current_price': None,
                        'original_price': None,
                        'error': "Timed out"
                    }

    def scrape_github_links(self):
        url = "https://github.com/BitMaker-hub/NerdMiner_v2"
        print(f"Scraping GitHub repository: {url}")
        try:
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get supported boards section
            boards_section = soup.find('h4', string='Current Supported Boards')
            if not boards_section:
                print("Couldn't find boards section")
                return []
                
            boards_list = boards_section.find_parent('div').find_next_sibling('ul')
            if not boards_list:
                print("Couldn't find boards list")
                return []

            # Extract board information and links
            results = []
            for li in boards_list.find_all('li'):
                board_name = li.get_text().split('(')[0].strip()
                
                for link in li.find_all('a'):
                    href = link.get('href')
                    if href and 'aliexpress.com' in href:
                        # Ensure the URL is absolute
                        full_href = href if href.startswith('http') else 'https:' + href
                        results.append({
                            'board_name': board_name,
                            'link': full_href,
                            'link_text': link.get_text().strip()
                        })
                        break  # Assuming only one relevant link per board
            
            print(f"Extracted {len(results)} links from GitHub.")
            return results

        except Exception as e:
            print(f"Error scraping GitHub: {e}")
            return []

    def scrape_all_prices(self):
        print("Scraping GitHub for links...")
        all_links = self.scrape_github_links()
        
        if not all_links:
            print("No links found!")
            return
        
        print(f"Found {len(all_links)} links to process")
        
        # Prepare Excel file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f'board_prices_{timestamp}.xlsx'
        print(f"Saving results to {excel_filename}")

        # List to hold all row data
        data = []

        # Process each link
        for i, item in enumerate(all_links, 1):
            print(f"\nProcessing {i}/{len(all_links)}: {item['board_name']}")
            print(f"URL: {item['link']}")

            # Set timeouts: 30,000ms for first link, 7,000ms for others
            if i == 1:
                nav_timeout = 60000  # 30 seconds
                selector_timeout = 60000  # 5 seconds
            else:
                nav_timeout = 7000  # 7 seconds
                selector_timeout = 2000  # 2 seconds

            # Get price information with retry logic
            price_info = self.get_price(item['link'], nav_timeout=nav_timeout, selector_timeout=selector_timeout)

            # Prepare row data
            row_data = {
                'board_name': item['board_name'],
                'link_text': item['link_text'],
                'link': item['link'],
                'current_price': price_info['current_price'],
                'original_price': price_info['original_price'],
                'error': price_info['error'],
                'timestamp': datetime.now().isoformat()
            }

            # Append row data to the list
            data.append(row_data)
            print(f"Row appended for {item['board_name']}.")

            # Print progress
            print(f"Price: {price_info['current_price']}")
            if price_info['error']:
                print(f"Error: {price_info['error']}")

        # Create a DataFrame and save to Excel
        df = pd.DataFrame(data)
        try:
            df.to_excel(excel_filename, index=False)
            print(f"\nAll done! Results saved to {excel_filename}")
        except Exception as e:
            print(f"Error saving to Excel: {e}")

def main():
    scraper = LinkScraper(headless=False, slow_mo=50)
    scraper.scrape_all_prices()

if __name__ == "__main__":
    main()
