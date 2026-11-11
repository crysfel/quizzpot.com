#!/usr/bin/env python3
"""raw/ (crawl output) -> site/ (what GitHub Pages serves).

    tools/.venv/bin/python -I tools/build.py

Strips everything that needs the old Rails server or shows other people's data:
sign-in/sign-up, forum and quiz links, comments, newsletter/mailing forms, the
"latest members" widget, enrolled-user avatars, CSRF tags, dead trackers.
Adds a static /contact/ page, 404.html, CNAME and .nojekyll.
"""
import re, shutil
from pathlib import Path
from bs4 import BeautifulSoup, Comment

RAW, SITE = Path("raw"), Path("site")
DOMAIN = "quizzpot.com"
CONTACT_EMAIL = "sales@bleext.com"
DEAD_PREFIXES = ("/signin", "/signup", "/forum", "/quizzes", "/users", "/members", "/password_resets",
                 "/subscribe", "/messages")

REMOVE = [
    "#user-bar", "#comments", "#askMail", "#fb-root",
    ".tabgroup",                      # lesson: email / register / login tabs
    ".article-download-section",      # lesson: "register to download videos and code"
    ".course-checkout", ".course-login", ".course-signed-users",   # course page enrol box + avatars
    ".widget_twitter",                # footer "latest members" list (spam accounts)
    ".widget_contactform",            # footer newsletter form
    'meta[name="csrf-param"]', 'meta[name="csrf-token"]',
    "form",                           # anything left that posts to the server
]


def clean(soup):
    for sel in REMOVE:
        for el in soup.select(sel):
            el.decompose()

    # Main menu: drop Foro / Entrar / Registrarse; Contacto now goes to the static page.
    for a in soup.select("#menu-main a"):
        href = a.get("href", "")
        if href.startswith(("/forum", "/signin", "/signup")):
            a.find_parent("li").decompose()
        elif href.startswith("/contact"):
            a["href"] = "/contact/"

    # Home teasers that only make sense with accounts (register, quizzes).
    for t in soup.select(".teaser"):
        if t.select_one('a[href^="/signup"], a[href^="/quizzes"]'):
            t.decompose()
    teasers = soup.select(".teaser")
    if teasers:
        for i, t in enumerate(teasers, 1):
            t["class"] = ["grid_6" if c == "grid_3" else c for c in t.get("class", [])]
            num = t.find(string=re.compile(r"^\s*\d\s*$"))
            if num:
                num.replace_with(str(i))

    # "Descarga Código Fuente / Video" buttons went to the sign-in wall.
    for a in soup.select('a[href$="/download_code"], a[href$="/download_video"]'):
        (a.find_parent("li") or a).decompose()

    # Blog listings: "Comments (N) |" counts point at comments that are no longer shown.
    for a in soup.select("a.comments"):
        sep = a.find_next_sibling("span")
        if sep and sep.get_text(strip=True) == "|":
            sep.decompose()
        a.decompose()
    for d in soup.select("div.comments"):
        if not d.get_text(strip=True):
            d.decompose()

    # Social menu: Google+ is gone.
    for a in soup.select('a[href*="plus.google.com"]'):
        (a.find_parent("li") or a).decompose()

    # Author links -> About page; any other link into a dead area -> plain text.
    for a in soup.select('a[href^="/users/1/"], a[href="/users/1"]'):
        a["href"] = "/about/"
    for a in soup.find_all("a", href=True):
        if a["href"].startswith(DEAD_PREFIXES):
            a.unwrap()

    # Dead trackers: old Google Analytics (UA-*, shut down 2023), Facebook SDK, newsletter init.
    for s in soup.find_all("script"):
        txt = s.string or ""
        src = s.get("src", "")
        if "_gaq" in txt or "connect.facebook.net" in txt or "Newsletter.init" in txt or "facebook" in src:
            s.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment) and "csrf" in x.lower()):
        c.extract()
    return soup


def contact_page(template_html):
    soup = BeautifulSoup(template_html, "html.parser")
    soup.title.string = "Contacto - Quizzpot"
    area = soup.select_one("#contentarea")
    area.clear()
    social = [(a.get_text(strip=True), a["href"]) for a in soup.select("#menu-social a")
              if a["href"].startswith("http")]
    frag = BeautifulSoup(
        '<div class="grid_12"><div class="entry-content">'
        "<h2>Contacto</h2>"
        "<p>Quizzpot ya no publica cursos nuevos, pero todo el contenido sigue disponible aquí.</p>"
        f'<p>Para cualquier duda o comentario escríbenos a <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>'
        "<p>También nos encuentras en:</p><ul>"
        + "".join(f'<li><a href="{h}">{n}</a></li>' for n, h in social)
        + "</ul></div></div>",
        "html.parser",
    )
    area.append(frag)
    return str(soup)


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    pages = 0
    for src in RAW.rglob("*"):
        if src.is_dir():
            continue
        dest = SITE / src.relative_to(RAW)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".html":
            soup = clean(BeautifulSoup(src.read_text("utf-8"), "html.parser"))
            dest.write_text(str(soup), "utf-8")
            pages += 1
        else:
            shutil.copy2(src, dest)

    about = (SITE / "about/index.html").read_text("utf-8")
    (SITE / "contact").mkdir(exist_ok=True)
    (SITE / "contact/index.html").write_text(contact_page(about), "utf-8")

    nf = BeautifulSoup(about, "html.parser")
    nf.title.string = "Página no encontrada - Quizzpot"
    area = nf.select_one("#contentarea"); area.clear()
    area.append(BeautifulSoup('<div class="grid_12"><div class="entry-content"><h2>Página no encontrada</h2>'
                              '<p>Esta página ya no existe. Revisa los <a href="/courses/">cursos</a> o el '
                              '<a href="/blog/">blog</a>.</p></div></div>', "html.parser"))
    (SITE / "404.html").write_text(str(nf), "utf-8")

    (SITE / "CNAME").write_text(DOMAIN + "\n")
    (SITE / ".nojekyll").write_text("")
    print(f"built {pages} pages + contact + 404 into {SITE}/")


if __name__ == "__main__":
    main()
