"""Shared HTML chrome, CSS, and badge helpers used by all page routers."""

_CSS = """
*,*::before,*::after{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     margin:0;background:#f8fafc;color:#1e293b;font-size:15px}
nav{background:#1e40af;padding:.7rem 1.5rem;display:flex;gap:1.5rem;align-items:center}
nav a{color:#fff;text-decoration:none;font-size:.9rem;opacity:.85}
nav a:hover{opacity:1;text-decoration:underline}
.brand{font-weight:700;color:#fff;font-size:1rem;opacity:1!important;margin-right:.5rem}
.container{max-width:1100px;margin:0 auto;padding:1.5rem 1rem}
h1{font-size:1.4rem;margin:0 0 1.2rem}
h2{font-size:1.1rem;margin:1.5rem 0 .6rem;color:#334155}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;
      overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}
th{background:#f1f5f9;padding:.55rem .9rem;text-align:left;font-size:.75rem;
   text-transform:uppercase;letter-spacing:.05em;color:#64748b;font-weight:600}
td{padding:.6rem .9rem;border-top:1px solid #f1f5f9;font-size:.875rem;vertical-align:middle}
tr:hover td{background:#fafbfd}
.badge{display:inline-block;padding:.18rem .55rem;border-radius:9999px;
       font-size:.72rem;font-weight:600;white-space:nowrap}
.green{background:#dcfce7;color:#166534}
.red{background:#fee2e2;color:#991b1b}
.yellow{background:#fef9c3;color:#854d0e}
.gray{background:#f1f5f9;color:#64748b}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
           gap:1rem;margin-bottom:1.5rem}
.stat{background:#fff;border-radius:8px;padding:.9rem 1rem;
      box-shadow:0 1px 3px rgba(0,0,0,.08)}
.stat-label{font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
.stat-value{font-size:1.6rem;font-weight:700;margin-top:.2rem;color:#1e293b}
.btn{display:inline-block;padding:.45rem 1rem;background:#2563eb;color:#fff;
     border:none;border-radius:6px;cursor:pointer;font-size:.875rem;
     text-decoration:none;line-height:1.4}
.btn:hover{background:#1d4ed8}
.btn-ghost{background:transparent;color:#2563eb;border:1px solid #2563eb}
.btn-ghost:hover{background:#eff6ff}
.card{background:#fff;border-radius:8px;padding:1.2rem 1.4rem;
      box-shadow:0 1px 3px rgba(0,0,0,.08);margin-bottom:1rem}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.75rem}
.meta-item .label{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8}
.meta-item .value{font-size:.9rem;font-weight:500;margin-top:.15rem;color:#1e293b}
/* chat */
#chat-wrap{display:flex;flex-direction:column;height:480px;background:#fff;
           border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);overflow:hidden}
#messages{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.6rem}
.msg{padding:.6rem .85rem;border-radius:8px;max-width:82%;line-height:1.55;
     font-size:.875rem;white-space:pre-wrap}
.msg.user{background:#2563eb;color:#fff;align-self:flex-end;border-radius:8px 8px 2px 8px}
.msg.assistant{background:#f1f5f9;color:#1e293b;align-self:flex-start;border-radius:8px 8px 8px 2px}
#chat-form{display:flex;gap:.5rem;padding:.7rem;border-top:1px solid #f1f5f9}
#chat-input{flex:1;padding:.5rem .75rem;border:1px solid #e2e8f0;border-radius:6px;
            font-size:.875rem;outline:none}
#chat-input:focus{border-color:#2563eb}
#send-btn{padding:.5rem 1rem;background:#2563eb;color:#fff;border:none;
          border-radius:6px;cursor:pointer;font-size:.875rem;white-space:nowrap}
#send-btn:disabled{opacity:.45;cursor:not-allowed}
/* tabs */
.tabs{display:flex;gap:0;border-bottom:2px solid #e2e8f0;margin-bottom:1.5rem}
.tab{padding:.55rem 1.1rem;border:none;background:none;color:#64748b;font-size:.875rem;
     cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px}
.tab.active{color:#2563eb;border-bottom-color:#2563eb;font-weight:600}
.tab-pane{display:none}.tab-pane.active{display:block}
label.field{display:block;margin-top:1rem;font-size:.85rem;font-weight:500;color:#475569}
label.field input,label.field select{
  width:100%;padding:.45rem .75rem;margin-top:.3rem;
  border:1px solid #e2e8f0;border-radius:6px;font-size:.875rem}
"""

_NAV = """<nav>
<span class="brand">Call Analyzer</span>
<a href="/">Calls</a>
<a href="/upload">Upload</a>
<a href="/analyze">Analyze</a>
</nav>"""

_TAB_JS = """<script>
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{
  const wrap=t.closest('.tab-section');
  wrap.querySelectorAll('.tab,.tab-pane').forEach(el=>el.classList.remove('active'));
  t.classList.add('active');
  wrap.querySelector('#'+t.dataset.target).classList.add('active');
}));
</script>"""


def page(title: str, body: str, extra_js: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Call Analyzer</title>
<style>{_CSS}</style></head>
<body>{_NAV}<div class="container">{body}</div>
{_TAB_JS}{extra_js}</body></html>"""


def badge_score(score: float | None) -> str:
    if score is None:
        return '<span class="badge gray">pending</span>'
    colour = "green" if score >= 70 else ("yellow" if score >= 50 else "red")
    return f'<span class="badge {colour}">{score:.0f}/100</span>'


def badge_billable(billable: bool | None) -> str:
    if billable is None:
        return ""
    return (
        '<span class="badge green">billable</span>'
        if billable
        else '<span class="badge red">not billable</span>'
    )
