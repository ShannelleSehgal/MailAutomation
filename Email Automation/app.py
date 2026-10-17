"""
Mail Summary - a small Flask website that shows how many emails you
received on each of the previous 3 days, for Gmail, Outlook, Yahoo,
iCloud or any other IMAP mail server.

Run:  python app.py      then open  http://127.0.0.1:5000
"""
import imaplib
import re
from datetime import date, timedelta

from flask import Flask, render_template_string, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# 1. Provider settings. "domains" = the only email endings allowed for that
#    provider. Add more domains (e.g. "hotmail.com") to a list if you want.
# ---------------------------------------------------------------------------
PROVIDERS = {
    "gmail":   {"label": "Gmail",   "domains": ["gmail.com"],   "server": "imap.gmail.com"},
    "outlook": {"label": "Outlook", "domains": ["outlook.com"], "server": "outlook.office365.com"},
    "yahoo":   {"label": "Yahoo",   "domains": ["yahoo.com"],   "server": "imap.mail.yahoo.com"},
    "icloud":  {"label": "iCloud",  "domains": ["icloud.com"],  "server": "imap.mail.me.com"},
    "other":   {"label": "Other (custom IMAP)", "domains": None, "server": None},
}

# How to get the app password, shown on the page under the password box
HELP = {
    "gmail": {"link": "https://myaccount.google.com/apppasswords",
              "steps": "Turn on 2-Step Verification in your Google Account, then open the App passwords page and create a password named Mail Summary. Copy the 16-character code."},
    "outlook": {"link": "https://account.microsoft.com/security",
              "steps": "Open Security, then Advanced security options. Turn on two-step verification, then choose Create a new app password and copy it."},
    "yahoo": {"link": "https://login.yahoo.com/account/security",
              "steps": "Open Account security, turn on two-step verification, then choose Generate app password and copy it."},
    "icloud": {"link": "https://account.apple.com",
              "steps": "Sign in, open Sign-In and Security, choose App-Specific Passwords, then create one and copy it."},
    "other": {"link": "",
              "steps": "Find your IMAP server name in your email provider's help page (search for 'IMAP settings'). Use your normal mailbox password, or an app password if your provider offers one. Ask your IT admin if you are unsure."},
}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def imap_date(d: date) -> str:
    """IMAP wants dates like 16-Oct-2026 (English month names)."""
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def validate(provider_key, email, password, custom_server):
    """Return an error message, or None if the input is fine."""
    if provider_key not in PROVIDERS:
        return "Please choose a mail provider."
    if not EMAIL_RE.match(email):
        return "Enter a valid email address."
    provider = PROVIDERS[provider_key]
    if provider["domains"]:
        domain = email.split("@")[1].lower()
        if domain not in provider["domains"]:
            allowed = " or ".join("@" + d for d in provider["domains"])
            return f"{provider['label']} accounts must use an address ending in {allowed}."
    elif not custom_server:
        return "Enter your IMAP server (for example imap.yourcompany.com)."
    if not password:
        return "Enter your app password."
    return None


def count_last_3_days(server, email, password):
    """Log in over IMAP and count mails received on each of the last 3 days."""
    today = date.today()
    results = []
    mail = imaplib.IMAP4_SSL(server, 993, timeout=30)
    try:
        mail.login(email, password)
        mail.select("INBOX", readonly=True)   # readonly: never changes your mails
        for i in range(1, 4):                 # yesterday, 2 days ago, 3 days ago
            day = today - timedelta(days=i)
            nxt = day + timedelta(days=1)
            status, data = mail.search(None, "SINCE", imap_date(day), "BEFORE", imap_date(nxt))
            count = len(data[0].split()) if status == "OK" and data[0] else 0
            results.append({"label": day.strftime("%d %B %Y"),
                            "weekday": day.strftime("%A"),
                            "count": count})
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return results


PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mail Summary</title>
<style>
  :root{
    --bg:#EEF2F0; --panel:#FFFFFF; --ink:#16231F; --muted:#5B6B65;
    --line:#CBD5D0; --accent:#1F6F5C; --accent-ink:#FFFFFF; --bad:#A3321F;
  }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#101816; --panel:#18221F; --ink:#E7EFEC; --muted:#9BAAA4;
           --line:#2C3B36; --accent:#4FB89C; --accent-ink:#0B1512; --bad:#F08A76; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font-family:"Segoe UI",system-ui,-apple-system,Helvetica,Arial,sans-serif;line-height:1.5}
  main{max-width:960px;margin:0 auto;padding:40px 20px 60px;
       display:grid;grid-template-columns:minmax(0,380px) minmax(0,1fr);gap:32px}
  @media (max-width:800px){ main{grid-template-columns:1fr} }
  h1{font-family:Georgia,"Times New Roman",serif;font-size:2rem;margin:0 0 6px}
  .sub{color:var(--muted);margin:0 0 24px}
  form{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:22px}
  label{display:block;font-weight:600;margin:14px 0 6px;font-size:.92rem}
  label:first-of-type{margin-top:0}
  input,select{width:100%;padding:10px 12px;font:inherit;color:var(--ink);
       background:var(--bg);border:1px solid var(--line);border-radius:6px}
  input:focus,select:focus,button:focus-visible{outline:3px solid var(--accent);outline-offset:1px}
  button{margin-top:20px;width:100%;padding:12px;font:inherit;font-weight:600;cursor:pointer;
       background:var(--accent);color:var(--accent-ink);border:0;border-radius:6px}
  .pw{display:flex;gap:8px}
  .pw input{flex:1}
  button.ghost{margin:0;width:auto;padding:0 16px;background:transparent;color:var(--accent);
       border:1px solid var(--line)}
  .help{margin-top:12px;padding:12px 14px;border-left:4px solid var(--accent);
       background:var(--bg);border-radius:6px;font-size:.88rem}
  .help a{color:var(--accent);font-weight:600}
  .hint{color:var(--muted);font-size:.82rem;margin-top:6px}
  .error{background:var(--panel);border:1px solid var(--bad);color:var(--bad);
       border-radius:8px;padding:12px 14px;margin-bottom:16px}
  .result h2{font-family:Georgia,serif;margin:0 0 4px;font-size:1.3rem}
  .days{display:grid;gap:12px;margin-top:16px}
  .day{display:flex;justify-content:space-between;align-items:center;
       background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--accent);
       border-radius:8px;padding:16px 20px}
  .day .date{font-weight:600}
  .day .wd{color:var(--muted);font-size:.88rem}
  .day .n{font-family:Georgia,serif;font-size:2.4rem;line-height:1}
  .empty{color:var(--muted);border:1px dashed var(--line);border-radius:8px;padding:28px}
  .total{margin-top:14px;color:var(--muted)}
</style>
</head>
<body>
<main>
  <section>
    <h1>Mail Summary</h1>
    <p class="sub">See how many emails reached your inbox on each of the last three days.</p>
    <form method="post" autocomplete="off">
      <label for="provider">Mail provider</label>
      <select id="provider" name="provider">
        {% for key, p in providers.items() %}
          <option value="{{ key }}" data-domains="{{ (p.domains or [])|join(',') }}"
            {{ 'selected' if form.provider == key else '' }}>{{ p.label }}</option>
        {% endfor %}
      </select>

      <div id="custom-wrap" hidden>
        <label for="server">IMAP server</label>
        <input id="server" name="server" value="{{ form.server }}" placeholder="imap.yourcompany.com">
      </div>

      <label for="email">Email address</label>
      <input id="email" name="email" type="email" value="{{ form.email }}" required>
      <div class="hint" id="email-hint"></div>

      <label for="password">App password</label>
      <div class="pw">
        <input id="password" name="password" type="password" required>
        <button type="button" id="toggle" class="ghost" aria-pressed="false">Show</button>
      </div>
      <div class="hint">Used once to read your mail counts. It is never stored.</div>
      <div class="help" id="help"></div>

      <button type="submit">Show my summary</button>
    </form>
  </section>

  <section class="result" aria-live="polite">
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if results %}
      <h2>{{ form.email }}</h2>
      <div class="sub">Emails received per day</div>
      <div class="days">
        {% for r in results %}
          <div class="day">
            <div><div class="date">{{ r.label }}</div><div class="wd">{{ r.weekday }}</div></div>
            <div class="n">{{ r.count }}</div>
          </div>
        {% endfor %}
      </div>
      <div class="total">Total over 3 days: {{ results|sum(attribute='count') }}</div>
    {% elif not error %}
      <div class="empty">Choose your provider, enter your email and app password, and your three-day summary will appear here.</div>
    {% endif %}
  </section>
</main>

<script>
  // Update hint / custom server box when the provider changes
  const provider = document.getElementById('provider');
  const hint = document.getElementById('email-hint');
  const email = document.getElementById('email');
  const customWrap = document.getElementById('custom-wrap');
  function refresh(){
    const opt = provider.options[provider.selectedIndex];
    const domains = opt.dataset.domains ? opt.dataset.domains.split(',') : [];
    customWrap.hidden = provider.value !== 'other';
    if (domains.length){
      const ends = domains.map(d => '@' + d).join(' or ');
      hint.textContent = 'Must end with ' + ends;
      email.placeholder = 'yourname' + '@' + domains[0];
      email.pattern = '.+@(' + domains.map(d => d.replace(/\\./g,'\\\\.')).join('|') + ')$';
      email.title = 'Address must end with ' + ends;
    } else {
      hint.textContent = 'Enter any email address your IMAP server supports.';
      email.placeholder = 'you@yourcompany.com';
      email.removeAttribute('pattern');
    }
  }
  const HELP = {{ help|tojson }};
  const helpBox = document.getElementById('help');
  function showHelp(){
    const h = HELP[provider.value];
    helpBox.innerHTML = '';
    const b = document.createElement('strong');
    b.textContent = 'How to get your app password: ';
    helpBox.appendChild(b);
    helpBox.appendChild(document.createTextNode(h.steps + ' '));
    if (h.link){
      const a = document.createElement('a');
      a.href = h.link; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = 'Open the page';
      helpBox.appendChild(a);
    }
  }
  const pw = document.getElementById('password');
  const toggle = document.getElementById('toggle');
  toggle.addEventListener('click', () => {
    const show = pw.type === 'password';
    pw.type = show ? 'text' : 'password';
    toggle.textContent = show ? 'Hide' : 'Show';
    toggle.setAttribute('aria-pressed', show);
  });
  provider.addEventListener('change', () => { refresh(); showHelp(); });
  showHelp();
  refresh();
</script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    form = {"provider": "gmail", "email": "", "server": ""}
    error, results = None, None

    if request.method == "POST":
        form["provider"] = request.form.get("provider", "gmail")
        form["email"] = request.form.get("email", "").strip()
        form["server"] = request.form.get("server", "").strip()
        password = request.form.get("password", "")

        error = validate(form["provider"], form["email"], password, form["server"])
        if not error:
            server = PROVIDERS[form["provider"]]["server"] or form["server"]
            try:
                results = count_last_3_days(server, form["email"], password)
            except imaplib.IMAP4.error:
                error = ("Login failed. Check the email and app password, and make sure "
                         "IMAP is enabled for this account.")
            except Exception as exc:
                error = f"Could not reach {server}. Check the server name and your internet connection. ({exc})"

    return render_template_string(PAGE, providers=PROVIDERS, help=HELP, form=form,
                                  error=error, results=results)


if __name__ == "__main__":
    import os
    # debug is OFF unless you set FLASK_DEBUG=1 (never leave debug on for a public site)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")