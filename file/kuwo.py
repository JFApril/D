# KuWoMusic.py  —— 酷我音乐 TVBox 爬虫（单文件 · 零第三方依赖）
# coding=utf-8
"""
单文件版：原 KuWoClient.py（TVBox 爬虫）+ kuwo_server.js（本地 9528 中转服务）合并。

变更点：
  1. 不再需要 Node、不再需要本地 9528 服务，Python 直接请求酷我接口。
  2. 只依赖 Python 标准库（urllib / json / zlib / base64），无需 pip install requests。
  3. 原 Node 端能力全部保留：
       - 搜索（search.kuwo.cn/r.s）
       - 播放直链（nmobi convert_url_with_sign，支持 128k / 192k / 320k / flac 无损）
       - 歌词三级兜底（openapi -> newh5-http -> newh5-https）
       - 逐字歌词 LRCX 解析（含 [kuwo:八进制] 偏移换算法、gb18030 解码）
       - 封面（artistpicserver）
  4. 接口方法名与原 KuWoHttpClient 完全一致，Spider 逻辑未改动。

扩展配置（extend 传 JSON，均可省略）：
    {"quality": "320k",      # 128k / 192k / 320k / flac
     "word_lyric": 1,        # 1=逐字歌词（卡拉OK高亮），0=普通逐行
     "timeout": 20}
    旧配置里的 server_url 已无意义，传了也会被忽略。

命令行自测（不装 TVBox 也能验证）：
    python KuWoMusic.py 周杰伦
"""

import ast
import base64
import gzip
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

try:
    from base.spider import Spider as BaseSpider
except Exception:
    # 脱离影视+ 环境（纯命令行自测）时兜底，TVBox 内始终能正常导入
    class BaseSpider(object):
        def __init__(self, *a, **k):
            pass

# ==================== 日志 ====================

LOG_DIR = "/storage/emulated/0/WebHTV/logs"
LOG_FILE = os.path.join(LOG_DIR, "kuwo_music.log")


def log(msg):
    try:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (timestamp, msg))
    except Exception:
        pass


# ==================== 配置 ====================

DEFAULT_CONFIG = {
    "quality": "320k",
    "word_lyric": 1,
    "timeout": 20,
}

QUALITY_NAMES = {
    "128k": "标准音质",
    "192k": "高品音质",
    "320k": "超品质",
    "flac": "无损音质",
}

ARTIST_LIST = [
    {"n": "全部", "v": ""},
    {"n": "阿杜", "v": "阿杜"},
    {"n": "阿牛", "v": "阿牛"},
    {"n": "阿桑", "v": "阿桑"},
    {"n": "阿信", "v": "阿信"},
    {"n": "阿肆", "v": "阿肆"},
    {"n": "阿兰", "v": "阿兰"},
    {"n": "阿朵", "v": "阿朵"},
    {"n": "阿冗", "v": "阿冗"},
    {"n": "阿YueYue", "v": "阿YueYue"},
    {"n": "阿悠悠", "v": "阿悠悠"},
    {"n": "阿冷", "v": "阿冷"},
    {"n": "阿哲", "v": "阿哲"},
    {"n": "阿悄", "v": "阿悄"},
    {"n": "阿佳组合", "v": "阿佳组合"},
    {"n": "阿里郎", "v": "阿里郎"},
    {"n": "阿木", "v": "阿木"},
    {"n": "阿宝", "v": "阿宝"},
    {"n": "阿云嘎", "v": "阿云嘎"},
    {"n": "阿鲁阿卓", "v": "阿鲁阿卓"},
    {"n": "阿幼朵", "v": "阿幼朵"},
    {"n": "安又琪", "v": "安又琪"},
    {"n": "安琥", "v": "安琥"},
    {"n": "安心亚", "v": "安心亚"},
    {"n": "艾怡良", "v": "艾怡良"},
    {"n": "艾热", "v": "艾热"},
    {"n": "艾福杰尼", "v": "艾福杰尼"},
    {"n": "艾辰", "v": "艾辰"},
    {"n": "安来宁", "v": "安来宁"},
    {"n": "安溥", "v": "安溥"},
    {"n": "Beyond", "v": "Beyond"},
    {"n": "八三夭", "v": "八三夭"},
    {"n": "巴奈", "v": "巴奈"},
    {"n": "白安", "v": "白安"},
    {"n": "白举纲", "v": "白举纲"},
    {"n": "白小白", "v": "白小白"},
    {"n": "白鹿", "v": "白鹿"},
    {"n": "白百何", "v": "白百何"},
    {"n": "半吨兄弟", "v": "半吨兄弟"},
    {"n": "芭比", "v": "芭比"},
    {"n": "巴雅尔", "v": "巴雅尔"},
    {"n": "鲍家街43号", "v": "鲍家街43号"},
    {"n": "蔡依林", "v": "蔡依林"},
    {"n": "蔡健雅", "v": "蔡健雅"},
    {"n": "蔡琴", "v": "蔡琴"},
    {"n": "蔡国庆", "v": "蔡国庆"},
    {"n": "蔡旻佑", "v": "蔡旻佑"},
    {"n": "蔡妍", "v": "蔡妍"},
    {"n": "蔡淳佳", "v": "蔡淳佳"},
    {"n": "蔡诗芸", "v": "蔡诗芸"},
    {"n": "蔡黄汝", "v": "蔡黄汝"},
    {"n": "曹格", "v": "曹格"},
    {"n": "曹方", "v": "曹方"},
    {"n": "曹轩宾", "v": "曹轩宾"},
    {"n": "曹杨", "v": "曹杨"},
    {"n": "草蜢", "v": "草蜢"},
    {"n": "侧田", "v": "侧田"},
    {"n": "曾轶可", "v": "曾轶可"},
    {"n": "曾沛慈", "v": "曾沛慈"},
    {"n": "曾之乔", "v": "曾之乔"},
    {"n": "曾昱嘉", "v": "曾昱嘉"},
    {"n": "曾静玟", "v": "曾静玟"},
    {"n": "陈奕迅", "v": "陈奕迅"},
    {"n": "陈百强", "v": "陈百强"},
    {"n": "陈楚生", "v": "陈楚生"},
    {"n": "陈粒", "v": "陈粒"},
    {"n": "陈绮贞", "v": "陈绮贞"},
    {"n": "陈慧娴", "v": "陈慧娴"},
    {"n": "陈慧琳", "v": "陈慧琳"},
    {"n": "陈卓璇", "v": "陈卓璇"},
    {"n": "陈小春", "v": "陈小春"},
    {"n": "陈冠希", "v": "陈冠希"},
    {"n": "陈伟霆", "v": "陈伟霆"},
    {"n": "陈学冬", "v": "陈学冬"},
    {"n": "陈翔", "v": "陈翔"},
    {"n": "陈冰", "v": "陈冰"},
    {"n": "陈乐基", "v": "陈乐基"},
    {"n": "陈芳语", "v": "陈芳语"},
    {"n": "陈势安", "v": "陈势安"},
    {"n": "陈升", "v": "陈升"},
    {"n": "陈洁仪", "v": "陈洁仪"},
    {"n": "陈明", "v": "陈明"},
    {"n": "陈红", "v": "陈红"},
    {"n": "陈淑桦", "v": "陈淑桦"},
    {"n": "陈秋霞", "v": "陈秋霞"},
    {"n": "陈芬兰", "v": "陈芬兰"},
    {"n": "陈百潭", "v": "陈百潭"},
    {"n": "陈雷", "v": "陈雷"},
    {"n": "陈明章", "v": "陈明章"},
    {"n": "陈建年", "v": "陈建年"},
    {"n": "陈志朋", "v": "陈志朋"},
    {"n": "陈珊妮", "v": "陈珊妮"},
    {"n": "陈瑞", "v": "陈瑞"},
    {"n": "邓紫棋", "v": "邓紫棋"},
    {"n": "邓丽君", "v": "邓丽君"},
    {"n": "戴佩妮", "v": "戴佩妮"},
    {"n": "单依纯", "v": "单依纯"},
    {"n": "动力火车", "v": "动力火车"},
    {"n": "杜德伟", "v": "杜德伟"},
    {"n": "刀郎", "v": "刀郎"},
    {"n": "大张伟", "v": "大张伟"},
    {"n": "丁当", "v": "丁当"},
    {"n": "戴荃", "v": "戴荃"},
    {"n": "邓超", "v": "邓超"},
    {"n": "董又霖", "v": "董又霖"},
    {"n": "窦唯", "v": "窦唯"},
    {"n": "戴爱玲", "v": "戴爱玲"},
    {"n": "邓福如", "v": "邓福如"},
    {"n": "迪克牛仔", "v": "迪克牛仔"},
    {"n": "丁薇", "v": "丁薇"},
    {"n": "丁世光", "v": "丁世光"},
    {"n": "丢火车", "v": "丢火车"},
    {"n": "段林希", "v": "段林希"},
    {"n": "段奥娟", "v": "段奥娟"},
    {"n": "多亮", "v": "多亮"},
    {"n": "杜丽莎", "v": "杜丽莎"},
    {"n": "贰佰", "v": "贰佰"},
    {"n": "二珂", "v": "二珂"},
    {"n": "凤凰传奇", "v": "凤凰传奇"},
    {"n": "费翔", "v": "费翔"},
    {"n": "费玉清", "v": "费玉清"},
    {"n": "凤飞飞", "v": "凤飞飞"},
    {"n": "方大同", "v": "方大同"},
    {"n": "范玮琪", "v": "范玮琪"},
    {"n": "房东的猫", "v": "房东的猫"},
    {"n": "方力申", "v": "方力申"},
    {"n": "方季惟", "v": "方季惟"},
    {"n": "冯提莫", "v": "冯提莫"},
    {"n": "冯曦妤", "v": "冯曦妤"},
    {"n": "郭富城", "v": "郭富城"},
    {"n": "郭静", "v": "郭静"},
    {"n": "光良", "v": "光良"},
    {"n": "关喆", "v": "关喆"},
    {"n": "隔壁老樊", "v": "隔壁老樊"},
    {"n": "告五人", "v": "告五人"},
    {"n": "古巨基", "v": "古巨基"},
    {"n": "高晓松", "v": "高晓松"},
    {"n": "高进", "v": "高进"},
    {"n": "高嘉朗", "v": "高嘉朗"},
    {"n": "高胜美", "v": "高胜美"},
    {"n": "高慧君", "v": "高慧君"},
    {"n": "关智斌", "v": "关智斌"},
    {"n": "关诗敏", "v": "关诗敏"},
    {"n": "关心妍", "v": "关心妍"},
    {"n": "韩红", "v": "韩红"},
    {"n": "韩磊", "v": "韩磊"},
    {"n": "韩庚", "v": "韩庚"},
    {"n": "韩雪", "v": "韩雪"},
    {"n": "韩安旭", "v": "韩安旭"},
    {"n": "韩宝仪", "v": "韩宝仪"},
    {"n": "何洁", "v": "何洁"},
    {"n": "何炅", "v": "何炅"},
    {"n": "何润东", "v": "何润东"},
    {"n": "何晟铭", "v": "何晟铭"},
    {"n": "何韵诗", "v": "何韵诗"},
    {"n": "黄龄", "v": "黄龄"},
    {"n": "黄霄雲", "v": "黄霄雲"},
    {"n": "华晨宇", "v": "华晨宇"},
    {"n": "好妹妹", "v": "好妹妹"},
    {"n": "黑豹乐队", "v": "黑豹乐队"},
    {"n": "海龟先生", "v": "海龟先生"},
    {"n": "花儿乐队", "v": "花儿乐队"},
    {"n": "黄品源", "v": "黄品源"},
    {"n": "黄立行", "v": "黄立行"},
    {"n": "黄义达", "v": "黄义达"},
    {"n": "黄舒骏", "v": "黄舒骏"},
    {"n": "黄磊", "v": "黄磊"},
    {"n": "黄大炜", "v": "黄大炜"},
    {"n": "黄安", "v": "黄安"},
    {"n": "黄耀明", "v": "黄耀明"},
    {"n": "黄小琥", "v": "黄小琥"},
    {"n": "黄丽玲", "v": "黄丽玲"},
    {"n": "林俊杰", "v": "林俊杰"},
    {"n": "周杰伦", "v": "周杰伦"},
    {"n": "张学友", "v": "张学友"},
    {"n": "张信哲", "v": "张信哲"},
    {"n": "张惠妹", "v": "张惠妹"},
    {"n": "张靓颖", "v": "张靓颖"},
    {"n": "张韶涵", "v": "张韶涵"},
    {"n": "张碧晨", "v": "张碧晨"},
    {"n": "张杰", "v": "张杰"},
    {"n": "张宇", "v": "张宇"},
    {"n": "张悬", "v": "张悬"},
    {"n": "张玮伽", "v": "张玮伽"},
    {"n": "张芸京", "v": "张芸京"},
    {"n": "郑秀文", "v": "郑秀文"},
    {"n": "甄妮", "v": "甄妮"},
    {"n": "周华健", "v": "周华健"},
    {"n": "周传雄", "v": "周传雄"},
    {"n": "周深", "v": "周深"},
    {"n": "周兴哲", "v": "周兴哲"},
    {"n": "周笔畅", "v": "周笔畅"},
    {"n": "张震岳", "v": "张震岳"},
    {"n": "张敬轩", "v": "张敬轩"},
    {"n": "张栋梁", "v": "张栋梁"},
    {"n": "筷子兄弟", "v": "筷子兄弟"},
    {"n": "邝美云", "v": "邝美云"},
    {"n": "柯有伦", "v": "柯有伦"},
    {"n": "柯以敏", "v": "柯以敏"},
    {"n": "康康", "v": "康康"},
    {"n": "刘德华", "v": "刘德华"},
    {"n": "黎明", "v": "黎明"},
    {"n": "林忆莲", "v": "林忆莲"},
    {"n": "林志炫", "v": "林志炫"},
    {"n": "梁静茹", "v": "梁静茹"},
    {"n": "刘若英", "v": "刘若英"},
    {"n": "李娜", "v": "李娜"},
    {"n": "李宇春", "v": "李宇春"},
    {"n": "李荣浩", "v": "李荣浩"},
    {"n": "李玖哲", "v": "李玖哲"},
    {"n": "李代沫", "v": "李代沫"},
    {"n": "李宗盛", "v": "李宗盛"},
    {"n": "李健", "v": "李健"},
    {"n": "李玟", "v": "李玟"},
    {"n": "李克勤", "v": "李克勤"},
    {"n": "李玉刚", "v": "李玉刚"},
    {"n": "李霄云", "v": "李霄云"},
    {"n": "李斯丹妮", "v": "李斯丹妮"},
    {"n": "李艺彤", "v": "李艺彤"},
    {"n": "毛阿敏", "v": "毛阿敏"},
    {"n": "毛宁", "v": "毛宁"},
    {"n": "毛不易", "v": "毛不易"},
    {"n": "马頔", "v": "马頔"},
    {"n": "马天宇", "v": "马天宇"},
    {"n": "马思纯", "v": "马思纯"},
    {"n": "马佳", "v": "马佳"},
    {"n": "马嘉祺", "v": "马嘉祺"},
    {"n": "马伯骞", "v": "马伯骞"},
    {"n": "马条", "v": "马条"},
    {"n": "马浚伟", "v": "马浚伟"},
    {"n": "那英", "v": "那英"},
    {"n": "南征北战", "v": "南征北战"},
    {"n": "牛奶咖啡", "v": "牛奶咖啡"},
    {"n": "南拳妈妈", "v": "南拳妈妈"},
    {"n": "倪安东", "v": "倪安东"},
    {"n": "品冠", "v": "品冠"},
    {"n": "平安", "v": "平安"},
    {"n": "潘玮柏", "v": "潘玮柏"},
    {"n": "潘越云", "v": "潘越云"},
    {"n": "潘长江", "v": "潘长江"},
    {"n": "潘美辰", "v": "潘美辰"},
    {"n": "潘裕文", "v": "潘裕文"},
    {"n": "彭佳慧", "v": "彭佳慧"},
    {"n": "彭坦", "v": "彭坦"},
    {"n": "彭羚", "v": "彭羚"},
    {"n": "齐秦", "v": "齐秦"},
    {"n": "齐豫", "v": "齐豫"},
    {"n": "戚薇", "v": "戚薇"},
    {"n": "乔任梁", "v": "乔任梁"},
    {"n": "秦昊", "v": "秦昊"},
    {"n": "秦岚", "v": "秦岚"},
    {"n": "钱正昊", "v": "钱正昊"},
    {"n": "邱泽", "v": "邱泽"},
    {"n": "任贤齐", "v": "任贤齐"},
    {"n": "任然", "v": "任然"},
    {"n": "容祖儿", "v": "容祖儿"},
    {"n": "容中尔甲", "v": "容中尔甲"},
    {"n": "S.H.E", "v": "S.H.E"},
    {"n": "孙燕姿", "v": "孙燕姿"},
    {"n": "孙楠", "v": "孙楠"},
    {"n": "宋冬野", "v": "宋冬野"},
    {"n": "苏星婕", "v": "苏星婕"},
    {"n": "苏妙玲", "v": "苏妙玲"},
    {"n": "苏打绿", "v": "苏打绿"},
    {"n": "苏有朋", "v": "苏有朋"},
    {"n": "苏醒", "v": "苏醒"},
    {"n": "苏慧伦", "v": "苏慧伦"},
    {"n": "苏永康", "v": "苏永康"},
    {"n": "苏见信", "v": "苏见信"},
    {"n": "沈以诚", "v": "沈以诚"},
    {"n": "TFBOYS", "v": "TFBOYS"},
    {"n": "田震", "v": "田震"},
    {"n": "田馥甄", "v": "田馥甄"},
    {"n": "谭咏麟", "v": "谭咏麟"},
    {"n": "谭维维", "v": "谭维维"},
    {"n": "谭松韵", "v": "谭松韵"},
    {"n": "逃跑计划", "v": "逃跑计划"},
    {"n": "痛仰", "v": "痛仰"},
    {"n": "唐磊", "v": "唐磊"},
    {"n": "唐朝乐队", "v": "唐朝乐队"},
    {"n": "陶喆", "v": "陶喆"},
    {"n": "陶晶莹", "v": "陶晶莹"},
    {"n": "王菲", "v": "王菲"},
    {"n": "王杰", "v": "王杰"},
    {"n": "王力宏", "v": "王力宏"},
    {"n": "王心凌", "v": "王心凌"},
    {"n": "王琳凯", "v": "王琳凯"},
    {"n": "王靖雯", "v": "王靖雯"},
    {"n": "王铮亮", "v": "王铮亮"},
    {"n": "王栎鑫", "v": "王栎鑫"},
    {"n": "王源", "v": "王源"},
    {"n": "王俊凯", "v": "王俊凯"},
    {"n": "王祖蓝", "v": "王祖蓝"},
    {"n": "王嘉尔", "v": "王嘉尔"},
    {"n": "王大陆", "v": "王大陆"},
    {"n": "王子异", "v": "王子异"},
    {"n": "王晰", "v": "王晰"},
    {"n": "王艺瑾", "v": "王艺瑾"},
    {"n": "王诗安", "v": "王诗安"},
    {"n": "王贰浪", "v": "王贰浪"},
    {"n": "王祖贤", "v": "王祖贤"},
    {"n": "许美静", "v": "许美静"},
    {"n": "许茹芸", "v": "许茹芸"},
    {"n": "许嵩", "v": "许嵩"},
    {"n": "许魏洲", "v": "许魏洲"},
    {"n": "许飞", "v": "许飞"},
    {"n": "许佳琪", "v": "许佳琪"},
    {"n": "许冠杰", "v": "许冠杰"},
    {"n": "谢安琪", "v": "谢安琪"},
    {"n": "谢霆锋", "v": "谢霆锋"},
    {"n": "谢娜", "v": "谢娜"},
    {"n": "谢春花", "v": "谢春花"},
    {"n": "谢天笑", "v": "谢天笑"},
    {"n": "谢军", "v": "谢军"},
    {"n": "谢金燕", "v": "谢金燕"},
    {"n": "辛晓琪", "v": "辛晓琪"},
    {"n": "薛之谦", "v": "薛之谦"},
    {"n": "薛凯琪", "v": "薛凯琪"},
    {"n": "徐佳莹", "v": "徐佳莹"},
    {"n": "徐良", "v": "徐良"},
    {"n": "徐怀钰", "v": "徐怀钰"},
    {"n": "徐誉滕", "v": "徐誉滕"},
    {"n": "徐秉龙", "v": "徐秉龙"},
    {"n": "希林娜依高", "v": "希林娜依高"},
    {"n": "小虎队", "v": "小虎队"},
    {"n": "小阿七", "v": "小阿七"},
    {"n": "小鬼", "v": "小鬼"},
    {"n": "小柯", "v": "小柯"},
    {"n": "杨钰莹", "v": "杨钰莹"},
    {"n": "杨丞琳", "v": "杨丞琳"},
    {"n": "杨千嬅", "v": "杨千嬅"},
    {"n": "杨宗纬", "v": "杨宗纬"},
    {"n": "杨坤", "v": "杨坤"},
    {"n": "杨幂", "v": "杨幂"},
    {"n": "杨采妮", "v": "杨采妮"},
    {"n": "杨培安", "v": "杨培安"},
    {"n": "杨乃文", "v": "杨乃文"},
    {"n": "叶倩文", "v": "叶倩文"},
    {"n": "叶炫清", "v": "叶炫清"},
    {"n": "叶世荣", "v": "叶世荣"},
    {"n": "叶启田", "v": "叶启田"},
    {"n": "叶丽仪", "v": "叶丽仪"},
    {"n": "游鸿明", "v": "游鸿明"},
    {"n": "尤长靖", "v": "尤长靖"},
    {"n": "郁可唯", "v": "郁可唯"},
    {"n": "于文文", "v": "于文文"},
    {"n": "于朦胧", "v": "于朦胧"},
    {"n": "袁娅维", "v": "袁娅维"},
    {"n": "袁咏琳", "v": "袁咏琳"},
]

STYLE_LIST = [
    {"n": "全部", "v": ""},
    {"n": "新歌", "v": "新歌"},
    {"n": "热歌", "v": "热歌"},
    {"n": "流行", "v": "流行"},
    {"n": "民谣", "v": "民谣"},
    {"n": "说唱", "v": "说唱"},
    {"n": "DJ舞曲", "v": "DJ舞曲"},
    {"n": "伤感", "v": "伤感"},
    {"n": "经典老歌", "v": "经典老歌"},
    {"n": "金曲", "v": "金曲"},
    {"n": "古风", "v": "古风"},
    {"n": "粤语", "v": "粤语"},
    {"n": "国风", "v": "国风"},
    {"n": "R&B", "v": "R&B"},
    {"n": "中文慢摇", "v": "中文慢摇"},
    {"n": "VIP歌曲", "v": "VIP歌曲"},
]

AUDIOBOOK_KEYWORDS = [
    "书场", "有声", "听书", "小说", "电台", "FM", "评书", "故事",
    "儿童", "朗读", "广播剧", "音频", "有声书", "化书场",
    "之音", "贤者", "恶魔",
]

# ==================== 网络层（零第三方依赖，纯标准库） ====================

UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
)
UA_PC = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

QUALITY_MAP = {"128k": 128, "192k": 192, "320k": 320, "flac": 2000, "2000k": 2000}


def http_get(url, headers=None, timeout=15):
    """GET 请求，返回 (status, text, raw_bytes)；自动 gzip/deflate 解压与跟随跳转"""
    h = {
        "User-Agent": UA_PC,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "close",
    }
    if headers:
        h.update(headers)

    req = urllib.request.Request(url, headers=h)
    status = 200
    enc = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200) or 200
            raw = resp.read()
            enc = (resp.headers.get("Content-Encoding") or "").lower()
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            raw = e.read() or b""
            enc = (e.headers.get("Content-Encoding") or "").lower() if e.headers else ""
        except Exception:
            raw = b""
    except Exception:
        raise

    if enc == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    elif enc == "deflate":
        try:
            raw = zlib.decompress(raw)
        except Exception:
            pass

    return status, raw.decode("utf-8", "replace"), raw


def get_json(url, headers=None, timeout=15):
    status, text, _ = http_get(url, headers, timeout)
    if status != 200:
        raise Exception("HTTP %s" % status)
    try:
        return json.loads(text)
    except Exception:
        raise Exception("响应不是 JSON: " + text[:120])


# ==================== rid 清洗 ====================

def clean_rid(rid):
    """MUSIC_228908 / music_228908 / 228908 -> 228908（歌词接口只认纯数字）"""
    if rid is None:
        return ""
    s = str(rid).strip()
    s = re.sub(r"^MUSIC_", "", s, flags=re.I)
    s = re.sub(r"^music[-_]", "", s, flags=re.I)
    m = re.search(r"\d+", s)
    return m.group(0) if m else ""


# ==================== 逐字歌词（LRCX） ====================
#
# 酷我 PC 客户端私有 LRCX 格式，每字带偏移：
#     [kuwo:045]
#     [00:39.917]<1694,-1694>天<3932,-2480>郁 ...
# 换算：字起始(ms) = |(a + b) / (offset * 2)|
#      offset/offset2 由 [kuwo:八进制数] 解出：offset = v // 10, offset2 = v % 10
# 输出增强 LRC：[00:39.917]天[00:40.159]郁 ...

LRCX_KEY = b"yeelion"


def kw_xor(buf):
    out = bytearray(len(buf))
    j = 0
    for i in range(len(buf)):
        out[i] = buf[i] ^ LRCX_KEY[j]
        j += 1
        if j >= len(LRCX_KEY):
            j = 0
    return bytes(out)


def build_lrcx_param(rid):
    s = "user=12345,web,web,web&requester=localhost&req=1&rid=MUSIC_%s&lrcx=1" % rid
    return base64.b64encode(kw_xor(s.encode("utf-8"))).decode("ascii")


def fetch_raw_lrcx(rid, timeout=15):
    url = "http://newlyric.kuwo.cn/newlyric.lrc?" + build_lrcx_param(rid)
    status, _, buf = http_get(url, {"User-Agent": UA_PC}, timeout)
    if status != 200:
        raise Exception("LRCX HTTP %s" % status)
    if buf[:10] != b"tp=content":
        raise Exception("LRCX 响应格式不符（可能该歌曲无逐字歌词）")
    idx = buf.find(b"\r\n\r\n")
    if idx < 0:
        raise Exception("LRCX 缺少分隔头")
    inflated = zlib.decompress(buf[idx + 4:])
    xored = kw_xor(base64.b64decode(inflated))
    try:
        return xored.decode("gb18030", "replace")
    except Exception:
        return xored.decode("utf-8", "replace")


def fmt_time(ms, digits=3):
    if ms is None or ms != ms or ms < 0:
        ms = 0
    m = int(ms // 60000)
    sec = (ms - m * 60000) / 1000.0
    if digits == 3:
        ss = ("%06.3f" % sec)
    else:
        ss = ("%05.2f" % sec)
    return "[%02d:%s]" % (m, ss)


LINE_RE = re.compile(r"^\[(\d{1,2}):(\d{2})\.(\d{1,3})\](.*)$")
WORD_RE = re.compile(r"<(-?\d+),(-?\d+)>([^<]*)")


def _line_start_ms(m):
    return int(m.group(1)) * 60000 + int(m.group(2)) * 1000 + int((m.group(3) + "000")[:3])


def convert_lrcx(raw, digits=3):
    lines = re.split(r"\r\n|\r|\n", raw)
    offset, offset2 = 1, 1
    tag = re.search(r"\[kuwo:(\d+)\]", raw)
    if tag:
        try:
            v = int(tag.group(1), 8)
        except Exception:
            v = 0
        a, b = v // 10, v % 10
        if a > 0 and b > 0:
            offset, offset2 = a, b

    out = []
    for i, ln in enumerate(lines):
        m = LINE_RE.match(ln)
        if not m:
            continue
        line_start = _line_start_ms(m)
        content = m.group(4)
        if not content:
            continue
        # 翻译行跳过
        if content.startswith("<0,0>") and re.search(r"[\u4e00-\u9fa5]", content):
            continue

        words = []
        for wm in WORD_RE.finditer(content):
            a, b = int(wm.group(1)), int(wm.group(2))
            start = abs((a + b) / (offset * 2.0))
            words.append((line_start + start, wm.group(3)))
        if not words:
            continue

        parts = [fmt_time(words[0][0], digits) + words[0][1]]
        for at, txt in words[1:]:
            parts.append(fmt_time(at, digits) + txt)

        last_at = words[-1][0]
        end_ms = None
        if i + 1 < len(lines):
            nm = LINE_RE.match(lines[i + 1])
            if nm:
                end_ms = _line_start_ms(nm)
        if end_ms is None:
            end_ms = last_at + 2000
        parts.append(fmt_time(max(end_ms, last_at + 1), digits))
        out.append("".join(parts))
    return "\n".join(out)


def fetch_word_lyric(rid, digits=3, timeout=15):
    try:
        raw = fetch_raw_lrcx(rid, timeout)
        if not re.search(r"<\d+,-?\d+>", raw):
            return False, "该歌曲无逐字（LRCX）数据", ""
        lrc = convert_lrcx(raw, digits)
        if not lrc:
            return False, "LRCX 解析结果为空", ""
        return True, "", lrc
    except Exception as e:
        return False, str(e), ""


# ==================== 逐行歌词解析 ====================

def to_seconds(t):
    if isinstance(t, (int, float)):
        return float(t)
    s = str(t or "").strip()
    if not s:
        return 0.0
    parts = s.split(":")
    try:
        if len(parts) >= 3:
            return int(parts[0] or 0) * 3600 + int(parts[1] or 0) * 60 + float(parts[2] or 0)
        if len(parts) == 2:
            return int(parts[0] or 0) * 60 + float(parts[1] or 0)
        return float(s)
    except Exception:
        return 0.0


def fmt_lrc_time(sec):
    if sec is None or sec < 0:
        sec = 0
    m = int(sec // 60)
    s = sec - m * 60
    return "[%02d:%05.2f]" % (m, s)


def build_lrc(items):
    lines = []
    for it in items:
        txt = str(it.get("lineLyric") or it.get("line") or "").strip()
        if not txt:
            continue
        if re.search(r"纯音乐|没有填词|请欣赏|此歌曲为", txt):
            continue
        lines.append(fmt_lrc_time(to_seconds(it.get("time"))) + txt)

    out = []
    strip = lambda x: re.sub(r"^\[[^\]]*\]\s*", "", x)
    for l in lines:
        if out and strip(out[-1]) == strip(l):
            continue
        out.append(l)
    return "\n".join(out)


# ==================== 三级歌词源 ====================

def lyric_source_openapi(rid, timeout=15):
    j = get_json(
        "https://kuwo.cn/openapi/v1/www/lyric/getlyric?musicId=%s" % rid,
        {"Referer": "http://m.kuwo.cn/", "User-Agent": UA_MOBILE}, timeout
    )
    if isinstance(j, dict):
        data = j.get("data") or {}
        lst = data.get("lrclist")
        if isinstance(lst, list) and lst:
            return build_lrc(lst), "openapi"
    return None


def lyric_source_newh5_http(rid, timeout=15):
    j = get_json(
        "http://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId=%s" % rid,
        {"Referer": "http://m.kuwo.cn/", "User-Agent": UA_MOBILE}, timeout
    )
    if isinstance(j, dict):
        data = j.get("data") or {}
        lst = data.get("lrclist")
        if isinstance(lst, list) and lst:
            return build_lrc(lst), "newh5-http"
    return None


def lyric_source_newh5_https(rid, timeout=15):
    j = get_json(
        "https://m.kuwo.cn/newh5/singles/songinfoandlrc?musicId=%s" % rid,
        {"Referer": "https://m.kuwo.cn/", "User-Agent": UA_MOBILE}, timeout
    )
    if isinstance(j, dict):
        data = j.get("data") or {}
        lst = data.get("lrclist")
        if isinstance(lst, list) and lst:
            return build_lrc(lst), "newh5-https"
    return None


def fetch_lyric(rid, timeout=15):
    errors = []
    for name, fn in (
        ("openapi", lyric_source_openapi),
        ("newh5-http", lyric_source_newh5_http),
        ("newh5-https", lyric_source_newh5_https),
    ):
        try:
            r = fn(rid, timeout)
            if r and r[0]:
                return True, r[0], r[1], errors
            errors.append(name + ": 无歌词")
        except Exception as e:
            errors.append(name + ": " + str(e))
    return False, "", "", errors


# ==================== 搜索 ====================

def parse_kuwo_response(text):
    if not text:
        return None
    s = text.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        return ast.literal_eval(s)
    except Exception:
        return None


def album_pic(item):
    raw = item.get("web_albumpic_short") or item.get("PICPATH") or item.get("hts_MVPIC") or ""
    if not raw:
        return ""
    if re.match(r"^https?:", raw, re.I):
        return raw
    tail = re.sub(r"^\d+/", "", raw)
    if not tail:
        return ""
    if tail.startswith("wmvpic/"):
        return "https://img1.kuwo.cn/" + tail
    return "http://img1.kwcdn.kuwo.cn/star/albumcover/500/" + tail


def search_songs(keyword, page=1, limit=30, timeout=15):
    if not keyword or not str(keyword).strip():
        keyword = "热歌"
    pn = (int(page) - 1) * int(limit)
    api = (
        "https://search.kuwo.cn/r.s?client=kt&pn=%s&rn=%s"
        "&all=%s&vipver=1&ft=music&encoding=utf8&rformat=json&mobi=1"
        % (pn, int(limit), urllib.parse.quote(str(keyword)))
    )
    status, text, _ = http_get(api, {"User-Agent": UA_PC, "Referer": "https://www.kuwo.cn/"}, timeout)
    if status != 200:
        raise Exception("搜索 HTTP %s" % status)
    data = parse_kuwo_response(text)
    if not isinstance(data, dict) or not isinstance(data.get("abslist"), list):
        return [], 0

    out = []
    for item in data["abslist"]:
        if not isinstance(item, dict):
            continue
        try:
            duration = int(item.get("DURATION") or 0)
        except Exception:
            duration = 0
        try:
            pay = int(item.get("PAY") or 0)
        except Exception:
            pay = 0
        out.append({
            "rid": clean_rid(item.get("MUSICRID") or item.get("DC_TARGETID") or item.get("musicrid")),
            "name": item.get("NAME") or item.get("SONGNAME") or "",
            "artist": item.get("ARTIST") or "",
            "album": item.get("ALBUM") or "",
            "duration": duration,
            "pic": album_pic(item),
            "pay": pay,
        })
    try:
        total = int(data.get("TOTAL") or len(out))
    except Exception:
        total = len(out)
    return out, total


# ==================== 播放链接 ====================

def get_play_url(rid, quality="320k", timeout=15):
    bitrate = QUALITY_MAP.get(str(quality), 320)
    fmt = "flac" if bitrate == 2000 else "mp3"
    api = (
        "https://nmobi.kuwo.cn/mobi.s?f=web&user=0"
        "&source=kwplayer_ar_4.4.2.7_B_nuoweida_vh.apk"
        "&type=convert_url_with_sign&rid=%s&bitrate=%s&format=%s&vip=1"
        % (rid, bitrate, fmt)
    )
    status, text, _ = http_get(api, {"User-Agent": UA_PC, "Referer": "https://www.kuwo.cn/"}, timeout)
    if status != 200:
        raise Exception("播放链接 HTTP %s" % status)
    j = json.loads(text)
    if isinstance(j, dict) and j.get("code") == 200 and isinstance(j.get("data"), dict) and j["data"].get("url"):
        return j["data"]["url"], bitrate
    raise Exception((j or {}).get("msg") or "获取播放链接失败")


# ==================== 酷我直连接口（替代原 Node 服务） ====================

class KuWoApi:
    """原 kuwo_server.js 的等价实现：search / get_url / get_lyric / get_cover"""

    def __init__(self, config=None):
        cfg = config or {}
        self.timeout = int(cfg.get("timeout", 20))
        self.quality = str(cfg.get("quality", "320k"))
        self.word_lyric = str(cfg.get("word_lyric", 1))
        self.cover_cache = {}
        self.lyric_cache = {}
        self.url_cache = {}
        self._lock = threading.Lock()
        log("KuWoApi 初始化: 直连酷我（无本地服务）quality=%s word_lyric=%s" % (self.quality, self.word_lyric))

    # ---- 搜索 ----
    def search(self, keyword, page=1, limit=30):
        log("搜索: keyword=%s, page=%s, limit=%s" % (keyword, page, limit))
        try:
            data, total = search_songs(keyword, page, limit, self.timeout)
            return {"code": 200, "data": data, "total": total}
        except Exception as e:
            log("搜索失败: %s" % e)
            return {"code": 500, "msg": str(e), "data": [], "total": 0}

    # ---- 播放链接 ----
    def get_url(self, rid, quality=None):
        rid = clean_rid(rid)
        quality = quality or self.quality
        key = "%s@%s" % (rid, quality)
        with self._lock:
            if key in self.url_cache:
                return self.url_cache[key]
        try:
            url, bitrate = get_play_url(rid, quality, self.timeout)
            res = {"code": 200, "rid": rid, "url": url, "quality": quality, "bitrate": bitrate}
            with self._lock:
                self.url_cache[key] = res
            return res
        except Exception as e:
            log("获取播放链接失败 rid=%s quality=%s: %s" % (rid, quality, e))
            return {"code": 500, "rid": rid, "msg": "获取播放链接失败: " + str(e)}

    # ---- 歌词 ----
    def get_lyric(self, rid):
        rid = clean_rid(rid)
        if not rid:
            return {"code": 400, "msg": "缺少或非法的 rid 参数"}
        ckey = "%s@w%s" % (rid, self.word_lyric)
        with self._lock:
            if ckey in self.lyric_cache:
                return self.lyric_cache[ckey]

        result = None
        if self.word_lyric == "1":
            ok, err, lrc = fetch_word_lyric(rid, 3, self.timeout)
            if ok:
                result = {"code": 200, "rid": rid, "lyric": lrc, "mode": "word", "source": "lrcx",
                          "lines": lrc.count("\n") + 1}
            else:
                ok2, lrc2, src2, errors = fetch_lyric(rid, self.timeout)
                if ok2:
                    result = {"code": 200, "rid": rid, "lyric": lrc2, "mode": "line", "source": src2,
                              "lines": lrc2.count("\n") + 1, "fallback_reason": err}
                else:
                    all_empty = bool(errors) and all("无歌词" in x for x in errors)
                    result = {
                        "code": 404 if all_empty else 502,
                        "rid": rid,
                        "lyric": "",
                        "msg": ("该歌曲暂无歌词" if all_empty else
                                "逐字与逐行均失败 | 逐字: %s | 逐行: %s" % (err, " / ".join(errors))),
                    }
        else:
            ok, lrc, src, errors = fetch_lyric(rid, self.timeout)
            if ok:
                result = {"code": 200, "rid": rid, "lyric": lrc, "source": src, "mode": "line",
                          "lines": lrc.count("\n") + 1}
            else:
                all_empty = bool(errors) and all("无歌词" in x for x in errors)
                result = {
                    "code": 404 if all_empty else 502,
                    "rid": rid,
                    "lyric": "",
                    "msg": ("该歌曲暂无歌词" if all_empty else "歌词接口异常: " + " | ".join(errors)),
                }

        if result.get("code") in (200, 404):
            with self._lock:
                self.lyric_cache[ckey] = result
        return result

    # ---- 封面 ----
    def get_cover(self, rid):
        rid = clean_rid(rid)
        if not rid:
            return ""
        with self._lock:
            if rid in self.cover_cache:
                return self.cover_cache[rid]
        try:
            status, text, _ = http_get(
                "http://artistpicserver.kuwo.cn/pic.web?type=rid_pic&pictype=url&size=500&rid=%s" % rid,
                {"User-Agent": UA_PC}, self.timeout
            )
            url = (text or "").strip()
            if status == 200 and url.startswith("http"):
                with self._lock:
                    self.cover_cache[rid] = url
                return url
        except Exception as e:
            log("获取封面失败 rid=%s: %s" % (rid, e))
        return ""

    def close(self):
        try:
            with self._lock:
                self.cover_cache.clear()
                self.lyric_cache.clear()
                self.url_cache.clear()
        except Exception:
            pass

class Spider(BaseSpider):

    # ============ 连播数量配置 ============
    PLAYLIST_SIZE = 50

    def __init__(self):
        super().__init__()
        log("=" * 50)
        log("酷我音乐爬虫初始化")
        self.config = DEFAULT_CONFIG.copy()
        self.client = KuWoApi(self.config)
        self.cache = {}

    def getName(self):
        return "酷我音乐"

    def init(self, extend=""):
        if extend:
            try:
                data = json.loads(str(extend)) if isinstance(extend, str) else extend
                self.config.update(data)
            except:
                pass
        self.client = KuWoApi(self.config)

    def homeContent(self, filter):
        log("homeContent 被调用")

        class_list = [
            {"type_id": "all", "type_name": "🥀 全部"},
            {"type_id": "hot", "type_name": "🔥 热歌榜"},
            {"type_id": "new", "type_name": "🆕 新歌榜"},
            {"type_id": "dj", "type_name": "🎧 DJ舞曲"},
            {"type_id": "manyao", "type_name": "🎧 中文慢摇"},
            {"type_id": "classic", "type_name": "📀 经典老歌"},
            {"type_id": "old70", "type_name": "📀 7080老歌"},
            {"type_id": "pop", "type_name": "🌟 流行"},
            {"type_id": "sad", "type_name": "😢 伤感"},
            {"type_id": "rap", "type_name": "🎤 说唱"},
            {"type_id": "folk", "type_name": "🎵 民谣"},
            {"type_id": "vip", "type_name": "💎 VIP歌曲"},
            {"type_id": "search", "type_name": "🔍 搜索"},
        ]

        filters = {}
        for c in class_list:
            tid = c["type_id"]
            filters[tid] = [
                {"key": "artist", "name": "🎤 歌手", "value": ARTIST_LIST, "init": ""},
                {"key": "style", "name": "🎵 风格", "value": STYLE_LIST, "init": ""},
            ]

        return {"class": class_list, "filters": filters}

    def homeVideoContent(self):
        return self.categoryContent("hot", "1", {}, {})

    def _is_audiobook(self, name, artist):
        """判断是否是听书/小说"""
        if name.strip().startswith("第"):
            return True
        if re.search(r'第\d+[集章回]', name):
            return True
        for kw in AUDIOBOOK_KEYWORDS:
            if kw in name or kw in artist:
                return True
        return False

    def _do_search(self, keyword, page=1, limit=30):
        log(f"执行搜索: keyword={keyword}, page={page}")
        if not keyword or keyword.strip() == "":
            keyword = "热歌"
        result = self.client.search(keyword, page=page, limit=limit)

        if result.get("code") != 200:
            return {"list": [], "page": page, "pagecount": page, "limit": limit, "total": 0}

        data = result.get("data", [])
        total = result.get("total", len(data))

        if total > 0:
            pagecount = (total + limit - 1) // limit
        else:
            pagecount = page

        if len(data) == 0:
            pagecount = page

        self.cache["songs"] = data

        # 建立 rid -> 歌曲信息 映射，供详情页回填歌名/歌手
        song_map = self.cache.setdefault("song_map", {})
        for it in data:
            _r = str(it.get("rid", ""))
            if _r:
                song_map[_r] = {"name": it.get("name", ""), "artist": it.get("artist", "")}

        items = []
        for item in data:
            rid = item.get("rid", "")
            if not rid:
                continue

            name = item.get("name", "")
            artist = item.get("artist", "")

            if self._is_audiobook(name, artist):
                continue

            # 服务端 /search 返回的 item 自带 pic，直接用，别再逐条请求 /cover
            # （原来每条一次请求，30 条 = 30 次，直接把服务端拖垮导致歌词超时）
            pic = item.get("pic", "") or ""
            if not pic.startswith("http"):
                pic = self.client.get_cover(rid)
            if not pic:
                pic = "https://t8.baidu.com/it/u=102347688,62200072&fm=193"

            items.append({
                "vod_id": f"kuwo_{rid}",
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": artist,
                "vod_actor": artist,
                "vod_player": "music",
                "style": {"type": "rect", "ratio": 1.0, "pic": pic},
            })

        log(f"返回 {len(items)} 个条目, total={total}, pagecount={pagecount}")
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": limit,
            "total": total,
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        limit = 30

        log(f"categoryContent: tid={tid}, pg={pg}, filter={filter}, extend={extend}")

        keyword_map = {
            "all": "",
            "hot": "热歌",
            "new": "新歌",
            "dj": "DJ舞曲",
            "manyao": "中文慢摇",
            "classic": "经典老歌",
            "old70": "7080",
            "pop": "流行",
            "sad": "伤感",
            "rap": "说唱",
            "folk": "民谣",
            "vip": "VIP歌曲",
        }

        keyword = ""

        if tid in keyword_map:
            keyword = keyword_map[tid]
            log(f"分类关键词: {keyword}")

        elif tid == "search":
            try:
                if extend:
                    if isinstance(extend, str):
                        extend_data = json.loads(extend)
                    else:
                        extend_data = extend
                    keyword = extend_data.get("keyword", "")
                    log(f"搜索关键词: {keyword}")
            except Exception as e:
                log(f"解析 extend 失败: {e}")

            if not keyword:
                log("搜索关键词为空，显示搜索入口")
                return {
                    "list": [{
                        "vod_id": "kuwo_search_action",
                        "vod_name": "🔍 点击搜索",
                        "vod_pic": "https://t8.baidu.com/it/u=102347688,62200072&fm=193",
                        "vod_tag": "action",
                    }],
                    "page": page,
                    "pagecount": page,
                    "limit": limit,
                    "total": 0,
                }

        else:
            keyword = tid
            log(f"歌手关键词: {keyword}")

        if not keyword:
            keyword = "热歌"

        filter_data = {}
        if filter:
            try:
                if isinstance(filter, str):
                    filter_data = json.loads(filter)
                elif isinstance(filter, dict):
                    filter_data = filter
                log(f"从 filter 取筛选数据: {filter_data}")
            except Exception as e:
                log(f"解析 filter 失败: {e}")

        if not filter_data and extend:
            try:
                if isinstance(extend, str):
                    filter_data = json.loads(extend)
                elif isinstance(extend, dict):
                    filter_data = extend
                log(f"从 extend 取筛选数据: {filter_data}")
            except Exception as e:
                log(f"解析 extend 失败: {e}")

        artist = filter_data.get("artist", "") if isinstance(filter_data, dict) else ""
        style = filter_data.get("style", "") if isinstance(filter_data, dict) else ""

        final_keyword = keyword

        if artist and artist != "全部":
            final_keyword = f"{artist} {final_keyword}"
            log(f"追加歌手: {artist}")

        if style and style != "全部":
            final_keyword = f"{final_keyword} {style}"
            log(f"追加风格: {style}")

        log(f"最终搜索词: {final_keyword}")

        return self._do_search(final_keyword, page, limit)

    # ==================== 连播构建 ====================

    def _build_playlist(self, rid, song_name, artist):
        """
        构建 50 首连播列表
        策略：优先同歌手，其次同歌名，兜底热歌；去重；过滤听书
        """
        playlist = []
        seen = {str(rid)}

        # ★ 核心修复：当前这首歌必须排在连播列表第一位。
        # 原写法只把当前歌放进 seen（去重集合）却没加进 playlist，
        # 导致播放器一进去就播了列表第 1 首「相关推荐」——
        # 于是出现「点的是花海，播的是别的歌，歌词还是空的」。
        playlist.append({
            "rid": str(rid),
            "name": song_name if song_name and song_name != "歌曲详情" else "当前歌曲",
            "artist": artist or "",
        })

        keywords = []
        if artist:
            keywords.append(artist)
        if song_name and song_name != "歌曲详情":
            keywords.append(song_name)
        keywords.append("热歌")  # 兜底

        for kw in keywords:
            if len(playlist) >= self.PLAYLIST_SIZE:
                break
            try:
                result = self.client.search(kw, page=1, limit=50)
                if result.get("code") != 200:
                    continue
                data = result.get("data", [])
                for item in data:
                    if len(playlist) >= self.PLAYLIST_SIZE:
                        break
                    _rid = str(item.get("rid", ""))
                    if not _rid or _rid in seen:
                        continue
                    _name = item.get("name", "")
                    _artist = item.get("artist", "")
                    if self._is_audiobook(_name, _artist):
                        continue
                    seen.add(_rid)
                    playlist.append({
                        "rid": _rid,
                        "name": _name,
                        "artist": _artist,
                    })
            except Exception as e:
                log(f"构建连播失败 kw={kw}: {e}")
                continue

        # 连播里的歌也回填进映射，方便详情页/播放页查名字
        song_map = self.cache.setdefault("song_map", {})
        for s in playlist:
            song_map[str(s["rid"])] = {"name": s["name"], "artist": s["artist"]}

        log(f"连播列表: {len(playlist)} 首 (seed={rid})")
        return playlist

    def _get_playlist(self, rid, song_name, artist):
        """连播结果按 rid 缓存，避免详情页/播放页反复发 3 次大搜索"""
        slot = self.cache.setdefault("playlist", {})
        key = str(rid)
        if key in slot:
            return slot[key]
        pl = self._build_playlist(rid, song_name, artist)
        slot[key] = pl
        return pl

    def _make_play_url(self, rid, song_name, artist):
        playlist = self._build_playlist(rid, song_name, artist)
        parts = []
        for song in playlist:
            name = song["name"]
            if song["artist"]:
                name = f"{name} - {song['artist']}"
            parts.append(f"{name}$kuwo_{song['rid']}")
        if not parts:
            parts.append(f"{song_name}$kuwo_{rid}")
        return "#".join(parts)

    # ==================== 详情 ====================

    def detailContent(self, ids):
        item_id = str(ids[0]) if isinstance(ids, list) else str(ids)
        rid = item_id.replace("kuwo_", "").strip()
        log(f"detailContent: rid={rid}")

        if not rid:
            return {"list": []}

        lyric_text = ""
        try:
            lyric_result = self.client.get_lyric(rid)
            if lyric_result.get("code") == 200:
                lyric_text = lyric_result.get("lyric", "")
        except:
            pass

        cover_url = self.client.get_cover(rid)
        if not cover_url:
            cover_url = "https://t8.baidu.com/it/u=102347688,62200072&fm=193"

        song_name = "歌曲详情"
        artist = ""
        info = self.cache.get("song_map", {}).get(rid)
        if info:
            song_name = info.get("name") or "歌曲详情"
            artist = info.get("artist", "")
        else:
            for song in self.cache.get("songs", []):
                if str(song.get("rid")) == rid:
                    song_name = song.get("name", "歌曲详情")
                    artist = song.get("artist", "")
                    break

        # 构建 50 首连播（首项就是当前这首）
        playlist = self._get_playlist(rid, song_name, artist)
        play_url = "#".join(
            f"{(s['name'] + ' - ' + s['artist']) if s['artist'] else s['name']}$kuwo_{s['rid']}"
            for s in playlist
        ) or f"{song_name}$kuwo_{rid}"

        content = lyric_text[:1500] if lyric_text else ""
        content += f"\n\n✨ 已生成 {len(playlist)} 首连播"

        return {
            "list": [{
                "vod_id": item_id,
                "vod_name": song_name,
                "vod_pic": cover_url,
                "vod_actor": artist,
                "vod_remarks": "歌词" if lyric_text else "暂无歌词",
                "vod_content": content,
                "vod_play_from": "酷我音乐",
                "vod_play_url": play_url,
                "vod_player": "music",
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        log(f"searchContent: key={key}, quick={quick}, pg={pg}")
        if not key or not key.strip():
            return {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}
        return self.categoryContent("search", pg, {}, json.dumps({"keyword": key.strip()}))

    def playerContent(self, flag, id, vipFlags):
        rid = str(id).replace("kuwo_", "").strip()
        log(f"playerContent: rid={rid}")

        if not rid:
            return {"parse": 0, "url": "", "msg": "无效歌曲ID"}

        quality = self.config.get("quality", "320k")

        # 获取播放链接
        url_result = self.client.get_url(rid, quality)

        # 获取歌词
        lyric = ""
        try:
            lyric_result = self.client.get_lyric(rid)
            code = lyric_result.get("code")
            if code == 200:
                lyric = lyric_result.get("lyric", "") or ""
                log(f"歌词成功 rid={rid} 长度={len(lyric)} 模式={lyric_result.get('mode')} 来源={lyric_result.get('source')}")
            else:
                log(f"歌词为空 rid={rid} code={code} msg={lyric_result.get('msg')}")
        except Exception as e:
            log(f"获取歌词异常 rid={rid}: {e}")

        # 高码率拿不到就逐级降级，别让用户直接没得听
        if not (url_result.get("code") == 200 and url_result.get("url")):
            for fallback in ["128k"]:
                if fallback == quality:
                    continue
                log(f"播放链接降级: {quality} -> {fallback} (rid={rid})")
                url_result = self.client.get_url(rid, fallback)
                if url_result.get("code") == 200 and url_result.get("url"):
                    quality = fallback
                    break

        if url_result.get("code") == 200 and url_result.get("url"):
            url = url_result["url"]
            if not url.startswith("http"):
                url = "http://" + url
            return {
                "parse": 0,
                "url": url,
                "lrc": lyric,
                "header": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.kuwo.cn/",
                },
                "flag": QUALITY_NAMES.get(quality, quality),
            }

        return {"parse": 0, "url": "", "msg": url_result.get("msg", "获取失败")}

    def action(self, action_str):
        log(f"action 收到: {action_str}")

        if action_str == "kuwo_search_action":
            log("返回搜索框")
            return {
                "action": {
                    "actionId": "kuwo_search",
                    "type": "input",
                    "title": "🎵 酷我音乐搜索",
                    "tip": "请输入歌手或歌名",
                    "value": "",
                }
            }

        try:
            if isinstance(action_str, str) and action_str.startswith("{"):
                payload = json.loads(action_str)
            elif isinstance(action_str, dict):
                payload = action_str
            else:
                return {"toast": "请点击源内搜索按钮"}
        except Exception as e:
            log(f"JSON解析失败: {e}")
            return {"toast": "解析失败"}

        log(f"payload: {payload}")

        action_id = payload.get("actionId") or payload.get("action", "")
        log(f"actionId: {action_id}")

        if action_id == "kuwo_search":
            raw_value = payload.get("value", "")
            log(f"raw_value: {raw_value}, type: {type(raw_value)}")

            keyword = ""
            if isinstance(raw_value, dict):
                for key, val in raw_value.items():
                    if val:
                        keyword = str(val).strip()
                        break
            else:
                keyword = str(raw_value).strip()

            log(f"提取的关键词: {keyword}")

            if not keyword:
                return {
                    "action": {
                        "actionId": "kuwo_search",
                        "type": "input",
                        "title": "🎵 酷我音乐搜索",
                        "tip": "请输入歌手或歌名",
                        "value": "",
                    }
                }

            log(f"跳转搜索: {keyword}")
            return {
                "action": {
                    "actionId": "__self_search__",
                    "skey": "",
                    "name": f"🎵 {keyword}",
                    "tid": keyword,
                    "flag": "1",
                }
            }

        return {"toast": f"未知操作: {action_id}"}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        log("destroy 被调用")
        log("=" * 50)
        try:
            self.client.close()
        except:
            pass


# ==================== 命令行自测 ====================

if __name__ == "__main__":
    import sys

    kw = sys.argv[1] if len(sys.argv) > 1 else "周杰伦"
    api = KuWoApi(DEFAULT_CONFIG)

    print("== 搜索: %s ==" % kw)
    r = api.search(kw, 1, 3)
    print("code=%s total=%s" % (r.get("code"), r.get("total")))
    for s in (r.get("data") or [])[:3]:
        print("  %s | %s | %s" % (s.get("rid"), s.get("name"), s.get("artist")))

    songs = r.get("data") or []
    if songs:
        rid = songs[0]["rid"]
        print("== 播放链接: %s ==" % rid)
        u = api.get_url(rid, DEFAULT_CONFIG["quality"])
        print("code=%s url=%s" % (u.get("code"), str(u.get("url"))[:90]))
        print("== 歌词: %s ==" % rid)
        ly = api.get_lyric(rid)
        print("code=%s mode=%s source=%s lines=%s" % (ly.get("code"), ly.get("mode"), ly.get("source"), ly.get("lines")))
        print("\n".join((ly.get("lyric") or "").splitlines()[:6]))
        print("== 封面 ==")
        print(api.get_cover(rid))
    api.close()
