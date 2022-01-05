#!/usr/bin/env python
# -*- coding: utf-8 -*-
import calendar
import time
import logging
import sqlite3
from enum import Enum

from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    ConversationHandler
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram bot token.
TOKEN = 'YOUR-TOKEN-HERE'
# DB filename.
DB_NAME = 'users.db'

# Time constants.
MINUTE_DURATION = 60
HOUR_DURATION = MINUTE_DURATION * 60
DAY_DURATION = HOUR_DURATION * 24
DAY_START = '18:52:00'
TIME_FORMAT = '%H:%M:%S'


MEDIA_PATH = 'Media/'
class MediaType(Enum):
    PHOTO = 1
    VIDEO = 2


# Messages config: key - message id (None means config for first message after dialog start), value - message config.
#   next_msg_id - next message id.
#   next_msg_time - time of day in UTC when message must be sent.
#   msg_text - message text.
#   msg_media_type - type of message media.
#   msg_media - name of media file inside MEDIA_PATH.
MESSAGES = {
    None: {
        'next_msg_delay': 0,
        'next_msg_id': 1,
    },
    1: {
        'msg_media_type': MediaType.PHOTO,
        'msg_media': 'room.jpg',
        'msg_text': 'Super message 1',
        'next_msg_delay': 1,
        'next_msg_id': 8,
    },
    8: {
        'msg_media_type': MediaType.VIDEO,
        'msg_media': 'stars.mkv',
        'msg_text': 'Super message 1',
        'next_msg_delay': 2,
        'next_msg_id': 3,
    },
    3: {
        'msg_text': 'Super message 4',
        'next_msg_delay': 10,
        'next_msg_id': 4,
    },
    4: {
        'msg_text': 'Super message 5',
        'next_msg_delay': 10,
        'next_msg_id': 5,
    },
    5: {
        'msg_text': 'Super message 6',
        'next_msg_time': DAY_START,
        'next_msg_id': 6,
    },
    6: {
        'msg_text': 'Super message 7',
        'next_msg_time': DAY_START,
        'next_msg_id': 7,
    },
    7: {
        'msg_text': 'Super message 8',
        'next_msg_time': DAY_START,
        'next_msg_id': None,
    },
}
CACHED_FILE_IDS = {}


def get_last_msg_id(conn, chat_id):
    """
    Returns last message id for given chat id.
    """
    cur = conn.cursor()
    cur.execute('SELECT last_msg_id FROM users WHERE chat_id=?', (chat_id,))
    row = cur.fetchone()
    return row[0] if row else None


def send_message(context):
    """
    Function that sends message to specific user. Called at next_msg_time of previous message.
    """
    job = context.job
    chat_id = int(job.name)
    # Uncomment if username needed
    user_info = context.bot.getChat(chat_id)

    conn = sqlite3.connect(DB_NAME)
    last_msg_id = get_last_msg_id(conn, chat_id)

    if last_msg_id not in MESSAGES:
        # Something went wrong and MESSAGES has no config for last_msg_id. It must not happen, but who knows.
        logger.error(f'User {user_info.username} tried to get config for last_msg_id {last_msg_id}, '
                     f'but there is none such thing.')
        return

    last_message = MESSAGES[last_msg_id]
    current_message_id = last_message['next_msg_id']
    message = MESSAGES.get(current_message_id)
    if message is None:
        # Something went wrong and MESSAGES has no config for current_message_id. It must not happen, but who knows.
        logger.error(f'User {user_info.username} tried to get config for current_message_id {current_message_id}, '
                     f'but there is none such thing.')
        return

    msg_text = message['msg_text']
    msg_media = message.get('msg_media')
    if msg_media:
        file_id = CACHED_FILE_IDS.get(msg_media)
        file = file_id if file_id else open(MEDIA_PATH + msg_media, "rb")
        msg_media_type = message['msg_media_type']
        if msg_media_type == MediaType.PHOTO:
            msg = context.bot.send_photo(job.context, caption=msg_text, photo=file)
            new_file_id = msg.photo[0].file_id
        elif msg_media_type == MediaType.VIDEO:
            msg = context.bot.send_video(job.context, caption=msg_text, video=file)
            new_file_id = msg.video.file_id
        else:
            assert False, f'Message media type {msg_media_type} not supported'

        if file_id is None:
            CACHED_FILE_IDS[msg_media] = new_file_id
            conn.execute(f"INSERT INTO cached_file_ids VALUES ('{msg_media}', '{new_file_id}')")
            conn.commit()
    else:
        context.bot.send_message(job.context, text=msg_text)

    cur_time = int(time.time())
    conn.execute(f"UPDATE users SET last_msg_id={current_message_id}, last_msg_receive_time={cur_time} "
                 f"WHERE chat_id={chat_id}")
    conn.commit()

    next_msg_id = message['next_msg_id']
    if next_msg_id is not None:
        send_delayed_message(context.job_queue, chat_id, message, cur_time)


def send_delayed_message(job_queue, chat_id, message_config, last_msg_receive_time):
    """
    Create delayed call of send_message() function.
    """
    next_msg_time = message_config.get('next_msg_time')
    next_msg_delay = message_config.get('next_msg_delay')
    cur_time = int(time.time())
    if next_msg_time is not None:
        time_of_current_day = cur_time % DAY_DURATION
        start_of_current_day = cur_time - time_of_current_day
        time_to_send = start_of_current_day + next_msg_time

        delay = time_to_send - cur_time
        if delay < 0:
            # If delay is negative it means that we need to send this message in next day.
            delay = time_to_send + DAY_DURATION - cur_time
    elif next_msg_delay is not None:
        last_msg_receive_time = last_msg_receive_time if last_msg_receive_time else cur_time
        time_to_send = last_msg_receive_time + next_msg_delay
        delay = time_to_send - cur_time
        if delay < 0:
            # If delay is negative it means that message must be already sent.
            delay = 0
    else:
        assert False, f'No next_msg_time or next_msg_delay found: {message_config}'

    logger.info(f'Create delayed message for chat_id {chat_id} with delay {delay}')
    job_queue.run_once(send_message, delay, context=chat_id, name=str(chat_id))


def start_command(update: Update, context: CallbackContext) -> None:
    effective_user = update.effective_user
    username = effective_user.username

    chat_id = update.message.chat_id
    conn = sqlite3.connect(DB_NAME)
    last_msg_id = get_last_msg_id(conn, chat_id)
    if last_msg_id is not None:
        logger.info(f'User {username} tried to start chat again, but all messages is sent')
        # It's not first message, no delayed call will be created.
        return

    # Send first message.
    logger.info(f'User {username} started dialog for the first time.')
    cur_time = int(time.time())
    conn.execute(f"INSERT INTO users VALUES ({chat_id}, NULL, {cur_time})")
    conn.commit()

    first_message_setup = MESSAGES[None]
    send_delayed_message(context.job_queue, chat_id, first_message_setup, cur_time)


def help_command(update: Update, context: CallbackContext) -> None:
    """
    This function is called when user types unsupported command.
    """
    update.message.reply_text("Этот бот периодически отправляет вам сообщения.")


def main() -> None:
    """
    This function is called on application start.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS 
        users (chat_id INTEGER PRIMARY KEY, last_msg_id INTEGER, last_msg_receive_time INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS 
        cached_file_ids (file_name TEXT PRIMARY KEY, file_id TEXT)''')

    updater = Updater(TOKEN, use_context=True)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={},
        fallbacks=[CommandHandler('help', help_command)]
    )
    updater.dispatcher.add_handler(conv_handler)
    updater.start_polling()

    for id_, message in MESSAGES.items():
        next_msg_time = message.get('next_msg_time')
        next_msg_delay = message.get('next_msg_delay')
        assert (next_msg_time is not None) ^ (next_msg_delay is not None), \
            f'Only next_msg_time OR next_msg_delay allowed to be used in message {id_}'
        if next_msg_time:
            time_to_send_tuple = time.strptime(next_msg_time, TIME_FORMAT)
            time_of_day_seconds = time_to_send_tuple.tm_hour * HOUR_DURATION + \
                                  time_to_send_tuple.tm_min * MINUTE_DURATION + \
                                  time_to_send_tuple.tm_sec
            message['next_msg_time'] = time_of_day_seconds

    cur = conn.cursor()
    cur.execute('SELECT file_name, file_id FROM cached_file_ids')
    while True:
        row = cur.fetchone()
        if row is None:
            # It's last selected row.
            break
        file_name, file_id = row
        CACHED_FILE_IDS[file_name] = file_id

    cur.execute('SELECT chat_id, last_msg_id, last_msg_receive_time FROM users')
    while True:
        row = cur.fetchone()
        if row is None:
            # It's last selected row.
            break

        chat_id, last_msg_id, last_msg_receive_time = row
        message = MESSAGES.get(last_msg_id)
        if message is None or message['next_msg_id'] is None:
            # There are no messages with last_msg_id or last_msg_id were the last in messages chain.
            continue
        send_delayed_message(updater.job_queue, chat_id, message, last_msg_receive_time)

    updater.idle()


if __name__ == '__main__':
    main()
