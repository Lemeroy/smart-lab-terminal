"""Build an offline, printable reading copy from the versioned Markdown files."""

from base64 import b64encode
from html import escape
from pathlib import Path
import re

from export_design_docx import diagram, QA


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
FILES = [
    "智能实验室终端设计开发文档.md",
    "目标检测训练与部署规范.md",
    "接口与数据契约.md",
    "开发实施与验收计划.md",
    "设计决策记录.md",
]
PARTS = {name: f"part-{idx + 1}" for idx, name in enumerate(FILES)}


def inline(value):
    tokens = {}

    def protect(html):
        key = f"DOCUMENTTOKEN{len(tokens)}END"
        tokens[key] = html
        return key

    value = re.sub(r"`([^`]+)`", lambda m: protect(f"<code>{escape(m[1])}</code>"), value)

    def link(match):
        label, href = match[1], match[2]
        name = Path(href).name
        if name in PARTS:
            href = "#" + PARTS[name]
        elif not href.startswith(("https://", "http://", "#")):
            return label
        return protect(f'<a href="{escape(href, quote=True)}">{escape(label)}</a>')

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    for key, html in tokens.items():
        value = value.replace(key, html)
    return value


def render_md(text, part):
    lines = text.splitlines()
    out = []
    idx = 0
    toc = []
    heading_no = 0
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            idx += 1
            continue
        if line.startswith("```"):
            lang = line[3:].strip()
            block = []
            idx += 1
            while idx < len(lines) and not lines[idx].startswith("```"):
                block.append(lines[idx])
                idx += 1
            if lang == "mermaid" and any("flowchart" in v for v in block):
                kind = "workflow" if any("登录" in v for v in block) else "architecture"
                encoded = b64encode(diagram(kind).read_bytes()).decode("ascii")
                alt = "业务流程" if kind == "workflow" else "系统架构"
                out.append(f'<figure><img src="data:image/png;base64,{encoded}" alt="{alt}"><figcaption>{alt}</figcaption></figure>')
            elif lang == "mermaid":
                rows = []
                for transition in block:
                    m = re.match(r"\s*(\S+)\s+-->\s+(\S+)(?::\s*(.*))?", transition)
                    if m:
                        rows.append(f"<tr><td><code>{escape(m[1])}</code></td><td>{escape(m[3] or '终结')}</td><td><code>{escape(m[2])}</code></td></tr>")
                out.append('<div class="table"><table><thead><tr><th>起点</th><th>条件或动作</th><th>终点</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
            else:
                out.append(f'<pre aria-label="{escape(lang or "示例")}"><code>{escape(chr(10).join(block))}</code></pre>')
            idx += 1
            continue
        if line.startswith("|"):
            rows = []
            while idx < len(lines) and lines[idx].startswith("|"):
                cells = [v.strip() for v in lines[idx].strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    rows.append(cells)
                idx += 1
            html_rows = []
            for row_no, cells in enumerate(rows):
                tag = "th" if row_no == 0 else "td"
                html_rows.append("<tr>" + "".join(f"<{tag}>{inline(cell)}</{tag}>" for cell in cells) + "</tr>")
            out.append('<div class="table"><table><thead>' + html_rows[0] + "</thead><tbody>" + "".join(html_rows[1:]) + "</tbody></table></div>")
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = min(len(heading[1]) + 1, 5)
            heading_no += 1
            hid = f"{part}-heading-{heading_no}"
            if len(heading[1]) == 2:
                toc.append((hid, heading[2]))
            out.append(f'<h{level} id="{hid}">{inline(heading[2])}</h{level}>')
            idx += 1
            continue
        bullet = re.match(r"^(?:[-*]\s+|\d+\.\s+)(.+)$", line)
        if bullet:
            ordered = bool(re.match(r"^\d+\.", line))
            tag = "ol" if ordered else "ul"
            items = []
            pattern = r"^\d+\.\s+(.+)$" if ordered else r"^[-*]\s+(.+)$"
            while idx < len(lines):
                m = re.match(pattern, lines[idx])
                if not m:
                    break
                value = m[1].replace("[ ] ", "☐ ")
                items.append("<li>" + inline(value) + "</li>")
                idx += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        paragraph = [line]
        idx += 1
        while idx < len(lines) and lines[idx].strip() and not re.match(r"^(#|\||```|[-*]\s|\d+\.\s)", lines[idx]):
            paragraph.append(lines[idx])
            idx += 1
        out.append("<p>" + "<br>".join(inline(v) for v in paragraph) + "</p>")
    return "\n".join(out), toc


def main():
    QA.mkdir(exist_ok=True)
    content = []
    navigation = []
    for name in FILES:
        body, toc = render_md((DOCS / name).read_text(encoding="utf-8"), PARTS[name])
        label = name.removesuffix(".md")
        content.append(f'<section id="{PARTS[name]}" class="part">{body}</section>')
        navigation.append(f'<li><a href="#{PARTS[name]}">{escape(label)}</a></li>')
    css = """
    :root{color-scheme:light;--ink:#1d252b;--muted:#52606b;--rule:#d4dbe0}
    *{box-sizing:border-box}body{margin:0;background:#f4f6f7;color:var(--ink);font:16px/1.85 'Microsoft YaHei','PingFang SC',sans-serif}
    header{max-width:1160px;margin:0 auto;padding:44px 48px 25px}header h1{font-size:30px;line-height:1.45;margin:0 0 12px;color:#000}header p{margin:0;color:var(--muted)}
    .layout{max-width:1160px;margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:24px;padding:0 24px 64px}
    nav{align-self:start;position:sticky;top:20px;padding:20px;background:#fff;border:1px solid var(--rule);border-radius:6px}nav strong{font-size:15px}nav ul{padding-left:20px}nav li{margin:12px 0;font-size:14px}
    main{min-width:0;background:white;padding:30px 36px;border:1px solid var(--rule);border-radius:6px}a{color:#185273;text-decoration:underline;text-underline-offset:3px}p{margin:10px 0 16px}
    h2,h3,h4,h5{color:#000;line-height:1.5;scroll-margin-top:22px}h2{font-size:24px;margin:14px 0 24px}h3{font-size:21px;margin:32px 0 15px}h4{font-size:18px;margin:23px 0 12px}h5{font-size:16px}
    .part+.part{margin-top:55px;padding-top:30px;border-top:1px solid var(--rule)}
    .table{overflow:auto;margin:20px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7}th,td{border:1px solid #cdd4da;padding:9px 11px;text-align:left;vertical-align:top}th{background:#eef1f3;font-weight:600}
    code{font:0.9em/1.65 Consolas,'Microsoft YaHei',monospace;overflow-wrap:anywhere;background:#f1f3f5;border-radius:3px;padding:1px 4px}
    pre{overflow:auto;padding:16px 18px;margin:20px 0;background:#f5f6f7;border:1px solid #d8dde1;font:13px/1.7 Consolas,'Microsoft YaHei',monospace}pre code{padding:0;background:transparent;overflow-wrap:normal}
    figure{margin:24px 0}img{display:block;width:100%;height:auto}figcaption{font-size:13px;text-align:center;color:var(--muted)}li{margin:7px 0}
    @media(max-width:850px){.layout{display:block;padding:0 12px 30px}nav{position:static;margin-bottom:16px}main{padding:22px}header{padding:25px 22px}nav ul{margin-bottom:0}}
    @media print{@page{size:A4;margin:18mm}body{background:white;font-size:10pt;line-height:1.65}header{padding:0 0 12mm}header h1{font-size:23pt}.layout{display:block;padding:0;max-width:none}nav{position:static;border:0;padding:0 0 7mm}main{border:0;padding:0;border-radius:0}.part+.part{break-before:page;border:0;padding:0}h2,h3,h4,h5{break-after:avoid;color:black}h2{font-size:19pt}h3{font-size:15pt}h4{font-size:12pt}.table{overflow:visible}table{font-size:8.5pt}thead{display:table-header-group}tr,figure{break-inside:avoid}pre{white-space:pre-wrap;overflow:visible;word-break:break-all;font-size:8pt}a{color:inherit}p{orphans:3;widows:3}}
    """
    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>智能实验室终端完整设计开发文档</title><style>{css}</style></head>
<body><header><h1>智能实验室终端完整设计开发文档</h1><p>设计基线 0.1.0 · 2026-10-12 · 主设计与训练 接口 实施规范</p><p>本阅读版包含完整配套文档，可离线打开，并通过浏览器打印。性能数字是待验证的验收目标。</p></header>
<div class="layout"><nav aria-label="文档目录"><strong>文档目录</strong><ul>{''.join(navigation)}</ul></nav><main>{''.join(content)}</main></div></body></html>'''
    target = DOCS / "智能实验室终端完整阅读版.html"
    target.write_text(html, encoding="utf-8")
    print(f"Reading copy: {len(FILES)} source documents, {target.stat().st_size} bytes")


if __name__ == "__main__":
    main()
