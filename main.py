"""
WhatsApp Web Bulk Messenger via Selenium
⚠️ WARNING: This violates WhatsApp ToS. Account will be banned.
Use ONLY for testing/development. Not for production SaaS.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

class WhatsAppSender:
    def __init__(self, excel_file, country_code="+962"):
        if not country_code.startswith("+"):
            raise ValueError(f"Country code must start with '+', got: {country_code}")

        self.excel_file = excel_file
        self.country_code = country_code
        self.driver = None
        self.sent_count = 0
        self.failed_count = 0

    def setup_driver(self):
        """Initialize Chrome driver with persistent profile to skip QR scan after first login."""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        self.driver = webdriver.Chrome(options=chrome_options)
        print("✓ Chrome driver initialized")

    def login_whatsapp(self):
        """Open WhatsApp Web and wait for login (QR scan or saved session)."""
        print("\n📱 Opening WhatsApp Web...")
        self.driver.get("https://web.whatsapp.com")
        print("⏳ Waiting for login (60 seconds)...")
        try:
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid='chat-list']"))
            )
            print("✓ Login successful!")
            return True
        except Exception as e:
            print(f"✗ Login failed: {e}")
            return False

    def format_phone(self, phone):
        """Format phone number with country code."""
        phone = str(phone).strip()
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if phone.startswith("+"):
            return phone
        country_digits = self.country_code.lstrip("+")
        if phone.startswith(country_digits):
            return f"+{phone}"
        if phone.startswith("0"):
            phone = phone[1:]
        return f"{self.country_code}{phone}"

    def read_excel(self):
        """Read Excel file and validate."""
        try:
            df = pd.read_excel(self.excel_file)
            df.columns = df.columns.str.strip()

            if 'phone' not in df.columns:
                print("✗ Excel must have 'phone' column")
                return None
            if 'message' not in df.columns:
                df['message'] = None

            df['phone'] = df['phone'].fillna('').astype(str).str.strip()
            df['message'] = df['message'].fillna('').astype(str).str.strip()

            no_content_mask = (df['message'] == '') & (df['phone'] != '')
            for _, row in df[no_content_mask].iterrows():
                print(f"✗ {row['phone']} - Skipped: no message")
                self.failed_count += 1

            initial_count = len(df)
            df = df[df['message'] != '']
            df = df[df['phone'] != '']

            filtered_count = len(df)
            if filtered_count < initial_count:
                print(f"⚠ Filtered out {initial_count - filtered_count} invalid rows")

            print(f"✓ Loaded {filtered_count} valid records from {self.excel_file}")
            return df
        except FileNotFoundError:
            print(f"✗ Excel file not found: {self.excel_file}")
            return None
        except Exception as e:
            print(f"✗ Error reading Excel: {e}")
            return None

    def send_text_message(self, phone, message):
        """Send a text message to a phone number."""
        phone_formatted = self.format_phone(phone)
        self.driver.get("about:blank")
        time.sleep(1)
        self.driver.get(f"https://web.whatsapp.com/send?phone={phone_formatted}")
        time.sleep(5)

        # Fail fast if number is not on WhatsApp
        try:
            self.driver.find_element(By.XPATH, "//*[contains(text(),'Phone number shared via URL is invalid')]"
                                                " | //*[contains(text(),'not registered')]")
            raise Exception(f"Phone not on WhatsApp: {phone_formatted}")
        except Exception as e:
            if "Phone not on WhatsApp" in str(e):
                raise

        msg_box = WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@data-tab='10']"))
        )
        msg_box.click()
        time.sleep(0.5)
        msg_box.send_keys(Keys.CONTROL + 'a')
        msg_box.send_keys(Keys.DELETE)
        msg_box.send_keys(message)
        time.sleep(1)

        send_btn = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Send']"))
        )
        send_btn.click()

        self.sent_count += 1
        print(f"✓ {phone_formatted}")
        time.sleep(2)

    def _prompt_on_error(self, phone, allow_retry=True):
        """Prompt user what to do on send failure. Returns: 'retry', 'skip', or 'quit'."""
        while True:
            try:
                if allow_retry:
                    choice = input(f"\n[Error] Failed to send to {phone}.\n[R]etry / [S]kip / [Q]uit? ").strip().upper()
                    if choice in ['R', 'S', 'Q']:
                        return {'R': 'retry', 'S': 'skip', 'Q': 'quit'}[choice]
                else:
                    choice = input(f"\n[Error] Failed to send to {phone}.\n[S]kip / [Q]uit? ").strip().upper()
                    if choice in ['S', 'Q']:
                        return {'S': 'skip', 'Q': 'quit'}[choice]
                print("Invalid choice. Please enter " + ("R, S, or Q" if allow_retry else "S or Q") + ".")
            except EOFError:
                print("(non-interactive mode — skipping)")
                return 'skip'

    def send_message(self, phone, message):
        """Send a message with retry/skip/quit handling."""
        if not message or str(message).strip() == '':
            self.failed_count += 1
            print(f"✗ {phone} - No message provided")
            return

        attempt = 1
        max_attempts = 2
        while attempt <= max_attempts:
            try:
                self.send_text_message(phone, message)
                return
            except Exception as e:
                if attempt < max_attempts:
                    action = self._prompt_on_error(phone)
                    if action == 'retry':
                        attempt += 1
                        continue
                    elif action == 'skip':
                        self.failed_count += 1
                        print(f"✗ {phone} - Skipped: {str(e)[:50]}")
                        return
                    else:
                        print("\n⚠ Exiting...")
                        raise KeyboardInterrupt("User quit")
                else:
                    action = self._prompt_on_error(phone, allow_retry=False)
                    if action == 'quit':
                        print("\n⚠ Exiting...")
                        raise KeyboardInterrupt("User quit")
                    else:
                        self.failed_count += 1
                        print(f"✗ {phone} - Skipped: {str(e)[:50]}")
                        return

    def send_bulk(self):
        """Send messages to all contacts."""
        df = self.read_excel()
        if df is None or len(df) == 0:
            print("✗ No data to process")
            return

        if not self.login_whatsapp():
            return

        print(f"\n📤 Starting bulk send... ({len(df)} messages)\n")
        for i, (idx, row) in enumerate(df.iterrows(), start=1):
            print(f"[{i}/{len(df)}] ", end="")
            self.send_message(row['phone'], row['message'])

        self.print_summary()

    def print_summary(self):
        """Print results summary."""
        total = self.sent_count + self.failed_count
        print(f"\n{'='*50}")
        print(f"📊 SUMMARY")
        print(f"{'='*50}")
        print(f"✓ Sent: {self.sent_count}/{total}")
        print(f"✗ Failed: {self.failed_count}/{total}")
        if total > 0:
            print(f"Success rate: {(self.sent_count/total)*100:.1f}%")
        else:
            print("Success rate: N/A (no messages processed)")
        print(f"{'='*50}\n")

    def run(self):
        """Main entry point."""
        try:
            self.setup_driver()
            self.send_bulk()
        finally:
            if self.driver:
                self.driver.quit()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <excel_file> [country_code]")
        print("Example: python main.py messages.xlsx +962")
        sys.exit(1)

    excel_file = sys.argv[1]
    country_code = sys.argv[2] if len(sys.argv) > 2 else "+962"

    try:
        sender = WhatsAppSender(excel_file, country_code)
        sender.run()
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        sys.exit(1)
