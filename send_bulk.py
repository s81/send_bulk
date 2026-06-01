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
from datetime import datetime
import os

class WhatsAppSender:
    def _resolve_image_path(self, image_path, excel_dir):
        """Resolve relative paths to absolute, leave absolute paths unchanged."""
        if os.path.isabs(image_path):
            return image_path
        return os.path.abspath(os.path.join(excel_dir, image_path))

    def __init__(self, excel_file, country_code="+962"):
        """
        Args:
            excel_file: Path to Excel file with columns 'phone' and 'message'
            country_code: Default country code (e.g., "+962" for Jordan, "+20" for Egypt)
        """
        if not country_code.startswith("+"):
            raise ValueError(f"Country code must start with '+', got: {country_code}")

        self.excel_file = excel_file
        self.country_code = country_code
        self.driver = None
        self.sent_count = 0
        self.failed_count = 0
        self.log = []

    def setup_driver(self):
        """Initialize Chrome driver with headless option (disable for testing)"""
        chrome_options = Options()
        # chrome_options.add_argument("--headless")  # Uncomment for background mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        print("✓ Chrome driver initialized")

    def login_whatsapp(self):
        """Open WhatsApp Web and wait for manual QR scan"""
        print("\n📱 Opening WhatsApp Web...")
        self.driver.get("https://web.whatsapp.com")
        
        print("⏳ Waiting for QR code scan (60 seconds)...")
        print("🔗 Scan the QR code in the browser window with your phone")
        
        try:
            # Wait for chat list to load (indicates successful login)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid='chat-list']"))
            )
            print("✓ Login successful!")
            return True
        except Exception as e:
            print(f"✗ Login failed: {e}")
            return False

    def format_phone(self, phone):
        """Format phone number with country code"""
        phone = str(phone).strip()
        
        # Remove spaces, dashes, parentheses
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # If already has +, return as-is
        if phone.startswith("+"):
            return phone
        
        # If starts with 0, remove it (for local formats like 0123456789)
        if phone.startswith("0"):
            phone = phone[1:]
        
        # Add country code
        return f"{self.country_code}{phone}"

    def read_excel(self):
        """Read Excel file and validate"""
        try:
            df = pd.read_excel(self.excel_file)

            # Check required columns (phone is required, message/image_path optional)
            if 'phone' not in df.columns:
                print("✗ Excel must have 'phone' column")
                return None

            # Add missing columns if they don't exist
            if 'message' not in df.columns:
                df['message'] = None
            if 'image_path' not in df.columns:
                df['image_path'] = None

            # Convert to string and strip whitespace, handling NaN values
            df['phone'] = df['phone'].fillna('').astype(str).str.strip()
            df['message'] = df['message'].fillna('').astype(str).str.strip()
            df['image_path'] = df['image_path'].fillna('').astype(str).str.strip()

            # Filter: at least one of message or image_path must be provided
            initial_count = len(df)
            df = df[~((df['message'] == '') & (df['image_path'] == ''))]
            df = df[df['phone'] != '']

            # Resolve image paths relative to Excel directory and validate existence
            excel_dir = os.path.dirname(os.path.abspath(self.excel_file))

            def resolve_and_validate_image_path(image_path):
                """Resolve path and validate it exists"""
                if not image_path or image_path == '':
                    return ''

                resolved_path = self._resolve_image_path(image_path, excel_dir)

                # Validate that the file exists
                if resolved_path and not os.path.exists(resolved_path):
                    print(f"⚠ Image not found: {resolved_path}")
                    return ''

                return resolved_path

            df['image_path'] = df['image_path'].apply(resolve_and_validate_image_path)

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
        """Send a text message to a phone number"""
        try:
            phone_formatted = self.format_phone(phone)

            # Open WhatsApp chat link
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone_formatted}")
            time.sleep(3)  # Wait for page load

            # Find message input box
            msg_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'][@data-tab='10']"))
            )

            # Clear and type message
            msg_box.click()
            time.sleep(0.5)
            msg_box.clear()
            msg_box.send_keys(message)
            time.sleep(1)

            # Click send button
            send_btn = self.driver.find_element(By.XPATH, "//button[@aria-label='Send']")
            send_btn.click()

            self.sent_count += 1
            status = f"✓ {phone_formatted} (text)"
            print(status)
            self.log.append(status)

            # Rate limiting
            time.sleep(2)
            return True

        except Exception as e:
            # Let exception propagate for dispatcher to handle
            raise

    def send_image_message(self, phone, image_path, caption=None):
        """Send an image to a phone number with optional caption"""
        try:
            phone_formatted = self.format_phone(phone)

            # Open WhatsApp chat link
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone_formatted}")
            time.sleep(3)  # Wait for page load

            # Click attachment button (paperclip icon)
            attach_btn = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(@aria-label, 'Attach')]"))
            )
            attach_btn.click()
            time.sleep(1)

            # Find and interact with file input
            file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            file_input.send_keys(image_path)
            time.sleep(2)

            # Wait for preview to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid='caption']"))
            )
            time.sleep(1)

            # Type caption if provided
            if caption and caption.strip():
                caption_box = self.driver.find_element(By.XPATH, "//div[@data-testid='caption']")
                caption_box.click()
                caption_box.send_keys(caption)
                time.sleep(1)

            # Click send button
            send_btn = self.driver.find_element(By.XPATH, "//button[@aria-label='Send']")
            send_btn.click()

            self.sent_count += 1
            status = f"✓ {phone_formatted} (image)"
            print(status)
            self.log.append(status)

            # Rate limiting
            time.sleep(2)
            return True

        except Exception as e:
            # Let exception propagate for dispatcher to handle
            raise

    def _prompt_on_error(self, phone, message_type):
        """Prompt user what to do on send failure. Returns: 'retry', 'skip', or 'quit'"""
        while True:
            prompt = f"\n[Error] Failed to send to {phone} ({message_type}).\n[R]etry / [S]kip / [Q]uit? "
            choice = input(prompt).strip().upper()
            if choice in ['R', 'S', 'Q']:
                return {'R': 'retry', 'S': 'skip', 'Q': 'quit'}[choice]
            print("Invalid choice. Please enter R, S, or Q.")

    def send_bulk(self):
        """Send messages to all contacts"""
        df = self.read_excel()
        if df is None or len(df) == 0:
            print("✗ No data to process")
            return

        if not self.login_whatsapp():
            return

        print(f"\n📤 Starting bulk send... ({len(df)} messages)\n")
        
        for idx, row in df.iterrows():
            phone = row['phone']
            message = row['message']

            print(f"[{idx + 1}/{len(df)}] ", end="")
            self.send_message(phone, message)
        
        self.print_summary()

    def print_summary(self):
        """Print results summary"""
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
        
        # Save log
        log_file = f"whatsapp_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(log_file, 'w') as f:
            f.write("\n".join(self.log))
        print(f"Log saved to: {log_file}")

    def run(self):
        """Main entry point"""
        try:
            self.setup_driver()
            self.send_bulk()
        finally:
            if self.driver:
                self.driver.quit()


if __name__ == "__main__":
    # Usage
    if len(sys.argv) < 2:
        print("Usage: python whatsapp_sender.py <excel_file> [country_code]")
        print("Example: python whatsapp_sender.py messages.xlsx +20")
        sys.exit(1)

    excel_file = sys.argv[1]
    country_code = sys.argv[2] if len(sys.argv) > 2 else "+20"

    try:
        sender = WhatsAppSender(excel_file, country_code)
        sender.run()
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        sys.exit(1)
