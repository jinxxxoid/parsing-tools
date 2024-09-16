import logging
from types import SimpleNamespace
import re
import feedparser
import datetime
from dateutil.parser import parse as parse_date
from telegram.ext import ApplicationBuilder, CommandHandler, JobQueue

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = ""

sent_links = set()

# List of predefined RSS links
rss_links = [
    'https://feeds.bloomberg.com/politics/news.rss',
    'https://feeds.bloomberg.com/economics/news.rss',
    'https://feeds.bloomberg.com/bview/news.rss',
    'https://feeds.bloomberg.com/wealth/news.rss',
    'https://feeds.bloomberg.com/markets/news.rss',
    'https://feeds.bloomberg.com/technology/news.rss',
    'https://news.google.com/rss/search?q=when:24h+allinurl:bloomberg.com&hl=en-US&gl=US&ceid=US:en',
    'https://www.ft.com/rss/home',
    'http://feeds.washingtonpost.com/rss/world',
    'http://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://foreignpolicy.com/feed/',
    'https://www.france24.com/en/europe/rss',
    'https://www.france24.com/en/rss',
    'https://www.lemonde.fr/en/rss/une.xml',
    'https://www.rfi.fr/en/rss',
    'https://www.mediapart.fr/articles/feed',
    'https://feeds.leparisien.fr/leparisien/rss',
    'https://feeds.leparisien.fr/leparisien/rss/politique',
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://feeds.bbci.co.uk/news/politics/rss.xml',
    'https://feeds.bbci.co.uk/news/rss.xml',
    'https://www.theguardian.com/world/rss',
    'https://www.theguardian.com/world/europe-news/rss',
    'http://www.faz.net/rss/aktuell/'
]

# Preset keywords for scheduled parsing
preset_keywords = ['Russia', 'Putin', 'Kremlin', 'Russie', 'Poutine', 'Russland', 'Russischen Föderation']

# Global variable to store the chat_id for the scheduled task and job interval
chat_id = None
job_interval = 900  # Default interval of 15 minutes in seconds

# Global dictionary to track user-specific states
user_states = {}


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
    user_id = update.effective_chat.id
    if preset_keywords:
        keywords_list = '\n'.join(preset_keywords)
        await context.bot.send_message(chat_id=user_id,
                                       text=f"Current preset keywords:\n{keywords_list}")
    else:

        logging.info(f"Starting scheduled RSS parsing job every {job_interval // 60} minutes.")
    await context.bot.send_message(chat_id=user_id, text=f"Scheduled RSS parsing job started, "
                                                         f"running every {job_interval // 60} minutes.")

    # Schedule the periodic_task job for this user
    context.job_queue.run_repeating(lambda context: periodic_task(context, user_id), interval=job_interval,
                                    name=f"user_{user_id}_job")


async def start(update, context):
    global user_states

    user_id = update.effective_chat.id
    if user_id in user_states and user_states[user_id]:
        await context.bot.send_message(chat_id=user_id, text="Bot is already running.")
        return

    user_states[user_id] = True
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await context.bot.send_message(chat_id=user_id,
                                   text=f"Hey there! I'm up and running at {current_time}")

    logging.info(f"Starting scheduled RSS parsing job every {job_interval // 60} minutes for user {user_id}.")
    await context.bot.send_message(chat_id=user_id, text=f"Scheduled RSS parsing job started, "
                                                         f"running every {job_interval // 60} minutes.")

    # Schedule the periodic_task job for this user
    context.job_queue.run_repeating(lambda context: periodic_task(context, user_id), interval=job_interval,
                                    name=f"user_{user_id}_job")


async def periodic_task(context, user_id):
    if user_states.get(user_id, False):
        logging.info(f"Executing periodic_task for user {user_id}")
        # Handle errors within the task to ensure uninterrupted execution
        try:
            await parse_rss_feeds(None, SimpleNamespace(args=[]))
        except Exception as e:
            logging.error(f"Error during periodic task for user {user_id}: {e}")


async def parse_rss_feeds(update, context):
    keywords = context.args[:-1] if len(context.args) > 1 else preset_keywords
    time_frame = context.args[-1] if context.args and context.args[-1] in ['today', 'yesterday', 'last hour',
                                                                           'last 3 hours'] else 'today'

    if not context.args:
        keywords = preset_keywords
        time_frame = 'today'

    time_delta = get_time_frame_delta(time_frame)
    found_articles = []

    logging.info(f"Parsing RSS feeds with keywords: {keywords} and time frame: {time_frame}")

    for rss_link in set(rss_links):
        logging.info(f"Parsing RSS feed: {rss_link}")
        try:
            feed = feedparser.parse(rss_link)
            if feed.bozo:
                raise Exception(f"Failed to parse RSS feed: {rss_link}")

            articles_count = 0
            for entry in feed.entries:
                title = entry.title
                description = entry.get('summary', '')
                content = ' '.join([c['value'] for c in entry.get('content', [])])
                pub_date = parse_date(entry.published) if 'published' in entry else None

                if pub_date and pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=datetime.timezone.utc)

                for keyword in keywords:
                    pattern = create_keyword_pattern(keyword)
                    if (pattern.search(title) or pattern.search(description) or pattern.search(content)) and (
                            entry.link not in sent_links):
                        if time_delta and pub_date and pub_date >= time_delta:
                            found_articles.append((entry.title, entry.link))
                            sent_links.add(entry.link)
                            articles_count += 1
                            break

            logging.info(f"Found {articles_count} articles in RSS feed: {rss_link}")
        except Exception as e:
            error_message = f"Error processing RSS feed: {rss_link}, error: {str(e)}"
            logging.error(error_message)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=error_message)

    if found_articles:
        for title, link in found_articles:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"Found article: {title}\nLink: {link}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"No articles found with the specified keywords.")


async def stop(update, context):
    global user_states

    user_id = update.effective_chat.id
    if user_id not in user_states or not user_states[user_id]:
        await context.bot.send_message(chat_id=user_id, text="Bot is not running.")
        return

    user_states[user_id] = False
    await context.bot.send_message(chat_id=user_id, text="Stopping bot...")
    logging.info("Stopping bot...")
    context.job_queue.stop()  # Stops all jobs (you might want to manage this more specifically)
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
        "keywords, date range: today, yesterday, last hour, last day, last 3 days, last week \n"
        "/add_rss - add a custom list of RSS feeds\n"
        "/interval - Set an interval for checking news in minutes\n"
        "/add_keywords - Add new keywords to presets\n"
        "/remove_keyword - Remove keyword from presets\n"
        "/list_keywords - List all existing keyword presets\n"
        "/list_rss_links - List all existing RSS links\n"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)


def get_time_frame_delta(time_frame):
    logging.info(f"In timeframe: {time_frame}...")
    now = datetime.datetime.now(datetime.timezone.utc)

    if time_frame == 'today':
        start_of_day = datetime.datetime.combine(now.date(), datetime.time(), tzinfo=datetime.timezone.utc)
        logging.info(f"Start of today {start_of_day}")
        return start_of_day
    elif time_frame == 'yesterday':
        yesterday = now - datetime.timedelta(days=1)
        logging.info(f"Yesterday: {yesterday}")
        start_of_yesterday = datetime.datetime.combine(yesterday.date(), datetime.time(), tzinfo=datetime.timezone.utc)
        logging.info(f"Start of Yesterday {start_of_yesterday}")
        return start_of_yesterday
    elif time_frame == 'last hour':
        return now - datetime.timedelta(hours=1)
    elif time_frame == 'last 3 hours':
        return now - datetime.timedelta(hours=3)
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


async def list_rss_links(update, context):
    if rss_links:
        rss_list_text = "\n".join(rss_links)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Current RSS links:\n{rss_list_text}")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No RSS links configured.")


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


def create_keyword_pattern(keyword):
    return re.compile(r'\b' + re.escape(keyword) + r'\b')


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


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).job_queue(JobQueue()).build()

    start_handler = CommandHandler('start', start)
    stop_handler = CommandHandler('stop', stop)
    status_handler = CommandHandler('status', status)
    help_handler = CommandHandler('help', help_command)
    parse_rss_handler = CommandHandler('f', parse_rss_feeds)
    add_rss_links_handler = CommandHandler('add_rss', add_rss_links)
    remove_rss_links_handler = CommandHandler('remove_rss', remove_rss_links)
    list_rss_links_handler = CommandHandler('list_rss', list_rss_links)
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
    application.add_handler(list_rss_links_handler)

    application.add_handler(set_interval_handler)
    application.add_handler(add_keywords_handler)
    application.add_handler(remove_keywords_handler)
    application.add_handler(list_keywords_handler)

    application.run_polling()
