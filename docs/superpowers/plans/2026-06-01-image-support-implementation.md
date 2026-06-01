# Image Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add support for sending images with optional captions alongside text messages in the WhatsApp bulk sender.

**Architecture:** Refactor `send_message()` into three methods: `send_text_message()` for text-only, `send_image_message()` for images, and a dispatcher `send_message()` that routes based on input. Enhance `read_excel()` to load and validate the new `image_path` column with file path resolution. Add interactive error prompts for send failures.

**Tech Stack:** Selenium, pandas, os (for file path handling)

---

## Task 1: Add imports and helper function for path resolution

**Files:**
- Modify: `send_bulk.py:1-20`

- [ ] **Step 1: Add `os` import at top of file**

```python
import os
```

Add after line 15 (`from datetime import datetime`).

- [ ] **Step 2: Add path resolution helper function**

Add this function after the `WhatsAppSender` class definition but before `__init__`:

```python
def _resolve_image_path(self, image_path, excel_dir):
    """Resolve relative paths to absolute, leave absolute paths unchanged."""
    if os.path.isabs(image_path):
        return image_path
    return os.path.abspath(os.path.join(excel_dir, image_path))
```

- [ ] **Step 3: Commit**

```bash
git add send_bulk.py
git commit -m "feat: add os import and path resolution helper"
```

---

## Task 2: Refactor and enhance `read_excel()` to load image_path column

**Files:**
- Modify: `send_bulk.py:78-110` (read_excel method)

- [ ] **Step 1: Update read_excel() to load image_path column**

Replace the entire `read_excel()` method with:

```python
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

        # Convert to string and strip whitespace
        df['phone'] = df['phone'].astype(str).str.strip()
        df['message'] = df['message'].astype(str).str.strip()
        df['image_path'] = df['image_path'].astype(str).str.strip()

        # Filter: at least one of message or image_path must be provided
        initial_count = len(df)
        df = df[~((df['message'] == '') & (df['image_path'] == ''))]
        df = df[df['phone'] != '']
        
        # Resolve image paths relative to Excel directory
        excel_dir = os.path.dirname(os.path.abspath(self.excel_file))
        df['image_path'] = df['image_path'].apply(
            lambda x: self._resolve_image_path(x, excel_dir) if x and x != '' else ''
        )

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
```

- [ ] **Step 2: Commit**

```bash
git add send_bulk.py
git commit -m "feat: enhance read_excel() to load and resolve image_path column"
```

---

## Task 3: Refactor existing send_message() into send_text_message()

**Files:**
- Modify: `send_bulk.py:94-131` (send_message method)

- [ ] **Step 1: Rename and simplify to send_text_message()**

Replace the current `send_message()` method with:

```python
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
```

Note: Returns `(False, error_message)` on failure for the dispatcher to handle.

- [ ] **Step 2: Commit**

```bash
git add send_bulk.py
git commit -m "refactor: rename send_message() to send_text_message() with error tuple return"
```

---

## Task 4: Implement send_image_message() method

**Files:**
- Modify: `send_bulk.py` (add new method after send_text_message)

- [ ] **Step 1: Add send_image_message() method**

Add this method after `send_text_message()`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add send_bulk.py
git commit -m "feat: add send_image_message() method for image uploads"
```

---

## Task 5: Implement error handling prompt function

**Files:**
- Modify: `send_bulk.py` (add helper method)

- [ ] **Step 1: Add interactive error prompt method**

Add this method after `send_image_message()`:

```python
def _prompt_on_error(self, phone, message_type):
    """Prompt user what to do on send failure. Returns: 'retry', 'skip', or 'quit'"""
    while True:
        prompt = f"\n[Error] Failed to send to {phone} ({message_type}).\n[R]etry / [S]kip / [Q]uit? "
        choice = input(prompt).strip().upper()
        if choice in ['R', 'S', 'Q']:
            return {'R': 'retry', 'S': 'skip', 'Q': 'quit'}[choice]
        print("Invalid choice. Please enter R, S, or Q.")
```

- [ ] **Step 2: Commit**

```bash
git add send_bulk.py
git commit -m "feat: add _prompt_on_error() for interactive failure handling"
```

---

## Task 6: Implement send_message() dispatcher with retry logic

**Files:**
- Modify: `send_bulk.py` (add dispatcher method)

- [ ] **Step 1: Add send_message() dispatcher method**

Add this method after `_prompt_on_error()`:

```python
def send_message(self, phone, message, image_path):
    """Dispatcher: route to text or image sender with retry/skip/quit handling"""
    # Validate inputs
    has_message = message and str(message).strip() != ''
    has_image = image_path and str(image_path).strip() != ''

    if not has_message and not has_image:
        self.failed_count += 1
        status = f"✗ {phone} - No message or image provided"
        print(status)
        self.log.append(status)
        return

    # Validate image file exists if provided
    if has_image:
        if not os.path.exists(image_path):
            self.failed_count += 1
            status = f"✗ {phone} - Image not found: {image_path}"
            print(status)
            self.log.append(status)
            return
        if not os.access(image_path, os.R_OK):
            self.failed_count += 1
            status = f"✗ {phone} - Cannot read image: {image_path}"
            print(status)
            self.log.append(status)
            return

    # Route to appropriate sender
    message_type = 'image' if has_image else 'text'
    attempt = 1
    max_attempts = 2

    while attempt <= max_attempts:
        try:
            if has_image:
                caption = message if has_message else None
                self.send_image_message(phone, image_path, caption)
            else:
                self.send_text_message(phone, message)
            
            return  # Success, exit function

        except Exception as e:
            if attempt < max_attempts:
                action = self._prompt_on_error(phone, message_type)
                if action == 'retry':
                    attempt += 1
                    continue
                elif action == 'skip':
                    self.failed_count += 1
                    status = f"✗ {phone} - Skipped after error"
                    print(status)
                    self.log.append(status)
                    return
                else:  # quit
                    print("\n⚠ Exiting...")
                    raise KeyboardInterrupt("User quit")
            else:
                self.failed_count += 1
                status = f"✗ {phone} - {str(e)[:50]}"
                print(status)
                self.log.append(status)
                return
```

- [ ] **Step 2: Commit**

```bash
git add send_bulk.py
git commit -m "feat: add send_message() dispatcher with retry/skip/quit logic"
```

---

## Task 7: Update send_bulk() to pass image_path to send_message()

**Files:**
- Modify: `send_bulk.py:141-150` (send_bulk method)

- [ ] **Step 1: Update send_bulk() to pass image_path**

Replace the message sending loop in `send_bulk()`:

```python
for idx, row in df.iterrows():
    phone = row['phone']
    message = row['message']
    image_path = row['image_path']

    print(f"[{idx + 1}/{len(df)}] ", end="")
    self.send_message(phone, message, image_path)
```

- [ ] **Step 2: Commit**

```bash
git add send_bulk.py
git commit -m "feat: update send_bulk() to pass image_path to send_message()"
```

---

## Task 8: Test with mixed Excel data

**Files:**
- Create: `test_image_data.xlsx`

- [ ] **Step 1: Create test Excel file with mixed data**

```python
import pandas as pd

test_data = {
    'phone': ['1234567890', '9876543210', '5555555555'],
    'message': ['Hello text message', '', 'Image with caption'],
    'image_path': ['', './test_images/photo1.jpg', './test_images/photo2.jpg']
}

df = pd.DataFrame(test_data)
df.to_excel('test_image_data.xlsx', index=False)
print("✓ Test file created")
```

Run this locally (not in the script) to create the test file.

- [ ] **Step 2: Create test_images directory**

```bash
mkdir -p test_images
touch test_images/photo1.jpg test_images/photo2.jpg
```

- [ ] **Step 3: Manual test - run script**

```bash
python3 send_bulk.py test_image_data.xlsx +962
```

Expected behavior:
- Row 1: Send text message to 1234567890
- Row 2: Send image (photo1.jpg) to 9876543210
- Row 3: Send image (photo2.jpg) with caption "Image with caption" to 5555555555

- [ ] **Step 4: Test error handling**

Delete one of the test image files and run again. Script should:
- Report file not found
- Not attempt to send
- Continue with other rows

- [ ] **Step 5: Commit test data (optional)**

```bash
git add test_image_data.xlsx test_images/
git commit -m "test: add mixed message/image test data"
```

---

## Task 9: Verify backward compatibility

**Files:**
- Use existing: `messages.xlsx`

- [ ] **Step 1: Test with existing text-only Excel file**

```bash
python3 send_bulk.py messages.xlsx +962
```

Expected: Script works as before, sends all text messages successfully.

- [ ] **Step 2: Verify no changes to output format**

Check that:
- Success messages show `(text)` suffix
- Summary still shows sent/failed counts
- Log file is created with correct format

---

## Task 10: Code review and cleanup

**Files:**
- Modify: `send_bulk.py` (final review)

- [ ] **Step 1: Review send_bulk.py for consistency**

Check:
- All method signatures match spec (phone, message, image_path parameters)
- All error messages are clear and consistent
- No duplicate code or logic
- Comments are minimal and only for non-obvious behavior

- [ ] **Step 2: Run final test with both text and images**

```bash
python3 send_bulk.py test_image_data.xlsx +962
```

- [ ] **Step 3: Final commit**

```bash
git log --oneline | head -10
git status
```

Should show clean state with 9 commits for this feature.

---

## Verification Checklist

Before considering this complete, verify:

- [ ] Excel file with 3 columns (phone, message, image_path) loads correctly
- [ ] Relative paths resolve correctly relative to Excel directory
- [ ] Absolute paths work unchanged
- [ ] Text-only messages send via send_text_message()
- [ ] Images-only send via send_image_message()
- [ ] Image with caption sends both
- [ ] Missing image file is caught before send attempt
- [ ] Send failure prompts user with R/S/Q options
- [ ] Retry works and retries the send
- [ ] Skip logs failure and continues to next row
- [ ] Quit exits with current summary
- [ ] Backward compatible with existing text-only Excel files
- [ ] Sent/failed counts are accurate
- [ ] Log file shows message type (text/image)
