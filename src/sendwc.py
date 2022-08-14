#!/bin/python
from datetime import datetime, timedelta
import pymongo
import asyncio
from telebot.async_telebot import AsyncTeleBot
from word_cloud import generate_word_cloud
from mino_config import MinoConfig

mino_conf = MinoConfig.new('config.json')

bot = AsyncTeleBot(mino_conf.telegram_api_key)

conn_str = f'mongodb+srv://{mino_conf.chatlog_db_user}:{mino_conf.chatlog_db_password}@cluster0.ennznc0.mongodb.net/?retryWrites=true&w=majority'
client = pymongo.MongoClient(conn_str, serverSelectionTimeoutMS=5000)
db = client['ChatLog']

async def sendwc():
    collection_names = db.list_collection_names()
    yesterday_timestamp = int((datetime.now() - timedelta(1)).timestamp())
    date_filter = {
        'date':{
            '$gte': yesterday_timestamp
        }
    }
    async def send(collection_name):
        if db[collection_name].count_documents(date_filter) == 0:
            continue
        content = ''
        for doc in db[collection_name].find(date_filter):
            content += doc['content']
        img_path = generate_word_cloud(collection_name, content)
        text = '截至今日' + datetime.now().strftime('%H:%M') +'，发言数:\n' + str(db[collection_name].count_documents(date_filter))
        await bot.send_message(chat_id=collection_name, text=text)
        with open(img_path, 'rb') as f:
            await bot.send_photo(chat_id=collection_name, photo=f)
    coroutines = []
    for collection_name in collection_names:
        coroutines.append(send(collection_name))
    await asyncio.gather(*coroutines)

asyncio.run(sendwc())