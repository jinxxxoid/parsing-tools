import logging
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext, ApplicationBuilder
from collections import defaultdict

# Google Docs setup
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']
TOKEN = '7316290190:AAFXUAROmOrtpeZ56X9pykJzENbbJ4nT0qQ'

# Load Google credentials
creds = service_account.Credentials.from_service_account_file('tstprj-359809-5bfb09eceda2.json', scopes=SCOPES)
service = build('docs', 'v1', credentials=creds)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def extract_document_id(google_doc_url):
    """Extract the document ID from the Google Doc URL."""
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', google_doc_url)
    if match:
        return match.group(1)
    else:
        return None


def fetch_document_text(document_id):
    try:
        doc = service.documents().get(documentId=document_id).execute()
        content = doc.get('body').get('content', [])
        text = parse_google_doc_content(content)
        return text
    except Exception as e:
        logging.error(f"Error fetching document: {e}")
        raise


def split_text(text, max_length=4096):
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 1 <= max_length:
            current_chunk += paragraph + '\n'
        else:
            # Ensure chunk does not end in the middle of a Markdown entity
            while len(current_chunk) > 0 and current_chunk[-1] in '*_~`[':
                current_chunk = current_chunk[:-1]

            chunks.append(current_chunk)
            current_chunk = paragraph + '\n'

    # Add the last chunk if any content is left
    if current_chunk:
        chunks.append(current_chunk)

    # Split chunks that still exceed max_length
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_length:
            while len(chunk) > max_length:
                split_point = max_length
                while split_point > 0 and chunk[split_point] not in [' ', '\n']:
                    split_point -= 1

                # Ensure not breaking in the middle of Markdown entities
                final_chunk = chunk[:split_point].rstrip()
                while len(final_chunk) > 0 and final_chunk[-1] in '*_~`[':
                    final_chunk = final_chunk[:-1]

                final_chunks.append(final_chunk)
                chunk = chunk[split_point:].lstrip()
            if chunk:
                final_chunks.append(chunk)
        else:
            final_chunks.append(chunk)

    return final_chunks


def parse_google_doc_content(content):
    """Parse Google Docs content into Markdown while preserving formatting and exact newlines."""
    text = ''
    for element in content:
        if 'paragraph' in element:
            paragraph_text = ''
            for part in element['paragraph']['elements']:
                if 'textRun' in part:
                    run = part['textRun']
                    if 'content' in run and run['content'].strip():  # Ensure content is not empty
                        if 'textStyle' in run and run['textStyle']:
                            paragraph_text += apply_text_style(run['textStyle'], run['content'])
                        else:
                            paragraph_text += run['content']

            if paragraph_text:
                # Add the paragraph text and ensure a single newline at the end of each paragraph
                text += paragraph_text + '\n'

    # Ensure that newlines from the original document are preserved correctly
    text = re.sub(r'\n{2,}', '\n\n', text)  # Convert multiple newlines into two newlines
    text = text.strip()  # Remove any trailing newlines
    return text


def apply_text_style(style, text):
    if 'bold' in style and style['bold']:
        text = f"*{text}*"
    if 'italic' in style and style['italic']:
        text = f"_{text}_"
    if 'link' in style and 'url' in style['link']:
        text = f"[{text}]({style['link']['url']})"
    return text


async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Send me a Google Doc link, and I'll fetch and format it for you.",
                                    parse_mode=ParseMode.MARKDOWN)


async def stop(update: Update, context: CallbackContext):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Stopping bot...")
    logging.info("Stopping bot...")
    await context.application.stop()
    await context.application.shutdown()
    context.job_queue.stop()
    logging.info("Bot stopped")


# Dictionary to store user-specific data
user_data = defaultdict(dict)


async def latest(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id in user_data and 'last_document' in user_data[user_id]:
        document_id = user_data[user_id]['last_document']
        try:
            text = fetch_document_text(document_id)
            chunks = split_text(text)
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("No recent document found. Please send a Google Doc link first.",
                                        parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    google_doc_link = update.message.text
    document_id = extract_document_id(google_doc_link)

    if document_id:
        try:
            text = fetch_document_text(document_id)
            chunks = split_text(text)
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            user_data[user_id]['last_document'] = document_id
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {str(e)}", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("Please provide a valid Google Doc link.", parse_mode=ParseMode.MARKDOWN)


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("latest", latest))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Starting bot...")
    application.run_polling()


if __name__ == '__main__':
    main()
