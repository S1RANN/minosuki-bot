import os
import logging
import logging.handlers
import asyncio
import random
import telebot.util
from telebot import async_telebot
import pandas as pd
from word_cloud import generate_word_cloud
import signal
from datetime import datetime, timedelta
import json
import psycopg2
import re
from filelock import FileLock
import pymongo
import string
from crawl_dyxhs import crawl_douyin, crawl_xhs
from sqlalchemy import create_engine, String, Integer, select, insert, desc
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
# import openai
from mino_config import MinoConfig
import sys
import aiohttp

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.handlers.RotatingFileHandler(
    filename='log/main.log', maxBytes=10000)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s]%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

mino_conf = MinoConfig.new('config.json')

bot = async_telebot.AsyncTeleBot(mino_conf.telegram_api_key)

TRAILING_PARAM = r''
search_waitlist = []

# openai.api_key = mino_conf.openai_api_key

conn = psycopg2.connect(
    f'dbname={mino_conf.setu_db_name} user={mino_conf.setu_db_user} password={mino_conf.setu_db_password}')
cur = conn.cursor()

gpt_engine = create_engine(f'sqlite:///gpt_log.db')

conn_str = f'mongodb+srv://{mino_conf.chatlog_db_user}:{mino_conf.chatlog_db_password}@cluster0.ennznc0.mongodb.net/?retryWrites=true&w=majority'
client = pymongo.MongoClient(conn_str, serverSelectionTimeoutMS=5000)
db = client['ChatLog']

def exit_handler(signum, frame):
    cur.close()
    conn.close()
    mino_conf.dump()
    sys.exit(0)

signal.signal(signal.SIGTERM, exit_handler)

def check_if_url(message):
    if (message.entities == None):
        return False
    for e in message.entities:
        if (e.type == 'url'):
            return True
    return False

def check_if_initialied(message):
    collection_names = db.list_collection_names()
    return str(message.chat.id) in collection_names

@bot.message_handler(commands=['start'])
async def start(message):
    if message.chat.type != 'supergroup':
        await bot.reply_to(
            message, 'Sorry, but this bot is only available for supergroup.')
    elif not check_if_initialied(message):
        try:
            collection = db[str(message.chat.id)]
            doc = {
                '_id': message.message_id,
                'user_id': message.from_user.id,
                'username': message.from_user.username,
                'date': message.date,
                'content': message.text
            }
            collection.insert_one(doc)
            await bot.reply_to(message, "WordCloud ready!")
        except:
            logger.error('Error creating chatlog database %s', message.chat.id)
            await bot.reply_to(message, 'Something went wrong, try again later.')
    else:
        await bot.reply_to(message, 'Already initialized!')

@bot.message_handler(commands=['getwordcloud'])
async def get_word_cloud(message):
    if not check_if_initialied(message):
        await bot.reply_to(message, 'Uninitialized! Failed to get word cloud.')
        return
    collection = db[str(message.chat.id)]
    content = ''
    yesterday_timestamp = int((datetime.now() - timedelta(1)).timestamp())
    date_filter = {
        'date': {
            '$gte': yesterday_timestamp
        }
    }
    if collection.count_documents(date_filter) == 0:
        await bot.reply_to(message, 'Not enough data')
        return
    for doc in collection.find(date_filter):
        content += doc['content']
    img_path = generate_word_cloud(str(message.chat.id), content)
    with open(img_path, 'rb') as f:
        await bot.send_photo(chat_id=message.chat.id, photo=f,
                             reply_to_message_id=message.message_id)

class Base(DeclarativeBase):
    pass


class ChatLog(Base):
    __tablename__ = 'chatLogs'
    id: Mapped[int] = mapped_column(
        Integer(), primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(String(2000))

    def __repr__(self):
        return "<User(user_id='%s', role='%s', content='%s')>" % (
            self.user_id, self.role, self.content)

async def ask_gpt(message, model):
    question = telebot.util.extract_arguments(message.text)

    logger.info('%s asking question: %s', message.from_user.id, question)

    if not question:
        await bot.reply_to(message, 'Do not ask empty questions.')
        return
    
    user_question = {}
    messages = []
    
    if model == 'gemini':
        messages = [{'role':'USER', 'parts':[{'text':question}]}]
    else:
        with gpt_engine.begin() as conn:
            log_table = ChatLog.__table__
            stmt = select(log_table.c.role, log_table.c.content).where(log_table.c.user_id == message.from_user.id).order_by(log_table.c.id.desc())
            logs = conn.execute(stmt).fetchall()
            if logs != []:
                user_question = {'role':'user', 'content':question}
                messages = [user_question]
                length = len(question)
                for log in logs:
                    if (length + len(log[1])) < 2000:
                        messages.append({'role':log[0], 'content':log[1]})
                        length += len(log[1])
                    else:
                        break
                messages.reverse()
            else:
                user_question = {'role':'system', 'content':question}
                messages = [user_question]    
    
    session = await async_telebot.asyncio_helper.session_manager.get_session()
    
    json_body = {}
    if model == 'gemini':
        json_body['contents'] = messages
        headers = {'x-goog-api-key': mino_conf.gemini_api_key}
        endpoint = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent'
    else:
        json_body['model'] = model
        json_body['messages'] = messages
        headers = {'Authorization': f'Bearer {mino_conf.chatgpt_api_key}'}
        endpoint = mino_conf.chatgpt_api_endpoint
    
    logger.debug('ChatGPT request json body: %s', json_body)

    try:
        async with session.post(endpoint, json=json_body, headers=headers) as response:
            if response.status == 200:
                result = await response.json()
            else:
                logger.info('Failed to receiver answer: %s %s', response.status, await response.text())
                await bot.reply_to(message, text='Error ocurred, please retry.')
                return
    except aiohttp.ClientConnectorError as e:
        logger.info('Failed to receive answer: %s', e)
        await bot.reply_to(message, text='Error ocurred, please retry.')
        return

    if model == 'gemini':
        response_log = result['candidates'][0]['contents']
        result = response_log['parts'][0]['text']
    else:
        response_log = result['choices'][0]['message']
        result = response_log['content']

    logger.info('response to question: %s', result)

    response_log['user_id'] = message.from_user.id
    user_question['user_id'] = message.from_user.id

    if model != 'gemini':
        with gpt_engine.begin() as conn:
            log_table = ChatLog.__table__
            conn.execute(insert(log_table), user_question)
            conn.execute(insert(log_table), response_log)
            conn.commit()
    try:
        await bot.reply_to(message, text=result, parse_mode='Markdown')
    except:
        await bot.reply_to(message, text=result)

@bot.message_handler(commands=['ask'])
async def ask_gpt3dot5(message):
    await ask_gpt(message, 'gpt-3.5-turbo')

@bot.message_handler(commands=['ask4'])
async def ask_gpt4(message):
    await ask_gpt(message, 'gpt-4')

@bot.message_handler(commands=['askg'])
async def ask_gemini(message):
    await ask_gpt(message, 'gemini')

@bot.message_handler(commands=['img'])
async def gen_img(message):
    prompt = telebot.util.extract_arguments(message.text)
    if not prompt:
        await bot.reply_to(message, 'Please provide a prompt')
        return
    logger.info('%s generating images with prompt: %s',
                message.from_user.id, prompt)
    try:
        import openai
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size='1024x1024'
        )
        img_url = response['data'][0]['url']
        logger.info('response image url to prompt: %s', img_url)
    except:
        await bot.reply_to(message, 'Error ocurred, please retry.')
        return
    await bot.send_photo(chat_id=message.chat.id, photo=img_url,
                         reply_to_message_id=message.message_id)

@bot.message_handler(commands=['getpassword'])
async def get_password(message):
    if message.chat.type != 'private':
        await bot.reply_to(message, '请私聊')
        return
    password_dir = 'password.json'
    with FileLock(password_dir + '.lock'):
        with open(password_dir, 'r') as f:
            passwords = json.load(f)
        if str(message.from_user.id) in passwords:
            password = passwords[str(message.from_user.id)]
            await bot.reply_to(message, password)
            logger.info('%s asking for password: %s',
                        message.from_user.username, password)
            return
        src_chars = string.ascii_letters + string.digits
        password = ''.join(random.choice(src_chars) for _ in range(24))
        passwords[message.from_user.id] = password
        with open(password_dir, 'w') as f:
            json.dump(passwords, f)
        await bot.reply_to(message, password)
        logger.info('%s asking for password: %s',
                    message.from_user.username, password)

@bot.edited_message_handler(content_types=['text'])
async def edit_log(message):
    if not check_if_initialied(message):
        return
    collection = db[str(message.chat.id)]
    collection.update_one(
        {'id': message.message_id},
        {'$set': {
            'content': message.text
        }}
    )

def check_douyin_url(message):
    return 'v.douyin.com' in message.text

def parse_entity(text: str, offset: int, length: int) -> str:
    count = 0
    _offset = 0
    _length = 0
    text = text.encode()
    i = 0
    for byte in text:
        if count == offset:
            _offset = i
        if (byte & 0xc0) != 0x80:
            if byte >= 0xf0:
                count += 2
            else:
                count += 1
        if count - offset == length:
            _length = i + 1
        i += 1
    return text[_offset:_length].decode()


@bot.message_handler(func=check_douyin_url, content_types=['text'])
async def analyze_douyin_url(message):
    for e in message.entities:
        if e.type == 'url':
            url = parse_entity(message.text, e.offset, e.length)
            if '图文' in message.text:
                logger.info('crawling douyin pictures: %s', url)
            else:
                logger.info('crawling douyin video: %s', url)
            session = await async_telebot.asyncio_helper.session_manager.get_session()
            result = await crawl_douyin(session, url)
            if isinstance(result, str):
                with open(result, 'rb') as f:
                    await bot.send_video(message.chat.id, f, reply_to_message_id=message.message_id)
                    logger.info('sending douyin video: %s', result)
            elif isinstance(result, list):
                i = 0
                while i < len(result):
                    arr = []
                    for j in range(10):
                        if i + j < len(result):
                            arr.append(result[i + j])
                        else:
                            break
                    i += 10
                    logger.info('sending media group to %s: %s',
                                message.chat.id, arr)
                    medias = [telebot.types.InputMediaPhoto(
                        media) for media in arr]
                    await bot.send_media_group(chat_id=message.chat.id,
                                               media=medias, reply_to_message_id=message.message_id)

@bot.message_handler(func=lambda x: "xhslink.com" in x.text, content_types=['text'])
async def analyze_xhs_url(message):
    for e in message.entities:
        if e.type == 'url':
            url = parse_entity(message.text, e.offset, e.length)
            logger.info("crawling xhs video: %s", url)
            result = crawl_xhs(url)
            if isinstance(result, str):
                with open(result, 'rb') as f:
                    await bot.send_video(message.chat.id, f, reply_to_message_id=message.message_id)
                    logger.info('sending douyin video: %s', result)
                os.remove(result)
            elif isinstance(result, list):
                i = 0
                while i < len(result):
                    arr = []
                    for j in range(10):
                        if i + j < len(result):
                            arr.append(result[i + j])
                        else:
                            break
                    i += 10
                    logger.info('sending media group to %s: %s',
                                message.chat.id, arr)
                    medias = [telebot.types.InputMediaPhoto(
                        media) for media in arr]
                    await bot.send_media_group(chat_id=message.chat.id,
                                               media=medias, reply_to_message_id=message.message_id)


def has_url(message):
    pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    return pattern.search(message.text) is not None

@bot.message_handler(func=has_url, content_types=['text'])
async def filter_url(message):
    pass

@bot.message_handler(content_types=['text'])
async def write_to_log(message):
    if not check_if_initialied(message):
        return
    collection = db[str(message.chat.id)]
    doc = {
        '_id': message.message_id,
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'date': message.date,
        'content': message.text
    }
    collection.insert_one(doc)
    logger.info('writing to log: %s', doc)

asyncio.run(bot.infinity_polling())
