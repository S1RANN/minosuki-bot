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
from telegraph import Telegraph
import requests
import pymongo
import string
from crawl_dyxhs import crawl_douyin, crawl_xhs
from sqlalchemy import create_engine, String, Integer, select, insert, desc
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
import openai
from gpt4free import phind, ora
from mino_config import MinoConfig
import sys
import aiohttp

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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

openai.api_key = mino_conf.openai_api_key

conn = psycopg2.connect(
    f'dbname={mino_conf.setu_db_name} user={mino_conf.setu_db_user}')
cur = conn.cursor()

gpt_engine = create_engine(f'sqlite:///gpt_log.db')

conn_str = f'mongodb+srv://{mino_conf.chatlog_db_user}:{mino_conf.chatlog_db_password}@cluster0.ennznc0.mongodb.net/?retryWrites=true&w=majority'
client = pymongo.MongoClient(conn_str, serverSelectionTimeoutMS=5000)
db = client['ChatLog']

gpt4_chatbot_ids = ['b8b12eaa-5d47-44d3-92a6-4d706f2bcacf', 'fbe53266-673c-4b70-9d2d-d247785ccd91', 'bd5781cf-727a-45e9-80fd-a3cfce1350c6', '993a0102-d397-47f6-98c3-2587f2c9ec3a', 'ae5c524e-d025-478b-ad46-8843a5745261', 'cc510743-e4ab-485e-9191-76960ecb6040', 'a5cd2481-8e24-4938-aa25-8e26d6233390', '6bca5930-2aa1-4bf4-96a7-bea4d32dcdac', '884a5f2b-47a2-47a5-9e0f-851bbe76b57c', 'd5f3c491-0e74-4ef7-bdca-b7d27c59e6b3', 'd72e83f6-ef4e-4702-844f-cf4bd432eef7',
                    '6e80b170-11ed-4f1a-b992-fd04d7a9e78c', '8ef52d68-1b01-466f-bfbf-f25c13ff4a72', 'd0674e11-f22e-406b-98bc-c1ba8564f749', 'a051381d-6530-463f-be68-020afddf6a8f', '99c0afa1-9e32-4566-8909-f4ef9ac06226', '1be65282-9c59-4a96-99f8-d225059d9001', 'dba16bd8-5785-4248-a8e9-b5d1ecbfdd60', '1731450d-3226-42d0-b41c-4129fe009524', '8e74635d-000e-4819-ab2c-4e986b7a0f48', 'afe7ed01-c1ac-4129-9c71-2ca7f3800b30', 'e374c37a-8c44-4f0e-9e9f-1ad4609f24f5']
ora_model = ora.CompletionModel.load(gpt4_chatbot_ids[0], 'gpt-4')

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


def update_speak_time(message):
    filename = f'chatLog/{message.chat.id}/monitored.json'
    if os.path.exists(filename):
        df = pd.read_json(filename)
        if message.from_user.id in df['user_id'].values:
            df.loc[df['user_id'] == message.from_user.id, 'date'] = message.date
        df.to_json(filename, indent=1, date_unit='s')


async def _send_setu_preview(chat_id, img_set_date):
    setus = []
    cur.execute(
        'SELECT DISTINCT img_set_index FROM img WHERE img_set_date=%s', (img_set_date,))
    img_set_indexes = cur.fetchall()
    i = 0
    for img_set_index in img_set_indexes:
        cur.execute(
            'SELECT img_url FROM img WHERE img_set_index=%s ORDER BY img_index', (img_set_index[0],))
        imgs = cur.fetchall()
        # imgs = prepend_domain(imgs)
        imgs = [img[0] for img in imgs]
        length = len(imgs)
        tup = (0, int(length/2), length - 1)
        for t in tup:
            setus.append((imgs[t], str(i)))
            if len(setus) == 10:
                medias = [telebot.types.InputMediaPhoto(
                    media[0] + TRAILING_PARAM, media[1]) for media in setus]
                try:
                    logger.info('sending preview to %s %s', chat_id, setus)
                    await bot.send_media_group(chat_id=chat_id, media=medias)
                except telebot.apihelper.ApiTelegramException as e:
                    logger.error('%s', e.description)
                    if e.error_code == 429:
                        from time import sleep
                        sleep(e.result_json['parameters']['retry_after'])
                setus = []
                # while True:
                #     try:
                #         if index_to_change is not None:
                #             from random import randint
                #             r = randint(0, 100)
                #             medias[index_to_change] = telebot.types.InputMediaPhoto(setus[index_to_change][0] + f'?{r}', setus[index_to_change][1])
                #             index_to_change = None
                #         print('sending preview to', chat_id, setus)
                #         bot.send_media_group(chat_id = chat_id, media = medias)
                #         setus = []
                #     except telebot.apihelper.ApiTelegramException as e:
                #         print(e.description)
                #         if e.error_code == 429:
                #             from time import sleep
                #             sleep(e.result_json['parameters']['retry_after'])
                #         elif e.error_code == 400:
                #             index_to_change = int(re.search('#[0-9]+', e.description).group()[1:]) - 1
                #         else:
                #             break
                #     else:
                #         break
                # from random import randint
                # setus[-1] = telebot.types.InputMediaPhoto(imgs[t] + '?random=' + randint(0, 100))
        i += 1
    if setus:
        medias = [telebot.types.InputMediaPhoto(
            media[0] + TRAILING_PARAM, media[1]) for media in setus]
        try:
            logger.info('sending preview to %s %s', chat_id, setus)
            await bot.send_media_group(chat_id=chat_id, media=medias)
        except telebot.apihelper.ApiTelegramException as e:
            logger.error('%s', e.description)
            if e.error_code == 429:
                from time import sleep
                sleep(e.result_json['parameters']['retry_after'])
        # index_to_change = None
        # while True:
        #     try:
        #         if index_to_change is not None:
        #             from random import randint
        #             r = randint(0, 100)
        #             medias[index_to_change] = telebot.types.InputMediaPhoto(setus[index_to_change][0] + f'?{r}', setus[index_to_change][1])
        #             index_to_change = None
        #         print('sending preview to', chat_id, setus)
        #         bot.send_media_group(chat_id = chat_id, media = medias)
        #     except telebot.apihelper.ApiTelegramException as e:
        #         print(e.description)
        #         if e.error_code == 429:
        #             from time import sleep
        #             sleep(e.result_json['parameters']['retry_after'])
        #         elif e.error_code == 400:
        #             index_to_change = int(re.search('#[0-9]+', e.description).group()[1:]) - 1
        #         else:
        #             break
        #     else:
        #         break


def is_setu_date(message):
    if re.search('[0-9]{4}-[0-9]{2}-[0-9]{2}', message.text) is None:
        return False
    if re.search('[0-9]{4}-[0-9]{2}-[0-9]{2}', message.text).group() == message.text:
        return True
    return False


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


@bot.message_handler(commands=['subscribesetu'])
async def subscribe_setu(message):
    if message.chat.type != 'supergroup':
        await bot.reply_to(
            message, 'Sorry, but this bot is only available for supergroup.')
        return
    df = pd.read_json('subscribe_setu.json')
    if message.chat.id not in df.values:
        df.loc[len(df.index)] = [message.chat.id, message.chat.title,
                                 datetime.now().strftime('%Y-%m-%d')]
        df.to_json('subscribe_setu.json')
        await bot.reply_to(message, 'Subscribed successfully.')
    else:
        await bot.reply_to(message, 'Already subscribed.')


@bot.message_handler(commands=['unsubcribesetu'])
async def unsubscribe_setu(message):
    if message.chat.type != 'supergroup':
        await bot.reply_to(
            message, 'Sorry, but this bot is only available for supergroup.')
        return
    df = pd.read_json('subscribe_setu.json')
    if message.chat.id in df.values:
        df.drop(df[df['chat_id'] == message.chat.id].index)
        df.to_json('subscribe_setu.json')
        await bot.reply_to(message, 'Unsubscribed successfully.')
    else:
        await bot.reply_to(message, 'Not subscribed yet.')


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


@bot.message_handler(commands=['monitor'])
async def monitor(message):
    if message.chat.type != 'supergroup':
        await bot.reply_to(
            message, 'Sorry, but you can only use monitor in a supergroup.')
        return
    if not check_if_initialied(message):
        await bot.reply_to(message, 'Sorry, but you need to initialized first.')
        return
    filename = f'chatLog/{message.chat.id}/monitored.json'
    if os.path.exists(filename):
        df = pd.read_json(filename)
        if message.from_user.id not in df['user_id'].values:
            df.loc[len(df.index)] = [message.from_user.id, message.date, 0]
            df.to_json(filename, indent=1, date_unit='s')
            await bot.reply_to(message, 'You are now being monitored.')
        else:
            await bot.reply_to(message, 'You are already being monitored.')
    else:
        df = {'user_id': [message.from_user.id],
              'date': [message.date], 'count': 0}
        df = pd.DataFrame(df)
        df.to_json(filename, indent=1, date_unit='s')
        await bot.reply_to(message, 'You are now being monitored.')


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


@bot.message_handler(commands=['ask'])
async def ask_gpt(message):
    question = telebot.util.extract_arguments(message.text)

    ############ gpt4free-ora version #################
    try:
        result = ora.Completion.create(ora_model, question, False)
    except Exception as e:
        logger.error('Failed to get chat completion for %s from %s, error: %s',
                     question, message.from_user.id, e)
        await bot.reply_to(message, text='Error occurred, please retry')
        return
    for content in telebot.util.smart_split(result.completion.choices[0].text):
        try:
            await bot.reply_to(message, text=content, parse_mode='Markdown')
        except:
            await bot.reply_to(message, text=content)
    ############ gpt4free-phind version ###############
    # try:
    #     result = phind.Completion.create(model='gpt-4',
    #                                      prompt=question,
    #                                      results=phind.Search.create(prompt=question, actualSearch=False))
    # except Exception as e:
    #     logger.error('Failed to get chat completion for %s from %s, error: %s',
    #                  question, message.from_user.id, e)
    #     await bot.reply_to(message, text='Error occurred, please retry')
    #     return
    # for content in telebot.util.smart_split(result.completion.choices[0].text):
    #     try:
    #         await bot.reply_to(message, text=content, parse_mode='Markdown')
    #     except:
    #         await bot.reply_to(message, text=content)

    ############### ChatGPT version ###############
    # if not question:
    #     bot.reply_to(message, 'Do not ask empty questions.')
    #     return
    # user_question = {}
    # with gpt_engine.begin() as conn:
    #     log_table = ChatLog.__table__
    #     stmt = select(log_table.c.role, log_table.c.content).where(log_table.c.user_id == message.from_user.id).order_by(log_table.c.id.desc())
    #     logs = conn.execute(stmt).fetchall()
    # if logs != []:
    #     messages = []
    #     length = 0
    #     for log in logs:
    #         if (length + len(log[1])) < 2000:
    #             messages.append({'role':log[0], 'content':log[1]})
    #             length += len(log[1])
    #         else:
    #             break
    #     messages.reverse()
    #     user_question['role'] = 'user'
    #     user_question['content'] = question
    #     messages.append(user_question)
    # else:
    #     user_question['role'] = 'system'
    #     user_question['content'] = question
    #     messages = [user_question]
    # logger.info('%s asking %s', message.from_user.id, user_question)
    # try:
    #     response = openai.ChatCompletion.create(model='gpt-3.5-turbo', messages=messages)
    #     logger.info('response to question: %s', response)
    # except:
    #     bot.reply_to(message, text='Error ocurred, please retry.')
    #     return
    # response_log = response['choices'][0]['message']
    # response_log['user_id'] = message.from_user.id
    # user_question['user_id'] = message.from_user.id
    # with gpt_engine.begin() as conn:
    #     log_table = ChatLog.__table__
    #     conn.execute(insert(log_table), user_question)
    #     conn.execute(insert(log_table), response_log)
    #     conn.commit()
    # try:
    #     bot.reply_to(message, text=response_log['content'], parse_mode='Markdown')
    # except:
    #     bot.reply_to(message, text=response_log['content'])


@bot.message_handler(commands=['img'])
async def gen_img(message):
    prompt = telebot.util.extract_arguments(message.text)
    if not prompt:
        await bot.reply_to(message, 'Please provide a prompt')
        return
    logger.info('%s generating images with prompt: %s',
                message.from_user.id, prompt)
    try:
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


@bot.message_handler(commands=['cancelmonitor'])
async def cancel_monitor(message):
    if message.chat.type != 'supergroup':
        await bot.reply_to(message, 'You are not being monitored.')
        return
    if not check_if_initialied(message):
        await bot.reply_to(message, 'You are not being monitored.')
        return
    filename = f'chatLog/{message.chat.id}/monitored.json'
    if os.path.exists(filename):
        df = pd.read_json(filename)
        if message.from_user.id not in df['user_id'].values:
            await bot.reply_to(message, 'You are not being monitored.')
        else:
            df = df.drop(df[df['user_id'] == message.from_user.id].index)
            df.to_json(filename, indent=1, date_unit='s')
            await bot.reply_to(message, 'Successfully canceled.')
    else:
        await bot.reply_to(message, 'You are not being monitored.')


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


# @bot.message_handler(commands=['setu'])
# def send_setu(message):
#     with open(directory + 'last_setu.txt', 'r') as f:
#         last_setu = f.read()
#     for dir in os.scandir(setu_dir):
#         if os.path.basename(dir) > last_setu:
#             for imgjson in os.scandir(dir):
#                 df = pd.read_json(imgjson)
#                 i = 0
#                 while i < len(df.index):
#                     arr = []
#                     for j in range(10):
#                         if i + j < len(df.index):
#                             arr.append(telebot.types.InputMediaPhoto(df.loc[i + j]['media']))
#                         else:
#                             break
#                     i += 10
#                     bot.send_media_group(message.chat.id, arr)
#                     sleep(5)


@bot.message_handler(commands=['setu'])
async def select_setu_date(message):
    cur.execute(
        'SELECT DISTINCT img_set_date FROM img ORDER BY img_set_date DESC')
    dates = cur.fetchmany(size=10)
    last_date = dates[len(dates) - 1][0].strftime('%Y-%m-%d')
    dates = {date[0].strftime('%Y-%m-%d'): {'callback_data': 'selected_date ' +
                                            date[0].strftime('%Y-%m-%d')} for date in dates}
    dates['下一页'] = {'callback_data': 'next ' + last_date}
    reply_mk = telebot.util.quick_markup(dates, row_width=2)
    await bot.reply_to(message, '请选择日期：', reply_markup=reply_mk)


@bot.message_handler(func=is_setu_date, content_types=['text'])
async def respond_to_date(message):
    date = message.text
    cur.execute(
        'SELECT DISTINCT img_set_index FROM img WHERE img_set_date=%s', (date,))
    img_set_indexes = cur.fetchall()
    img_set_indexes = {str(i): {'callback_data': 'selected_setu ' + str(
        img_set_index[0])} for i, img_set_index in zip(range(len(img_set_indexes)), img_set_indexes)}
    img_set_indexes['预览'] = {'callback_data': 'preview ' + date}
    img_set_indexes['返回'] = {'callback_data': 'back_to_select_date ' + date}
    reply_mk = telebot.util.quick_markup(img_set_indexes, row_width=4)
    await bot.send_message(message.chat.id, date + ' 请选择色图：', reply_markup=reply_mk)


@bot.callback_query_handler(func=lambda call: 'selected_date ' in call.data)
async def select_setu(call):
    date = call.data.replace('selected_date ', '')
    cur.execute(
        'SELECT DISTINCT img_set_index, img_set_name FROM img WHERE img_set_date=%s', (date,))
    img_sets = cur.fetchall()
    i = 0
    text = date + ':\n'
    for img_set in img_sets:
        # cur.execute('SELECT img_set_telegraph FROM img_set WHERE img_set_index=%s', (img_set[0],))
        # img_set_telegraph = cur.fetchone()
        # if img_set_telegraph is not None:
        # text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format('https://telegra.ph/' + img_set_telegraph[0], img_set[1], img_set[0])
        # else:
        # text += str(i) + '. {}          <code>{}</code>\n'.format(img_set[1], img_set[0])
        text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format(
            mino_conf.mino_api + str(img_set[0]), img_set[1], img_set[0])
        i += 1
    # img_set_indexes = cur.fetchall()
    # img_set_indexes = { str(i): {'callback_data': 'selected_setu ' + str(img_set_index[0])} for i, img_set_index in zip(range(len(img_set_indexes)), img_set_indexes) }
    # img_set_indexes['预览'] = {'callback_data': 'preview ' + date}
    reply_mk = {}
    reply_mk['返回'] = {'callback_data': 'back_to_select_date ' + date}
    reply_mk = telebot.util.quick_markup(reply_mk)
    await bot.send_message(call.message.chat.id, text,
                           reply_markup=reply_mk, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: 'back_to_select_date ' in call.data)
async def back_to_select_date(call):
    date = call.data.replace('back_to_select_date ', '')
    flag1 = flag2 = False
    cur.execute(
        'SELECT DISTINCT img_set_date FROM img WHERE img_set_date<%s ORDER BY img_set_date DESC', (date,))
    dates1 = cur.fetchmany(size=10)
    if cur.fetchone() is not None:
        flag1 = True
    cur.execute(
        'SELECT DISTINCT img_set_date FROM img WHERE img_set_date<%s ORDER BY img_set_date DESC', (date,))
    dates2 = cur.fetchmany(size=10)
    if cur.fetchone() is not None:
        flag2 = True
    if len(dates1) > len(dates2):
        dates = dates1
        dates.sort(reverse=True)
    else:
        dates = dates2
    first_date = dates[0][0].strftime('%Y-%m-%d')
    last_date = dates[len(dates) - 1][0].strftime('%Y-%m-%d')
    dates = {date[0].strftime('%Y-%m-%d'): {'callback_data': 'selected_date ' +
                                            date[0].strftime('%Y-%m-%d')} for date in dates}
    if flag2:
        dates['上一页'] = {'callback_data': 'prev ' + first_date}
    if flag1:
        dates['下一页'] = {'callback_data': 'next ' + last_date}
    reply_mk = telebot.util.quick_markup(dates, row_width=2)
    await bot.edit_message_text('请选择日期：', chat_id=call.message.chat.id,
                                message_id=call.message.id, reply_markup=reply_mk)


@bot.callback_query_handler(func=lambda call: 'next ' in call.data)
async def next_page(call):
    date = call.data.replace('next ', '')
    cur.execute(
        'SELECT DISTINCT img_set_date FROM img WHERE img_set_date<%s ORDER BY img_set_date DESC', (date,))
    dates = cur.fetchmany(size=10)
    last_date = dates[len(dates) - 1][0].strftime('%Y-%m-%d')
    first_date = dates[0][0].strftime('%Y-%m-%d')
    dates = {date[0].strftime('%Y-%m-%d'): {'callback_data': 'selected_date ' +
                                            date[0].strftime('%Y-%m-%d')} for date in dates}
    dates['上一页'] = {'callback_data': 'prev ' + first_date}
    if cur.fetchone() is not None:
        dates['下一页'] = {'callback_data': 'next ' + last_date}
    reply_mk = telebot.util.quick_markup(dates, row_width=2)
    await bot.edit_message_text('请选择日期：', chat_id=call.message.chat.id,
                                message_id=call.message.id, reply_markup=reply_mk)


@bot.callback_query_handler(func=lambda call: 'prev ' in call.data)
async def prev_page(call):
    date = call.data.replace('prev ', '')
    cur.execute(
        'SELECT DISTINCT img_set_date FROM img WHERE img_set_date>%s ORDER BY img_set_date', (date,))
    dates = cur.fetchmany(size=10)
    dates.sort(reverse=True)
    last_date = dates[len(dates) - 1][0].strftime('%Y-%m-%d')
    first_date = dates[0][0].strftime('%Y-%m-%d')
    dates = {date[0].strftime('%Y-%m-%d'): {'callback_data': 'selected_date ' +
                                            date[0].strftime('%Y-%m-%d')} for date in dates}
    if cur.fetchone() is not None:
        dates['上一页'] = {'callback_data': 'prev ' + first_date}
    dates['下一页'] = {'callback_data': 'next ' + last_date}
    reply_mk = telebot.util.quick_markup(dates, row_width=2)
    await bot.edit_message_text('请选择日期：', chat_id=call.message.chat.id,
                                message_id=call.message.id, reply_markup=reply_mk)


@bot.callback_query_handler(func=lambda call: 'preview ' in call.data)
async def send_setu_preview(call):
    date = call.data.replace('preview ', '')
    await _send_setu_preview(call.message.chat.id, date)


@bot.message_handler(commands=['search'])
async def search_setu(message):
    search_waitlist.append(message.chat.id)
    await bot.reply_to(message, '请发送关键词：')


@bot.message_handler(func=lambda message: message.chat.id in search_waitlist)
async def respond_to_search(message):
    if (re.search('[0-9]+', message.text) is not None) and (re.search('[0-9]+', message.text).group() == message.text):
        sql = 'SELECT DISTINCT img_set_name, img_set_index FROM img WHERE img_set_index=%s'
        cur.execute(sql, (message.text,))
        img_set = cur.fetchone()
        if img_set is None:
            await bot.reply_to(message, '未查询到结果')
        else:
            # cur.execute('SELECT img_set_telegraph FROM img_set WHERE img_set_index=%s', (img_set[1],))
            # img_telegraph = cur.fetchone()
            # if img_telegraph is not None:
            #     text = '查询结果：\n<a href="{}">{}</a>'.format(img_telegraph[0], img_set[0])
            # else:
            #     text = '查询结果：\n' + img_set[0]
            text = '查询结果：\n<a href="{}">{}</a>'.format(
                mino_conf.mino_api + str(img_set[1]), img_set[0])
            # reply_mk = {'发送':{'callback_data':'selected_setu ' + str(img_set[1])}}
            # reply_mk = telebot.util.quick_markup(reply_mk)
            await bot.reply_to(message, text, parse_mode='HTML')
            search_waitlist.remove(message.chat.id)
    else:
        keywords = message.text.lower().split()
        if keywords:
            sql = 'SELECT DISTINCT img_set_name, img_set_index FROM img WHERE'
            flag = True
            for keyword in keywords:
                if flag:
                    sql += " lower(img_set_name) ~ %s"
                    flag = False
                else:
                    sql += " AND lower(img_set_name) ~ %s"
            sql += " ORDER BY img_set_index"
            cur.execute(sql, tuple(keywords))
            img_sets = cur.fetchmany(20)
            if not img_sets:
                await bot.reply_to(message, '未查询到结果')
            else:
                text = '查询结果：\n'
                i = 0
                test = cur.fetchone()
                for img_set in img_sets:
                    # cur.execute('SELECT img_set_telegraph FROM img_set WHERE img_set_index=%s', (img_set[1],))
                    # img_telegraph = cur.fetchone()
                    # if img_telegraph is not None:
                    #     text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format('https://telegra.ph/' + img_telegraph[0], img_set[0], img_set[1])
                    # else:
                    #     text += str(i) + '. {}      <code>{}</code>\n'.format(img_set[0], img_set[1])
                    text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format(
                        mino_conf.mino_api + str(img_set[1]), img_set[0], img_set[1])
                    i += 1
                reply_mk = {}
                if test is not None:
                    reply_mk['下一页'] = {'callback_data': 'next_search_page ' +
                                       str(i) + ' ' + str(img_sets[-1][1]) + ' ' + message.text}
                reply_mk = telebot.util.quick_markup(reply_mk)
                await bot.reply_to(message, text, reply_markup=reply_mk,
                                   parse_mode='HTML')
        search_waitlist.remove(message.chat.id)


@bot.callback_query_handler(func=lambda call: 'next_search_page ' in call.data)
async def next_search_page(call):
    keywords = call.data.replace('next_search_page ', '').split()
    index = keywords[0]
    max_img_set_index = keywords[1]
    keywords.pop(0)
    keywords.pop(0)
    if keywords:
        sql = 'SELECT DISTINCT img_set_name, img_set_index FROM img WHERE'
        flag = True
        for keyword in keywords:
            if flag:
                sql += " lower(img_set_name) ~ %s"
                flag = False
            else:
                sql += " AND lower(img_set_name) ~ %s"
        sql += " AND img_set_index>{}".format(max_img_set_index)
        sql += " ORDER BY img_set_index"
        cur.execute(sql, tuple(keywords))
        img_sets = cur.fetchmany(20)
        text = '查询结果：\n'
        i = int(index)
        test = cur.fetchone()
        for img_set in img_sets:
            # cur.execute('SELECT img_set_telegraph FROM img_set WHERE img_set_index=%s', (img_set[1],))
            # img_telegraph = cur.fetchone()
            # if img_telegraph is not None:
            #     text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format('https://telegra.ph/' + img_telegraph[0], img_set[0], img_set[1])
            # else:
            #     text += str(i) + '. {}      <code>{}</code>\n'.format(img_set[0], img_set[1])
            text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format(
                mino_conf.mino_api + str(img_set[1]), img_set[0], img_set[1])
            i += 1
        reply_mk = {}
        keywords = ' '.join([keyword[1:-1] for keyword in keywords])
        reply_mk['上一页'] = {'callback_data': 'prev_search_page ' +
                           str(int(index) - 20) + ' ' + str(img_sets[0][1]) + ' ' + keywords}
        if test is not None:
            reply_mk['下一页'] = {'callback_data': 'next_search_page ' +
                               str(i) + ' ' + str(img_sets[-1][1]) + ' ' + keywords}
        reply_mk = telebot.util.quick_markup(reply_mk)
        await bot.edit_message_text(text, call.message.chat.id,
                                    call.message.id, reply_markup=reply_mk, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: 'prev_search_page ' in call.data)
async def prev_search_page(call):
    keywords = call.data.replace('prev_search_page ', '').split()
    index = keywords[0]
    min_img_set_index = keywords[1]
    keywords.pop(0)
    keywords.pop(0)
    if keywords:
        sql = 'SELECT DISTINCT img_set_name, img_set_index FROM img WHERE'
        flag = True
        for keyword in keywords:
            if flag:
                sql += " lower(img_set_name) ~ %s"
                flag = False
            else:
                sql += " AND lower(img_set_name) ~ %s"
        sql += " AND img_set_index<{}".format(min_img_set_index)
        sql += " ORDER BY img_set_index DESC"
        cur.execute(sql, tuple(keywords))
        img_sets = cur.fetchmany(20)
        img_sets.sort(key=lambda e: e[1])
        text = '查询结果：\n'
        test = cur.fetchone()
        i = int(index)
        for img_set in img_sets:
            # cur.execute('SELECT img_set_telegraph FROM img_set WHERE img_set_index=%s', (img_set[1],))
            # img_telegraph = cur.fetchone()
            # if img_telegraph is not None:
            #     text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format('https://telegra.ph/' + img_telegraph[0], img_set[0], img_set[1])
            # else:
            #     text += str(i) + '. {}      <code>{}</code>\n'.format(img_set[0], img_set[1])
            text += str(i) + '. <a href="{}">{}</a>         <code>{}</code>\n'.format(
                mino_conf.mino_api + str(img_set[1]), img_set[0], img_set[1])
            i += 1
        reply_mk = {}
        keywords = ' '.join([keyword[1:-1] for keyword in keywords])
        if test is not None:
            reply_mk['上一页'] = {'callback_data': 'prev_search_page ' +
                               str(int(index) - 20) + ' ' + str(img_sets[-1][1]) + ' ' + keywords}
        reply_mk['下一页'] = {'callback_data': 'next_search_page ' +
                           str(i) + ' ' + str(img_sets[-1][1]) + ' ' + keywords}
        reply_mk = telebot.util.quick_markup(reply_mk)
        await bot.edit_message_text(text, call.message.chat.id,
                                    call.message.id, reply_markup=reply_mk, parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: 'selected_setu ' in call.data)
async def send_setu(call):
    await bot.send_message(call.message.chat.id, '大家好啊，我是米诺，今天来点大家想看的东西啊~')
    index = call.data.replace('selected_setu ', '')
    cur.execute('SELECT img_set_name FROM img where img_set_index=%s', (index,))
    title = cur.fetchone()
    if title:
        title = title[0]
        await bot.send_message(call.message.chat.id, index + '. <a href="{}">{}</a>'.format(
            mino_conf.mino_api + index, title), parse_mode='HTML')
    else:
        await bot.send_message(call.message.chat.id, 'Image set not found')
    # if TELEGRAPH_FLAG:
    #     cur.execute('SELECT img_set_name, img_set_telegraph FROM img_set WHERE img_set_index=%s', (index,))
    #     img_set = cur.fetchone()
    #     if img_set is None:
    #         cur.execute('SELECT img_set_name, img_url FROM img WHERE img_set_index=%s ORDER BY img_index', (index,))
    #         imgs = cur.fetchall()
    #         title = imgs[0][0]
    #         imgs = [ {'tag':'img', 'attrs':{'src': img[1]}} for img in imgs ]
    #         page = telegraph.create_page('Title', ['content'])
    #         telegraph.edit_page(page['path'], title, content=imgs)
    #         cur.execute('INSERT INTO img_set VALUES(%s,%s,%s) ON CONFLICT DO NOTHING', (index, title, page['path']))
    #         conn.commit()
    #         bot.send_message(call.message.chat.id, index + '. <a href="{}">{}</a>'.format('https://telegra.ph/' + page['path'], title), parse_mode='HTML')
    #     else:
    #         bot.send_message(call.message.chat.id, index + '. <a href="{}">{}</a>'.format('https://telegra.ph/' + img_set[1], img_set[0]), parse_mode='HTML')
    # else:
    #     cur.execute('SELECT img_url FROM img WHERE img_set_index=%s ORDER BY img_index', (index,))
    #     imgs = cur.fetchall()
    #     imgs = [ img[0] for img in imgs ]
    #     i = 0
    #     while i < len(imgs):
    #         arr = []
    #         for j in range(10):
    #             if i + j < len(imgs):
    #                 arr.append(imgs[i + j])
    #             else:
    #                 break
    #         i += 10
    #         print('sending media group to', call.message.chat.id, arr)
    #         medias = [ telebot.types.InputMediaPhoto(media + TRAILING_PARAM) for media in arr ]
    #         try:
    #             bot.send_media_group(chat_id = call.message.chat.id, media = medias)
    #         except telebot.apihelper.ApiTelegramException as e:
    #             print(e.description)
    #             if e.error_code == 429:
    #                 from time import sleep
    #                 sleep(e.result_json['parameters']['retry_after'])

        # index_to_change = None
        # while True:
        #     try:
        #         if index_to_change is not None:
        #             from random import randint
        #             r = randint(0, 100)
        #             medias[index_to_change] = telebot.types.InputMediaPhoto(arr[index_to_change] + f'?{r}')
        #             index_to_change = None
        #         bot.send_media_group(chat_id = call.message.chat.id, media = medias)
        #     except telebot.apihelper.ApiTelegramException as e:
        #         print(e.description)
        #         if e.error_code == 429:
        #             from time import sleep
        #             sleep(e.result_json['parameters']['retry_after'])
        #         elif e.error_code == 400:
        #             index_to_change = int(re.search('#[0-9]+', e.description).group()[1:]) - 1
        #         else:
        #             break
        #     else:
        #         break


@bot.message_handler(commands=['setcalendar'])
async def set_calendar_repond(message):
    mino_conf.awaiting_sending_calendar = True
    await bot.reply_to(message, 'Please send the new calendar')


@bot.message_handler(content_types=['photo'])
async def repond_to_photo(message):
    if mino_conf.awaiting_sending_calendar:
        mino_conf.calendar_id = message.photo[3].file_id
        await bot.reply_to(message, 'Calendar set successfully!')
        mino_conf.awaiting_sending_calendar = False


@bot.message_handler(func=lambda message: message.text == '米诺米诺米诺', content_types=['text'])
async def bobo(message):
    await bot.reply_to(message, '思诺拳，思如泉涌！念诺剑，念念不忘！浩诺掌，生生世世！米诺！米诺！米诺！')


@bot.message_handler(func=lambda message: message.text == '柚恩柚恩柚恩', content_types=['text'])
async def bobo(message):
    await bot.reply_to(message, '''有一些 心里话 想要说给你！
柚恩酱 就是你 最可爱的你！
喜欢你 喜欢你 就是喜欢你！
翻过山 越过海 你就是唯一！
有了你 生命里 全都是奇迹！
失去你 不再有 燃烧的意义！
让我们 再继续 绽放吧生命！
全世界 所有人 我最喜欢你！
我・最・喜・欢・你！！''')


@bot.message_handler(func=lambda message: message.text == '啵啵', content_types=['text'])
async def bobo(message):
    await bot.reply_to(message, '啵你妈臭屄')


# @bot.message_handler(func=lambda message: message.text == '?' or message.text == '？', content_types=['text'])
# async def curse_single_question_mark(message):
#     for _ in range(int(random.random()*5) + 1):
#         res = requests.request('GET', 'https://fun.886.be/api.php?level=max')
#         telebot.util.antiflood(
#             bot.reply_to, message=message, text=res.content.decode())


@bot.message_handler(func=lambda message: message.text == '日程表', content_types=['text'])
async def send_calendar(message):
    await bot.send_photo(chat_id=message.chat.id, photo=mino_conf.calendar_id,
                         reply_to_message_id=message.message_id)


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

    # filename = directory + 'chatLog/' + str(message.chat.id) + '/data.json'
    # with FileLock(filename + '.lock'):
    #     df = pd.read_json(filename)
    #     df.loc[df['message_id'] == message.message_id, 'content'] = message.text
    #     df.to_json(filename, indent = 1, date_unit = 's')


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

# @bot.message_handler(func=check_if_url, content_types=['text'])
# def deal_with_url(message):
#     pass


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
    update_speak_time(message)
    # filename = directory + 'chatLog/' + str(message.chat.id) + '/data.json'
    # print('reading: ', filename)
    # with FileLock(filename + '.lock'):
    #     df = pd.read_json(filename)
    #     df.loc[len(df.index)] = [message.message_id, message.from_user.id,
    #                              message.from_user.username, message.date, message.text]
    #     print('writing to log: ', message.message_id, message.from_user.id,
    #           message.from_user.username, message.date, message.text)
    #     update_speak_time(message)
    #     df.to_json(filename, indent=1, date_unit='s')


asyncio.run(bot.infinity_polling())
