# Image Support for WhatsApp Bulk Sender

**Date:** 2026-06-01  
**Status:** Design approved  
**Scope:** Add ability to send images with optional captions alongside text messages

## Overview

Extend the WhatsApp bulk sender to support sending image files from an Excel spreadsheet. Users can specify images via file path, optionally paired with caption text. The script will maintain existing text-only functionality while adding image upload capability.

## Requirements

### Functional
- Support sending images with optional text captions
- Accept file paths as absolute or relative (relative to Excel location)
- Handle cases where both message and image are provided (send image with caption)
- Prompt user interactively on send failure (retry/skip/stop)
- Track sent messages and images separately in logs

### Data Structure
- Excel columns: `phone`, `message`, `image_path`
- At least one of `message` or `image_path` must be provided
- Filter out rows with both empty
- Resolve relative paths to absolute paths using Excel file directory

### Constraints
- No file format validation (let WhatsApp handle it)
- Support both absolute and relative file paths
- File must exist before attempting upload
- Interactive error handling (pause and prompt on failure)

## Design

### Data Layer

**Excel validation in `read_excel()`:**
- Load three columns: `phone`, `message`, `image_path`
- Drop rows where both `message` and `image_path` are empty
- Convert `image_path` values to absolute paths:
  - If starts with `/` or contains `:`, use as absolute
  - Otherwise, resolve relative to Excel file's directory
- Warn user if any rows were filtered due to missing content

### Message Layer

Two separate sending methods handle different message types:

**`send_text_message(phone, message)`**
- Existing text sending logic (type message, click send)
- Used when only `message` column is filled

**`send_image_message(phone, image_path, caption=None)`**
- Click attachment button (paperclip icon) in WhatsApp Web
- Locate and interact with hidden `<input type="file">` element
- Send file path via `send_keys()` to upload image
- Wait for image preview to appear (timeout: 10 seconds)
- If caption provided, type it in message box
- Click send button

**`send_message(phone, message, image_path)` (dispatcher)**
- Validates inputs:
  - If `image_path` provided, check file exists (raise clear error if not)
  - If neither provided, return error
- Routes to appropriate sender based on what's filled
- Handles failures via interactive prompt (see Error Handling section)

### Error Handling

**Pre-send validation:**
- File existence check: raise `FileNotFoundError` with path in error message
- File readability check: raise `PermissionError` if not readable

**On send failure:**
- Pause execution and display prompt:
  ```
  [Error] Failed to send to +962123456789 (image). 
  [R]etry / [S]kip / [Q]uit?
  ```
- Wait for user input (R/S/Q):
  - **R**: Retry the send immediately
  - **S**: Skip this message and continue to next
  - **Q**: Exit script with summary
- Log the failure with error details

**Retry logic:**
- Maximum 1 retry per message (2 total attempts)
- If retry fails, prompt again

### Logging & Output

**Console output format:**
- Text message success: `✓ +962123456789 (text)`
- Image message success: `✓ +962123456789 (image)`
- Failure: `✗ +962123456789 (image) - Error message`

**Summary report:**
- Continue tracking `sent_count` and `failed_count` (combined for both types)
- Optional: separate counters for text vs image sent (for future reporting)

## Technical Details

### File Path Resolution

```python
def resolve_image_path(image_path, excel_dir):
    if os.path.isabs(image_path):
        return image_path
    return os.path.join(excel_dir, image_path)
```

### Selenium for Image Upload

```
1. Click attachment button: find_element(By.XPATH, "//button[contains(@aria-label, 'Attach')]")
2. Find file input: find_element(By.CSS_SELECTOR, "input[type='file']")
3. Send file path: file_input.send_keys(absolute_path)
4. Wait for preview: WebDriverWait(...).until(EC.presence_of_element_located((By.XPATH, "//div[@data-testid='caption']")))
5. Type caption if provided
6. Click send
```

### Changes to Existing Code

**`__init__`:**
- No changes (country code validation stays same)

**`read_excel()`:**
- Add loading of `image_path` column
- Add validation for rows with both empty
- Add file path resolution logic
- Update success message to show count

**`send_message()`:**
- Rename current implementation to `send_text_message()`
- Create new `send_image_message()` with image upload logic
- Create dispatcher `send_message(phone, message, image_path)` that routes to appropriate method
- Add interactive error prompt on failure

**`send_bulk()`:**
- Pass `image_path` to `send_message()` alongside `message`

**`format_phone()`:**
- No changes

**`print_summary()`:**
- No changes (works with combined sent/failed counts)

## Testing Strategy

1. **Validation:**
   - Test with Excel containing text-only, image-only, and mixed rows
   - Test with absolute and relative paths
   - Test with missing/invalid file paths

2. **Sending:**
   - Send text message (existing functionality)
   - Send image only (no caption)
   - Send image with caption
   - Verify WhatsApp Web displays content correctly

3. **Error handling:**
   - Test missing file (should prompt user)
   - Test network timeout (should prompt user)
   - Test user canceling upload (should prompt user)

## Rollout

This feature is additive and backward-compatible:
- Existing Excel files with only `phone` and `message` columns continue to work
- New column `image_path` is optional
- Script gracefully handles missing columns (treats as empty)

## Out of Scope

- File format validation
- Batch image uploads (one per message row only)
- Image compression or resizing
- Preview of images before sending
- Support for media albums or grouped images
