import pymongo
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot import asyncio_helper
from mino_config import MinoConfig
from os import environ

# if MINO_PROXY is set, use proxy
if 'MINO_PROXY' in environ:
    asyncio_helper.proxy = environ['MINO_PROXY']

mino_conf = MinoConfig.new('config.json')
bot = AsyncTeleBot(mino_conf.telegram_api_key)
conn_str = f'mongodb+srv://{mino_conf.chatlog_db_user}:{mino_conf.chatlog_db_password}@cluster0.ennznc0.mongodb.net/?retryWrites=true&w=majority'
client = pymongo.MongoClient(conn_str, serverSelectionTimeoutMS=5000)
db = client['ChatLog']

async def update_chat_info():
    chat_ids = db.list_collection_names()
    has_chats = 'chats' in chat_ids
    # remove 'chats' and 'users' from chat_ids
    if 'users' in chat_ids:
        chat_ids.remove('users')
    if 'chats' in chat_ids:
        chat_ids.remove('chats')
    tasks = []
    for chat_id in chat_ids:
        tasks.append(bot.get_chat(chat_id))
    chats = await asyncio.gather(*tasks)
    info = [{'_id': chat.id,
             'title': chat.title, 
             'type': chat.type,
             'bio': chat.bio} for chat in chats]
    
    async def get_photo(index):
        photo_id = chats[index].photo.big_file_id
        photo_file = await bot.get_file(photo_id)
        photo = await bot.download_file(photo_file.file_path)
        info[index]['photo'] = photo
    
    tasks = []
    for i in range(len(chats)):
        tasks.append(get_photo(i))
    
    await asyncio.gather(*tasks)
    
    for _info in info:
        chat = db[str(_info['_id'])]
        _info['user_ids'] = chat.distinct('user_id')
        
    # if collection chats exist, drop it
    if has_chats:
        db.drop_collection('chats')
    # create new collection
    collection = db['chats']
    collection.insert_many(info)

# async def update_user_info():
#     chat_ids = db.list_collection_names()
#     has_users = 'users' in chat_ids
#     if 'users' in chat_ids:
#         chat_ids.remove('users')
#     if 'chats' in chat_ids:
#         chat_ids.remove('chats')
#     # get all unique user_id fields from all collections
#     collection_map = {}
#     for chat_id in chat_ids:
#         collection = db[chat_id]
#         user_ids = collection.distinct('user_id')
#         for user in user_ids:
#             collection_map[user] = chat_id
    
#     async def get_chat_member(chat_id, user_id):
#         try:
#             return await bot.get_chat_member(chat_id, user_id)
#         except Exception as e:
#             return chat_id, user_id, e, None
    
#     tasks = []
#     for user_id, chat_id in collection_map.items():
#         tasks.append(get_chat_member(chat_id, user_id))
#     members = await asyncio.gather(*tasks)
#     users = [member.user for member in members if member is not None]
    
#     async def get_user_photo(user):
#         photos = await bot.get_user_profile_photos(user.id)
#         photo_id = photos.photos[0][0].file_id
#         photo_file = await bot.get_file(photo_id)
#         photo = await bot.download_file(photo_file.file_path)
#         user.photo = photo
        
#     tasks = []
#     for user in users:
#         tasks.append(get_user_photo(user))
#     await asyncio.gather(*tasks)
    
#     info = [{'_id': user.id,
#              'first_name': user.first_name,
#              'last_name': user.last_name,
#              'username': user.username,
#              'photo': user.photo} for user in users]

#     # if collection users exist, drop it
#     if has_users:
#         db.drop_collection('users')
#     # create new collection
#     collection = db['users']
#     collection.insert_many(info)
    
async def main():
    await update_chat_info()
    client.close()
    
asyncio.run(main())