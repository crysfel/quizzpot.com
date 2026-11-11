# quizzpot.com (static archive)

Quizzpot, my first project that made money online, frozen as a static site on GitHub Pages.
The original was a Rails app on the `sites` droplet; this copy keeps the public pages
(home, courses and lessons, blog, the old 2009–2011 posts, about) and drops everything that
needed the server or showed other people's data (sign-in/sign-up, forum, quizzes, comments,
newsletter forms, member lists).

| Path | What |
|---|---|
| `site/` | What GitHub Pages serves (deployed by `.github/workflows/pages.yml` on push to `main`) |
| `tools/crawl.py` | Crawls the live site into `raw/` (git-ignored) with static, clean URLs |
| `tools/build.py` | `raw/` → `site/`: strips dynamic/user parts, adds `/contact/`, `404.html`, `CNAME` |

Rebuild (only possible while the old server is up):

```bash
python3 -I tools/crawl.py --out raw
python3 -m venv tools/.venv && tools/.venv/bin/pip install beautifulsoup4==4.12.3
tools/.venv/bin/python -I tools/build.py
cd site && python3 -m http.server 8765   # preview at http://127.0.0.1:8765
```

Still loaded from outside: lesson images and avatars from `s3.amazonaws.com/quizzpot/`,
YouTube/Vimeo embeds, Google Fonts. Already broken before the move (left as-is): old
`/wp-content/` files, `demos.bleext.com`, the googlecode.com code-highlighting scripts.
