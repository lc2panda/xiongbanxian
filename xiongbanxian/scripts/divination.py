# -*- coding: utf-8 -*-
"""
梅花易数 核心算法模块
========================

实现以下功能：
1. 年月日时起卦（农历 + 地支数）
2. 数字/字符起卦（规则 1 / 规则 2）
3. 本卦、互卦、变卦、错卦、综卦
4. 体卦、用卦，五行生克关系判断
5. 小六壬 起课

使用方法（作为库调用）：
    from divination import divine_by_datetime, divine_by_numbers
    result = divine_by_datetime("2026-04-16 14:30", question="求问事业")

使用方法（CLI）：
    python divination.py --datetime "2026-04-16 14:30" --question "求问事业"
    python divination.py --numbers "123"
    python divination.py --xiaoliuren --datetime "2026-04-16 14:30"

说明：
- 起卦口诀（邵雍先天数起卦法，已交叉验证权威文献）：
    上卦 = (年数 + 月 + 日) mod 8，余 0 取 8
    下卦 = (年数 + 月 + 日 + 时) mod 8，余 0 取 8
    动爻 = (年数 + 月 + 日 + 时) mod 6，余 0 取 6
- 先天八卦数：乾 1、兑 2、离 3、震 4、巽 5、坎 6、艮 7、坤 8
- 年数、时数以地支对应数（子 1 ... 亥 12）取
- 体用关系：动爻在下卦 → 上卦为体；动爻在上卦 → 下卦为体
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# 兼容作为脚本直接运行 与 作为包导入两种场景
try:
    from .data import (
        TRIGRAM_BY_XIAN_NUM, MOD8_TO_TRIGRAM, TRIGRAM_YAO,
        ELEMENT_MAP, DIZHI_NUM, CHINESE_HOURS, TRIGRAM_META,
        hexagram_names, hexagram_names2, HEXAGRAM_TEXT_BY_NAME,
        WANWU_LEIXIANG, XIAO_LIU_REN_NAMES, XIAO_LIU_REN_DETAIL,
        LIUSHEN_ORDER, RIGAN_LIUSHEN_START, LIUSHEN_DESCRIPTION,
        LIUSHEN_LIUQIN_DETAIL, LIUQIN_FADONG_DETAIL,
    )
except ImportError:
    from data import (  # type: ignore
        TRIGRAM_BY_XIAN_NUM, MOD8_TO_TRIGRAM, TRIGRAM_YAO,
        ELEMENT_MAP, DIZHI_NUM, CHINESE_HOURS, TRIGRAM_META,
        hexagram_names, hexagram_names2, HEXAGRAM_TEXT_BY_NAME,
        WANWU_LEIXIANG, XIAO_LIU_REN_NAMES, XIAO_LIU_REN_DETAIL,
        LIUSHEN_ORDER, RIGAN_LIUSHEN_START, LIUSHEN_DESCRIPTION,
        LIUSHEN_LIUQIN_DETAIL, LIUQIN_FADONG_DETAIL,
    )


# ---------------------------------------------------------
# 时间与农历
# ---------------------------------------------------------
def to_lunar(dt: datetime):
    """阳历 → 农历；返回 (lunar_month, lunar_day, year_ganzhi, hour_ganzhi, solar_str, lunar_str)"""
    try:
        from lunar_python import Solar
    except ImportError:
        raise RuntimeError(
            "缺少依赖 lunar_python。请运行：pip install lunar_python --break-system-packages"
        )
    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second or 0)
    lunar = solar.getLunar()
    month = lunar.getMonth()
    if month < 0:
        month = -month  # 闰月按其月份处理
    day = lunar.getDay()
    return {
        "lunar_month": month,
        "lunar_day": day,
        "year_ganzhi": lunar.getYearInGanZhi(),
        "month_ganzhi": lunar.getMonthInGanZhi(),
        "day_ganzhi": lunar.getDayInGanZhi(),
        "hour_ganzhi": lunar.getTimeInGanZhi(),
        "solar_str": str(solar),
        "lunar_str": str(lunar),
    }


def dizhi_to_num(char: str) -> int:
    """地支单字 → 序数 (子=1 … 亥=12)。"""
    return DIZHI_NUM.get(char, 0)


def year_branch_num(year_ganzhi: str) -> int:
    """从 "甲辰年" 一类字符串中取年支 → 1-12。"""
    m = re.search(r"(\S)年", year_ganzhi) or re.search(r"(\S)$", year_ganzhi)
    if not m:
        return 0
    return dizhi_to_num(m.group(1))


def hour_branch_num(hour_ganzhi: str) -> int:
    """从 "甲子时" 类字符串中取时支 → 1-12。"""
    for i, h in enumerate(CHINESE_HOURS):
        if h in hour_ganzhi:
            return i + 1  # 子时=1 … 亥时=12
    # 兼容仅给单字地支
    for i, ch in enumerate("子丑寅卯辰巳午未申酉戌亥"):
        if ch in hour_ganzhi:
            return i + 1
    return 0


# ---------------------------------------------------------
# 卦象工具
# ---------------------------------------------------------
def trigram_from_value(v: int) -> str:
    """以 mod 8 的余数（0-7）映射回卦名。"""
    return MOD8_TO_TRIGRAM[v % 8]


def trigram_from_yao(yao: List[int]) -> str:
    for name, pattern in TRIGRAM_YAO.items():
        if pattern == yao:
            return name
    return "未知"


def hexagram_pattern(upper: str, lower: str) -> List[int]:
    """上下卦 → 六爻数组（自上而下）。"""
    # hexagram[0..2] = upper [上爻, 五爻, 四爻] （与 hexagram_names2 中 pattern 保持一致）
    # hexagram_names2 中 pattern 顺序为自顶至底 (上爻→初爻)
    u = TRIGRAM_YAO[upper][::-1]  # 反转为自顶向下
    l = TRIGRAM_YAO[lower][::-1]
    return u + l


def hexagram_name(upper: str, lower: str) -> str:
    return hexagram_names.get((upper, lower), "未知卦")


def flip_line(v: int) -> int:
    return 0 if v else 1


def mutual_hexagram(pattern_top_down: List[int]) -> Tuple[str, str, List[int]]:
    """互卦：上卦=本卦第3,4,5爻，下卦=本卦第2,3,4爻。
    pattern_top_down 为自上而下的 6 爻数组，
    则 自下而上 = pattern_top_down[::-1]，
    第 2/3/4/5 爻（自下向上，1-indexed）对应 [::-1] 的 index 1..4。
    """
    bot_up = pattern_top_down[::-1]  # 自下而上
    # 互卦 上卦 = 本卦第三、四、五爻  -> bot_up[2], bot_up[3], bot_up[4]
    # 互卦 下卦 = 本卦第二、三、四爻  -> bot_up[1], bot_up[2], bot_up[3]
    upper_yao_bot_up = [bot_up[2], bot_up[3], bot_up[4]]
    lower_yao_bot_up = [bot_up[1], bot_up[2], bot_up[3]]
    upper = trigram_from_yao(upper_yao_bot_up)
    lower = trigram_from_yao(lower_yao_bot_up)
    # 重建 pattern 自顶而下
    new_pattern = (upper_yao_bot_up[::-1]) + (lower_yao_bot_up[::-1])
    return upper, lower, new_pattern


def changed_hexagram(pattern_top_down: List[int], moving_line: int) -> Tuple[str, str, List[int]]:
    """变卦：将动爻（1-6，自下而上）翻转。"""
    bot_up = pattern_top_down[::-1]
    if 1 <= moving_line <= 6:
        bot_up[moving_line - 1] = flip_line(bot_up[moving_line - 1])
    new_top_down = bot_up[::-1]
    # 上卦 = top_down[0..2] 对应 bot_up[3..5]
    upper_yao = bot_up[3:6]  # 自下而上 的 上卦
    lower_yao = bot_up[0:3]  # 自下而上 的 下卦
    upper = trigram_from_yao(upper_yao)
    lower = trigram_from_yao(lower_yao)
    return upper, lower, new_top_down


def opposite_hexagram(pattern_top_down: List[int]) -> Tuple[str, str, List[int]]:
    """错卦：每一爻阴阳皆反。"""
    new = [flip_line(v) for v in pattern_top_down]
    bot_up = new[::-1]
    upper_yao = bot_up[3:6]
    lower_yao = bot_up[0:3]
    return trigram_from_yao(upper_yao), trigram_from_yao(lower_yao), new


def reverse_hexagram(pattern_top_down: List[int]) -> Tuple[str, str, List[int]]:
    """综卦：六爻整体上下颠倒。"""
    new = pattern_top_down[::-1]
    bot_up = new[::-1]
    upper_yao = bot_up[3:6]
    lower_yao = bot_up[0:3]
    return trigram_from_yao(upper_yao), trigram_from_yao(lower_yao), new


def body_use(upper: str, lower: str, moving_line: int) -> Tuple[str, str, str, str]:
    """根据动爻位置（1-6）判体用。返回 (body, use, body_desc, use_desc)。
    动爻在下卦（1-3）→ 体卦=上卦、用卦=下卦
    动爻在上卦（4-6）→ 体卦=下卦、用卦=上卦
    """
    if 1 <= moving_line <= 3:
        return upper, lower, "上卦", "下卦"
    else:
        return lower, upper, "下卦", "上卦"


def element_relationship(body_el: str, use_el: str) -> Dict[str, str]:
    """体用五行生克关系。返回 {relation, level, detail}."""
    gen_pairs = [("木", "火"), ("火", "土"), ("土", "金"), ("金", "水"), ("水", "木")]
    ke_pairs = [("木", "土"), ("火", "金"), ("土", "水"), ("金", "木"), ("水", "火")]
    if body_el == use_el:
        return {"relation": "体用比和", "level": "大吉",
                "detail": f"体卦{body_el}与用卦{use_el}五行相同，比和最吉，诸事皆顺。"}
    if (body_el, use_el) in gen_pairs:
        return {"relation": "体生用", "level": "小凶",
                "detail": f"体{body_el}生用{use_el}，体气外泄，小有耗损，主力有不逮。"}
    if (use_el, body_el) in gen_pairs:
        return {"relation": "用生体", "level": "大吉",
                "detail": f"用{use_el}生体{body_el}，外助内旺，财喜自来，诸事有成。"}
    if (body_el, use_el) in ke_pairs:
        return {"relation": "体克用", "level": "小吉",
                "detail": f"体{body_el}克用{use_el}，可得其利，然须费力，小吉。"}
    if (use_el, body_el) in ke_pairs:
        return {"relation": "用克体", "level": "大凶",
                "detail": f"用{use_el}克体{body_el}，外力相逼，诸事不利，宜守避祸。"}
    return {"relation": "未知", "level": "—", "detail": ""}


# ---------------------------------------------------------
# 六神装卦 & 六亲
# ---------------------------------------------------------
def assign_liushen(day_ganzhi: str) -> List[str]:
    """根据日干确定六爻各自的六神（自下而上，返回 [初爻, 二爻, ..., 上爻] 共 6 个六神名）。

    甲乙日起青龙、丙丁日起朱雀、戊日起勾陈、己日起螣蛇、庚辛日起白虎、壬癸日起玄武。
    六神从初爻（第1爻）起依次排列。
    """
    # 取日干（干支字串的第一个字）
    rigan = day_ganzhi[0] if day_ganzhi else ""
    start = RIGAN_LIUSHEN_START.get(rigan, 0)
    return [LIUSHEN_ORDER[(start + i) % 6] for i in range(6)]


def get_liuqin(hex_name: str) -> List[str]:
    """获取本卦六爻的六亲信息（自上而下 → 反转为自下而上）。

    从 hexagram_names2 的 correspondence 字段获取，格式如 ["父母戌土", "兄弟申金", ...]。
    correspondence 在原数据中是自上而下的，返回值调整为自下而上（初爻在 index 0）。
    """
    info = hexagram_names2.get(hex_name, {})
    corr = info.get("correspondence", [])
    if not corr:
        return [""] * 6
    # 原数据是自上而下（上爻在[0]），反转为自下而上
    return list(reversed(corr))


def get_moving_liuqin(hex_name: str, moving_line: int) -> Tuple[str, str]:
    """获取动爻所在的六亲名 和 对应的六亲发动详解。

    返回 (liuqin_name, fadong_detail)。
    """
    liuqin_list = get_liuqin(hex_name)  # 自下而上
    if 1 <= moving_line <= 6:
        full_text = liuqin_list[moving_line - 1]  # e.g. "父母戌土"
        liuqin_name = full_text[:2] if len(full_text) >= 2 else ""
    else:
        liuqin_name = ""
    fadong_detail = LIUQIN_FADONG_DETAIL.get(liuqin_name, "")
    return liuqin_name, fadong_detail


# ---------------------------------------------------------
# 起卦
# ---------------------------------------------------------
def build_full_hexagram(upper_value: int, lower_value: int, moving_value: int,
                        meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    给定 上卦余数 下卦余数 动爻余数（皆为 mod 前结果），构建完整卦象。
    移动爻约定：余 0 则取 6
    上下卦：余 0 则坤（MOD8_TO_TRIGRAM[0]）
    """
    upper = MOD8_TO_TRIGRAM[upper_value % 8]
    lower = MOD8_TO_TRIGRAM[lower_value % 8]
    moving_line = moving_value % 6
    if moving_line == 0:
        moving_line = 6

    main_pattern = hexagram_pattern(upper, lower)
    main_name = hexagram_name(upper, lower)

    hu_up, hu_low, hu_pattern = mutual_hexagram(main_pattern)
    bian_up, bian_low, bian_pattern = changed_hexagram(main_pattern, moving_line)
    cuo_up, cuo_low, cuo_pattern = opposite_hexagram(main_pattern)
    zong_up, zong_low, zong_pattern = reverse_hexagram(main_pattern)

    body, use, body_pos, use_pos = body_use(upper, lower, moving_line)
    body_el = ELEMENT_MAP[body]
    use_el = ELEMENT_MAP[use]
    rel = element_relationship(body_el, use_el)

    main_info = hexagram_names2.get(main_name, {})
    main_text = HEXAGRAM_TEXT_BY_NAME.get(main_name, {})
    bian_name = hexagram_name(bian_up, bian_low)
    hu_name = hexagram_name(hu_up, hu_low)
    cuo_name = hexagram_name(cuo_up, cuo_low)
    zong_name = hexagram_name(zong_up, zong_low)

    return {
        "meta": meta,
        "main_hexagram": {
            "name": main_name,
            "upper": upper,
            "lower": lower,
            "pattern": main_pattern,
            "info": main_info,
            "text": main_text,
        },
        "mutual_hexagram": {
            "name": hu_name,
            "upper": hu_up, "lower": hu_low, "pattern": hu_pattern,
        },
        "changed_hexagram": {
            "name": bian_name,
            "upper": bian_up, "lower": bian_low, "pattern": bian_pattern,
            "info": hexagram_names2.get(bian_name, {}),
        },
        "opposite_hexagram": {
            "name": cuo_name,
            "upper": cuo_up, "lower": cuo_low, "pattern": cuo_pattern,
        },
        "reverse_hexagram": {
            "name": zong_name,
            "upper": zong_up, "lower": zong_low, "pattern": zong_pattern,
        },
        "moving_line": moving_line,
        "body_use": {
            "body": body, "use": use,
            "body_position": body_pos, "use_position": use_pos,
            "body_element": body_el, "use_element": use_el,
            "relationship": rel,
        },
        "wanwu_leixiang": {
            "upper": WANWU_LEIXIANG.get(upper, ""),
            "lower": WANWU_LEIXIANG.get(lower, ""),
        },
        # 六神 & 六亲 会在 divine_by_datetime 中填充（需要日干信息）
        "liushen": [],
        "liuqin": [],
        "moving_liuqin": {"name": "", "fadong_detail": ""},
        "liushen_liuqin_detail": [],  # 六神+六亲组合详解（6 条）
    }


def divine_by_datetime(dt_str: str, question: str = "") -> Dict[str, Any]:
    """年月日时起卦（已验证的邵雍先天起卦法）。

    公式：
      上卦 = (年支数 + 农历月 + 农历日) mod 8
      下卦 = (年支数 + 农历月 + 农历日 + 时支数) mod 8
      动爻 = (年支数 + 农历月 + 农历日 + 时支数) mod 6
    """
    dt = _parse_datetime(dt_str)
    lu = to_lunar(dt)
    year_n = year_branch_num(lu["year_ganzhi"])
    hour_n = hour_branch_num(lu["hour_ganzhi"])
    lm = lu["lunar_month"]
    ld = lu["lunar_day"]

    upper_value = (year_n + lm + ld) % 8
    lower_value = (year_n + lm + ld + hour_n) % 8
    moving_value = (year_n + lm + ld + hour_n) % 6

    meta = {
        "question": question,
        "method": "年月日时起卦",
        "input_datetime": dt.strftime("%Y-%m-%d %H:%M"),
        "solar": lu["solar_str"],
        "lunar": lu["lunar_str"],
        "year_ganzhi": lu["year_ganzhi"],
        "month_ganzhi": lu["month_ganzhi"],
        "day_ganzhi": lu["day_ganzhi"],
        "hour_ganzhi": lu["hour_ganzhi"],
        "year_num": year_n, "hour_num": hour_n,
        "lunar_month": lm, "lunar_day": ld,
        "formula": {
            "upper": f"({year_n}+{lm}+{ld})%8 = {upper_value}",
            "lower": f"({year_n}+{lm}+{ld}+{hour_n})%8 = {lower_value}",
            "moving": f"({year_n}+{lm}+{ld}+{hour_n})%6 = {moving_value}",
        },
    }
    result = build_full_hexagram(upper_value, lower_value, moving_value, meta)

    # 填充六神装卦（需要日干）
    day_gz = lu.get("day_ganzhi", "")
    if day_gz:
        liushen_list = assign_liushen(day_gz)
        result["liushen"] = liushen_list  # 自下而上 [初爻..上爻]

    # 填充六亲
    main_name = result["main_hexagram"]["name"]
    liuqin_list = get_liuqin(main_name)
    result["liuqin"] = liuqin_list  # 自下而上

    # 动爻六亲 + 发动详解
    ml = result["moving_line"]
    lq_name, fadong = get_moving_liuqin(main_name, ml)
    result["moving_liuqin"] = {"name": lq_name, "fadong_detail": fadong}

    # 六神+六亲组合详解
    details = []
    for i in range(6):
        shen = liushen_list[i] if i < len(liushen_list) else ""
        qin_full = liuqin_list[i] if i < len(liuqin_list) else ""
        qin_name = qin_full[:2] if len(qin_full) >= 2 else ""
        combo_text = LIUSHEN_LIUQIN_DETAIL.get((shen, qin_name), "")
        details.append({
            "yao": i + 1,
            "liushen": shen,
            "liuqin": qin_full,
            "detail": combo_text,
        })
    result["liushen_liuqin_detail"] = details

    return result


def divine_by_numbers(text: str, question: str = "",
                      rule: str = "规则1",
                      replace_zero_with_8: bool = True,
                      use_hour_for_moving: bool = False,
                      dt_str: Optional[str] = None,
                      stroke_variant: str = "simplified") -> Dict[str, Any]:
    """以数字/字符串起卦。

    - 若输入是中文字符，则使用离线笔画表 (strokes_util) 逐字取笔画数。
    - 若输入是阿拉伯数字，按数字直接参与计算。
    - 规则 1（常用）：
        * 1 个数字：上卦=该数%8，下卦=时支%8，动爻=(该数+时支)%6
        * 2 个数字：上卦=d1%8，下卦=d2%8，动爻=(d1+d2)%6
        * 3 个数字：上卦=d1%8，下卦=d2%8，动爻=d3%6（动爻可加时辰）
        * 4+ 数字：前半段求和为上卦、后半段求和为下卦、总和为动爻
    - 规则 2：上卦=d1，下卦=d2+d3，动爻=所有数字之和（可选 0 视为 8）

    stroke_variant:
        "simplified" | "traditional" | "kangxi"
        梅花易数的笔画制式。默认 simplified（按 Unihan 主笔画，对简体友好）。
    """
    digits = [int(c) for c in text if c.isdigit()]
    input_mode = "数字"
    strokes_detail: List[Dict[str, Any]] = []

    if not digits:
        # 未发现数字，尝试按汉字笔画起卦
        try:
            try:
                from .strokes_util import text_strokes_variant, to_traditional, stroke_count
            except ImportError:
                from strokes_util import text_strokes_variant, to_traditional, stroke_count  # type: ignore
        except ImportError:
            raise ValueError(
                "起卦输入需要至少一个阿拉伯数字，或可识别的汉字（缺少 strokes_util 模块）。"
            )
        stroke_list = text_strokes_variant(text, variant=stroke_variant)
        digits = [n for n in stroke_list if n > 0]
        if not digits:
            raise ValueError("输入无法识别为数字或有笔画的汉字，请换一组字符。")
        input_mode = f"笔画({stroke_variant})"
        # 用于卡片展示：逐字 -> 笔画
        lookup_text = (to_traditional(text)
                       if stroke_variant in ("traditional", "kangxi") else text)
        for src_ch, out_ch in zip(text, lookup_text):
            if src_ch.isspace():
                continue
            n = stroke_count(out_ch)
            strokes_detail.append({
                "char": src_ch,
                "lookup": out_ch if out_ch != src_ch else None,
                "strokes": n,
            })

    hour_n = 0
    if use_hour_for_moving or len(digits) == 1:
        # 如果启用「动爻取时辰」或只有 1 位数字，都需要时支数
        if dt_str is None:
            dt_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        dt = _parse_datetime(dt_str)
        lu = to_lunar(dt)
        hour_n = hour_branch_num(lu["hour_ganzhi"])

    n = len(digits)
    if rule == "规则2":
        if replace_zero_with_8:
            digits = [8 if d == 0 else d for d in digits]
        if n < 3:
            raise ValueError("规则 2 需要至少 3 位数字。")
        upper_v = digits[0] % 8
        lower_v = (digits[1] + digits[2]) % 8
        moving_v = sum(digits[:3]) % 6
        if use_hour_for_moving:
            moving_v = (moving_v + hour_n) % 6
    else:  # 规则 1
        if n == 1:
            upper_v = digits[0] % 8
            lower_v = hour_n % 8
            moving_v = (digits[0] + hour_n) % 6
        elif n == 2:
            upper_v = digits[0] % 8
            lower_v = digits[1] % 8
            moving_v = (digits[0] + digits[1]) % 6
            if use_hour_for_moving:
                moving_v = (moving_v + hour_n) % 6
        elif n == 3:
            upper_v = digits[0] % 8
            lower_v = digits[1] % 8
            moving_v = digits[2] % 6
            if use_hour_for_moving:
                moving_v = (moving_v + hour_n) % 6
        else:
            half = n // 2
            upper_v = sum(digits[:half]) % 8
            lower_v = sum(digits[half:]) % 8
            moving_v = sum(digits) % 6
            if use_hour_for_moving:
                moving_v = (moving_v + hour_n) % 6

    method_label = f"{input_mode}起卦 / {rule}"
    meta = {
        "question": question,
        "method": method_label,
        "input_text": text,
        "digits": digits,
        "use_hour_for_moving": use_hour_for_moving,
        "replace_zero_with_8": replace_zero_with_8,
        "hour_num": hour_n,
        "stroke_variant": stroke_variant if input_mode.startswith("笔画") else None,
        "strokes_detail": strokes_detail,
        "formula": {
            "upper": f"余数 = {upper_v}",
            "lower": f"余数 = {lower_v}",
            "moving": f"余数 = {moving_v}",
        },
    }
    return build_full_hexagram(upper_v, lower_v, moving_v, meta)


def divine_xiaoliuren(dt_str: Optional[str] = None, question: str = "") -> Dict[str, Any]:
    """小六壬起课：月上起大安，按农历月→日→时依次数 6 宫。"""
    if dt_str is None:
        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    dt = _parse_datetime(dt_str)
    lu = to_lunar(dt)
    hour_n = hour_branch_num(lu["hour_ganzhi"])  # 1-12
    lm = lu["lunar_month"]
    ld = lu["lunar_day"]

    # 月 → 日 → 时 递推，每步之间前一个结果作为下一个起点
    month_idx = (lm - 1) % 6
    day_idx = (month_idx + ld - 1) % 6
    hour_idx = (day_idx + hour_n - 1) % 6

    month_result = XIAO_LIU_REN_NAMES[month_idx]
    day_result = XIAO_LIU_REN_NAMES[day_idx]
    hour_result = XIAO_LIU_REN_NAMES[hour_idx]

    return {
        "meta": {
            "question": question, "method": "小六壬",
            "input_datetime": dt.strftime("%Y-%m-%d %H:%M"),
            "solar": lu["solar_str"], "lunar": lu["lunar_str"],
            "year_ganzhi": lu["year_ganzhi"], "month_ganzhi": lu["month_ganzhi"],
            "day_ganzhi": lu["day_ganzhi"], "hour_ganzhi": lu["hour_ganzhi"],
            "lunar_month": lm, "lunar_day": ld, "hour_num": hour_n,
        },
        "month": {"name": month_result, **XIAO_LIU_REN_DETAIL[month_result]},
        "day": {"name": day_result, **XIAO_LIU_REN_DETAIL[day_result]},
        "hour": {"name": hour_result, **XIAO_LIU_REN_DETAIL[hour_result]},
        "summary_name": hour_result,  # 终断以时课为主
    }


# ---------------------------------------------------------
# helpers
# ---------------------------------------------------------
def _parse_datetime(s: str) -> datetime:
    s = s.strip()
    fmts = [
        "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S",
        "%Y年%m月%d日 %H:%M", "%Y年%m月%d日 %H时",
        "%Y-%m-%d",
    ]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            if dt.hour == 0 and "%H" not in f:
                dt = dt.replace(hour=datetime.now().hour)
            return dt
        except ValueError:
            continue
    raise ValueError(f"无法解析时间 '{s}'，请用如 '2026-04-16 14:30' 的格式。")


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="熊半仙 · 梅花易数起卦")
    ap.add_argument("--datetime", help="阳历时间，如 '2026-04-16 14:30'")
    ap.add_argument("--numbers", help="用数字/字符串起卦（1~N 位数字）")
    ap.add_argument("--question", default="", help="所问事项（选填）")
    ap.add_argument("--rule", choices=["规则1", "规则2"], default="规则1")
    ap.add_argument("--replace-zero-with-8", action="store_true", default=True)
    ap.add_argument("--use-hour", action="store_true", help="数字起卦时动爻加时辰数")
    ap.add_argument("--stroke-variant", choices=["simplified", "traditional", "kangxi"],
                    default="simplified", help="汉字笔画制式（仅在以汉字起卦时生效）")
    ap.add_argument("--xiaoliuren", action="store_true", help="改为小六壬起课")
    ap.add_argument("--skin", choices=["auto", "a", "b", "c"], default="auto",
                    help="HTML 卡片皮肤：a=宋代文人(年月日时), b=民俗木刻(数字/笔画), "
                         "c=道符掐指(小六壬)。默认 auto（按起卦方式匹配）")
    ap.add_argument("--output-json", help="同时写出 JSON 文件")
    ap.add_argument("--output-html", help="同时写出 HTML 结果卡片")
    ap.add_argument("--output-png",
                    help="写出精准裁剪的长图 PNG；不传则在 --output-html 同目录"
                         "同文件名自动生成（关闭请用 --no-png）")
    ap.add_argument("--no-png", action="store_true",
                    help="即使设置了 --output-html 也不自动生成长图 PNG")
    ap.add_argument("--png-width", type=int, default=900,
                    help="长图视口宽度（默认 900，和卡片宽度匹配）")
    ap.add_argument("--png-scale", type=int, default=2,
                    help="长图像素倍率（1=标清, 2=Retina, 默认 2）")
    args = ap.parse_args()

    if args.xiaoliuren:
        result = divine_xiaoliuren(args.datetime, args.question)
    elif args.numbers:
        result = divine_by_numbers(
            args.numbers, question=args.question, rule=args.rule,
            replace_zero_with_8=args.replace_zero_with_8,
            use_hour_for_moving=args.use_hour, dt_str=args.datetime,
            stroke_variant=args.stroke_variant,
        )
    else:
        dt_str = args.datetime or datetime.now().strftime("%Y-%m-%d %H:%M")
        result = divine_by_datetime(dt_str, question=args.question)

    json_str = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            f.write(json_str)
    else:
        print(json_str)

    if args.output_html:
        try:
            from render_card import render_html
        except ImportError:
            from .render_card import render_html  # type: ignore
        # 按 --skin 显式指定；auto 则根据起卦方式自动选择
        skin = args.skin
        if skin == "auto":
            if args.xiaoliuren:
                skin = "c"
            elif args.numbers:
                skin = "b"
            else:
                skin = "a"
        html = render_html(result, is_xiaoliuren=args.xiaoliuren, skin=skin)
        with open(args.output_html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML 卡片已写入：{args.output_html}（皮肤：{skin}）", file=sys.stderr)

        # ---- 自动长图（跨平台，环境不支持时静默降级）----
        # 默认：HTML 已输出 + 未显式 --no-png  → 尝试生成 PNG
        if not args.no_png:
            png_path = args.output_png
            if not png_path:
                from os.path import splitext
                png_path = splitext(args.output_html)[0] + ".png"

            # 延迟导入 + 兜住一切异常，确保主流程永不因截图失败中断
            try:
                try:
                    from screenshot import html_to_png, ScreenshotUnavailable
                except ImportError:
                    from .screenshot import html_to_png, ScreenshotUnavailable  # type: ignore

                try:
                    out = html_to_png(
                        args.output_html, png_path,
                        width=args.png_width, scale=args.png_scale,
                    )
                    print(f"长图已保存：{out}", file=sys.stderr)
                except ScreenshotUnavailable as e:
                    print(f"[长图生成跳过] {e}", file=sys.stderr)
                    print("  → HTML 卡片已生成，用户可在浏览器中打开后点击"
                          "右上角「📸 保存为长图」按钮手动导出。",
                          file=sys.stderr)
                    print("  → 或在本机安装后重试（Mac/Windows/Linux 通用）：",
                          file=sys.stderr)
                    print("      pip install playwright", file=sys.stderr)
                    print("      playwright install chromium", file=sys.stderr)
            except Exception as e:  # 最后兜底，绝不打断
                print(f"[长图生成跳过 · 未知异常] {type(e).__name__}: {e}",
                      file=sys.stderr)


if __name__ == "__main__":
    main()
