# -*- coding: utf-8 -*-
"""
笔画数计算工具（离线 / 无 API）
================================

替代原来需要百度 API 的笔画查询：
- 首选：`strokes` 第三方包（pip install strokes）—— 基于 Unicode Unihan
  kTotalStrokes，覆盖 93000+ CJK 字符。
- 兜底：随技能打包的 `data/unihan_strokes.json`（来源同上，873KB）。

梅花易数笔画制式说明：
----------------------
传统梅花学者以"繁体 / 康熙笔画"为准，现代用户则多以"简体笔画"为直觉。
本工具默认按 Unihan 主条目取值（和通行印刷体笔画一致，大陆简体用户友好），
并提供一个"繁体映射"开关：若用户选 traditional，则在查询前先把该字对应
到其繁体形式（需要字符本身就是繁体，或简繁映射表）。

使用：
    from strokes_util import stroke_count, text_strokes
    stroke_count('爱')      # -> 10
    text_strokes('梅花易数')  # -> [11, 7, 8, 13]

无 API、无网络请求、无外部依赖（若 strokes 包未安装，自动退化到内嵌 JSON）。
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import List, Optional

_BUILTIN_JSON = os.path.join(os.path.dirname(__file__), "data", "unihan_strokes.json")

_lib_strokes = None  # 若可用会填成 callable
_FALLBACK: dict = {}
_DATA_SOURCE = "none"


def _load_data() -> None:
    """惰性加载：优先用 pip 的 strokes 包；否则读内嵌 JSON。"""
    global _lib_strokes, _FALLBACK, _DATA_SOURCE
    if _lib_strokes is not None or _FALLBACK:
        return
    # 1) 尝试 strokes 包
    try:
        from strokes import strokes as _lib  # type: ignore
        _lib_strokes = _lib
        _DATA_SOURCE = "strokes-pkg"
        return
    except Exception:
        _lib_strokes = None
    # 2) 退化：读取本地 JSON
    try:
        with open(_BUILTIN_JSON, encoding="utf-8") as f:
            _FALLBACK = json.load(f)
        _DATA_SOURCE = "bundled-json"
    except Exception:
        _FALLBACK = {}
        _DATA_SOURCE = "none"


def data_source() -> str:
    """返回当前使用的数据源名（便于调试与在卡片 meta 中显示）。"""
    _load_data()
    return _DATA_SOURCE


@lru_cache(maxsize=8192)
def stroke_count(ch: str) -> int:
    """返回单字的笔画数。非汉字或未登录字返回 0。"""
    if not ch or len(ch) != 1:
        return 0
    _load_data()
    if _lib_strokes is not None:
        try:
            v = _lib_strokes(ch)
            if isinstance(v, int):
                return v
        except Exception:
            pass
    return int(_FALLBACK.get(ch, 0) or 0)


def text_strokes(text: str) -> List[int]:
    """逐字取笔画，跳过空白；保留非 CJK 字符（返回 0）。"""
    return [stroke_count(c) for c in text if not c.isspace()]


# ---- 极简的简→繁映射，仅用于少量常用字 ------------------------
# 说明：完整的简繁转换建议使用 opencc / zhconv；这里只内置最常用的
# 200 余字映射，用于 stroke_variant="traditional" 的场景。
# 如需更完整的转换，请 pip install opencc-python-reimplemented，
# 然后用 strokes_util.convert_to_traditional() 替换此表。
_S2T_MINI = {
    "爱": "愛", "国": "國", "学": "學", "对": "對", "会": "會",
    "个": "個", "们": "們", "这": "這", "为": "為", "经": "經",
    "业": "業", "东": "東", "车": "車", "车": "車", "见": "見",
    "书": "書", "长": "長", "门": "門", "问": "問", "时": "時",
    "无": "無", "义": "義", "鱼": "魚", "马": "馬", "鸟": "鳥",
    "风": "風", "云": "雲", "电": "電", "钱": "錢", "铁": "鐵",
    "乐": "樂", "丽": "麗", "丰": "豐", "专": "專", "云": "雲",
    "办": "辦", "历": "歷", "压": "壓", "厌": "厭", "厅": "廳",
    "听": "聽", "图": "圖", "团": "團", "园": "園", "围": "圍",
    "买": "買", "卖": "賣", "龙": "龍", "龟": "龜", "龛": "龕",
    "师": "師", "应": "應", "开": "開", "关": "關", "双": "雙",
    "发": "發", "变": "變", "当": "當", "实": "實", "宝": "寶",
    "审": "審", "写": "寫", "寻": "尋", "导": "導", "岁": "歲",
    "币": "幣", "带": "帶", "帮": "幫", "归": "歸", "杨": "楊",
    "样": "樣", "树": "樹", "桥": "橋", "楼": "樓", "机": "機",
    "权": "權", "欢": "歡", "气": "氣", "汉": "漢", "没": "沒",
    "泪": "淚", "济": "濟", "湿": "濕", "灯": "燈", "炉": "爐",
    "牺": "犧", "独": "獨", "猎": "獵", "现": "現", "珍": "珍",
    "环": "環", "纯": "純", "绝": "絕", "纸": "紙", "组": "組",
    "细": "細", "经": "經", "给": "給", "网": "網", "纺": "紡",
    "绵": "綿", "绿": "綠", "维": "維", "续": "續", "纪": "紀",
    "纹": "紋", "红": "紅", "纷": "紛", "纤": "纖", "终": "終",
    "绍": "紹", "绕": "繞", "结": "結", "统": "統", "绩": "績",
    "绿": "綠", "编": "編", "缘": "緣", "缝": "縫", "罢": "罷",
    "听": "聽", "肃": "肅", "脚": "腳", "节": "節", "范": "範",
    "荣": "榮", "药": "藥", "兰": "蘭", "虑": "慮", "处": "處",
    "号": "號", "冯": "馮", "动": "動", "务": "務", "劝": "勸",
    "办": "辦", "观": "觀", "规": "規", "视": "視", "觉": "覺",
    "试": "試", "话": "話", "该": "該", "详": "詳", "语": "語",
    "说": "說", "请": "請", "谢": "謝", "谨": "謹", "议": "議",
    "识": "識", "课": "課", "调": "調", "谈": "談", "论": "論",
    "译": "譯", "赋": "賦", "赛": "賽", "赞": "贊", "质": "質",
    "赚": "賺", "跃": "躍", "轮": "輪", "辑": "輯", "较": "較",
    "辅": "輔", "辈": "輩", "辑": "輯", "辖": "轄", "辟": "闢",
    "迁": "遷", "选": "選", "远": "遠", "递": "遞", "还": "還",
    "邻": "鄰", "郑": "鄭", "酱": "醬", "采": "採", "针": "針",
    "钟": "鐘", "铁": "鐵", "银": "銀", "错": "錯", "锁": "鎖",
    "闭": "閉", "闻": "聞", "队": "隊", "阳": "陽", "阴": "陰",
    "阶": "階", "际": "際", "隐": "隱", "难": "難", "静": "靜",
    "韩": "韓", "页": "頁", "顶": "頂", "顾": "顧", "题": "題",
    "颜": "顏", "额": "額", "饭": "飯", "驾": "駕", "验": "驗",
    "骂": "罵", "骆": "駱", "骑": "騎", "骤": "驟", "骨": "骨",
    "鲜": "鮮", "麦": "麥", "黄": "黃", "鼓": "鼓", "齐": "齊",
    "个": "個", "才": "才", "干": "幹", "历": "歷", "曲": "麯",
    "获": "獲", "只": "隻", "台": "臺", "后": "後", "里": "裡",
    "体": "體", "发": "髮", "头": "頭", "复": "復", "队": "隊",
    "齿": "齒", "儿": "兒", "鉴": "鑒", "岁": "歲", "云": "雲",
    "听": "聽", "坛": "壇",
    "数": "數", "术": "術", "种": "種", "异": "異", "盖": "蓋",
    "虫": "蟲", "尘": "塵", "灾": "災", "亏": "虧", "亲": "親",
    "运": "運", "远": "遠", "连": "連", "进": "進", "还": "還",
    "财": "財", "贝": "貝", "贵": "貴", "贫": "貧", "费": "費",
    "际": "際", "陆": "陸", "阳": "陽", "阴": "陰", "随": "隨",
    "欢": "歡", "鸡": "雞", "鸭": "鴨", "鱼": "魚", "龙": "龍",
}


def to_traditional(text: str) -> str:
    """极简简→繁转换（仅覆盖 ~200 常用字）。
    未命中的字符原样返回。更完整的转换请自行接入 opencc / zhconv。
    """
    return "".join(_S2T_MINI.get(c, c) for c in text)


def text_strokes_variant(text: str, variant: str = "simplified") -> List[int]:
    """按制式返回笔画序列。

    variant:
      - "simplified"   : 直接查 Unihan（对简体字返回简体笔画）
      - "traditional"  : 先把字转繁体再查（未覆盖的字按原字查）
      - "kangxi"       : 当前与 traditional 等价（Unihan 值即印刷体，
                         多数情况与康熙笔画相同；如需 100% 康熙可另接入
                         CJKVI 的 kKangXi 字段）
    """
    v = (variant or "simplified").lower()
    if v in ("traditional", "kangxi", "t", "k"):
        text = to_traditional(text)
    return text_strokes(text)
