from wordcloud import WordCloud
import pandas as pd
import os
import telebot
import jieba
import jieba.analyse
import numpy as np
from PIL import Image
from datetime import datetime

# def generate_word_cloud(dir):
#     df = pd.read_json(dir + '/' + 'data.json')
#     content = ""
#     for sentence in df['content']:
#         content += str(sentence) + ' '
#     content = jieba.analyse.extract_tags(content, topK = 100, withWeight = True)
#     content = { x: y for x, y in content }
#     wc = WordCloud(mask = mask, height = 1200, width = 1200, font_path = font_path, min_font_size=10, margin = 10, background_color = 'white', max_font_size=200).generate_from_frequencies(content)
#     wc.to_file(dir + '/wc.png')

def generate_word_cloud(chat_id:str, text:str):
    jieba.enable_parallel(4)
    jieba.analyse.set_stop_words('stopwords.txt')
    jieba.load_userdict('userdict.txt')
    font_path = '/usr/share/fonts/adobe-source-han-sans/SourceHanSansCN-Regular.otf'
    mask = np.array(Image.open('mask.png'))
    freq = jieba.analyse.extract_tags(text, topK = 100, withWeight = True)
    freq = { x: y for x, y in freq }
    wc = WordCloud(mask = mask, height = 1200, width = 1200,
     font_path = font_path, min_font_size=10, margin = 10,
      background_color = 'white', max_font_size=250,
       relative_scaling=0.7).generate_from_frequencies(freq)
    img_path = f'/tmp/wc_{chat_id}.png'
    wc.to_file(img_path)
    return img_path

# def word_count(df):
#     current_time = datetime.now().strftime('%H:%M')
#     return '截至今日' + current_time +'，发言数:\n' + df['username'].value_counts().to_string()

# def send_word_count(dir):
#     df = pd.read_json(dir + '/' + 'data.json')
#     bot.send_message(chat_id = os.path.basename(dir), text = word_count(df))

# def send_word_cloud(dir):
#     generate_word_cloud(dir)
#     bot.send_photo(chat_id = os.path.basename(dir), photo = open(dir + '/wc.png', 'rb'))

# def send_word_count_cloud(dir):
#     send_word_count(dir)
#     send_word_cloud(dir)

# def send_multiple_word_clouds(dirs):
#     for dir in dirs:
#         if os.path.exists(dir + '/data.json'):
#             with open(dir + '/data.json', 'r') as f:
#                 if(len(f.readlines())>10):
#                     send_word_count_cloud(dir) 
#                     reset_data(dir)
#                 else:
#                     print(dir + ' not enough data, failed to send word cloud')
#         else:
#             print(dir + ' not enough data, failed to send word cloud')

# def sendwc():
#     dirs = [ f.path for f in os.scandir(directory + 'chatLog/') if f.is_dir()]
#     send_multiple_word_clouds(dirs)

    
# def reset_data(dir):
#     os.rename(dir + '/data.json', dir + '/' + datetime.now().strftime('%Y-%m-%d') + '.json')
#     with open(dir + '/data.json', 'w') as f:
#         f.write('{"message_id":{}, "user_id":{}, "username":{},"date":{},"content":{}}')
