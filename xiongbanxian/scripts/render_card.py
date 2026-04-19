# -*- coding: utf-8 -*-
"""
熊半仙 · 推演结果卡片渲染
=============================
将 divination.py 生成的结果字典渲染为一张自包含的 HTML 卡片。

用法：
  from render_card import render_html
  html = render_html(result_dict, skin="a")
  open("card.html", "w", encoding="utf-8").write(html)

三套皮肤：
  skin="a"  宋代文人雅致  —— 年月日时起卦
  skin="b"  民俗木刻喜气  —— 数字 / 笔画起卦
  skin="c"  道符掐指神秘  —— 小六壬

特性：
  - 纯自包含 HTML，无外部依赖（CSS、SVG 内联）
  - 卡片右上角自带"导出长图"按钮，基于 modern-screenshot（CDN）
  - 页面载入时自动展开所有 <details>，方便截图
  - #capture-root 容器保证精准裁剪边界
  - 中文字体栈兼容 macOS / Windows / Linux
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Tuple

try:
    from .data import ELEMENT_COLOR, ELEMENT_MAP, TRIGRAM_META, TRIGRAM_YAO, LIUSHEN_DESCRIPTION
except ImportError:
    from data import ELEMENT_COLOR, ELEMENT_MAP, TRIGRAM_META, TRIGRAM_YAO, LIUSHEN_DESCRIPTION  # type: ignore


# ============================================================
# 一、皮肤设计系统
# ============================================================
#
# 每套皮肤描述：配色、字体、纹样、hero 图的 SVG 花饰。
# CSS 用 CSS 变量写一次模板，皮肤仅靠替换变量与几处 SVG 实现差异化。
# ------------------------------------------------------------

SKINS: Dict[str, Dict[str, Any]] = {
    # 皮肤 A · 宋代文人（年月日时起卦）
    "a": {
        "name": "宋代文人",
        "ja_en": "Song Literati",
        "vars": {
            "--bg":           "#eadfcc",
            "--card-bg":      "#FFFAF0",
            "--card-alt":     "#F5ECD9",
            "--ink":          "#1A1A1A",
            "--ink-soft":     "#3a2e1f",
            "--muted":        "#5A5552",
            "--accent":       "#C41E3A",
            "--accent-soft":  "#D4A574",
            "--hue":          "#B5D8EB",
            "--line":         "#D0C3A8",
            "--shadow":       "0 2px 28px rgba(40,20,0,0.14)",
            "--font-title":   "'LXGW WenKai','Noto Serif SC','Source Han Serif SC','Songti SC','STSong','SimSun',serif",
            "--font-body":    "'Noto Serif SC','Source Han Serif SC','Songti SC','STSong','SimSun',serif",
            "--ornament-url": "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 24'><path d='M0 12 q10 -10 20 0 t20 0 t20 0 t20 0 t20 0 t20 0' stroke='%235A5552' fill='none' stroke-width='1'/></svg>\")",
        },
        "tagline": "观象玩辞 · 观变玩占",
        "tag_en":  "Observe the symbols · Contemplate the change",
        "seal":    "易",
    },

    # 皮肤 B · 民俗木刻（数字 / 笔画起卦）· 米黄宣纸 + 暗朱 + 古金
    "b": {
        "name": "民俗木刻",
        "ja_en": "Folk Woodblock",
        "vars": {
            "--bg":           "#E8D9B0",   # 米黄底（旧报纸）
            "--card-bg":      "#F7ECC9",   # 淡金笺
            "--card-alt":     "#EFE0B8",
            "--ink":          "#2A1A10",   # 浓墨
            "--ink-soft":     "#4A3223",
            "--muted":        "#6C543A",
            "--accent":       "#8B2518",   # 暗朱砂（非高亮红）
            "--accent-soft":  "#B8860B",   # 古金
            "--hue":          "#5A6B3A",
            "--line":         "#C4A868",
            "--shadow":       "0 3px 22px rgba(60,40,10,0.18)",
            "--font-title":   "'LXGW WenKai','LXGW Marker Gothic','Noto Sans SC','Source Han Sans SC',sans-serif",
            "--font-body":    "'LXGW WenKai','Noto Serif SC','Songti SC',serif",
            # 回纹 (key fret) — 古金描边
            "--ornament-url": "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M0 0 h24 v24 h-24 z M4 4 h16 v16 h-16 z M8 8 h8 v8 h-8 z' fill='none' stroke='%23B8860B' stroke-width='1'/></svg>\")",
        },
        "tagline": "笔笔有象 · 画画见吉",
        "tag_en":  "Each stroke a symbol · Each number an omen",
        "seal":    "福",
    },

    # 皮肤 C · 道符掐指（小六壬）· 素笺 + 松柏墨青 + 褐金
    "c": {
        "name": "道符掐指",
        "ja_en": "Daoist Talisman",
        "vars": {
            "--bg":           "#D4CDAE",   # 素笺底
            "--card-bg":      "#EFE8CE",   # 柔黄笺
            "--card-alt":     "#E3D9B5",
            "--ink":          "#1F1A12",
            "--ink-soft":     "#3A3426",
            "--muted":        "#5C5544",
            "--accent":       "#2F4F3E",   # 松柏墨青（取代扎眼朱）
            "--accent-soft":  "#8B6F47",   # 褐金
            "--hue":          "#2F4F3E",
            "--line":         "#B59E6F",
            "--shadow":       "0 3px 32px rgba(60,50,20,0.22)",
            "--font-title":   "'KaiTi','STKaiti','DFKai-SB','LXGW WenKai','Noto Serif SC',serif",
            "--font-body":    "'KaiTi','STKaiti','LXGW WenKai','Noto Serif SC','Source Han Serif SC',serif",
            # 八卦角章 — 墨青描边
            "--ornament-url": "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 60'><circle cx='30' cy='30' r='24' fill='none' stroke='%232F4F3E' stroke-width='1.4'/><circle cx='30' cy='30' r='18' fill='none' stroke='%232F4F3E' stroke-width='0.8'/><g stroke='%232F4F3E' stroke-width='3' stroke-linecap='round' fill='none'><path d='M30 8 L30 14 M30 46 L30 52 M8 30 L14 30 M46 30 L52 30 M14.5 14.5 L18.5 18.5 M41.5 41.5 L45.5 45.5 M45.5 14.5 L41.5 18.5 M18.5 41.5 L14.5 45.5'/></g></svg>\")",
        },
        "tagline": "掐指而断 · 立见吉凶",
        "tag_en":  "Count on fingers · See fortune instantly",
        "seal":    "符",
    },
}


def _skin(s: str) -> Dict[str, Any]:
    """规范化并取皮肤配置。"""
    key = (s or "a").lower()
    if key not in SKINS:
        key = "a"
    return SKINS[key], key  # type: ignore[return-value]


# ============================================================
# 二、爻象 SVG
# ============================================================

def trigram_svg(name: str, highlight: bool = False, accent: str = "#a34b28") -> str:
    """单卦三爻 SVG，自上而下绘制（上爻、二爻、初爻）。"""
    pattern_bottom_up = TRIGRAM_YAO[name]  # [初,二,三]
    pattern_top_down = pattern_bottom_up[::-1]  # [三,二,初]
    stroke = accent if highlight else "currentColor"
    lines = []
    for i, y in enumerate(pattern_top_down):
        y_pos = 8 + i * 14
        if y == 1:  # 阳爻 整线
            lines.append(
                f'<rect x="4" y="{y_pos-3}" width="56" height="6" rx="1.5" fill="{stroke}"/>'
            )
        else:  # 阴爻 两段
            lines.append(
                f'<rect x="4" y="{y_pos-3}" width="22" height="6" rx="1.5" fill="{stroke}"/>'
                f'<rect x="38" y="{y_pos-3}" width="22" height="6" rx="1.5" fill="{stroke}"/>'
            )
    return f'<svg viewBox="0 0 64 50" width="64" height="50" style="color:currentColor">{"".join(lines)}</svg>'


def hexagram_svg(pattern_top_down: List[int], moving_line: int = 0,
                 accent: str = "#b8391f") -> str:
    """6 爻 SVG（自上而下）。moving_line 为 1-6（自下而上）。"""
    lines = []
    for i, v in enumerate(pattern_top_down):
        is_moving = (moving_line and (5 - i) == moving_line - 1)
        stroke = accent if is_moving else "currentColor"
        y_pos = 10 + i * 16
        if v == 1:
            lines.append(
                f'<rect x="4" y="{y_pos-3}" width="72" height="6" rx="2" fill="{stroke}"/>'
            )
        else:
            lines.append(
                f'<rect x="4" y="{y_pos-3}" width="30" height="6" rx="2" fill="{stroke}"/>'
                f'<rect x="46" y="{y_pos-3}" width="30" height="6" rx="2" fill="{stroke}"/>'
            )
        if is_moving:
            lines.append(f'<circle cx="82" cy="{y_pos}" r="4" fill="{accent}"/>')
    return f'<svg viewBox="0 0 92 108" width="92" height="108" style="color:currentColor">{"".join(lines)}</svg>'


# ============================================================
# 三、HTML 小工具
# ============================================================

def _esc(s: str) -> str:
    return html.escape(s or "")


def _nl2br(s: str) -> str:
    return _esc(s).replace("\n", "<br>")


def _element_chip(el: str) -> str:
    c = ELEMENT_COLOR.get(el, "#888")
    return f'<span class="chip" style="background:{c}">{_esc(el)}</span>'


def _trigram_block(trig: str, label: str, highlight: bool = False,
                    accent: str = "#C41E3A") -> str:
    meta = TRIGRAM_META.get(trig, {})
    el = ELEMENT_MAP.get(trig, "")
    return f'''
    <div class="trigram-block">
      <div class="trigram-label">{_esc(label)}</div>
      <div class="trigram-art">{trigram_svg(trig, highlight, accent=accent)}</div>
      <div class="trigram-name">{_esc(trig)}</div>
      <div class="trigram-meta">{_esc(meta.get("symbol",""))} · {_esc(meta.get("family",""))} · {_element_chip(el)}</div>
    </div>'''


def _hexagram_card(title: str, data: Dict[str, Any], moving_line: int = 0,
                   subtitle: str = "", accent: str = "#b8391f") -> str:
    name = data.get("name", "未知")
    upper = data.get("upper", "")
    lower = data.get("lower", "")
    pattern = data.get("pattern", [])
    return f'''
    <div class="hex-card">
      <div class="hex-card-title">{_esc(title)}
        {f'<span class="hex-card-subtitle">{_esc(subtitle)}</span>' if subtitle else ''}
      </div>
      <div class="hex-card-body">
        <div class="hex-svg">{hexagram_svg(pattern, moving_line, accent=accent)}</div>
        <div class="hex-info">
          <div class="hex-name">{_esc(name)}</div>
          <div class="hex-trigrams">上{_esc(upper)} · 下{_esc(lower)}</div>
          <div class="hex-element">
            上 {_element_chip(ELEMENT_MAP.get(upper,""))} ·
            下 {_element_chip(ELEMENT_MAP.get(lower,""))}
          </div>
        </div>
      </div>
    </div>'''


def _render_strokes_block(meta: Dict[str, Any]) -> str:
    """当以汉字笔画起卦时，渲染"字→笔画"可视化条。"""
    details = meta.get("strokes_detail") or []
    if not details:
        return ""
    variant = meta.get("stroke_variant") or "simplified"
    variant_label = {
        "simplified":  "简体笔画",
        "traditional": "繁体笔画",
        "kangxi":      "康熙笔画",
    }.get(variant, variant)
    cells = []
    for d in details:
        ch = d.get("char", "")
        lookup = d.get("lookup")
        n = d.get("strokes", 0)
        badge = (f'<span class="stroke-lookup">按「{_esc(lookup)}」</span>'
                 if lookup else "")
        cells.append(f'''
        <div class="stroke-cell">
          <div class="stroke-char">{_esc(ch)}</div>
          {badge}
          <div class="stroke-num">{n}</div>
          <div class="stroke-label">画</div>
        </div>''')
    return f'''
    <div class="strokes-section">
      <div class="strokes-title">
        <span>笔画起卦 · {_esc(variant_label)}</span>
        <span class="strokes-hint">（离线 Unihan 查询 · 无 API 依赖）</span>
      </div>
      <div class="strokes-row">{"".join(cells)}</div>
    </div>'''


# ============================================================
# 四、总入口
# ============================================================

def render_html(result: Dict[str, Any], is_xiaoliuren: bool = False,
                skin: str = "auto") -> str:
    """主入口。skin: 'auto' | 'a' | 'b' | 'c'。"""
    # 自动匹配
    if skin == "auto":
        if is_xiaoliuren or result.get("meta", {}).get("method") == "小六壬":
            skin = "c"
        else:
            method = result.get("meta", {}).get("method", "")
            if "数字" in method or "笔画" in method:
                skin = "b"
            else:
                skin = "a"

    skin_cfg, skin_key = _skin(skin)

    if is_xiaoliuren or result.get("meta", {}).get("method") == "小六壬":
        return _render_xiaoliuren(result, skin_cfg, skin_key)
    return _render_meihua(result, skin_cfg, skin_key)


# ============================================================
# 五、渲染梅花易数卡片（皮肤 A / B 共用模板）
# ============================================================

def _render_liushen_liuqin(result: Dict[str, Any]) -> str:
    liushen = result.get("liushen", [])
    liuqin = result.get("liuqin", [])
    details = result.get("liushen_liuqin_detail", [])
    if not liushen and not liuqin:
        return ""

    moving_line = result.get("moving_line", 0)
    main_pattern = result.get("main_hexagram", {}).get("pattern", [])

    shen_colors = {
        "青龙": "#228B22", "朱雀": "#FF4500", "勾陈": "#8B5A2B",
        "螣蛇": "#6B4226", "白虎": "#888", "玄武": "#3B5BDB",
    }

    yao_names = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]
    rows = []
    for i in range(5, -1, -1):
        shen = liushen[i] if i < len(liushen) else ""
        qin = liuqin[i] if i < len(liuqin) else ""
        is_moving = (i + 1 == moving_line)
        bot_up = main_pattern[::-1] if main_pattern else []
        yao_val = bot_up[i] if i < len(bot_up) else 0
        yao_sym = "━━━" if yao_val == 1 else "━ ━"
        yao_class = "yao-moving" if is_moving else ""
        shen_c = shen_colors.get(shen, "#333")
        rows.append(f'''
        <tr class="{yao_class}">
          <td class="ls-yao">{_esc(yao_names[i])}{' <span class="dot-moving">●</span>' if is_moving else ''}</td>
          <td class="ls-sym">{yao_sym}</td>
          <td class="ls-shen" style="color:{shen_c}">{_esc(shen)}</td>
          <td class="ls-qin">{_esc(qin)}</td>
        </tr>''')

    return f'''
    <div class="liushen-section">
      <h3>六爻 · 六神 · 六亲</h3>
      <table class="liushen-table">
        <thead><tr><th>爻位</th><th>爻象</th><th>六神</th><th>六亲</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
      <details class="liushen-desc" open>
        <summary>六神详解</summary>
        <div class="liushen-desc-body">
          {''.join(f'<p><b style="color:{shen_colors.get(s,"#333")}">{_esc(s)}</b>：{_esc(LIUSHEN_DESCRIPTION.get(s,"")[:80])}…</p>' for s in ["青龙","朱雀","勾陈","螣蛇","白虎","玄武"])}
        </div>
      </details>
    </div>'''


def _render_fadong(result: Dict[str, Any]) -> str:
    moving_lq = result.get("moving_liuqin", {})
    name = moving_lq.get("name", "")
    detail = moving_lq.get("fadong_detail", "")
    if not name or not detail:
        return ""
    return f'''
    <details class="fadong-section" open>
      <summary>【{_esc(name)}爻发动】详解</summary>
      <div class="fadong-body">
        <p>{_nl2br(detail)}</p>
      </div>
    </details>'''


def _render_meihua(result: Dict[str, Any], skin_cfg: Dict[str, Any], skin_key: str) -> str:
    meta = result["meta"]
    main = result["main_hexagram"]
    hu = result["mutual_hexagram"]
    bian = result["changed_hexagram"]
    cuo = result["opposite_hexagram"]
    zong = result["reverse_hexagram"]
    bu = result["body_use"]
    moving_line = result["moving_line"]

    main_info = main.get("info", {}) or {}
    main_text = main.get("text", {}) or {}

    description_list = main_info.get("description", [])
    description_str = " · ".join(description_list) if description_list else ""
    category = main_info.get("category", "")
    additional = main_info.get("additional_info", [""])[0] if main_info.get("additional_info") else ""

    rel = bu["relationship"]
    rel_label = rel["relation"]
    rel_level = rel["level"]
    rel_detail = rel["detail"]

    level_color = {
        "大吉": "#c1272d", "小吉": "#d4a017",
        "小凶": "#7b5544", "大凶": "#222",
        "—": "#888",
    }.get(rel_level, "#888")

    def maybe(key: str, title: str, data: Dict[str, Any]) -> str:
        v = data.get(key)
        if not v:
            return ""
        return f'''
        <div class="text-block">
          <h4>{_esc(title)}</h4>
          <p>{_nl2br(v)}</p>
        </div>'''

    text_sections = ""
    for key, title in [
        ("原文", "《易经》原文"),
        ("白话", "白话译文"),
        ("象意", "象意"),
        ("《断易天机》解", "《断易天机》"),
        ("北宋易学家邵雍解", "邵雍解"),
        ("台湾国学大儒傅佩荣解", "傅佩荣解"),
        ("传统解卦", "传统解卦"),
    ]:
        text_sections += maybe(key, title, main_text)

    philosophy = main_text.get("哲学含义", "")
    if philosophy and philosophy != "无":
        text_sections += f'''
        <details class="philosophy" open>
          <summary>哲学含义</summary>
          <p>{_nl2br(philosophy)}</p>
        </details>'''

    upper_wanwu = result.get("wanwu_leixiang", {}).get("upper", "")
    lower_wanwu = result.get("wanwu_leixiang", {}).get("lower", "")
    wanwu_html = ""
    if upper_wanwu or lower_wanwu:
        wanwu_html = f'''
        <details class="wanwu" open>
          <summary>万物类象（上下卦各自类象）</summary>
          <div class="wanwu-grid">
            <div class="wanwu-col"><pre>{_esc(upper_wanwu)}</pre></div>
            <div class="wanwu-col"><pre>{_esc(lower_wanwu)}</pre></div>
          </div>
        </details>'''

    formula_lines = ""
    if "formula" in meta:
        f = meta["formula"]
        formula_lines = (
            f'<div class="formula">上卦：{_esc(f.get("upper",""))}　·　'
            f'下卦：{_esc(f.get("lower",""))}　·　'
            f'动爻：{_esc(f.get("moving",""))}</div>'
        )

    header_info = []
    if meta.get("question"):
        header_info.append(f'<span class="q-label">所问：</span>{_esc(meta["question"])}')
    header_info.append(f'<span class="q-label">起卦方式：</span>{_esc(meta.get("method",""))}')
    if meta.get("solar"):
        header_info.append(f'<span class="q-label">阳历：</span>{_esc(meta["solar"])}')
    if meta.get("lunar"):
        header_info.append(f'<span class="q-label">阴历：</span>{_esc(meta["lunar"])}')
    if meta.get("year_ganzhi"):
        header_info.append(
            f'<span class="q-label">干支：</span>'
            f'{_esc(meta.get("year_ganzhi",""))}年 '
            f'{_esc(meta.get("month_ganzhi",""))}月 '
            f'{_esc(meta.get("day_ganzhi",""))}日 '
            f'{_esc(meta.get("hour_ganzhi",""))}时'
        )

    head_html = "　·　".join(header_info)

    moving_line_text = {1: "初爻", 2: "二爻", 3: "三爻",
                        4: "四爻", 5: "五爻", 6: "上爻"}[moving_line]

    # 笔画块（仅 skin=b 时相关）
    strokes_html = _render_strokes_block(meta)

    accent = skin_cfg["vars"]["--accent"]
    svg_accent = skin_cfg["vars"]["--accent"]

    body = f'''
  <header class="top">
    <div class="brand">
      <span class="seal">{_esc(skin_cfg["seal"])}</span>
      <span class="brand-zh">熊半仙</span>
      <span class="brand-en">{_esc(skin_cfg["ja_en"])} · 梅花易数</span>
    </div>
    <div class="tagline">{_esc(skin_cfg["tagline"])}
      <span class="tag-en">{_esc(skin_cfg["tag_en"])}</span>
    </div>
  </header>

  <div class="meta-line">{head_html}</div>
  {formula_lines}
  {strokes_html}

  <!-- 主卦 Hero -->
  <section class="main-hero">
    <div class="hero-left">
      <div class="main-name">{_esc(main["name"])}</div>
      <div class="main-sub">上 <b>{_esc(main["upper"])}</b> · 下 <b>{_esc(main["lower"])}</b>
        {_esc(category)} · {_esc(additional)}</div>
      <div class="main-desc">{_esc(description_str)}</div>
      <div class="main-xiang">{_nl2br(main_text.get("象意",""))}</div>
    </div>
    <div class="hero-right">
      {hexagram_svg(main["pattern"], moving_line, accent=svg_accent)}
      <div class="moving-label">动爻：{moving_line_text}（第 {moving_line} 爻）</div>
    </div>
  </section>

  <!-- 体用 -->
  <section class="bodyuse">
    <div class="bodyuse-row">
      {_trigram_block(bu["body"], f"体卦 · {bu['body_position']}", highlight=False, accent=accent)}
      <div class="bu-connector">
        <div class="bu-arrow">▶</div>
        <div class="bu-rel" style="color:{level_color}">{_esc(rel_label)}</div>
        <div class="bu-level" style="background:{level_color}">{_esc(rel_level)}</div>
      </div>
      {_trigram_block(bu["use"], f"用卦 · {bu['use_position']}", highlight=True, accent=accent)}
    </div>
    <div class="bu-detail">{_esc(rel_detail)}</div>
  </section>

  <!-- 六爻·六神·六亲 -->
  {_render_liushen_liuqin(result)}

  <!-- 六亲发动 -->
  {_render_fadong(result)}

  <!-- 四卦联动 -->
  <section class="grid-4">
    {_hexagram_card("互卦 · 中间进程", hu, subtitle="由二三四五爻组成", accent=svg_accent)}
    {_hexagram_card("变卦 · 事情结局", bian, moving_line=moving_line, subtitle=f"动爻({moving_line_text})变", accent=svg_accent)}
    {_hexagram_card("错卦 · 反面镜像", cuo, subtitle="六爻阴阳俱反", accent=svg_accent)}
    {_hexagram_card("综卦 · 换位视角", zong, subtitle="六爻整体倒置", accent=svg_accent)}
  </section>

  <!-- 卦辞 -->
  <section class="text-area">
    <h3>《{_esc(main["name"])}》卦辞详解</h3>
    {text_sections if text_sections else "<p>（该卦无收录详解）</p>"}
  </section>

  {wanwu_html}

  <footer class="footer">
    <div class="footer-l">结果仅供决策参考 · 梅花易数贵在象、理、数、占综合研判</div>
    <div class="footer-r">· 熊半仙 · {_esc(meta.get("input_datetime",""))}</div>
  </footer>
'''
    return _wrap_page(body, skin_cfg, skin_key,
                       title=f"熊半仙 · 梅花易数推演 · {main['name']}")


# ============================================================
# 六、渲染小六壬卡片（皮肤 C）
# ============================================================

def _render_xiaoliuren(result: Dict[str, Any], skin_cfg: Dict[str, Any], skin_key: str) -> str:
    meta = result["meta"]
    m = result["month"]; d = result["day"]; h = result["hour"]
    header_info = []
    if meta.get("question"):
        header_info.append(f'<span class="q-label">所问：</span>{_esc(meta["question"])}')
    header_info.append(f'<span class="q-label">起课方式：</span>小六壬')
    header_info.append(f'<span class="q-label">阳历：</span>{_esc(meta.get("solar",""))}')
    header_info.append(f'<span class="q-label">阴历：</span>{_esc(meta.get("lunar",""))}')
    header_info.append(
        f'<span class="q-label">干支：</span>'
        f'{_esc(meta.get("year_ganzhi",""))}年 '
        f'{_esc(meta.get("month_ganzhi",""))}月 '
        f'{_esc(meta.get("day_ganzhi",""))}日 '
        f'{_esc(meta.get("hour_ganzhi",""))}时'
    )
    head_html = "　·　".join(header_info)

    def _step(title: str, info: Dict[str, Any]) -> str:
        el = info.get("五行", "")
        c = ELEMENT_COLOR.get(el, "#888")
        return f'''
        <div class="xlr-step">
          <div class="xlr-step-title">{_esc(title)}</div>
          <div class="xlr-step-name" style="color:{c}">{_esc(info["name"])}</div>
          <div class="xlr-step-meta">
            五行 {_element_chip(el)} · {_esc(info.get("方位",""))} · {_esc(info.get("神兽",""))}
          </div>
          <div class="xlr-step-xiang">{_esc(info.get("象意",""))}</div>
        </div>'''

    body = f'''
  <header class="top">
    <div class="brand">
      <span class="seal">{_esc(skin_cfg["seal"])}</span>
      <span class="brand-zh">熊半仙</span>
      <span class="brand-en">{_esc(skin_cfg["ja_en"])} · 小六壬</span>
    </div>
    <div class="tagline">{_esc(skin_cfg["tagline"])}
      <span class="tag-en">{_esc(skin_cfg["tag_en"])}</span>
    </div>
  </header>

  <div class="meta-line">{head_html}</div>

  <section class="xlr-hero">
    <div class="bagua-corner bagua-tl"></div>
    <div class="bagua-corner bagua-tr"></div>
    <div class="bagua-corner bagua-bl"></div>
    <div class="bagua-corner bagua-br"></div>
    <div class="xlr-final">{_esc(h["name"])}</div>
    <div class="xlr-final-sub">{_esc(h.get("象意",""))}</div>
  </section>

  <section class="xlr-row">
    {_step("月课", m)} {_step("日课", d)} {_step("时课（终断）", h)}
  </section>

  <section class="text-area">
    <h3>《{_esc(h["name"])}》详解</h3>
    <div class="text-block"><h4>判辞</h4><p>{_nl2br(h.get("判辞",""))}</p></div>
    <div class="text-block"><h4>详解</h4><p>{_nl2br(h.get("详解",""))}</p></div>
  </section>

  <footer class="footer">
    <div class="footer-l">小六壬起于月、转于日、落于时——终以「时课」为断</div>
    <div class="footer-r">· 熊半仙 · {_esc(meta.get("input_datetime",""))}</div>
  </footer>
'''
    return _wrap_page(body, skin_cfg, skin_key,
                       title=f"熊半仙 · 小六壬起课 · {h['name']}")


# ============================================================
# 七、页面包装（皮肤变量 + CSS 模板 + 长截图导出按钮）
# ============================================================

def _wrap_page(body_html: str, skin_cfg: Dict[str, Any], skin_key: str,
               title: str) -> str:
    # 组装 CSS 变量
    var_css = "\n".join(f"  {k}: {v};" for k, v in skin_cfg["vars"].items())
    css = _css_template()
    skin_tag = f"skin-{skin_key}"

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
:root {{
{var_css}
}}
{css}
</style>
</head>
<body class="{skin_tag}">

<!-- 导出按钮（截图时自动隐藏） -->
<div class="export-bar no-export">
  <button id="xbx-export-btn" type="button">📸 保存为长图</button>
  <span class="export-tip">生成高清 PNG，可直接分享到朋友圈 / 小红书</span>
</div>

<main id="capture-root">
<article class="card">
{body_html}
</article>
</main>

<!-- modern-screenshot（本地打开时无网络会退化为提示） -->
<script src="https://cdn.jsdelivr.net/npm/modern-screenshot@4.5.2/dist/index.umd.js" crossorigin="anonymous"></script>
<script>
(function() {{
  // 1) 页面加载后自动展开所有 <details>
  function expandAll() {{
    document.querySelectorAll('details').forEach(function(d) {{ d.open = true; }});
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', expandAll);
  }} else {{
    expandAll();
  }}

  // 2) 导出长图
  var btn = document.getElementById('xbx-export-btn');
  if (!btn) return;
  btn.addEventListener('click', async function() {{
    var lib = window.modernScreenshot || window.ms;
    if (!lib || !lib.domToPng) {{
      alert('长图组件未加载（可能是离线打开）。请在联网环境下重试，或使用浏览器\\"网页截图\\"功能。');
      return;
    }}
    btn.disabled = true;
    var original = btn.textContent;
    btn.textContent = '⏳ 生成中…';
    document.body.classList.add('export-mode');
    expandAll();
    // 等字体
    try {{ await document.fonts.ready; }} catch (e) {{}}
    try {{
      var root = document.getElementById('capture-root');
      var rootBg = getComputedStyle(document.body).backgroundColor;
      var dataUrl = await lib.domToPng(root, {{
        scale: 2,
        backgroundColor: rootBg,
        style: {{ margin: '0' }},
      }});
      var a = document.createElement('a');
      a.href = dataUrl;
      var ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = 'xiongbanxian-' + ts + '.png';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }} catch (err) {{
      console.error(err);
      alert('生成长图失败：' + (err && err.message ? err.message : err));
    }} finally {{
      document.body.classList.remove('export-mode');
      btn.disabled = false;
      btn.textContent = original;
    }}
  }});
}})();
</script>
</body>
</html>
'''


# ============================================================
# 八、CSS 模板（使用 CSS 变量 + 各皮肤差异化 class）
# ============================================================

def _css_template() -> str:
    return r"""
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--ink);
  padding: 28px 0 36px;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

/* 导出按钮栏 */
.export-bar {
  max-width: 820px;
  margin: 0 auto 14px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.export-bar button {
  background: var(--accent);
  color: #fff;
  border: none;
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
  border-radius: 4px;
  cursor: pointer;
  box-shadow: 0 2px 10px rgba(0,0,0,0.18);
  transition: transform .15s;
  font-family: var(--font-body);
}
.export-bar button:hover { transform: translateY(-1px); }
.export-bar button:disabled { opacity: .6; cursor: not-allowed; transform: none; }
.export-tip { color: var(--muted); font-size: 12px; letter-spacing: 1px; }

/* 导出模式：隐藏按钮 & 微交互 */
body.export-mode .no-export { display: none !important; }
body.export-mode details > summary::-webkit-details-marker,
body.export-mode details > summary::marker { color: transparent; }
body.export-mode details > summary { pointer-events: none; cursor: default; }

/* 截图容器（精准裁剪边界） */
#capture-root {
  max-width: 820px;
  margin: 0 auto;
  padding: 20px 24px 28px;
  background: var(--bg);
}

.card {
  background: var(--card-bg);
  color: var(--ink);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  padding: 36px 44px 28px;
  position: relative;
}

/* 顶部 */
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  border-bottom: 2px solid var(--accent);
  padding-bottom: 14px;
  margin-bottom: 16px;
  position: relative;
}
.brand { display: flex; align-items: baseline; gap: 10px; }
.seal {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  width: 40px; height: 40px;
  background: var(--accent);
  color: var(--card-bg);
  font-family: var(--font-title);
  font-size: 22px;
  font-weight: 700;
  border-radius: 4px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.18);
}
.brand-zh {
  font-family: var(--font-title);
  font-size: 34px;
  letter-spacing: 6px;
  color: var(--accent);
  font-weight: 700;
}
.brand-en { color: var(--muted); font-size: 12px; letter-spacing: 2px; }
.tagline {
  color: var(--muted);
  font-size: 14px;
  letter-spacing: 2px;
  text-align: right;
  line-height: 1.5;
}
.tag-en { display: block; font-size: 10px; letter-spacing: 1px; opacity: .75; }

/* Meta / 公式 */
.meta-line {
  font-size: 13px;
  color: var(--ink-soft);
  margin-bottom: 6px;
  line-height: 1.9;
}
.q-label { color: var(--muted); font-weight: 700; }
.formula {
  background: var(--card-alt);
  border-left: 3px solid var(--accent);
  padding: 8px 12px;
  font-size: 13px;
  color: var(--ink-soft);
  margin: 8px 0 14px;
  letter-spacing: 1px;
  font-family: var(--font-body);
}

/* 笔画展示 */
.strokes-section {
  background: var(--card-alt);
  border: 1px dashed var(--accent);
  padding: 14px 16px;
  margin: 0 0 18px;
}
.strokes-title {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  color: var(--accent);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 1.5px;
  margin-bottom: 10px;
}
.strokes-hint { font-weight: 400; color: var(--muted); font-size: 11px; letter-spacing: 1px; }
.strokes-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.stroke-cell {
  flex: 1 1 70px;
  min-width: 70px;
  text-align: center;
  padding: 10px 6px;
  background: var(--card-bg);
  border: 1px solid var(--line);
}
.stroke-char {
  font-family: var(--font-title);
  font-size: 28px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.1;
}
.stroke-lookup {
  display: block;
  font-size: 10px;
  color: var(--muted);
  margin: 2px 0 4px;
}
.stroke-num {
  font-family: var(--font-title);
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
}
.stroke-label { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* 主卦 Hero */
.main-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  background: var(--card-alt);
  border: 1px solid var(--line);
  padding: 22px 26px;
  margin-bottom: 22px;
  position: relative;
}
.hero-left { flex: 1; }
.main-name {
  font-family: var(--font-title);
  font-size: 40px;
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 2px;
  line-height: 1.15;
}
.main-sub { color: var(--muted); margin-top: 4px; font-size: 13px; }
.main-desc { margin-top: 12px; font-size: 16px; color: var(--ink); line-height: 1.7; }
.main-xiang { margin-top: 10px; color: var(--ink-soft); line-height: 1.8; font-size: 14px; }
.hero-right { display: flex; flex-direction: column; align-items: center; color: var(--ink); }
.moving-label { margin-top: 6px; color: var(--accent); font-size: 12px; font-weight: 700; }

/* 体用 */
.bodyuse {
  background: var(--card-bg);
  border: 1px solid var(--line);
  padding: 18px;
  margin-bottom: 22px;
  position: relative;
}
.bodyuse-row {
  display: flex;
  justify-content: space-around;
  align-items: center;
}
.trigram-block { text-align: center; width: 130px; color: var(--ink); }
.trigram-label { font-size: 13px; color: var(--muted); letter-spacing: 1px; margin-bottom: 4px; }
.trigram-art svg { display: block; margin: 0 auto; }
.trigram-name {
  font-family: var(--font-title);
  font-size: 22px;
  color: var(--ink);
  font-weight: 700;
  margin-top: 4px;
}
.trigram-meta { font-size: 12px; color: var(--muted); margin-top: 2px; }
.bu-connector { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.bu-arrow { color: var(--accent-soft); font-size: 22px; }
.bu-rel { font-size: 16px; font-weight: 700; letter-spacing: 2px; }
.bu-level { color: #fff; padding: 2px 12px; font-size: 12px; border-radius: 2px; }
.bu-detail { margin-top: 12px; text-align: center; color: var(--ink-soft); font-size: 14px; }
.chip {
  display: inline-block;
  color: #fff;
  padding: 1px 8px;
  font-size: 12px;
  border-radius: 2px;
  margin: 0 2px;
}

/* 四卦 grid */
.grid-4 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  margin-bottom: 22px;
}
.hex-card {
  background: var(--card-alt);
  border: 1px solid var(--line);
  padding: 14px 16px;
  color: var(--ink);
}
.hex-card-title {
  font-weight: 700;
  color: var(--accent);
  font-size: 14px;
  letter-spacing: 1px;
  border-bottom: 1px dashed var(--line);
  padding-bottom: 4px;
  margin-bottom: 8px;
}
.hex-card-subtitle { margin-left: 6px; color: var(--muted); font-size: 12px; font-weight: 400; }
.hex-card-body { display: flex; gap: 14px; align-items: center; color: var(--ink); }
.hex-svg { flex-shrink: 0; }
.hex-info { flex: 1; }
.hex-name { font-family: var(--font-title); font-size: 22px; font-weight: 700; }
.hex-trigrams { color: var(--muted); font-size: 13px; }
.hex-element { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* 文本节 */
.text-area {
  background: var(--card-bg);
  border: 1px solid var(--line);
  padding: 18px 20px;
}
.text-area h3 {
  color: var(--accent);
  font-family: var(--font-title);
  margin: 0 0 10px;
  font-size: 20px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 4px;
}
.text-block { margin-bottom: 12px; }
.text-block h4 {
  margin: 0 0 4px;
  color: var(--accent-soft);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 1px;
}
.text-block p { margin: 0; line-height: 1.85; color: var(--ink); font-size: 14px; }
.philosophy {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--card-alt);
  border-left: 3px solid var(--accent-soft);
}
.philosophy summary { cursor: pointer; color: var(--accent); font-weight: 700; }
.philosophy p { margin: 8px 0 0; line-height: 1.85; font-size: 14px; }

.wanwu {
  margin-top: 14px;
  background: var(--card-bg);
  border: 1px solid var(--line);
  padding: 12px 14px;
}
.wanwu summary { cursor: pointer; color: var(--accent); font-weight: 700; }
.wanwu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 8px;
}
.wanwu-col pre {
  font-family: var(--font-body);
  white-space: pre-wrap;
  margin: 0;
  font-size: 12px;
  color: var(--ink-soft);
  line-height: 1.7;
}

/* footer */
.footer {
  margin-top: 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--muted);
  font-size: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}

/* 六神六亲 */
.liushen-section {
  background: var(--card-bg);
  border: 1px solid var(--line);
  padding: 16px 18px;
  margin-bottom: 22px;
}
.liushen-section h3 {
  color: var(--accent);
  font-family: var(--font-title);
  margin: 0 0 10px;
  font-size: 20px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 4px;
}
.liushen-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.liushen-table th {
  background: var(--card-alt);
  color: var(--muted);
  padding: 6px 8px;
  text-align: center;
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  letter-spacing: 1px;
}
.liushen-table td {
  padding: 6px 8px;
  text-align: center;
  border-bottom: 1px dashed var(--line);
}
.liushen-table tr.yao-moving td { background: var(--card-alt); }
.ls-yao { font-weight: 700; width: 80px; }
.ls-sym { font-family: monospace; font-size: 16px; letter-spacing: 2px; width: 60px; }
.ls-shen { font-weight: 700; width: 60px; }
.ls-qin { color: var(--ink-soft); }
.dot-moving { color: var(--accent); font-size: 10px; }
.liushen-desc { margin-top: 10px; padding: 8px 10px; background: var(--card-alt); }
.liushen-desc summary { cursor: pointer; color: var(--accent); font-weight: 700; }
.liushen-desc-body p { margin: 4px 0; font-size: 13px; line-height: 1.7; color: var(--ink-soft); }

.fadong-section {
  background: var(--card-bg);
  border: 1px solid var(--line);
  padding: 14px 18px;
  margin-bottom: 22px;
}
.fadong-section summary { cursor: pointer; color: var(--accent); font-weight: 700; font-size: 15px; }
.fadong-body p { margin: 10px 0 0; line-height: 1.85; font-size: 14px; color: var(--ink); }

/* 小六壬 */
.xlr-hero {
  background: var(--card-alt);
  border: 1px solid var(--line);
  padding: 32px 22px 26px;
  text-align: center;
  margin-bottom: 20px;
  position: relative;
}
.bagua-corner {
  position: absolute;
  width: 48px; height: 48px;
  background-image: var(--ornament-url);
  background-size: contain;
  background-repeat: no-repeat;
  opacity: .55;
}
.bagua-tl { top: 8px; left: 8px; }
.bagua-tr { top: 8px; right: 8px; }
.bagua-bl { bottom: 8px; left: 8px; }
.bagua-br { bottom: 8px; right: 8px; }
.xlr-final {
  font-family: var(--font-title);
  font-size: 56px;
  color: var(--accent);
  letter-spacing: 12px;
  font-weight: 700;
  text-shadow: 2px 2px 0 var(--card-bg);
}
.xlr-final-sub { color: var(--ink-soft); margin-top: 10px; font-size: 14px; letter-spacing: 1px; }
.xlr-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 22px;
}
.xlr-step {
  background: var(--card-bg);
  border: 1px solid var(--line);
  padding: 16px 14px;
  text-align: center;
  color: var(--ink);
}
.xlr-step-title { font-size: 12px; letter-spacing: 2px; color: var(--muted); }
.xlr-step-name {
  font-family: var(--font-title);
  font-size: 30px;
  font-weight: 700;
  margin: 6px 0;
  letter-spacing: 3px;
}
.xlr-step-meta { color: var(--muted); font-size: 12px; margin-bottom: 4px; }
.xlr-step-xiang { color: var(--ink-soft); font-size: 13px; line-height: 1.7; }

/* ===== 皮肤专属微调 ===== */

/* 皮肤 A：宋代文人 —— 顶部再加一道云纹 */
.skin-a .top::before {
  content: '';
  position: absolute;
  top: -24px;
  left: 0; right: 0;
  height: 16px;
  background-image: var(--ornament-url);
  background-size: 120px 16px;
  background-repeat: repeat-x;
  opacity: .45;
}

/* 皮肤 B：民俗木刻 —— 暗朱双线 + 古金回纹 */
.skin-b #capture-root {
  padding: 28px 24px 32px;
}
.skin-b .card {
  border: 4px double var(--accent);
  outline: 1px solid var(--line);
  outline-offset: -7px;
  box-shadow: 0 0 0 2px var(--card-bg), 0 4px 26px rgba(80,55,20,0.22);
}
.skin-b .card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 10px;
  background-image: var(--ornament-url);
  background-size: 24px 10px;
  background-repeat: repeat-x;
  opacity: .6;
}
.skin-b .seal {
  background: var(--accent);
  color: var(--card-bg);
  border: 2px solid var(--card-bg);
  box-shadow: 0 0 0 2px var(--accent), 0 2px 8px rgba(50,20,5,0.28);
}
.skin-b .main-name { text-shadow: 1px 1px 0 rgba(139,37,24,0.18); }
.skin-b .stroke-cell {
  border: 1px solid var(--accent);
  box-shadow: inset 0 0 0 2px var(--card-bg), 0 0 0 1px var(--line);
  background: var(--card-alt);
  color: var(--ink);
}
.skin-b .stroke-char { color: var(--ink); }
.skin-b .chip { border: 1px solid var(--line); }

/* 皮肤 C：道符掐指 —— 朱砂大印 + 八卦角章 */
.skin-c .card::after {
  content: '';
  position: absolute;
  right: 18px; top: 18px;
  width: 70px; height: 70px;
  background-image: var(--ornament-url);
  background-size: contain;
  background-repeat: no-repeat;
  opacity: .8;
  pointer-events: none;
}
.skin-c .xlr-final {
  color: var(--accent);
  font-family: var(--font-title);
  font-style: normal;
  font-weight: 700;
}
.skin-c .seal {
  background: var(--accent);
  color: var(--card-bg);
  border-radius: 50%;
  font-family: var(--font-title);
}

/* 移动端响应 */
@media (max-width: 640px) {
  #capture-root { padding: 14px; }
  .card { padding: 22px 20px; }
  .main-hero { flex-direction: column; gap: 16px; }
  .grid-4 { grid-template-columns: 1fr; }
  .xlr-row { grid-template-columns: 1fr; }
  .brand-zh { font-size: 28px; }
  .main-name { font-size: 32px; }
  .xlr-final { font-size: 42px; letter-spacing: 8px; }
}
"""
