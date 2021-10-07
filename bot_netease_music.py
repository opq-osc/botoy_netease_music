import binascii
import json
import re
import time

import httpx
from Crypto.Cipher import AES
from botoy import logger
from botoy.action import Action
from botoy.decorators import ignore_botself, startswith
from botoy.session import SessionHandler, session

__doc__ = "点歌_网易云"

handler_music = SessionHandler(
    ignore_botself,
    startswith('点歌'),
    single_user=True,
    expiration=20
).receive_group_msg()


class NeteaseApi:
    """ Netease music api http://music.163.com """

    # https://github.com/0xHJK/music-dl
    @classmethod
    def encode_netease_data(cls, data) -> str:
        data = json.dumps(data)
        key = binascii.unhexlify("7246674226682325323F5E6544673A51")
        encryptor = AES.new(key, AES.MODE_ECB)
        # 补足data长度，使其是16的倍数
        pad = 16 - len(data) % 16
        fix = chr(pad) * pad
        byte_data = (data + fix).encode("utf-8")
        return binascii.hexlify(encryptor.encrypt(byte_data)).upper().decode()


def netease_search(keyword):
    """ Search song from netease music """
    number = 10
    eparams = {
        "method": "POST",
        "url": "http://music.163.com/api/cloudsearch/pc",
        "params": {"s": keyword, "type": 1, "offset": 0, "limit": number},
    }
    data = {"eparams": NeteaseApi.encode_netease_data(eparams)}

    res_data = (
        httpx.post(
            "http://music.163.com/api/linux/forward", data=data
        )
    )
    if res_data.status_code == 200:
        data_finish = res_data.json()
        if data_finish['code'] == 200:
            return data_finish['result']


def get_singer(data):
    return "/".join([singer['name'] for singer in data])


def build_music_choice_list(music_data_raw) -> str:
    music_info = []
    for music in music_data_raw['songs']:
        music_info.append(
            f"[{music_data_raw['songs'].index(music)}].{music['name']}  {get_singer(music['ar'])}-{music['al']['name']}"
        )
    return "\r".join(music_info)


def build_music_json_msg(music_data) -> str:
    singer = get_singer(music_data['ar'])
    music_id = music_data['id']
    pic_url = music_data['al']['picUrl']
    title = music_data['name']
    msg_dict = {
        "app": "com.tencent.structmsg",
        "desc": "音乐",
        "view": "music",
        "ver": "0.0.0.1",
        "prompt": f"[分享]{title}",
        "meta": {
            "music": {
                "action": "",
                "android_pkg_name": "",
                "app_type": 1,
                "appid": 100495085,
                "desc": singer,
                "jumpUrl": f"https://y.music.163.com/m/song?id={music_id}",
                "musicUrl": f"http://music.163.com//song//media//outer//url?id={music_id}",
                "preview": pic_url,
                "sourceMsgId": "0",
                "source_icon": "",
                "source_url": "",
                "tag": "网易云音乐",
                "title": title
            }
        }
    }
    return json.dumps(msg_dict)


@handler_music.handle
def _():
    if info_re := re.match("点歌(.*)", session.ctx.Content):
        if info_re[1].strip():  # 指定了歌名
            music_keyword = info_re[1].strip()
            session.set("music_name", music_keyword)
        else:
            music_keyword = session.want("music_name", "请发送歌曲关键词? (发送退出可以退出点歌)", timeout=30, default="退出")
            if music_keyword == "退出":
                handler_music.finish()
    else:
        handler_music.finish()
        return
    logger.info(f'点歌: {music_keyword}')
    music_data_raw = netease_search(music_keyword)
    if not music_data_raw:
        session.send_text("未获取到歌曲信息")
        handler_music.finish()
    session.send_text(build_music_choice_list(music_data_raw))
    time.sleep(1)
    while music_index := session.want("music_index", "请选择序号", pop=True, default="退出"):
        if music_index == "退出":
            handler_music.finish()
        if music_index.isdigit():
            if len(music_data_raw['songs']) > int(music_index) >= 0:
                break
            else:
                session.send_text("请输入正确的序号")
                time.sleep(1)
                continue
        else:
            session.send_text("请输入数字")
            time.sleep(1)
            continue
    music_json_msg = build_music_json_msg(music_data_raw['songs'][int(music_index)])
    Action(qq=session.ctx.CurrentQQ).sendGroupJson(session.ctx.FromGroupId, music_json_msg)
    handler_music.finish()
