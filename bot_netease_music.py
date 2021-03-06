"""网易云点歌
发送 点歌
发送 点歌+歌名
"""
import binascii
import json

import httpx
from botoy import logger
from botoy.decorators import ignore_botself, startswith
from botoy.session import SessionHandler, ctx, session
from Crypto.Cipher import AES

handler_music = SessionHandler(
    ignore_botself, startswith("点歌"), expiration=30
).receive_group_msg()


class NeteaseApi:
    """Netease music api http://music.163.com"""

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
    """Search song from netease music"""
    number = 10
    eparams = {
        "method": "POST",
        "url": "http://music.163.com/api/cloudsearch/pc",
        "params": {"s": keyword, "type": 1, "offset": 0, "limit": number},
    }
    data = {"eparams": NeteaseApi.encode_netease_data(eparams)}

    res_data = httpx.post(
        "http://music.163.com/api/linux/forward",
        data=data,
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 Edg/94.0.992.38",
            "referer": "http://music.163.com/",
        },
    )
    if res_data.status_code == 200:
        data_finish = res_data.json()
        if data_finish["code"] == 200:
            return data_finish["result"]


def get_singer(music):
    return "/".join([singer["name"] for singer in music["ar"]])


def build_msg(music) -> str:
    singer = get_singer(music)
    music_id = music["id"]
    pic_url = music["al"]["picUrl"]
    title = music["name"]
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
                "musicUrl": f"http://music.163.com/song/media/outer/url?id={music_id}",
                "preview": pic_url,
                "sourceMsgId": "0",
                "source_icon": "",
                "source_url": "",
                "tag": "网易云音乐",
                "title": title,
            }
        },
    }
    return json.dumps(msg_dict)


@handler_music.handle
def _():
    keyword = ctx.Content[2:].strip()
    if not keyword:
        keyword = session.want(
            "music_name", "请发送歌曲关键词 (发送退出可以退出点歌)", timeout=20, default="退出"
        )
        if not keyword or keyword == "退出":
            handler_music.finish("已退出")

    data = netease_search(keyword)
    if not data:
        handler_music.finish("未获取到歌曲信息")
    logger.success(f"群:{ctx.FromGroupId}; 点歌:{keyword}")

    items = ["退出点歌"]
    for music in data["songs"]:
        items.append(f"{music['name']} {get_singer(music)}-{music['al']['name']}")

    if ret := session.choose(items, always_prompt=False, retry_times=3):
        _, idx = ret
        # idx == 0 时为退出选歌
        if idx <= 0:
            handler_music.finish('已退出')
        else:
            session.action.sendGroupJson(
                ctx.FromGroupId,
                build_msg(data["songs"][idx - 1]),
            )

    handler_music.finish()
