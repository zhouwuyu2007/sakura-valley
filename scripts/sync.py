#!/usr/bin/env python3
"""从豆包 doubao.link 抓取最新版页面，清掉平台注入的角标/统计/编辑器标注，写成可独立部署的 index.html。"""

import re
import sys
import urllib.request
from pathlib import Path

SOURCE = (
    "https://4kx5tsk4zqjf5.doubao.link/app/app_17jbev6zpks/"
    "?use_xbridge3=true&loader_name=forest&need_sec_link=1&sec_link_scene=im&theme=dark"
)
ROOT = Path(__file__).resolve().parent.parent
THREE_TAG = re.compile(
    r'<script src="https://[^"]*jsdelivr\.net[^"]*three[^"]*"></script>'
)


def fetch() -> str:
    req = urllib.request.Request(SOURCE, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "ignore")


def strip_script_blocks(html: str, needles) -> str:
    def repl(match):
        block = match.group(0)
        return "" if any(n in block for n in needles) else block

    return re.sub(r"<script\b[^>]*>.*?</script>", repl, html, flags=re.S)


def clean(html: str) -> str:
    # 平台统计脚本 / 运行时脚本（角标、评论、编辑态）
    html = strip_script_blocks(
        html,
        (
            "Slardar",
            "collectEvent",
            "LogAnalyticsObject",
            "window.appId=",
            "MiaodaComments",
            "data-custom-element",
            "watermark",
        ),
    )
    html = re.sub(r'<base href="[^"]*">', "", html)
    html = re.sub(
        r'<script src="https://lf3-short\.ibytedapm\.com[^"]*"[^>]*></script>', "", html
    )
    html = re.sub(r'<iframe id="miaoda-html-comment"[^>]*></iframe>', "", html)
    html = re.sub(r'<script type="application/json" id="__srcmap">.*?</script>', "", html, flags=re.S)
    html = re.sub(r'<meta property="og:[^"]*"[^>]*>', "", html)
    html = re.sub(r'<link rel="icon" href="https://lf3-static\.bytednsdoc\.com[^"]*">', "", html)
    html = re.sub(r'<link rel="preconnect" href="https://miaoda\.feishu\.cn"[^>]*>', "", html)
    # 编辑器标注，对运行没有意义，顺手清掉让文件小一点
    html = re.sub(r'\s+data-inspector-id="[^"]*"', "", html)
    html = re.sub(r'\s+data-src-ver="[^"]*"', "", html)
    return html


def inline_three(html: str) -> str:
    js = (ROOT / "assets" / "three.min.js").read_text(encoding="utf-8")
    return THREE_TAG.sub(lambda _: "<script>\n" + js + "\n</script>", html, count=1)


def main() -> int:
    html = clean(fetch())
    if "樱花山谷庭园" not in html or len(html) < 200_000:
        print("抓回来的页面不像正常页面，放弃本次同步", file=sys.stderr)
        return 1
    if "watermark" in html or "MiaodaComments" in html:
        print("平台注入脚本没清干净，放弃本次同步", file=sys.stderr)
        return 1
    html = inline_three(html)
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html 已写入，{len(html)} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
