import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
import io
import os
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import re

# Replace this with your Telegram Bot Token from BotFather
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! I am a Telegram bot that downloads and modifies app thumbnails from the Play Store. Send me a Play Store URL (e.g., https://play.google.com/store/apps/details?id=org.telegram.messenger).",
        disable_web_page_preview=True
    )

async def process_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if the update contains a message with text
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "Please send a valid Play Store URL as text.",
            disable_web_page_preview=True
        )
        return

    play_store_url = update.message.text.strip()

    # URL validation
    if not play_store_url.startswith("https://play.google.com/store/apps/details?id="):
        await update.message.reply_text(
            "Invalid Play Store URL. Please provide a valid URL (e.g., https://play.google.com/store/apps/details?id=org.telegram.messenger).",
            disable_web_page_preview=True
        )
        return

    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Mobile Safari/537.36'
    }

    try:
        # Fetch the page
        response = requests.get(play_store_url, headers=headers, timeout=10)
        if response.status_code != 200:
            await update.message.reply_text(f"Failed to load page. Status code: {response.status_code}")
            return

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract app name (from <title> tag)
        app_name_tag = soup.find("title")
        app_name = app_name_tag.text.split(" - ")[0] if app_name_tag else "Unknown App"

        # Extract description (from meta tag with name="description")
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = description_tag.get("content", "No description available.") if description_tag else "No description available."
        # Limit description to first 100 characters for brevity
        description = (description[:100] + "...") if len(description) > 100 else description

        # Extract version number
        version = "Unknown"
        # Look for version number in the page (often near "Current Version" or in a specific div/span)
        for div in soup.find_all("div"):
            text = div.get_text().strip()
            if "Current Version" in text:
                # The version is usually in the next sibling element or nearby
                next_sibling = div.find_next_sibling()
                if next_sibling:
                    version = next_sibling.get_text().strip()
                    break
            # Alternative: Look for specific class names (Play Store often uses obfuscated class names)
            if div.get("class") and "version" in " ".join(div.get("class")).lower():
                version = div.get_text().strip()
                break

        # Extract thumbnail URL
        og_image_tag = soup.find("meta", property="og:image")
        if og_image_tag:
            image_url = og_image_tag.get("content")
            if not image_url:
                await update.message.reply_text("Image URL not found.")
                return

            # Extract app ID
            match = re.search(r'id=([a-zA-Z0-9._]+)', play_store_url)
            app_id = match.group(1) if match else "app"

            # Download thumbnail
            thumbnail_response = requests.get(image_url, headers=headers)
            thumbnail = Image.open(io.BytesIO(thumbnail_response.content)).convert('RGBA')

            # Create a new landscape image (1200x600 for better quality)
            canvas_width, canvas_height = 1200, 600
            canvas = Image.new('RGBA', (canvas_width, canvas_height), (255, 255, 255, 255))  # Fully white background

            # Resize thumbnail (50% of canvas width as per your latest code)
            thumbnail_width = int(canvas_width * 0.5)
            thumbnail_aspect = thumbnail.height / thumbnail.width
            thumbnail_height = int(thumbnail_width * thumbnail_aspect)
            thumbnail = thumbnail.resize((thumbnail_width, thumbnail_height), Image.Resampling.LANCZOS)

            # Create a rounded mask for the thumbnail
            mask = Image.new('L', (thumbnail_width, thumbnail_height), 0)
            draw = ImageDraw.Draw(mask)
            corner_radius = int(min(thumbnail_width, thumbnail_height) * 0.2)
            draw.rounded_rectangle(
                (0, 0, thumbnail_width, thumbnail_height),
                radius=corner_radius,
                fill=255
            )

            # Apply the rounded mask to the thumbnail
            rounded_thumbnail = Image.new('RGBA', (thumbnail_width, thumbnail_height))
            rounded_thumbnail.paste(thumbnail, (0, 0), mask)

            # Center the thumbnail on the canvas
            thumbnail_x = (canvas_width - thumbnail_width) // 2
            thumbnail_y = (canvas_height - thumbnail_height) // 2
            canvas.paste(rounded_thumbnail, (thumbnail_x, thumbnail_y), rounded_thumbnail)

            # Save to a temporary file
            temp_path = Path("temp_image.jpg")
            canvas = canvas.convert('RGB')
            canvas.save(temp_path, "JPEG", quality=95, optimize=True)

            # Create caption with version
            caption = f"**{app_name}** **v{version}**\n\n** {description}**"

            # Send the image to the user with the caption
            with open(temp_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=caption)

            # Delete the temporary file from the bot's system
            os.remove(temp_path)

        else:
            await update.message.reply_text("Thumbnail not found on the page.")
    except requests.RequestException as e:
        await update.message.reply_text(f"Network error: {e}")
    except OSError as e:
        await update.message.reply_text(f"File system error: {e}")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")

def main():
    # Initialize the bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))

    # URL message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_url))

    # Start the bot
    print("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

# Suggested New Features:
# 1. Add a /download command to allow users to save the modified image to their device.
# 2. Include the app's last updated date in the caption (e.g., "Last Updated: May 2025").
# 3. Add a feature to fetch and display the app's download count (e.g., "Downloads: 100M+").
# 4. Allow users to apply filters to the thumbnail (e.g., /filter grayscale).
# 5. Add a /border command to add a colored border around the thumbnail (e.g., /border red).
