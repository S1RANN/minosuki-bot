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
import http.cookies

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
    # lua_source = '''function main(splash, args)
  # user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36'
  # splash:set_user_agent(user_agent)
  # assert(splash:go(args.url))
  # assert(splash:wait(4))
  # return splash:html()
# end'''
    # async with session.get(f"http://127.0.0.1:8050/execute?url={url}&lua_source={quote(lua_source)}") as response:
        # data = await response.text()
    cookie_str = 'douyin.com; device_web_cpu_core=6; device_web_memory_size=8; architecture=amd64; webcast_local_quality=null; ttwid=1%7Cezqq-bEoESmHac80M9BDPPnHG_sPZh6mqIFdel6oTb8%7C1683607499%7Ca91ab1164f896891a61fe44ba735c0511220f487efd3f7685e6d52a4d7d75c36; my_rd=1; xgplayer_user_id=680181495828; bd_ticket_guard_client_data=eyJiZC10aWNrZXQtZ3VhcmQtdmVyc2lvbiI6MiwiYmQtdGlja2V0LWd1YXJkLWl0ZXJhdGlvbi12ZXJzaW9uIjoxLCJiZC10aWNrZXQtZ3VhcmQtcmVlLXB1YmxpYy1rZXkiOiJCRHZsVHV5YmZaSXo2Zkc3MVFrK0pVVnJ4Wi9oNFI3VjlHOERxL09HdlAyaTI3Q3JOcWlhYXlUemdDdStHVEVDalk3UGthQmpjRkxLaDRTVU1tZ1IrMG89IiwiYmQtdGlja2V0LWd1YXJkLXdlYi12ZXJzaW9uIjoxfQ==; __ac_nonce=0650af7ef003731e0794e; __ac_signature=_02B4Z6wo00f013YvYIgAAIDCZnGFsWGQhBt2D2QAALiMF2iyqZ6MDGFg2vCOdPiOEvOLJ6egSStJWWk18FJ8WB2-H1bE4hfw9t4F938tm9dlL.A1UXH0yQv4UJeF2naCi5tL.ock5zDtFE4fa5; strategyABtestKey=%221695217647.657%22; FORCE_LOGIN=%7B%22videoConsumedRemainSeconds%22%3A180%7D; s_v_web_id=verify_lmrstgk5_bzI4FSZv_QCX6_4S1x_8fne_rW85zpMvIOso; passport_csrf_token=9eb5b1d212d2d18529e89566dcb83b2d; passport_csrf_token_default=9eb5b1d212d2d18529e89566dcb83b2d; stream_recommend_feed_params=%22%7B%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22screen_width%5C%22%3A1536%2C%5C%22screen_height%5C%22%3A864%2C%5C%22browser_online%5C%22%3Atrue%2C%5C%22cpu_core_num%5C%22%3A6%2C%5C%22device_memory%5C%22%3A8%2C%5C%22downlink%5C%22%3A10%2C%5C%22effective_type%5C%22%3A%5C%224g%5C%22%2C%5C%22round_trip_time%5C%22%3A150%7D%22; download_guide=%221%2F20230920%2F0%22; home_can_add_dy_2_desktop=%221%22; msToken=TU6gDxOrLQcAfltMZIo-UMK1Emq0rEoXhLWKDiQ_qtCWqwkRURMFgi1iVWSZDJ3mgwDXxYGOoUjt8FkcI-ySObVLrnJYmQFWcl4ndmvlUDAJTzDsVJdMRWV8XbRGN-w=; msToken=V0o3LYqxs1R3SB69DKaU56t9vcHTLpqli2JFAarH8suxwNa805UQAJKi-OGOEaJfhfD_ZLntLahPadBXfv30c16F4wOn_o62biGb6MQ1CO73J__g7vDHgBCcj3QGtxM=; tt_scid=DyiW4-hghPwMhK5sb7I-etaXMwKh.5JwlRePeV-OZC7qMszVIJJmOthejgGoPf.w2caf; volume_info=%7B%22isUserMute%22%3Atrue%2C%22isMute%22%3Atrue%2C%22volume%22%3A0.982%7D; IsDouyinActive=false'
    cookies = http.cookies.SimpleCookie(cookie_str)
    async with session.get(url, cookies=cookies) as response:
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
