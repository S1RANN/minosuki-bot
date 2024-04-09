from wordcloud import WordCloud
import pandas as pd
import os
import telebot
import jieba
import jieba.analyse
import numpy as np
from PIL import Image
from datetime import datetime

tmp_dir = '/tmp/mino/'

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
    img_path = f'{tmp_dir}wc_{chat_id}.png'
    wc.to_file(img_path)
    return img_path
