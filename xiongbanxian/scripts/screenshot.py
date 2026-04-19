#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
熊半仙 · 自动长截图工具（跨平台）
=================================

输入：熊半仙渲染出的 HTML 结果卡（由 render_card.render_html 生成）。
输出：精准裁剪到 #capture-root 元素的长图 PNG。

支持平台
--------
* macOS（Intel / Apple Silicon）
* Windows 10 / 11
* Linux（含 WSL、Docker、服务器）

自动降级
--------
只要以下任一条件不满足，本模块的调用方会**安全跳过**并仅输出 HTML，
不抛异常打断主流程：
  1. 未安装 playwright（`pip install playwright`）
  2. 未安装 Chromium 内核（`playwright install chromium`）
  3. 受沙箱/容器/防病毒软件限制无法启动浏览器

调用方可先用 `can_screenshot()` 做预检，或直接调用 `html_to_png()` 并捕获
`ScreenshotUnavailable` 异常——凡能分辨的环境问题都会归到该异常类型。

CLI 用法
--------
    python screenshot.py input.html output.png
    python screenshot.py --check          # 仅预检当前环境

Python API
----------
    from screenshot import html_to_png, can_screenshot
    ok, reason = can_screenshot()
    if ok:
        html_to_png("card.html", "card.png", width=900, scale=2)

"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Union


class ScreenshotUnavailable(RuntimeError):
    """当前环境无法执行长截图（缺依赖 / 沙箱限制 / Chromium 缺失等）。"""


# ---- JS：展开折叠块 + 隐藏导出栏 ----
_EXPAND_JS = r"""
() => {
  document.querySelectorAll('details').forEach(d => { d.open = true; });
  document.querySelectorAll('.export-bar, #xbx-export-btn').forEach(el => {
    el.style.display = 'none';
  });
  document.body.classList.add('export-mode');
  document.documentElement.style.scrollBehavior = 'auto';
  return true;
}
"""

# ---- Chromium 启动参数：兼容 Linux 容器 / WSL / 无 /dev/shm 环境 ----
_CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--hide-scrollbars",
]


def _load_playwright():
    """延迟导入 playwright，抛 ScreenshotUnavailable 以便调用方安全降级。"""
    try:
        from playwright.sync_api import sync_playwright  # noqa: WPS433
        return sync_playwright
    except ImportError as e:
        raise ScreenshotUnavailable(
            "playwright 未安装。请运行："
            "`pip install playwright`"
            "；随后运行 `playwright install chromium`。"
        ) from e


def can_screenshot() -> Tuple[bool, str]:
    """
    预检当前环境是否支持自动长图。

    Returns
    -------
    (ok, reason) : (True, "ok") 或 (False, 原因描述)
    """
    try:
        sync_playwright = _load_playwright()
    except ScreenshotUnavailable as e:
        return False, str(e)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_CHROMIUM_ARGS)
            browser.close()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        hint = ""
        if "Executable doesn't exist" in msg or "install" in msg.lower():
            hint = "：请运行 `playwright install chromium`"
        elif "running as root" in msg.lower() or "sandbox" in msg.lower():
            hint = "：沙箱/容器环境，可忽略（模块已加 --no-sandbox）"
        return False, f"Chromium 启动失败{hint} — {type(e).__name__}: {msg[:200]}"

    return True, "ok"


def html_to_png(
    html_path: Union[str, Path],
    png_path: Union[str, Path],
    *,
    width: int = 900,
    scale: int = 2,
    selector: str = "#capture-root",
    wait_ms: int = 350,
    timeout_ms: int = 15000,
) -> str:
    """
    将一张熊半仙 HTML 结果卡渲染为精准长截图。

    Parameters
    ----------
    html_path : 本地 HTML 文件路径（Mac/Win/Linux 均可，使用 pathlib 统一处理）
    png_path  : 输出 PNG 路径
    width     : 视口宽度（默认 900px）
    scale     : device scale factor（1 = 标清，2 = Retina）
    selector  : 要截取的元素 CSS 选择器，默认 #capture-root
    wait_ms   : 展开 details 之后等待 layout 的毫秒数
    timeout_ms: 单次操作最长等待毫秒数

    Raises
    ------
    ScreenshotUnavailable : 当前环境无法执行（缺依赖 / 沙箱 / 其他）
    FileNotFoundError     : 输入 HTML 不存在

    Returns
    -------
    输出 PNG 的绝对路径（str）。
    """
    sync_playwright = _load_playwright()

    html_path = Path(html_path).resolve()
    png_path = Path(png_path).resolve()
    if not html_path.exists():
        raise FileNotFoundError(html_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    # pathlib.as_uri() 在 Mac/Linux/Windows 上都会生成合法的 file:// URL
    # Windows: C:\path\file.html  →  file:///C:/path/file.html
    url = html_path.as_uri()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=_CHROMIUM_ARGS)
            try:
                context = browser.new_context(
                    viewport={"width": width, "height": 1200},
                    device_scale_factor=scale,
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # CDN 脚本（modern-screenshot）可能阻塞 networkidle；容忍超时
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                page.evaluate(_EXPAND_JS)
                page.wait_for_timeout(wait_ms)
                locator = page.locator(selector)
                locator.wait_for(state="visible", timeout=5000)
                locator.screenshot(
                    path=str(png_path), type="png", animations="disabled"
                )
            finally:
                browser.close()
    except ScreenshotUnavailable:
        raise
    except Exception as e:  # noqa: BLE001
        raise ScreenshotUnavailable(
            f"长截图失败：{type(e).__name__}: {e}。"
            f"若是首次运行，请先 `playwright install chromium`；"
            f"Linux 服务器/容器如仍失败，可改由用户在浏览器里点 '保存为长图' 按钮。"
        ) from e

    return str(png_path)


# ---------------------------------------------------------------
# CLI
# ---------------------------------------------------------------
def _cli() -> int:
    ap = argparse.ArgumentParser(
        description="熊半仙 · 把 HTML 结果卡渲染为精准长图 PNG（跨平台）"
    )
    ap.add_argument("html", nargs="?", help="输入 HTML 文件路径")
    ap.add_argument("png", nargs="?", help="输出 PNG 文件路径")
    ap.add_argument("--width", type=int, default=900, help="视口宽度（默认 900）")
    ap.add_argument("--scale", type=int, default=2, help="像素倍率（默认 2）")
    ap.add_argument("--selector", default="#capture-root",
                    help="截图目标 CSS 选择器")
    ap.add_argument("--wait", type=int, default=350,
                    help="展开后等待毫秒数（默认 350）")
    ap.add_argument("--check", action="store_true",
                    help="仅预检当前环境是否支持长截图")
    args = ap.parse_args()

    if args.check:
        ok, reason = can_screenshot()
        print(("[ok] " if ok else "[skip] ") + reason)
        return 0 if ok else 1

    if not args.html or not args.png:
        ap.print_help()
        return 2

    try:
        out = html_to_png(
            args.html, args.png,
            width=args.width, scale=args.scale,
            selector=args.selector, wait_ms=args.wait,
        )
    except ScreenshotUnavailable as e:
        print(f"[screenshot] 已跳过：{e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"[screenshot] 输入不存在：{e}", file=sys.stderr)
        return 2
    print(f"[screenshot] 已生成：{out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
