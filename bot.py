import io
import os
import logging
from PIL import Image
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Dictionary to store uploaded images in memory per user: {user_id: [PIL.Image, ...]}
user_images = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends welcome message and usage instructions."""
    welcome_text = (
        "👋 **Welcome to the Image to PDF Bot!**\n\n"
        "How to use:\n"
        "1. Send me one or multiple images (photos or image files).\n"
        "2. Tap `/convert` to compile them into a PDF.\n"
        "3. Tap `/clear` if you want to reset your queue.\n"
        "4. Tap `/about` to read more about this bot."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays available commands and help info."""
    help_text = (
        "📖 **Bot Help & Commands**\n\n"
        "• `/start` - Start the bot and see instructions\n"
        "• `/convert` - Build a PDF from your uploaded images\n"
        "• `/clear` - Remove all queued images\n"
        "• `/about` - About this bot\n"
        "• `/help` - Show this help menu"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays information about the bot."""
    about_text = (
        "ℹ️️ **About This Bot**\n\n"
        "This bot compiles your photos and image files into a high-quality PDF document instantly.\n\n"
        "🔒 **Privacy:** Uploaded images are processed temporarily in memory and automatically cleared once your PDF is generated."
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles photos sent directly."""
    user_id = update.effective_user.id

    # Get the highest resolution photo sent
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = await photo_file.download_as_bytearray()

    # Open image using Pillow and convert to RGB (required for PDF conversion)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if user_id not in user_images:
        user_images[user_id] = []

    user_images[user_id].append(img)
    count = len(user_images[user_id])

    await update.message.reply_text(
        f"📸 Image {count} added! Send more or tap /convert when ready."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles uncompressed images sent as files/documents."""
    document = update.message.document

    # Check if document is an image
    if not document.mime_type or not document.mime_type.startswith("image/"):
        await update.message.reply_text("❌ Please send a valid image file.")
        return

    user_id = update.effective_user.id
    doc_file = await document.get_file()
    image_bytes = await doc_file.download_as_bytearray()

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if user_id not in user_images:
        user_images[user_id] = []

    user_images[user_id].append(img)
    count = len(user_images[user_id])

    await update.message.reply_text(
        f"📄 Image file {count} added! Send more or tap /convert when ready."
    )


async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Converts queued images into a single PDF file and sends it back."""
    user_id = update.effective_user.id

    if user_id not in user_images or not user_images[user_id]:
        await update.message.reply_text("⚠️ No images found! Send some images first.")
        return

    status_msg = await update.message.reply_text("⚙️ Converting images to PDF...")

    try:
        images = user_images[user_id]
        pdf_bytes = io.BytesIO()

        # Save first image as base PDF and append the rest
        first_image = images[0]
        remaining_images = images[1:] if len(images) > 1 else []

        first_image.save(
            pdf_bytes,
            format="PDF",
            save_all=True,
            append_images=remaining_images
        )
        pdf_bytes.seek(0)

        # Send the created PDF to the user
        await update.message.reply_document(
            document=pdf_bytes,
            filename="converted_document.pdf",
            caption="🎉 Here is your converted PDF!"
        )

        # Clear queue after success
        del user_images[user_id]
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error converting images to PDF: {e}")
        await update.message.reply_text("❌ Failed to create PDF. Please try again.")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears all queued images for the user."""
    user_id = update.effective_user.id
    if user_id in user_images and user_images[user_id]:
        del user_images[user_id]
        await update.message.reply_text("🗑️ Cleared all queued images.")
    else:
        await update.message.reply_text("ℹ️ Your image queue is already empty.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs exceptions and sends a message to notify the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred while processing your request. Please try again."
        )


def main():
    # Read Telegram Bot Token from Environment Variable
    bot_token = os.environ.get("BOT_TOKEN")

    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is missing!")

    app = ApplicationBuilder().token(bot_token).build()

    # 1. Command Handlers (must be registered FIRST)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("convert", convert))
    app.add_handler(CommandHandler("clear", clear))

    # 2. Message Handlers for Photos & Documents
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))

    # 3. Global Error Handler
    app.add_error_handler(error_handler)

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()