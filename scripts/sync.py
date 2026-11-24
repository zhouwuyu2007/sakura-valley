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
# 线上包已把 three 外置成同目录 assets/three.min.js，这里同样内联回单文件
REL_THREE = re.compile(r'<script src="(?:\./)?assets/three\.min\.js"></script>')


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
    tag = "<script>\n" + js + "\n</script>"
    if REL_THREE.search(html):
        return REL_THREE.sub(lambda _: tag, html, count=1)
    return THREE_TAG.sub(lambda _: tag, html, count=1)


RAW_AUDIO = re.compile(
    r'https://raw\.githubusercontent\.com/zhouwuyu2007/sakura-valley/main/(assets/[^"\'\s>]+\.mp3)'
)
SHIM_RE = re.compile(r'\n?<script>/\*BGM_RESILIENCE\*/.*?</script>', re.S)

BGM_SHIM = """<script>/*BGM_RESILIENCE*/
(function(){
  if (window.__bgmFix) return; window.__bgmFix = 1;
  var REL = 'assets/', PAGES = 'https://zhouwuyu2007.github.io/sakura-valley/assets/',
      RAW = 'https://raw.githubusercontent.com/zhouwuyu2007/sakura-valley/main/assets/';
  function variants(u){
    var m = /assets\\/([^\\/?#]+[.](?:mp3|m4a|ogg))/.exec(u || '');
    return m ? [REL + m[1], PAGES + m[1], RAW + m[1]] : [];
  }
  function log(s){ try{ console.info('[bgm-fix] ' + s); }catch(e){} }
  function arm(a){
    if (a.__bgmArm) return; a.__bgmArm = 1;
    var ev = ['pointerdown', 'touchstart', 'click', 'keydown'];
    function once(){
      ev.forEach(function(t){ document.removeEventListener(t, once, true); });
      try{ var p = a.play(); if (p && p.catch) p.catch(function(){}); }catch(e){}
    }
    ev.forEach(function(t){ document.addEventListener(t, once, true); });
  }
  function hook(a){
    if (!a || a.__bgmHooked) return a; a.__bgmHooked = 1;
    var q = variants(a.src || a.getAttribute('src') || ''), k = 0, rounds = 0;
    function cycle(why){
      if (!q.length) return;
      if (k + 1 >= q.length){ k = 0; if (++rounds > 3) return; } else k++;
      try{ a.src = q[k]; a.load(); }catch(e){}
      try{ var p = a.play(); if (p && p.catch) p.catch(function(){}); }catch(e){}
      log('换源 ' + why + ' -> ' + q[k]);
    }
    a.addEventListener('error', function(){ cycle('error'); });
    a.addEventListener('stalled', function(){ if (!a.paused) cycle('stalled'); });
    var play0 = a.play, pause0 = a.pause;
    a.play = function(){
      var p = play0.apply(a, arguments);
      if (p && p.catch) p.catch(function(e){
        var n = e && e.name;
        if (n === 'NotAllowedError') arm(a); else cycle('play:' + n);
      });
      return p;
    };
    a.pause = function(){ return pause0.apply(a, arguments); };
    return a;
  }
  var Native = window.Audio;
  if (Native){
    function A(src){ var a = src ? new Native(src) : new Native(); return hook(a); }
    A.prototype = Native.prototype;
    window.Audio = A;
  }
  function scan(){
    var l = document.querySelectorAll('audio');
    for (var i = 0; i < l.length; i++) hook(l[i]);
  }
  scan();
  document.addEventListener('DOMContentLoaded', scan);
  window.addEventListener('load', scan);
})();
</script>"""


def harden_bgm(html: str) -> str:
    """外链 raw 音频改为同源 assets/（页面能开就一定能下），并注入自动换源/重试垫片。"""
    html = SHIM_RE.sub("", html)
    html = RAW_AUDIO.sub(lambda m: m.group(1), html)
    return html.replace("</body>", "\n" + BGM_SHIM + "</body>", 1)


def main() -> int:
    html = clean(fetch())
    if "樱花山谷庭园" not in html or len(html) < 200_000:
        print("抓回来的页面不像正常页面，放弃本次同步", file=sys.stderr)
        return 1
    if "watermark" in html or "MiaodaComments" in html:
        print("平台注入脚本没清干净，放弃本次同步", file=sys.stderr)
        return 1
    html = inline_three(html)
    html = harden_bgm(html)
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html 已写入，{len(html)} 字节")
    # 同步时一并产出：版本自检用的构建号 + .nojekyll（否则 Pages 走 Jekyll 且 version.js 404）
    build = re.search(r"var BUILD = '([0-9a-zA-Z]{4,})'", html)
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "version.js").write_text(
        'window.__SAKURA_BUILD="%s";\n' % (build.group(1) if build else ""), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    print("[ver] build", build.group(1) if build else "?")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
