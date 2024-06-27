import logging
import feedparser
import datetime
from dateutil.parser import parse as parse_date
from telegram.ext import ApplicationBuilder, CommandHandler, JobQueue
from fastapi import FastAPI

app = FastAPI()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "7324107123:AAHj0uyWdHtqDzESBnP54jvZ0RrUoFTSQpw"

# List of predefined RSS links
rss_links = [
    'https://feeds.bloomberg.com/politics/news.rss',
    'https://feeds.bloomberg.com/markets/news.rss',
    'https://www.ft.com/rss/home',
    'http://feeds.washingtonpost.com/rss/world',
    'http://rss.nytimes.com/services/xml/rss/nyt/World.xml'
]

# Preset keywords for scheduled parsing
preset_keywords = ['Russia', 'Putin', 'GRU']

# Global variable to store the chat_id for the scheduled task and job interval
chat_id = None
job_interval = 900  # Default interval of 15 minutes in seconds


async def periodic_task(context):
    logging.info("Executing periodic_task")
    for keyword in preset_keywords:
        await parse_rss_with_keyword(context, keyword)


async def parse_rss_with_keyword(context, keyword):
    time_frame = None
    time_delta = get_time_frame_delta(time_frame)
    found_articles = []

    for rss_link in rss_links:
        logging.info(f"Parsing RSS feed: {rss_link}")
        feed = feedparser.parse(rss_link)
        if feed.bozo:
            error_message = f"Failed to parse RSS feed: {rss_link}"
            logging.error(error_message)
            await context.bot.send_message(chat_id=chat_id, text=error_message)
            continue

        articles_count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            description = entry.get('summary', '').lower()
            pub_date = parse_date(entry.published) if 'published' in entry else None

            if keyword.lower() in title or keyword.lower() in description:
                if time_delta and pub_date and pub_date < time_delta:
                    continue
                found_articles.append((entry.title, entry.link))
                articles_count += 1

        logging.info(f"Found {articles_count} articles in RSS feed: {rss_link}")
        await context.bot.send_message(chat_id=chat_id, text=f"Found {articles_count} articles in RSS feed: {rss_link}")

    if found_articles:
        for title, link in found_articles:
            await context.bot.send_message(chat_id=chat_id, text=f"Found article: {title}\nLink: {link}")
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"No articles found with the keyword '{keyword}'.")


async def add_keywords(update, context):
    global preset_keywords

    if len(context.args) < 1:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Usage: /add_keywords <keyword1> <keyword2> ...")
        return

    new_keywords = context.args

    for keyword in new_keywords:
        if keyword.lower() not in [kw.lower() for kw in preset_keywords]:
            preset_keywords.append(keyword)
            logging.info(f"Added keyword: {keyword}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Added keyword: {keyword}")
        else:
            logging.info(f"Keyword already exists: {keyword}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Keyword already exists: {keyword}")


async def remove_keyword(update, context):
    global preset_keywords

    if len(context.args) < 1:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /remove_keyword <keyword>")
        return

    keyword_to_remove = context.args[0]

    if keyword_to_remove in preset_keywords:
        preset_keywords.remove(keyword_to_remove)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Keyword '{keyword_to_remove}' removed successfully.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Keyword '{keyword_to_remove}' is not in the preset list.")


async def list_keywords(update, context):
    if preset_keywords:
        keywords_list = '\n'.join(preset_keywords)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Current preset keywords:\n{keywords_list}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No preset keywords defined.")


async def list_rss_links(update, context):
    if rss_links:
        rss_list_text = "\n".join(rss_links)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Current RSS links:\n{rss_list_text}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No RSS links configured.")


async def start(update, context):
    global chat_id
    chat_id = update.effective_chat.id
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await context.bot.send_message(chat_id=chat_id,
                                   text=f"Hey there! I'm up and running at {current_time}")

    # Indicate that the job is starting
    logging.info(f"Starting scheduled RSS parsing job every {job_interval // 60} minutes.")
    await context.bot.send_message(chat_id=chat_id, text=f"Scheduled RSS parsing job started, "
                                                         f"running every {job_interval // 60} minutes.")

    # Schedule the periodic_task job
    context.job_queue.run_repeating(periodic_task, interval=job_interval)


async def stop(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Stopping bot...")
    logging.info("Stopping bot...")
    await context.application.stop()
    await context.application.shutdown()  # Ensure all tasks are awaited
    context.job_queue.stop()
    logging.info("Bot stopped")


async def status(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Bot is running")


async def help_command(update, context):
    help_text = (
        "/start - Start the bot\n"
        "/stop - Stop the bot\n"
        "/status - Check if the bot is running\n"
        "/help - List all available commands\n"
        "/f <keyword1> <keyword2> <keyword3> <date_range> - Parse RSS feeds for articles containing the specified "
        "keywords, date range\n"
        "/add_rss - add a custom list of RSS feeds\n"
        "/interval - Set an interval for checking news in minutes\n"
        "/add_keywords - Add new keywords to presets\n"
        "/remove_keyword - Remove keyword from presets\n"
        "/list_keywords - List all existing keyword presets\n"
        "/list_rss_links - List all existing RSS links\n"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


def get_time_frame_delta(time_frame):
    if not time_frame:
        return None

    now = datetime.datetime.now()

    if time_frame == 'today':
        return datetime.datetime.combine(now.date(), datetime.time(), tzinfo=datetime.timezone.utc)
    elif time_frame == 'yesterday':
        yesterday = now - datetime.timedelta(days=1)
        return datetime.datetime.combine(yesterday.date(), datetime.time(), tzinfo=datetime.timezone.utc)
    elif time_frame == 'this week':
        start_of_week = now - datetime.timedelta(days=now.weekday())
        return datetime.datetime.combine(start_of_week.date(), datetime.time(), tzinfo=datetime.timezone.utc)
    elif time_frame == 'last hour':
        return now - datetime.timedelta(hours=1)
    elif time_frame == 'last day':
        return now - datetime.timedelta(days=1)
    elif time_frame == 'last 3 days':
        return now - datetime.timedelta(days=3)
    elif time_frame == 'last week':
        return now - datetime.timedelta(weeks=1)
    elif len(time_frame) == 10 and time_frame[4] == '-' and time_frame[7] == '-':
        return datetime.datetime.strptime(time_frame, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
    return None


async def add_rss_links(update, context):
    if len(context.args) < 1:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Usage: /add_rss_links <rss_link1> <rss_link2> ...")
        return

    new_rss_links = context.args

    for link in new_rss_links:
        if link not in rss_links:
            rss_links.append(link)
            logging.info(f"Added RSS link: {link}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Added RSS link: {link}")
        else:
            logging.info(f"RSS link already exists: {link}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"RSS link already exists: {link}")


async def remove_rss_links(update, context):
    if len(context.args) < 1:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Usage: /remove_rss_link <rss_link>")
        return

    rss_link_to_remove = context.args[0]

    if rss_link_to_remove in rss_links:
        rss_links.remove(rss_link_to_remove)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Removed RSS link: {rss_link_to_remove}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"RSS link '{rss_link_to_remove}' not found in the list.")


async def parse_rss(update, context):
    if len(context.args) < 1:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Usage: /parse [keyword1] [keyword2] [keyword3] [time_frame]")
        return

    keywords = context.args[:5]  # Take up to 5 keywords
    time_frame = context.args[5] if len(context.args) > 5 else None
    time_delta = get_time_frame_delta(time_frame)

    found_articles = []

    for rss_link in rss_links:
        logging.info(f"Parsing RSS feed: {rss_link}")
        feed = feedparser.parse(rss_link)
        if feed.bozo:
            error_message = f"Failed to parse RSS feed: {rss_link}"
            logging.error(error_message)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=error_message)
            continue

        articles_count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            description = entry.get('summary', '').lower()
            pub_date = parse_date(entry.published) if 'published' in entry else None

            for keyword in keywords:
                if keyword.lower() in title or keyword.lower() in description:
                    if time_delta and pub_date and pub_date < time_delta:
                        continue
                    found_articles.append((entry.title, entry.link))
                    articles_count += 1
                    break  # Break out of keyword loop if found

        logging.info(f"Found {articles_count} articles in RSS feed: {rss_link}")
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Found {articles_count} articles in RSS feed: {rss_link}")

    if found_articles:
        for title, link in found_articles:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"Found article: {title}\nLink: {link}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="No articles found with the specified keywords.")


async def set_interval(update, context):
    global job_interval

    if len(context.args) != 1:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /interval <minutes>")
        return

    try:
        minutes = int(context.args[0])
        if minutes < 1:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Interval must be at least 1 minute.")
            return

        job_interval = minutes * 60  # Convert minutes to seconds
        logging.info(f"Job interval set to {minutes} minutes ({job_interval} seconds).")
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Job interval set to {minutes} minutes. 🕒")

        # Send a message to the bot itself
        await context.bot.send_message(chat_id=update.message.chat_id,
                                       text=f"Job interval successfully set to {minutes} minutes. 🕒")

    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /interval <minutes>")


@app.get("/")
async def start_bot():
    application = ApplicationBuilder().token(TOKEN).job_queue(JobQueue()).build()

    start_handler = CommandHandler('start', start)
    stop_handler = CommandHandler('stop', stop)
    status_handler = CommandHandler('status', status)
    help_handler = CommandHandler('help', help_command)
    parse_rss_handler = CommandHandler('f', parse_rss)
    add_rss_links_handler = CommandHandler('add_rss', add_rss_links)
    remove_rss_links_handler = CommandHandler('remove_rss', remove_rss_links)
    set_interval_handler = CommandHandler('interval', set_interval)
    add_keywords_handler = CommandHandler('add_keywords', add_keywords)
    remove_keywords_handler = CommandHandler('remove_keyword', remove_keyword)
    list_keywords_handler = CommandHandler('list_keywords', list_keywords)

    application.add_handler(start_handler)
    application.add_handler(stop_handler)
    application.add_handler(status_handler)
    application.add_handler(help_handler)
    application.add_handler(parse_rss_handler)
    application.add_handler(add_rss_links_handler)
    application.add_handler(remove_rss_links_handler)

    application.add_handler(set_interval_handler)
    application.add_handler(add_keywords_handler)
    application.add_handler(remove_keywords_handler)
    application.add_handler(list_keywords_handler)

    application.run_polling()
    return {"message": "Bot started"}

    # Ensure the bot stops gracefully


@app.on_event("shutdown")
async def shutdown_event():
    await stop(None, None)
