import os
import re
import io
import csv
import json
import time
import shutil
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, abort, Response, g, session
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from slugify import slugify
import bleach
from PIL import Image

from config import Config
from database import get_db, init_db

# ---------------- App setup ----------------
app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
init_db(app)

# ---------------- Allowed HTML for sanitization ----------------
ALLOWED_TAGS = [
    "p","br","hr","strong","b","em","i","u","s","blockquote",
    "h1","h2","h3","h4","h5","h6",
    "ul","ol","li","a","img","figure","figcaption",
    "table","thead","tbody","tr","th","td",
    "code","pre","span","div","sup","sub"
]
ALLOWED_ATTRS = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "pre": ["class"],
    "span": ["class"],
}

def sanitize_html(html: str) -> str:
    return bleach.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
    )

# ---------------- Auth helpers ----------------
def current_user():
    """Return the currently logged-in user row, or None."""
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("এই পেজ দেখতে লগইন করুন।", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

def owner_required(f):
    """Resource must belong to the current user."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            flash("এই কাজ করতে লগইন করুন।", "error")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

# ---------------- Settings helpers ----------------
DEFAULT_SETTINGS = {
    "site_name": "IlmNote",
    "user_name": "User",
    "theme": "system",
    "font_family": "Noto Sans Bengali",
    "font_size": "18",
    "line_height": "1.8",
    "view_mode": "grid",
    "content_width": "760",
}

def get_settings(user_id=None):
    db = get_db()
    s = dict(DEFAULT_SETTINGS)
    # Global settings (user_id IS NULL)
    rows = db.execute("SELECT key, value FROM settings WHERE user_id IS NULL").fetchall()
    for r in rows:
        s[r["key"]] = r["value"]
    # User-specific overrides
    if user_id:
        rows = db.execute("SELECT key, value FROM settings WHERE user_id=?", (user_id,)).fetchall()
        for r in rows:
            s[r["key"]] = r["value"]
    return s

def set_setting(key, value, user_id=None):
    db = get_db()
    if user_id:
        row = db.execute("SELECT 1 FROM settings WHERE key=? AND user_id=?", (key, user_id)).fetchone()
        if row:
            db.execute("UPDATE settings SET value=? WHERE key=? AND user_id=?", (str(value), key, user_id))
        else:
            db.execute("INSERT INTO settings (key, value, user_id) VALUES (?,?,?)", (key, str(value), user_id))
    else:
        row = db.execute("SELECT 1 FROM settings WHERE key=? AND user_id IS NULL", (key,)).fetchone()
        if row:
            db.execute("UPDATE settings SET value=? WHERE key=? AND user_id IS NULL", (str(value), key))
        else:
            db.execute("INSERT INTO settings (key, value, user_id) VALUES (?,?,NULL)", (key, str(value)))
    db.commit()

@app.context_processor
def inject_globals():
    u = current_user()
    return {
        "settings": get_settings(u["id"] if u else None),
        "current_user": u,
        "now": datetime.now(),
    }

# ---------------- Reading time ----------------
def estimate_reading_time(text: str) -> int:
    if not text:
        return 1
    plain = re.sub(r"<[^>]+>", " ", text)
    words = re.findall(r"\S+", plain)
    return max(1, round(len(words) / 180))

# ============================================================
# AUTH ROUTES
# ============================================================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        display_name = request.form.get("display_name", "").strip()

        errors = []
        if not username or len(username) < 3:
            errors.append("ইউজারনেম কমপক্ষে ৩ অক্ষরের হতে হবে।")
        if not re.match(r"^[a-z0-9_]+$", username):
            errors.append("ইউজারনেমে শুধু ছোট হাতের অক্ষর, সংখ্যা এবং _ ব্যবহার করুন।")
        if not email or "@" not in email:
            errors.append("সঠিক ইমেইল দিন।")
        if len(password) < 6:
            errors.append("পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।")
        if password != password2:
            errors.append("দুইবার একই পাসওয়ার্ড দিন।")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("signup"))

        db = get_db()
        existing = db.execute(
            "SELECT 1 FROM users WHERE username=? OR email=?", (username, email)
        ).fetchone()
        if existing:
            flash("এই ইউজারনেম বা ইমেইল আগেই ব্যবহার হয়েছে।", "error")
            return redirect(url_for("signup"))

        pwd_hash = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO users (username, email, password_hash, display_name) VALUES (?,?,?,?)",
            (username, email, pwd_hash, display_name or username)
        )
        db.commit()
        session["user_id"] = cur.lastrowid
        flash(f"স্বাগতম, {display_name or username}!", "success")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("index"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? OR email=?",
            (identifier, identifier)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("লগইন সফল হয়েছে।", "success")
            next_url = request.args.get("next") or url_for("index")
            if not next_url.startswith("/"):
                next_url = url_for("index")
            return redirect(next_url)
        flash("ভুল ইউজারনেম বা পাসওয়ার্ড।", "error")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("লগআউট হয়েছে।", "success")
    return redirect(url_for("index"))

# ============================================================
# GUEST-VISIBLE ROUTES (Home, Articles, Reader, Search, Authors)
# ============================================================
@app.route("/")
def index():
    db = get_db()
    # For guests, show only published articles from all users.
    # For logged-in user, show their own articles.
    u = current_user()

    if u:
        base_where = "WHERE a.is_published=1 AND a.user_id=?"
        base_param = [u["id"]]
    else:
        base_where = "WHERE a.is_published=1 AND a.user_id IS NOT NULL"
        base_param = []

    total_articles = db.execute(f"SELECT COUNT(*) c FROM articles a {base_where}", base_param).fetchone()["c"]

    if u:
        total_categories = db.execute("SELECT COUNT(*) c FROM categories WHERE user_id=?", (u["id"],)).fetchone()["c"]
        total_tags = db.execute("SELECT COUNT(*) c FROM tags WHERE user_id=?", (u["id"],)).fetchone()["c"]
    else:
        total_categories = db.execute("SELECT COUNT(*) c FROM categories WHERE user_id IS NOT NULL").fetchone()["c"]
        total_tags = db.execute("SELECT COUNT(*) c FROM tags WHERE user_id IS NOT NULL").fetchone()["c"]

    recent = db.execute(f"""
        SELECT a.*, c.name AS category_name, c.color AS category_color
        FROM articles a LEFT JOIN categories c ON a.category_id=c.id
        {base_where}
        ORDER BY a.created_at DESC LIMIT 6
    """, base_param).fetchall()

    updated = db.execute(f"""
        SELECT a.*, c.name AS category_name, c.color AS category_color
        FROM articles a LEFT JOIN categories c ON a.category_id=c.id
        {base_where}
        ORDER BY a.updated_at DESC LIMIT 4
    """, base_param).fetchall()

    featured = db.execute(f"""
        SELECT a.*, c.name AS category_name, c.color AS category_color
        FROM articles a LEFT JOIN categories c ON a.category_id=c.id
        {base_where} AND a.is_featured=1
        ORDER BY a.updated_at DESC LIMIT 4
    """, base_param).fetchall()

    if u:
        bookmarked = db.execute("""
            SELECT a.*, c.name AS category_name, c.color AS category_color
            FROM articles a
            JOIN bookmarks b ON b.article_id=a.id
            LEFT JOIN categories c ON a.category_id=c.id
            WHERE b.user_id=?
            ORDER BY b.created_at DESC LIMIT 4
        """, (u["id"],)).fetchall()

        categories = db.execute("""
            SELECT c.*, (SELECT COUNT(*) FROM articles a WHERE a.category_id=c.id AND a.is_published=1) AS count
            FROM categories c WHERE c.user_id=? ORDER BY c.name
        """, (u["id"],)).fetchall()
    else:
        bookmarked = []
        categories = db.execute("""
            SELECT c.*, (SELECT COUNT(*) FROM articles a WHERE a.category_id=c.id AND a.is_published=1) AS count
            FROM categories c WHERE c.user_id IS NOT NULL ORDER BY c.name LIMIT 12
        """).fetchall()

    return render_template("index.html",
        total_articles=total_articles,
        total_categories=total_categories,
        total_tags=total_tags,
        recent=recent, updated=updated, featured=featured,
        bookmarked=bookmarked, categories=categories)


@app.route("/articles")
def articles():
    db = get_db()
    u = current_user()
    cat = request.args.get("category", "").strip()
    tag = request.args.get("tag", "").strip()
    fav = request.args.get("fav") == "1"
    bm  = request.args.get("bm") == "1"

    sql = """
        SELECT a.*, c.name AS category_name, c.color AS category_color
        FROM articles a
        LEFT JOIN categories c ON a.category_id=c.id
        WHERE a.is_published=1
    """
    params = []
    if u:
        # Show user's own articles + others' published articles
        pass  # guests will see everyone; logged-in user sees everyone
    else:
        sql += " AND a.user_id IS NOT NULL"

    if cat:
        sql += " AND c.slug=?"
        params.append(cat)
    if tag:
        sql += """ AND a.id IN (
            SELECT at.article_id FROM article_tags at
            JOIN tags t ON t.id=at.tag_id WHERE t.slug=?
        )"""
        params.append(tag)
    if fav and u:
        sql += " AND a.id IN (SELECT article_id FROM favorites WHERE user_id=?)"
        params.append(u["id"])
    if bm and u:
        sql += " AND a.id IN (SELECT article_id FROM bookmarks WHERE user_id=?)"
        params.append(u["id"])
    sql += " ORDER BY a.created_at DESC"

    rows = db.execute(sql, params).fetchall()

    tags_by_article = {}
    for a in rows:
        ts = db.execute("""
            SELECT t.name, t.slug FROM tags t
            JOIN article_tags at ON at.tag_id=t.id
            WHERE at.article_id=?
        """, (a["id"],)).fetchall()
        tags_by_article[a["id"]] = ts

    if u:
        categories = db.execute("SELECT * FROM categories WHERE user_id=? ORDER BY name", (u["id"],)).fetchall()
        all_tags = db.execute("""
            SELECT t.*, (SELECT COUNT(*) FROM article_tags at WHERE at.tag_id=t.id) AS count
            FROM tags t WHERE t.user_id=? ORDER BY t.name
        """, (u["id"],)).fetchall()
    else:
        categories = db.execute("SELECT * FROM categories WHERE user_id IS NOT NULL ORDER BY name").fetchall()
        all_tags = db.execute("""
            SELECT t.*, (SELECT COUNT(*) FROM article_tags at WHERE at.tag_id=t.id) AS count
            FROM tags t WHERE t.user_id IS NOT NULL ORDER BY t.name
        """).fetchall()

    return render_template("articles.html",
        articles=rows, categories=categories, all_tags=all_tags,
        tags_by_article=tags_by_article,
        active_category=cat, active_tag=tag, fav=fav, bm=bm)


@app.route("/article/<slug>")
def article(slug):
    db = get_db()
    a = db.execute("""
        SELECT a.*, c.name AS category_name, c.color AS category_color, c.slug AS category_slug
        FROM articles a LEFT JOIN categories c ON a.category_id=c.id
        WHERE a.slug=?
    """, (slug,)).fetchone()
    if not a:
        abort(404)
    # Guests can only view published
    if not a["is_published"]:
        u = current_user()
        if not u or u["id"] != a["user_id"]:
            abort(404)

    tags = db.execute("""
        SELECT t.name, t.slug FROM tags t
        JOIN article_tags at ON at.tag_id=t.id WHERE at.article_id=?
    """, (a["id"],)).fetchall()

    sources = db.execute("""
        SELECT idx, label, url FROM article_sources
        WHERE article_id=? ORDER BY idx
    """, (a["id"],)).fetchall()

    u = current_user()
    is_bm = False
    is_fav = False
    if u:
        is_bm = db.execute("SELECT 1 FROM bookmarks WHERE article_id=? AND user_id=?", (a["id"], u["id"])).fetchone() is not None
        is_fav = db.execute("SELECT 1 FROM favorites WHERE article_id=? AND user_id=?", (a["id"], u["id"])).fetchone() is not None

    related = db.execute("""
        SELECT a2.*, c.name AS category_name FROM articles a2
        LEFT JOIN categories c ON a2.category_id=c.id
        WHERE a2.category_id=? AND a2.id!=? AND a2.is_published=1
        ORDER BY a2.created_at DESC LIMIT 4
    """, (a["category_id"], a["id"])).fetchall()

    content = sanitize_html(a["content"])
    is_owner = bool(u and u["id"] == a["user_id"])

    return render_template("article.html",
        a=a, tags=tags, content=content,
        is_bookmarked=is_bm, is_favorite=is_fav, related=related,
        sources=sources, is_owner=is_owner)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        db = get_db()
        like = f"%{q}%"
        results = db.execute("""
            SELECT DISTINCT a.*, c.name AS category_name, c.color AS category_color
            FROM articles a
            LEFT JOIN categories c ON a.category_id=c.id
            LEFT JOIN article_tags at ON at.article_id=a.id
            LEFT JOIN tags t ON t.id=at.tag_id
            WHERE a.is_published=1 AND a.user_id IS NOT NULL AND (
                a.title LIKE ? OR a.short_description LIKE ? OR a.content LIKE ?
                OR a.source_name LIKE ? OR a.author_name LIKE ?
                OR c.name LIKE ? OR t.name LIKE ?
            )
            ORDER BY a.created_at DESC
        """, (like, like, like, like, like, like, like)).fetchall()
    return render_template("search.html", q=q, results=results)


@app.route("/authors")
def authors():
    db = get_db()
    rows = db.execute("""
        SELECT TRIM(author_name) AS name,
               COUNT(*) AS count,
               MAX(created_at) AS last_at
        FROM articles
        WHERE author_name IS NOT NULL AND TRIM(author_name) != ''
              AND is_published=1 AND user_id IS NOT NULL
        GROUP BY TRIM(author_name)
        ORDER BY count DESC, name ASC
    """).fetchall()
    return render_template("authors.html", authors=rows)


@app.route("/author/<path:name>")
def author(name):
    db = get_db()
    articles = db.execute("""
        SELECT a.*, c.name AS category_name, c.color AS category_color
        FROM articles a
        LEFT JOIN categories c ON a.category_id=c.id
        WHERE TRIM(a.author_name)=? AND a.is_published=1 AND a.user_id IS NOT NULL
        ORDER BY a.created_at DESC
    """, (name.strip(),)).fetchall()
    return render_template("author.html", name=name, articles=articles)

# ============================================================
# PROTECTED ROUTES (require login)
# ============================================================
@app.route("/new", methods=["GET", "POST"])
@app.route("/edit/<int:aid>", methods=["GET", "POST"])
@login_required
def editor(aid=None):
    db = get_db()
    u = current_user()
    article = None
    if aid:
        article = db.execute("SELECT * FROM articles WHERE id=? AND user_id=?", (aid, u["id"])).fetchone()
        if not article:
            flash("লেখাটি পাওয়া যায়নি বা অনুমতি নেই।", "error")
            return redirect(url_for("articles"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        short_desc = request.form.get("short_description", "").strip()
        content = request.form.get("content", "")
        category_id = request.form.get("category_id") or None
        tags_raw = request.form.get("tags", "").strip()
        source_name = request.form.get("source_name", "").strip()
        source_url  = request.form.get("source_url", "").strip()
        author_name = request.form.get("author_name", "").strip()
        is_published = 1 if request.form.get("is_published") == "1" else 0
        is_featured = 1 if request.form.get("is_featured") == "1" else 0

        if not title:
            flash("শিরোনাম দিতে হবে।", "error")
            return redirect(request.url)

        content_clean = sanitize_html(content)
        reading_time = estimate_reading_time(content_clean)

        cover_path = article["cover_image"] if article else ""
        file = request.files.get("cover_image")
        if file and file.filename:
            if allowed_file(file.filename) and allowed_mime(file):
                fname = f"{int(time.time())}_{secure_filename(file.filename)}"
                fpath = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                file.save(fpath)
                cover_path = f"uploads/covers/{fname}"

        base_slug = slugify(title) or f"article-{int(time.time())}"
        slug = base_slug
        n = 1
        while True:
            q = "SELECT id FROM articles WHERE slug=?"
            p = [slug]
            if article:
                q += " AND id!=?"
                p.append(article["id"])
            if not db.execute(q, p).fetchone():
                break
            n += 1
            slug = f"{base_slug}-{n}"

        if article:
            db.execute("""
                UPDATE articles SET title=?, slug=?, short_description=?, content=?,
                    cover_image=?, category_id=?, source_name=?, source_url=?,
                    author_name=?, reading_time=?, is_published=?, is_featured=?,
                    updated_at=datetime('now')
                WHERE id=? AND user_id=?
            """, (title, slug, short_desc, content_clean, cover_path,
                  category_id, source_name, source_url, author_name,
                  reading_time, is_published, is_featured, article["id"], u["id"]))
            article_id = article["id"]
        else:
            cur = db.execute("""
                INSERT INTO articles (title, slug, short_description, content,
                    cover_image, category_id, source_name, source_url,
                    author_name, reading_time, is_published, is_featured, user_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (title, slug, short_desc, content_clean, cover_path,
                  category_id, source_name, source_url, author_name,
                  reading_time, is_published, is_featured, u["id"]))
            article_id = cur.lastrowid

        # Tags
        db.execute("DELETE FROM article_tags WHERE article_id=?", (article_id,))
        for t in [x.strip() for x in tags_raw.split(",") if x.strip()]:
            tslug = slugify(t) or t
            db.execute("INSERT OR IGNORE INTO tags (name, slug, user_id) VALUES (?,?,?)", (t, tslug, u["id"]))
            row = db.execute("SELECT id FROM tags WHERE slug=? AND user_id=?", (tslug, u["id"])).fetchone()
            if not row:
                row = db.execute("SELECT id FROM tags WHERE slug=?", (tslug,)).fetchone()
            if row:
                db.execute("INSERT OR IGNORE INTO article_tags (article_id, tag_id) VALUES (?,?)",
                           (article_id, row["id"]))

        # Sources
        sources_raw = request.form.get("sources_raw", "")
        db.execute("DELETE FROM article_sources WHERE article_id=?", (article_id,))
        idx = 0
        for line in sources_raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            idx += 1
            m = re.match(r"^\[([০-৯0-9]+)\]\s*(.+)$", line)
            rest = m.group(2).strip() if m else line
            url_match = re.search(r"https?://\S+", rest)
            if url_match:
                url = url_match.group(0)
                label = rest.replace(url, "").strip(" —-–")
            else:
                url = ""
                label = rest
            if not label:
                label = url
            db.execute(
                "INSERT INTO article_sources (article_id, idx, label, url, user_id) VALUES (?,?,?,?,?)",
                (article_id, idx, label, url, u["id"]),
            )

        db.commit()
        flash("সংরক্ষণ করা হয়েছে।", "success")
        return redirect(url_for("article", slug=slug))

    categories = db.execute("SELECT * FROM categories WHERE user_id=? ORDER BY name", (u["id"],)).fetchall()
    tags_str = ""
    if article:
        rows = db.execute("""
            SELECT t.name FROM tags t JOIN article_tags at ON at.tag_id=t.id
            WHERE at.article_id=?
        """, (article["id"],)).fetchall()
        tags_str = ", ".join(r["name"] for r in rows)

    sources_raw = ""
    if article:
        srcs = db.execute(
            "SELECT idx, label, url FROM article_sources WHERE article_id=? ORDER BY idx",
            (article["id"],)
        ).fetchall()
        lines = []
        for s in srcs:
            num = s["idx"]
            if s["url"] and s["label"]:
                lines.append(f"[{num}] {s['label']} — {s['url']}")
            elif s["url"]:
                lines.append(f"[{num}] {s['url']}")
            else:
                lines.append(f"[{num}] {s['label']}")
        sources_raw = "\n".join(lines)

    return render_template("editor.html",
        article=article, categories=categories,
        tags_str=tags_str, sources_raw=sources_raw)


@app.route("/delete/<int:aid>", methods=["POST"])
@login_required
def delete_article(aid):
    db = get_db()
    u = current_user()
    db.execute("DELETE FROM articles WHERE id=? AND user_id=?", (aid, u["id"]))
    db.commit()
    flash("মুছে ফেলা হয়েছে।", "success")
    return redirect(url_for("articles"))


@app.route("/duplicate/<int:aid>", methods=["POST"])
@login_required
def duplicate_article(aid):
    db = get_db()
    u = current_user()
    a = db.execute("SELECT * FROM articles WHERE id=? AND user_id=?", (aid, u["id"])).fetchone()
    if not a:
        abort(404)
    new_title = a["title"] + " (কপি)"
    base_slug = slugify(new_title) or f"copy-{int(time.time())}"
    slug = base_slug
    n = 1
    while db.execute("SELECT id FROM articles WHERE slug=?", (slug,)).fetchone():
        n += 1
        slug = f"{base_slug}-{n}"
    cur = db.execute("""
        INSERT INTO articles (title, slug, short_description, content, cover_image,
            category_id, source_name, source_url, author_name, reading_time,
            is_published, is_featured, user_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (new_title, slug, a["short_description"], a["content"], a["cover_image"],
          a["category_id"], a["source_name"], a["source_url"], a["author_name"],
          a["reading_time"], 0, 0, u["id"]))
    new_id = cur.lastrowid
    srcs = db.execute("SELECT idx, label, url FROM article_sources WHERE article_id=? ORDER BY idx", (a["id"],)).fetchall()
    for s in srcs:
        db.execute("INSERT INTO article_sources (article_id, idx, label, url, user_id) VALUES (?,?,?,?,?)",
                   (new_id, s["idx"], s["label"], s["url"], u["id"]))
    db.commit()
    flash("কপি তৈরি হয়েছে।", "success")
    return redirect(url_for("editor", aid=new_id))


# ============================================================
# TOGGLE BOOKMARK/FAVORITE
# ============================================================
@app.route("/toggle/bookmark/<int:aid>", methods=["POST"])
@login_required
def toggle_bookmark(aid):
    db = get_db()
    u = current_user()
    row = db.execute("SELECT 1 FROM bookmarks WHERE article_id=? AND user_id=?", (aid, u["id"])).fetchone()
    if row:
        db.execute("DELETE FROM bookmarks WHERE article_id=? AND user_id=?", (aid, u["id"]))
        state = False
    else:
        db.execute("INSERT INTO bookmarks (article_id, user_id) VALUES (?,?)", (aid, u["id"]))
        state = True
    db.commit()
    return jsonify({"ok": True, "state": state})


@app.route("/toggle/favorite/<int:aid>", methods=["POST"])
@login_required
def toggle_favorite(aid):
    db = get_db()
    u = current_user()
    row = db.execute("SELECT 1 FROM favorites WHERE article_id=? AND user_id=?", (aid, u["id"])).fetchone()
    if row:
        db.execute("DELETE FROM favorites WHERE article_id=? AND user_id=?", (aid, u["id"]))
        state = False
    else:
        db.execute("INSERT INTO favorites (article_id, user_id) VALUES (?,?)", (aid, u["id"]))
        state = True
    db.commit()
    return jsonify({"ok": True, "state": state})


# ============================================================
# CATEGORIES / TAGS (protected)
# ============================================================
@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    db = get_db()
    u = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        color = request.form.get("color", "#176B4D").strip()
        if name:
            slug = slugify(name) or name
            try:
                db.execute("INSERT INTO categories (name, slug, description, color, user_id) VALUES (?,?,?,?,?)",
                           (name, slug, desc, color, u["id"]))
                db.commit()
                flash("ক্যাটাগরি যোগ হয়েছে।", "success")
            except sqlite3.IntegrityError:
                flash("এই ক্যাটাগরি আগেই আছে।", "error")
        return redirect(url_for("categories"))

    rows = db.execute("""
        SELECT c.*, (SELECT COUNT(*) FROM articles a WHERE a.category_id=c.id) AS count
        FROM categories c WHERE c.user_id=? ORDER BY c.name
    """, (u["id"],)).fetchall()
    return render_template("categories.html", categories=rows)


@app.route("/categories/delete/<int:cid>", methods=["POST"])
@login_required
def delete_category(cid):
    db = get_db()
    u = current_user()
    db.execute("DELETE FROM categories WHERE id=? AND user_id=?", (cid, u["id"]))
    db.commit()
    flash("ক্যাটাগরি মুছে ফেলা হয়েছে।", "success")
    return redirect(url_for("categories"))


@app.route("/tags", methods=["GET", "POST"])
@login_required
def tags():
    db = get_db()
    u = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            slug = slugify(name) or name
            try:
                db.execute("INSERT INTO tags (name, slug, user_id) VALUES (?,?,?)", (name, slug, u["id"]))
                db.commit()
                flash("ট্যাগ যোগ হয়েছে।", "success")
            except sqlite3.IntegrityError:
                flash("এই ট্যাগ আগেই আছে।", "error")
        return redirect(url_for("tags"))
    rows = db.execute("""
        SELECT t.*, (SELECT COUNT(*) FROM article_tags at WHERE at.tag_id=t.id) AS count
        FROM tags t WHERE t.user_id=? ORDER BY t.name
    """, (u["id"],)).fetchall()
    return render_template("tags.html", tags=rows)


@app.route("/tags/delete/<int:tid>", methods=["POST"])
@login_required
def delete_tag(tid):
    db = get_db()
    u = current_user()
    db.execute("DELETE FROM tags WHERE id=? AND user_id=?", (tid, u["id"]))
    db.commit()
    flash("ট্যাগ মুছে ফেলা হয়েছে।", "success")
    return redirect(url_for("tags"))


# ============================================================
# NOTES (protected)
# ============================================================
@app.route("/notes", methods=["GET"])
@login_required
def notes():
    db = get_db()
    u = current_user()
    q = request.args.get("q", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    tag = request.args.get("tag", "").strip()

    sql = "SELECT * FROM notes WHERE user_id=?"
    params = [u["id"]]
    if q:
        sql += " AND (body LIKE ? OR tags LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if date_from:
        sql += " AND note_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND note_date <= ?"
        params.append(date_to)
    if tag:
        sql += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    sql += " ORDER BY is_pinned DESC, note_date DESC, created_at DESC"

    rows = db.execute(sql, params).fetchall()

    groups = {}
    for r in rows:
        groups.setdefault(r["note_date"], []).append(r)

    all_tags = set()
    for r in db.execute("SELECT tags FROM notes WHERE tags != '' AND user_id=?", (u["id"],)).fetchall():
        for t in (r["tags"] or "").split(","):
            t = t.strip()
            if t:
                all_tags.add(t)

    return render_template("notes.html",
        groups=groups, q=q, date_from=date_from, date_to=date_to,
        active_tag=tag, all_tags=sorted(all_tags),
        total=len(rows))


@app.route("/notes/add", methods=["POST"])
@login_required
def note_add():
    db = get_db()
    u = current_user()
    body = (request.form.get("body") or "").strip()
    note_date = (request.form.get("note_date") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "খালি নোট গ্রহণযোগ্য নয়"}), 400
    if not note_date:
        note_date = datetime.now().strftime("%Y-%m-%d")
    mood = request.form.get("mood", "default")
    color = request.form.get("color", "")
    tags = (request.form.get("tags") or "").strip()

    cur = db.execute("""
        INSERT INTO notes (body, note_date, mood, color, tags, user_id)
        VALUES (?,?,?,?,?,?)
    """, (body, note_date, mood, color, tags, u["id"]))
    db.commit()
    return jsonify({"ok": True, "id": cur.lastrowid})


@app.route("/notes/<int:nid>/update", methods=["POST"])
@login_required
def note_update(nid):
    db = get_db()
    u = current_user()
    row = db.execute("SELECT id FROM notes WHERE id=? AND user_id=?", (nid, u["id"])).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Not found"}), 404

    body = (request.form.get("body") or "").strip()
    note_date = (request.form.get("note_date") or "").strip()
    mood = request.form.get("mood", "default")
    color = request.form.get("color", "")
    tags = (request.form.get("tags") or "").strip()
    is_pinned = 1 if request.form.get("is_pinned") == "1" else 0

    if not body:
        return jsonify({"ok": False, "error": "খালি নোট গ্রহণযোগ্য নয়"}), 400

    db.execute("""
        UPDATE notes SET body=?, note_date=?, mood=?, color=?, tags=?,
            is_pinned=?, updated_at=datetime('now')
        WHERE id=? AND user_id=?
    """, (body, note_date, mood, color, tags, is_pinned, nid, u["id"]))
    db.commit()
    return jsonify({"ok": True})


@app.route("/notes/<int:nid>/pin", methods=["POST"])
@login_required
def note_pin(nid):
    db = get_db()
    u = current_user()
    row = db.execute("SELECT is_pinned FROM notes WHERE id=? AND user_id=?", (nid, u["id"])).fetchone()
    if not row:
        return jsonify({"ok": False}), 404
    new_state = 0 if row["is_pinned"] else 1
    db.execute("UPDATE notes SET is_pinned=? WHERE id=? AND user_id=?", (new_state, nid, u["id"]))
    db.commit()
    return jsonify({"ok": True, "pinned": new_state})


@app.route("/notes/<int:nid>/delete", methods=["POST"])
@login_required
def note_delete(nid):
    db = get_db()
    u = current_user()
    db.execute("DELETE FROM notes WHERE id=? AND user_id=?", (nid, u["id"]))
    db.commit()
    return jsonify({"ok": True})


# ============================================================
# SETTINGS (protected)
# ============================================================
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    u = current_user()
    if request.method == "POST":
        for key in ["site_name","user_name","theme","font_family","font_size",
                    "line_height","view_mode","content_width"]:
            if key in request.form:
                set_setting(key, request.form.get(key, "").strip(), u["id"])
        flash("সেটিংস সংরক্ষণ হয়েছে।", "success")
        return redirect(url_for("settings_page"))
    return render_template("settings.html")


# ============================================================
# BACKUP / EXPORT (protected)
# ============================================================
@app.route("/backup")
@login_required
def backup():
    db_path = Config.DATABASE
    if not os.path.exists(db_path):
        abort(404)
    with open(db_path, "rb") as f:
        data = f.read()
    fname = f"ilmnote_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    return Response(data, mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.route("/export/json")
@login_required
def export_json():
    db = get_db()
    u = current_user()
    rows = db.execute("SELECT * FROM articles WHERE user_id=?", (u["id"],)).fetchall()
    data = [dict(r) for r in rows]
    return Response(json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=articles.json"})


@app.route("/export/markdown/<int:aid>")
@login_required
def export_markdown(aid):
    db = get_db()
    u = current_user()
    a = db.execute("SELECT * FROM articles WHERE id=? AND user_id=?", (aid, u["id"])).fetchone()
    if not a:
        abort(404)
    sources = db.execute(
        "SELECT idx, label, url FROM article_sources WHERE article_id=? ORDER BY idx",
        (aid,)
    ).fetchall()
    md = f"# {a['title']}\n\n{a['short_description']}\n\n---\n\n{a['content']}"
    if sources:
        md += "\n\n---\n\n## সোর্স / রেফারেন্স\n\n"
        for s in sources:
            line = f"[{s['idx']}] {s['label']}"
            if s['url']:
                line += f" — {s['url']}"
            md += line + "\n"
    return Response(md, mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={a['slug']}.md"})


@app.route("/export/csv")
@login_required
def export_csv():
    db = get_db()
    u = current_user()
    rows = db.execute("SELECT id,title,short_description,source_name,source_url,created_at FROM articles WHERE user_id=?", (u["id"],)).fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id","title","short_description","source_name","source_url","created_at"])
    for r in rows:
        w.writerow([r["id"], r["title"], r["short_description"],
                    r["source_name"], r["source_url"], r["created_at"]])
    return Response(out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=articles.csv"})


# ============================================================
# ABOUT & MISC
# ============================================================
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/uploads/covers/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


def allowed_file(fname):
    return "." in fname and fname.rsplit(".",1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def allowed_mime(file):
    return file.mimetype in app.config["ALLOWED_MIME"]


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)