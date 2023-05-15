import random
import string
from bs4 import BeautifulSoup
import requests
from urllib.parse import unquote, quote
import json
import shutil
# from playwright.sync_api import sync_playwright
import os
import re
import aiohttp

tmp_dir = '/tmp/mino/'

def gen_dict_extract(key, var):
    if hasattr(var,'items'):
        for k, v in var.items():
            if k == key:
                yield v
            if isinstance(v, dict):
                for result in gen_dict_extract(key, v):
                    yield result
            elif isinstance(v, list):
                for d in v:
                    for result in gen_dict_extract(key, d):
                        yield result

async def crawl_douyin(session: aiohttp.ClientSession, url:str) -> str | None | list[str]:
    # with sync_playwright() as p:
    result = None
        # response = requests.get(url)
        # video_id = re.search('/video/[^/]+/', response.url).group(0)
        # video_id = video_id.replace('/', '').replace('video', '')
        # browser = p.webkit.launch()
        # page = browser.new_page()
        # if type == 'video':
        #     new_url = f'https://www.douyin.com/video/{video_id}'
        # else:
        #     new_url = f'https://www.douyin.com/note/{video_id}'
        # print(new_url)
        # page.goto(url)
        # locator = page.locator("script#RENDER_DATA")
        # try:
            # locator.wait_for(timeout=5000, state='attached')
        # except:
        #     print('no script#render_data')
        #     print(page.content())
        # if locator.count() != 0:
    lua_source = '''function main(splash, args)
  user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36'
  splash:set_user_agent(user_agent)
  assert(splash:go(args.url))
  assert(splash:wait(4))
  return splash:html()
end'''
    async with session.get(f"http://127.0.0.1:8050/execute?url={url}&lua_source={quote(lua_source)}") as response:
        data = await response.text()
    data = BeautifulSoup(data, 'html.parser')
    data = data.select('script#RENDER_DATA')[0].string
    data = unquote(data)
    data = json.loads(data)
    generator = gen_dict_extract('aweme', data)
    detail = next(generator)['detail']
    playApi = detail['video']['playApi']
    if playApi != "":
        video_url = 'https:' + playApi
        response = requests.get(video_url, stream = True)
        print(f'douyin video_url: {video_url}')
        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)
        video_name = tmp_dir + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12)) + '.mp4'
        with open(video_name, 'wb') as f:
            response.raw.decode_content = True
            shutil.copyfileobj(response.raw, f)
        result = video_name
    else:
        images = detail['images']
        image_urls = [ image['urlList'][0] for image in images ]
        print(f'douyin image_urls: {image_urls}')
        result = image_urls
        # browser.close()
    return result

def crawl_xhs(url:str) -> str | None | list[str]:
    result = None
    # with sync_playwright() as p:
    #     result = None
    #     browser = p.chromium.launch()
    #     page = browser.new_page()
    #     page.goto(url)
    #     locator = page.locator("div.swiper-wrapper")
    #     try:
    #         locator.wait_for(timeout=5000, state='attached')
    #         if locator.count() != 0:
    #             imgs = locator.locator("div").all()
    #             imgs = [ img.get_attribute("style") for img in imgs ]
    #             imgs = set(imgs)
    #             imgs = [ re.sub('\"); width: [0-9]+px;', img.replace("background-image: url(\"", ""), '') for img in imgs ]  
    #             print(f'xhs image_urls: {imgs}')
    #             result = imgs
    #     except:
    #         print(page.content())
    #         locator = page.locator("script").filter(has_text="masterUrl")
    #         if locator.count() != 0:
    #             video_url = re.search('"masterUrl":"[^"]+"', locator.text_content).group(0)
    #             video_url = video_url.replace('"', '').replace('masterUrl:', '')
    #             response = requests.get(video_url, stream = True)
    #             print(f'xhs video_url: {video_url}')
    #             if not os.path.exists(tmp_dir):
    #                 os.mkdir(tmp_dir)
    #             video_name = tmp_dir + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5)) + '.mp4'
    #             with open(video_name, 'wb') as f:
    #                 response.raw.decode_content = True
    #                 shutil.copyfileobj(response.raw, f)
    #             result = video_name
    #         else:
    #             print('did not find xhs video')
    #     browser.close()
    return result
