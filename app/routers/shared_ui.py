"""Shared design system, sidebar, and page wrapper."""
from ..services.model_settings import get_model_key

_ICONS = {
    "calls":    '<path d="M3 5.5C3 4.7 3.7 4 4.5 4h2.6c.6 0 1.1.4 1.3 1l1 3c.1.5 0 1-.4 1.3L7.6 11.4a12 12 0 005 5l1.1-1.4c.3-.4.8-.5 1.3-.4l3 1c.6.2 1 .7 1 1.3v2.6c0 .8-.7 1.5-1.5 1.5A14.5 14.5 0 013 5.5z"/>',
    "upload":   '<path d="M12 16V4"/><path d="M8 8l4-4 4 4"/><path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>',
    "ask":      '<path d="M21 11.5a8.4 8.4 0 01-9 8.4L4 21l1.1-3.5A8.5 8.5 0 1121 11.5z"/><circle cx="8.5" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="11.5" r="1" fill="currentColor" stroke="none"/><circle cx="15.5" cy="11.5" r="1" fill="currentColor" stroke="none"/>',
    "spark":    '<path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z"/>',
    "search":   '<circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/>',
    "arrow":    '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
    "send":     '<path d="M5 12l15-7-7 15-2-6-6-2z"/>',
    "close":    '<path d="M6 6l12 12M18 6L6 18"/>',
}

def _icon(name: str, size: int = 16, stroke: float = 1.75, style: str = "") -> str:
    d = _ICONS.get(name, "")
    st = f' style="{style}"' if style else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round"{st}>{d}</svg>')


_CSS = """
:root {
  --bg:#ffffff; --bg-subtle:#fafafa; --bg-sidebar:#f7f7f8;
  --bg-hover:#f4f4f5; --bg-active:#ededf0; --bg-tint:#f3f3fc;
  --text:#18181b; --text-2:#5c5c66; --text-3:#8e8e98;
  --border:#ececee; --border-2:#e2e2e5; --border-3:#d4d4d8;
  --acc:#5b5bd6; --acc-hover:#5151c9; --acc-tint:#eeeefb; --acc-text:#4a45c4;
  --green:#1a7f4b; --green-bg:#e9f6ee;
  --red:#c0392b;   --red-bg:#fbecea;
  --amber:#a36a00; --amber-bg:#fbf2e2;
  --blue:#2563c9;  --blue-bg:#e9f0fc;
  --gray:#5c5c66;  --gray-bg:#f0f0f1;
  --radius:8px; --radius-sm:6px; --radius-lg:12px;
  --shadow-sm:0 1px 2px rgba(24,24,27,.05);
  --shadow:0 4px 14px -4px rgba(24,24,27,.12),0 1px 3px rgba(24,24,27,.06);
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,monospace;
  --sans:ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
}
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font-family:var(--sans);color:var(--text);background:var(--bg);font-size:14px;
     line-height:1.5;-webkit-font-smoothing:antialiased}
#root{height:100vh}
button{font-family:inherit;cursor:pointer}
input,textarea,select{font-family:inherit}
*::-webkit-scrollbar{width:10px;height:10px}
*::-webkit-scrollbar-thumb{background:#d9d9dd;border-radius:6px;border:3px solid transparent;background-clip:content-box}
*::-webkit-scrollbar-thumb:hover{background:#c2c2c8;background-clip:content-box}
a{text-decoration:none;color:inherit}

/* ── App shell ── */
.app{display:grid;grid-template-columns:220px 1fr;height:100vh;overflow:hidden}

/* ── Sidebar ── */
.sidebar{background:var(--bg-sidebar);border-right:1px solid var(--border);
         display:flex;flex-direction:column;padding:14px 10px;gap:2px;overflow-y:auto}
.brand{display:flex;align-items:center;gap:9px;padding:6px 8px 14px}
.brand-mark{width:26px;height:26px;border-radius:7px;background:var(--acc);
            display:grid;place-items:center;flex-shrink:0;box-shadow:var(--shadow-sm)}
.brand-mark svg{color:#fff}
.brand-name{font-weight:600;font-size:15px;letter-spacing:-.01em}
.brand-sub{font-size:11px;color:var(--text-3);margin-top:-2px;letter-spacing:.02em}
.nav-label{font-size:11px;font-weight:600;color:var(--text-3);text-transform:uppercase;
           letter-spacing:.05em;padding:10px 8px 4px}
.nav-item{display:flex;align-items:center;gap:9px;padding:7px 8px;border-radius:var(--radius-sm);
          color:var(--text-2);font-size:13.5px;font-weight:500;border:none;background:transparent;
          width:100%;text-align:left;cursor:pointer;transition:background .12s,color .12s;
          text-decoration:none}
.nav-item:hover{background:var(--bg-hover);color:var(--text)}
.nav-item.active{background:var(--bg-active);color:var(--text);font-weight:600}
.nav-item svg{color:var(--text-3);flex-shrink:0}
.nav-item.active svg{color:var(--acc)}
.nav-count{margin-left:auto;font-size:11.5px;color:var(--text-3);font-family:var(--mono)}

/* ── Main pane ── */
.main{display:flex;flex-direction:column;min-width:0;overflow:hidden}
.topbar{height:52px;flex-shrink:0;border-bottom:1px solid var(--border);
        display:flex;align-items:center;gap:10px;padding:0 22px}
.topbar h1{font-size:15px;font-weight:600;margin:0;letter-spacing:-.01em}
.topbar .crumb{color:var(--text-3);font-weight:500;font-size:15px}
.topbar .crumb-sep{color:var(--border-3);margin:0 2px}
.topbar-space{flex:1}
.content{flex:1;overflow-y:auto;min-height:0}
.content.full{overflow:hidden;display:flex;flex-direction:column}
.content-pad{padding:24px 26px 60px;max-width:1140px}

/* ── Buttons ── */
.btn{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:var(--radius-sm);
     font-size:13px;font-weight:550;border:1px solid var(--border-2);background:var(--bg);
     color:var(--text);cursor:pointer;transition:background .12s,border-color .12s;
     box-shadow:var(--shadow-sm);text-decoration:none}
.btn:hover{background:var(--bg-subtle);border-color:var(--border-3)}
.btn-primary{background:var(--acc);color:#fff;border-color:var(--acc)}
.btn-primary:hover{background:var(--acc-hover);border-color:var(--acc-hover)}
.btn-ghost{border-color:transparent;box-shadow:none;background:transparent;color:var(--text-2)}
.btn-ghost:hover{background:var(--bg-hover);color:var(--text)}
.btn-sm{padding:5px 9px;font-size:12.5px}
.btn-danger{background:#fee2e2;color:#991b1b;border-color:#fca5a5}
.btn-danger:hover{background:#fecaca}

/* ── Pills ── */
.pill{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:100px;
      font-size:12px;font-weight:550;line-height:1.5;white-space:nowrap}
.tone-green{color:var(--green);background:var(--green-bg)}
.tone-red{color:var(--red);background:var(--red-bg)}
.tone-amber{color:var(--amber);background:var(--amber-bg)}
.tone-blue{color:var(--blue);background:var(--blue-bg)}
.tone-gray{color:var(--gray);background:var(--gray-bg)}

/* ── Stat cards ── */
.stat-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:22px}
.stat-card{border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;background:var(--bg)}
.stat-card .sc-label{font-size:12px;color:var(--text-2);font-weight:500;display:flex;align-items:center;gap:6px}
.stat-card .sc-value{font-size:26px;font-weight:650;letter-spacing:-.02em;margin-top:6px;font-variant-numeric:tabular-nums}
.stat-card .sc-sub{font-size:12px;color:var(--text-3);margin-top:2px}

/* ── Table ── */
.table-wrap{border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden;background:var(--bg)}
.toolbar{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid var(--border);background:var(--bg-subtle);flex-wrap:wrap}
.search-box{display:flex;align-items:center;gap:7px;background:var(--bg);border:1px solid var(--border-2);
            border-radius:var(--radius-sm);padding:5px 10px;min-width:200px;color:var(--text-3)}
.search-box input{border:none;outline:none;background:transparent;color:var(--text);font-size:13px;width:100%}
.filter-select{display:inline-flex;align-items:center;padding:5px 8px;border-radius:var(--radius-sm);
               font-size:12.5px;font-weight:500;border:1px solid var(--border-2);background:var(--bg);
               color:var(--text-2);cursor:pointer;position:relative}
.filter-select select{border:none;background:transparent;font:inherit;color:inherit;padding:0 18px 0 0;
                      appearance:none;outline:none;cursor:pointer}
.count-label{font-size:12.5px;color:var(--text-3);font-family:var(--mono);margin-left:auto}
table.calls{width:100%;border-collapse:collapse;font-size:13px}
table.calls thead th{text-align:left;font-size:11.5px;font-weight:600;color:var(--text-3);
                     text-transform:uppercase;letter-spacing:.04em;padding:9px 14px;
                     border-bottom:1px solid var(--border);background:var(--bg);
                     position:sticky;top:0;z-index:1;white-space:nowrap}
table.calls tbody td{padding:11px 14px;border-bottom:1px solid var(--border);vertical-align:middle}
table.calls tbody tr{cursor:pointer;transition:background .1s}
table.calls tbody tr:hover{background:var(--bg-subtle)}
table.calls tbody tr:last-child td{border-bottom:none}
.mono{font-family:var(--mono);font-size:12.5px;font-variant-numeric:tabular-nums}
.cell-muted{color:var(--text-2)}

/* ── Call detail two-column ── */
.detail-grid{display:grid;grid-template-columns:1fr 360px;height:100%;min-height:0;overflow:hidden}
.detail-main{overflow-y:auto;padding:24px 28px 60px;min-width:0}
.detail-sidebar{border-left:1px solid var(--border);display:flex;flex-direction:column;background:var(--bg-subtle);min-height:0}
.detail-title{font-size:20px;font-weight:650;letter-spacing:-.02em;display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:16px}
.meta-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--border);
           border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;margin-bottom:20px}
.meta-cell{background:var(--bg);padding:11px 14px}
.meta-cell .k{font-size:11px;color:var(--text-3);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.meta-cell .v{font-size:13.5px;margin-top:3px;font-weight:500}
.section-title{font-size:11.5px;font-weight:600;color:var(--text-3);text-transform:uppercase;letter-spacing:.05em;
               margin:22px 0 10px;display:flex;align-items:center;gap:7px}
.ai-summary{border:1px solid #e6e6f6;background:linear-gradient(180deg,#fbfbff,#f7f7fd);
            border-radius:var(--radius);padding:14px 16px;font-size:13.5px;line-height:1.65}
.ai-head{display:flex;align-items:center;gap:7px;font-size:11.5px;font-weight:600;color:var(--acc-text);
         text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.transcript-wrap{display:flex;flex-direction:column;gap:12px}
.utt{display:grid;grid-template-columns:58px 1fr;gap:10px}
.utt .who{font-size:11.5px;font-weight:600;text-align:right;padding-top:2px}
.utt .who.agent{color:var(--acc-text)}
.utt .who.caller{color:var(--text-2)}
.utt .utime{font-family:var(--mono);font-size:10px;color:var(--text-3)}
.utt .txt{font-size:13px;line-height:1.6;color:var(--text)}

/* ── Chat panel ── */
.chat-panel{display:flex;flex-direction:column;height:100%;min-height:0}
.chat-head{padding:13px 16px;border-bottom:1px solid var(--border);flex-shrink:0;background:var(--bg);
           display:flex;align-items:center;gap:9px}
.chat-head-title{font-size:13.5px;font-weight:600}
.chat-head-sub{font-size:11.5px;color:var(--text-3)}
.chat-scroll{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:14px;min-height:0}
.chat-foot{padding:10px 12px 12px;border-top:1px solid var(--border);flex-shrink:0;background:var(--bg)}
.msg-ai{display:flex;gap:9px;align-items:flex-start}
.msg-user{display:flex;justify-content:flex-end}
.msg-av{width:24px;height:24px;border-radius:6px;display:grid;place-items:center;
        flex-shrink:0;background:var(--acc);color:#fff;font-size:11px;font-weight:600}
.bubble-ai{font-size:13.5px;line-height:1.62;color:var(--text);white-space:pre-wrap}
.bubble-user{background:var(--acc);color:#fff;padding:8px 12px;border-radius:12px 12px 3px 12px;
             font-size:13.5px;line-height:1.5;max-width:85%;white-space:pre-wrap}
.suggest-list{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.suggest-btn{text-align:left;width:100%;border:1px solid var(--border-2);background:var(--bg);
             color:var(--text);padding:8px 11px;border-radius:var(--radius-sm);font-size:13px;
             font-weight:500;cursor:pointer;display:flex;align-items:center;gap:8px;
             transition:background .12s,border-color .12s}
.suggest-btn:hover{background:var(--bg-tint,#f3f3fc);border-color:#d8d8f6}
.suggest-btn svg{color:var(--acc);flex-shrink:0}
.composer{display:flex;align-items:flex-end;gap:7px;border:1px solid var(--border-2);
          border-radius:var(--radius);padding:7px 8px 7px 12px;background:var(--bg);
          transition:border-color .12s,box-shadow .12s}
.composer:focus-within{border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-tint)}
.composer textarea{flex:1;border:none;outline:none;resize:none;font-size:13.5px;line-height:1.5;
                   max-height:100px;background:transparent;color:var(--text);padding:3px 0}
.send-btn{width:30px;height:30px;border-radius:var(--radius-sm);background:var(--acc);color:#fff;
          border:none;display:grid;place-items:center;flex-shrink:0;cursor:pointer;
          transition:background .12s,opacity .12s}
.send-btn:disabled{opacity:.4;cursor:not-allowed}
.send-btn:not(:disabled):hover{background:var(--acc-hover)}
.typing{display:flex;gap:4px;padding:4px 0}
.typing span{width:6px;height:6px;border-radius:50%;background:var(--text-3);animation:blink 1.2s infinite}
.typing span:nth-child(2){animation-delay:.2s}
.typing span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,60%,100%{opacity:.25;transform:translateY(0)}30%{opacity:1;transform:translateY(-2px)}}

/* ── Upload ── */
.upload-wrap{max-width:600px;margin:0 auto}
.dropzone{border:1.5px dashed var(--border-3);border-radius:var(--radius-lg);padding:44px 24px;
          text-align:center;background:var(--bg-subtle)}
.dz-icon{width:44px;height:44px;border-radius:12px;background:var(--bg);border:1px solid var(--border-2);
         display:grid;place-items:center;margin:0 auto 14px;color:var(--acc);box-shadow:var(--shadow-sm)}
.dz-title{font-size:15px;font-weight:600}
.dz-sub{font-size:13px;color:var(--text-3);margin-top:4px}

/* ── Tabs ── */
.tabs{display:flex;border-bottom:2px solid var(--border);margin-bottom:20px}
.tab-btn{padding:8px 14px;border:none;background:none;font:inherit;font-size:13.5px;font-weight:500;
         color:var(--text-2);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px}
.tab-btn.active{color:var(--acc);border-bottom-color:var(--acc);font-weight:600}
.tab-pane{display:none}.tab-pane.active{display:block}
.field-label{display:block;font-size:13px;font-weight:500;color:var(--text-2);margin-top:14px}
.field-label input,.field-label textarea,.field-label select{
  display:block;width:100%;margin-top:5px;padding:7px 10px;border:1px solid var(--border-2);
  border-radius:var(--radius-sm);font-size:13.5px;outline:none;background:var(--bg);color:var(--text)}
.field-label input:focus,.field-label textarea:focus{border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-tint)}

/* ── Analyze full-height chat ── */
.ask-wrap{width:100%;max-width:760px;height:100%;display:flex;flex-direction:column;
          border-left:1px solid var(--border);border-right:1px solid var(--border);
          margin:0 auto}
.range-bar{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--border);
           flex-shrink:0;background:var(--bg);flex-wrap:wrap}
.range-bar select{border:1px solid var(--border-2);border-radius:var(--radius-sm);padding:5px 8px;
                  font:inherit;font-size:13px;background:var(--bg);color:var(--text);outline:none}
.range-bar input[type=date]{border:1px solid var(--border-2);border-radius:var(--radius-sm);
                             padding:5px 8px;font:inherit;font-size:13px;background:var(--bg);
                             color:var(--text);outline:none}
.call-count-badge{font-size:12px;color:var(--text-3);font-family:var(--mono);margin-left:auto}

/* ── Model picker (sidebar footer) ── */
.model-picker{margin-top:auto;padding:12px 8px 4px;border-top:1px solid var(--border)}
.model-picker .mp-label{font-size:10.5px;font-weight:600;color:var(--text-3);
                         text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
.model-picker select{width:100%;padding:6px 8px;border-radius:var(--radius-sm);font:inherit;
                     font-size:12px;border:1px solid var(--border-2);background:var(--bg);
                     color:var(--text);outline:none;cursor:pointer}
.model-picker select:focus{border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-tint)}
"""


_TAB_JS = """<script>
document.querySelectorAll('.tab-btn').forEach(t => t.addEventListener('click', () => {
  const sec = t.closest('.tab-section');
  sec.querySelectorAll('.tab-btn,.tab-pane').forEach(el => el.classList.remove('active'));
  t.classList.add('active');
  sec.querySelector('#' + t.dataset.target).classList.add('active');
}));
</script>"""


def _icon_svg(name: str, size: int = 16, stroke: float = 1.75, cls: str = "") -> str:
    d = _ICONS.get(name, "")
    c = f' class="{cls}"' if cls else ""
    return (f'<svg{c} width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-linejoin="round">{d}</svg>')


def _sidebar(active: str, call_count: int | None = None) -> str:
    items = [
        ("calls",   "/",        "calls",  "Calls",  str(call_count) if call_count is not None else ""),
        ("upload",  "/upload",  "upload", "Upload", ""),
        ("analyze", "/analyze", "ask",    "Ask",    ""),
    ]
    rows = ""
    for key, href, icon, label, count in items:
        cls = "nav-item active" if active == key else "nav-item"
        cnt = f'<span class="nav-count">{count}</span>' if count else ""
        rows += f'<a href="{href}" class="{cls}">{_icon_svg(icon, 16)}{label}{cnt}</a>\n'

    mk = get_model_key()
    def _opt(key: str, label: str) -> str:
        sel = ' selected' if mk == key else ''
        return f'<option value="{key}"{sel}>{label}</option>'

    model_picker = f"""<div class="model-picker">
  <div class="mp-label">AI Model</div>
  <select id="model-select" onchange="switchModel(this.value)">
    {_opt("haiku",  "Haiku 4.5 — fastest")}
    {_opt("sonnet", "Sonnet 4.6 — balanced")}
    {_opt("opus",   "Opus 4.8 — smartest")}
  </select>
</div>"""

    return f"""<aside class="sidebar">
  <div class="brand">
    <div class="brand-mark">{_icon_svg("spark", 14, 2.2)}</div>
    <div><div class="brand-name">Cue</div><div class="brand-sub">Call intelligence</div></div>
  </div>
  <div class="nav-label">Workspace</div>
  {rows}
  {model_picker}
</aside>"""


def page(
    title: str,
    body: str,
    active_nav: str = "calls",
    extra_js: str = "",
    call_count: int | None = None,
    full_bleed: bool = False,
    topbar_extra: str = "",
    breadcrumb: str = "",
) -> str:
    content_cls = "content full" if full_bleed else "content"
    tb_title = breadcrumb if breadcrumb else title
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Cue</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{_CSS}</style></head>
<body><div id="root"><div class="app">
{_sidebar(active_nav, call_count)}
<main class="main">
  <div class="topbar">
    <h1>{tb_title}</h1>
    <div class="topbar-space"></div>
    {topbar_extra}
  </div>
  <div class="{content_cls}">{body}</div>
</main>
</div></div>
{_TAB_JS}
<script>
function switchModel(key) {{
  fetch('/settings/model', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{key}})
  }});
}}
</script>
{extra_js}</body></html>"""


def score_pill(score: float | None) -> str:
    if score is None:
        return '<span class="pill tone-gray">pending</span>'
    if score >= 70:
        return f'<span class="pill tone-green">{score:.0f}</span>'
    if score >= 50:
        return f'<span class="pill tone-amber">{score:.0f}</span>'
    return f'<span class="pill tone-red">{score:.0f}</span>'


# Keep old name as alias so other files don't break
def badge_score(score: float | None) -> str:
    return score_pill(score)
