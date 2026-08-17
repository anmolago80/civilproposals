"""
blog.py

The marketing blog: storage, rendering, and publishing.

WHERE THINGS LIVE
-----------------
Postgres (db.BlogPost / db.BlogImage) is the source of truth for post
content -- drafts, body markdown, images, scheduling, everything the editor
touches. It is NOT what readers hit.

Readers hit finished HTML stored in Cloudflare Workers KV, written by
publish_post() through a small authenticated API on the Worker (see
landing/_worker.js). That split is deliberate:

  * The blog stays up, and stays crawlable, when Railway is asleep, being
    redeployed, or down. Nothing on the read path touches this database.
  * Pages are served from Cloudflare's edge, so they're fast everywhere,
    which is a real ranking input for the search traffic this blog exists
    to earn.
  * Publishing is the only moment the two systems talk, so there's exactly
    one failure point to reason about, and it surfaces immediately in the
    editor rather than silently later.

Re-publishing is always safe: every page is re-rendered from the database
rows, so a botched push is fixed by pressing Publish again.

URL SHAPE
---------
    /blog/                        the listing
    /blog/<slug>/                 a post
    /blog/category/<slug>/        a category listing
    /blog/media/<key>             an uploaded image

Slugs are permanent once published. edit_would_break_links() exists so the
editor can warn before someone renames one and orphans a search result.
"""

from __future__ import annotations

import base64
import os
import re
import unicodedata
from datetime import datetime, timezone

import requests

from modules import db

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://civilproposals.com").rstrip("/")

# The Worker's publish API. Both must be set for publishing to work; the
# editor shows a clear "not configured" state rather than failing at the
# moment someone presses Publish.
#   BLOG_PUBLISH_URL     e.g. https://civilproposals.com/api/blog
#   BLOG_PUBLISH_SECRET  shared secret, must match the Worker's own secret
#                        (`wrangler secret put BLOG_PUBLISH_SECRET`)
PUBLISH_URL = os.environ.get("BLOG_PUBLISH_URL", f"{SITE_ORIGIN}/api/blog").rstrip("/")
PUBLISH_SECRET = os.environ.get("BLOG_PUBLISH_SECRET", "").strip()

PUBLISH_TIMEOUT_SECONDS = 30

# Fixed, on purpose. Free-form categories reliably sprawl into fifteen
# near-duplicates within a year ("Tendering", "Tenders", "Tender tips"),
# which splits internal linking and makes the category pages worthless.
# Adding one here is a deliberate act; tags below stay free-form because
# sprawl there is harmless.
CATEGORIES = [
    ("tendering-and-compliance", "Tendering & Compliance"),
    ("fee-and-pricing", "Fee & Pricing"),
    ("bid-strategy", "Bid Strategy"),
    ("product-updates", "Product Updates"),
]
CATEGORY_LABELS = dict(CATEGORIES)

STATUS_DRAFT = "draft"
STATUS_SCHEDULED = "scheduled"
STATUS_PUBLISHED = "published"
STATUS_UNPUBLISHED = "unpublished"

DEFAULT_AUTHOR = "The CivilProposals team"

# Reserved first path segments under /blog/ that a post slug may not take,
# or it would shadow a real route.
RESERVED_SLUGS = {"category", "media", "index", "feed", "page", "tag", "admin"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def now_utc() -> datetime:
    """Public alias for _now(), for callers outside this module (the editor
    needs a UTC timestamp when stamping published_at)."""
    return _now()


def is_publishing_configured() -> bool:
    return bool(PUBLISH_SECRET and PUBLISH_URL)


def has_unpublished_changes(post: "db.BlogPost") -> bool:
    """True when a live post has been edited since it was last pushed.

    Compares through _aware() because one of the two timestamps is often a
    value this process just set (timezone-aware) while the other came back
    from Postgres (naive) -- comparing those directly raises TypeError, and
    a status badge must never be able to crash the editor."""
    if post.status != STATUS_PUBLISHED or not post.last_published_at or not post.updated_at:
        return False
    return _aware(post.updated_at) > _aware(post.last_published_at)


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------

def slugify(value: str) -> str:
    """URL slug from a title: ascii, lowercase, hyphen-separated.

    Deliberately lossy and boring -- the slug is a permanent public
    identifier, so predictability matters more than cleverness."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value).strip("-")
    return value[:80].strip("-")


def slug_is_valid(slug: str) -> tuple[bool, str]:
    """(ok, reason). Reason is empty when ok."""
    if not slug:
        return False, "Slug can't be empty."
    if slug in RESERVED_SLUGS:
        return False, f"'{slug}' is reserved -- it would collide with a /blog/{slug}/ route."
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        return False, "Slug may only contain lowercase letters, numbers and single hyphens."
    return True, ""


def unique_slug(desired: str, exclude_id: str | None = None) -> str:
    """Appends -2, -3, ... until the slug is free."""
    base = slugify(desired) or "post"
    candidate = base
    n = 1
    with db.get_session() as s:
        while True:
            q = s.query(db.BlogPost).filter(db.BlogPost.slug == candidate)
            if exclude_id:
                q = q.filter(db.BlogPost.id != exclude_id)
            if q.first() is None:
                return candidate
            n += 1
            candidate = f"{base}-{n}"


def edit_would_break_links(post: "db.BlogPost", new_slug: str) -> bool:
    """True when changing this post's slug would orphan a URL that has
    already been live (and therefore possibly indexed or linked to)."""
    return bool(post.last_published_at) and new_slug != post.slug


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_posts(status: str | None = None, category: str | None = None) -> list["db.BlogPost"]:
    """Newest first. published_at is NULL for drafts, so fall back to
    created_at for ordering rather than dropping them to the bottom."""
    with db.get_session() as s:
        q = s.query(db.BlogPost)
        if status:
            q = q.filter(db.BlogPost.status == status)
        if category:
            q = q.filter(db.BlogPost.category == category)
        posts = q.all()
    # Normalise to aware datetimes before sorting: Postgres returns naive
    # values for TIMESTAMP columns and comparing those against aware ones
    # raises, which would take the whole editor down over a sort key.
    _floor = datetime.min.replace(tzinfo=timezone.utc)
    posts.sort(key=lambda p: _aware(p.published_at or p.created_at) or _floor, reverse=True)
    return posts


def live_posts() -> list["db.BlogPost"]:
    """Posts that should currently be public: published, plus scheduled
    ones whose time has come. Scheduled posts go live the next time
    anything is published (or the scheduler task runs) -- see
    publish_due_scheduled_posts()."""
    now = _now()
    out = []
    for p in list_posts():
        if p.status == STATUS_PUBLISHED:
            out.append(p)
        elif p.status == STATUS_SCHEDULED and p.published_at and _aware(p.published_at) <= now:
            out.append(p)
    return out


def get_post(post_id: str) -> "db.BlogPost | None":
    with db.get_session() as s:
        return s.query(db.BlogPost).filter(db.BlogPost.id == post_id).first()


def get_post_by_slug(slug: str) -> "db.BlogPost | None":
    with db.get_session() as s:
        return s.query(db.BlogPost).filter(db.BlogPost.slug == slug).first()


def create_post(title: str, author_id: str | None = None, author_name: str = "") -> "db.BlogPost":
    with db.get_session() as s:
        post = db.BlogPost(
            slug=unique_slug(title),
            title=title or "Untitled post",
            status=STATUS_DRAFT,
            author_id=author_id,
            author_name=author_name or DEFAULT_AUTHOR,
        )
        s.add(post)
        s.commit()
        s.refresh(post)
        return post


def save_post(post_id: str, **fields) -> "db.BlogPost | None":
    """Updates only the fields passed. Unknown keys are ignored rather than
    raising, so the editor can pass a dict of widget values directly."""
    allowed = {
        "slug", "title", "excerpt", "body_md", "hero_image_key", "category",
        "tags", "status", "published_at", "seo_title", "seo_description",
        "author_name",
    }
    with db.get_session() as s:
        post = s.query(db.BlogPost).filter(db.BlogPost.id == post_id).first()
        if post is None:
            return None
        for key, value in fields.items():
            if key in allowed:
                setattr(post, key, value)
        post.updated_at = _now()
        s.commit()
        s.refresh(post)
        return post


def delete_post(post_id: str) -> None:
    with db.get_session() as s:
        post = s.query(db.BlogPost).filter(db.BlogPost.id == post_id).first()
        if post:
            s.delete(post)
            s.commit()


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

_IMAGE_EXT_BY_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}


def save_image(filename: str, content_type: str, data: bytes, alt_text: str = "") -> "db.BlogImage":
    """Stores an uploaded image and returns it. The generated key becomes
    part of the public URL, so it's slugified from the filename with a short
    uniquifier rather than using the raw upload name."""
    stem = slugify(os.path.splitext(filename or "image")[0]) or "image"
    ext = _IMAGE_EXT_BY_TYPE.get(content_type, "jpg")
    key = f"{stem}.{ext}"
    with db.get_session() as s:
        n = 1
        while s.query(db.BlogImage).filter(db.BlogImage.key == key).first() is not None:
            n += 1
            key = f"{stem}-{n}.{ext}"
        image = db.BlogImage(
            key=key,
            filename=filename or key,
            content_type=content_type or "image/jpeg",
            alt_text=alt_text,
            image_bytes=data,
        )
        s.add(image)
        s.commit()
        s.refresh(image)
        return image


def list_images() -> list["db.BlogImage"]:
    with db.get_session() as s:
        images = s.query(db.BlogImage).all()
    images.sort(key=lambda i: i.uploaded_at or datetime.min, reverse=True)
    return images


def get_image(key: str) -> "db.BlogImage | None":
    with db.get_session() as s:
        return s.query(db.BlogImage).filter(db.BlogImage.key == key).first()


def delete_image(key: str) -> None:
    with db.get_session() as s:
        image = s.query(db.BlogImage).filter(db.BlogImage.key == key).first()
        if image:
            s.delete(image)
            s.commit()


def image_url(key: str) -> str:
    return f"{SITE_ORIGIN}/blog/media/{key}" if key else ""


# ---------------------------------------------------------------------------
# Markdown -> HTML
# ---------------------------------------------------------------------------

def _md_to_html(text: str) -> str:
    """Renders post markdown. Uses the `markdown` package when available and
    falls back to a small built-in renderer otherwise, so a missing optional
    dependency degrades the formatting rather than taking the blog down."""
    text = text or ""
    try:
        import markdown as _markdown  # noqa: PLC0415 -- optional dependency
        return _markdown.markdown(
            text,
            extensions=["extra", "sane_lists", "smarty", "toc"],
            output_format="html5",
        )
    except Exception:
        return _fallback_md(text)


def _fallback_md(text: str) -> str:
    """Deliberately minimal: headings, paragraphs, lists, bold/italic,
    links, images, blockquotes, fenced code. Enough that a post is readable
    and correctly structured for search engines even without the markdown
    package installed."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    in_list = in_quote = in_code = False

    def close_blocks(except_code: bool = False) -> None:
        nonlocal in_list, in_quote
        if in_list:
            out.append("</ul>")
            in_list = False
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                close_blocks()
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(_escape(line))
            continue
        if not line.strip():
            close_blocks()
            continue
        heading = re.match(r"^(#{1,4})\s+(.*)$", line)
        if heading:
            close_blocks()
            level = len(heading.group(1)) + 1  # h1 is the post title
            out.append(f"<h{min(level, 6)}>{_inline_md(heading.group(2))}</h{min(level, 6)}>")
            continue
        if line.lstrip().startswith(("- ", "* ")):
            if not in_list:
                close_blocks()
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline_md(line.lstrip()[2:])}</li>")
            continue
        if line.lstrip().startswith("> "):
            if not in_quote:
                close_blocks()
                out.append("<blockquote>")
                in_quote = True
            out.append(f"<p>{_inline_md(line.lstrip()[2:])}</p>")
            continue
        close_blocks()
        out.append(f"<p>{_inline_md(line)}</p>")

    if in_code:
        out.append("</code></pre>")
    close_blocks()
    return "\n".join(out)


def _inline_md(text: str) -> str:
    text = _escape(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _attr(text: str) -> str:
    """Escape for use inside a double-quoted HTML attribute."""
    return _escape(text).replace("'", "&#39;")


def reading_minutes(body_md: str) -> int:
    words = len(re.findall(r"\w+", body_md or ""))
    return max(1, round(words / 220))


def _aware(dt: datetime) -> datetime:
    """Postgres hands back naive datetimes for TIMESTAMP columns; treat
    those as UTC so comparisons against _now() don't raise."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fmt_date(dt: datetime | None) -> str:
    return _aware(dt).strftime("%d %B %Y") if dt else ""


def _iso(dt: datetime | None) -> str:
    return _aware(dt).isoformat() if dt else ""


# ---------------------------------------------------------------------------
# Page templates
#
# These mirror landing/index.html's visual language deliberately -- same
# font, same custom properties, same .wrap/.feature-card shapes -- rather
# than importing its stylesheet, because index.html keeps all its CSS in an
# inline <style> block. If the landing page's palette changes, update
# _BASE_CSS to match.
# ---------------------------------------------------------------------------

_BASE_CSS = """
  :root{
    --ink:#111827;
    --blue:#1D4ED8;
    --blue-dark:#1E3A8A;
    --blue-tint:#EFF4FF;
    --accent:#F97316;
    --surface:#F6F6F4;
    --surface-2:#F0F0EE;
    --border:#E4E4E0;
    --text-muted:#5B6472;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{
    font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    color:var(--ink);line-height:1.6;background:#fff;font-weight:500;
  }
  a{color:inherit;}
  img{max-width:100%;height:auto;}
  .wrap{max-width:1120px;margin:0 auto;padding:0 24px;}
  nav.wrap{display:flex;align-items:center;justify-content:space-between;padding-top:20px;padding-bottom:20px;}
  .logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:1.05rem;}
  .logo img{width:28px;height:28px;}
  .nav-links{display:flex;align-items:center;gap:22px;font-size:.92rem;font-weight:600;}
  .nav-links a{text-decoration:none;color:var(--text-muted);}
  .nav-links a:hover{color:var(--ink);}
  .nav-cta{
    background:var(--blue);color:#fff;text-decoration:none;padding:10px 18px;
    border-radius:8px;font-weight:700;font-size:.9rem;
  }
  .site-footer{background:var(--ink);color:#9CA3AF;margin-top:80px;padding:48px 0 32px;font-size:.88rem;}
  .site-footer a{color:#9CA3AF;text-decoration:none;}
  .site-footer a:hover{color:#fff;}
  .footer-bottom{display:flex;flex-wrap:wrap;gap:16px;justify-content:space-between;
    border-top:1px solid rgba(255,255,255,.1);margin-top:28px;padding-top:20px;}
  .footer-links{display:flex;flex-wrap:wrap;gap:18px;}
"""

_POST_CSS = """
  /* The header shares the body's 44em measure so the title, standfirst and
     first paragraph all start on the same left edge. Without the max-width
     here the header stretches to .wrap's full 1120px while the body stays
     centred at 44em, and the text visibly steps inwards below the title. */
  .post-head{padding:48px 0 8px;max-width:44em;margin:0 auto;}
  .post-meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
    font-size:.82rem;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em;}
  .post-cat{background:var(--blue-tint);color:var(--blue-dark);padding:4px 12px;border-radius:999px;
    text-decoration:none;letter-spacing:.03em;}
  .post-title{font-size:clamp(2rem,4.4vw,3rem);font-weight:800;line-height:1.15;letter-spacing:-.02em;margin:18px 0 14px;}
  .post-standfirst{font-size:1.12rem;color:var(--text-muted);max-width:40em;}
  .post-hero{margin:34px 0 10px;border-radius:14px;overflow:hidden;border:1px solid var(--border);}
  .post-hero img{display:block;width:100%;}
  .post-body{max-width:44em;margin:34px auto 0;font-size:1.05rem;}
  .post-body h2{font-size:1.6rem;font-weight:800;letter-spacing:-.01em;margin:40px 0 12px;}
  .post-body h3{font-size:1.22rem;font-weight:700;margin:30px 0 10px;}
  .post-body p{margin:0 0 18px;}
  .post-body ul,.post-body ol{margin:0 0 18px 22px;}
  .post-body li{margin:0 0 8px;}
  .post-body a{color:var(--blue);text-decoration:underline;text-underline-offset:2px;}
  .post-body img{border-radius:12px;border:1px solid var(--border);margin:10px 0 22px;}
  .post-body blockquote{border-left:3px solid var(--blue);background:var(--surface);
    padding:14px 20px;margin:0 0 20px;border-radius:0 10px 10px 0;color:var(--text-muted);}
  .post-body blockquote p:last-child{margin:0;}
  .post-body pre{background:var(--ink);color:#E5E7EB;padding:16px 18px;border-radius:10px;
    overflow-x:auto;margin:0 0 20px;font-size:.88rem;}
  .post-body code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em;}
  .post-body :not(pre)>code{background:var(--surface-2);padding:2px 6px;border-radius:5px;}
  .post-body table{width:100%;border-collapse:collapse;margin:0 0 22px;font-size:.95rem;}
  .post-body th,.post-body td{border:1px solid var(--border);padding:10px 12px;text-align:left;}
  .post-body th{background:var(--surface);font-weight:700;}
  .post-cta{max-width:44em;margin:44px auto 0;background:var(--surface);border:1px solid var(--border);
    border-radius:14px;padding:28px 30px;text-align:center;}
  .post-cta h2{font-size:1.3rem;font-weight:800;margin-bottom:8px;}
  .post-cta p{color:var(--text-muted);margin-bottom:18px;font-size:.98rem;}
  .btn-primary{background:var(--blue);color:#fff;text-decoration:none;padding:13px 26px;
    border-radius:9px;font-weight:700;display:inline-block;}
  .post-more{max-width:44em;margin:52px auto 0;}
  .post-more h2{font-size:1.1rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;
    color:var(--text-muted);margin-bottom:16px;}
  .post-more ul{list-style:none;}
  .post-more li{border-top:1px solid var(--border);padding:14px 0;}
  .post-more a{text-decoration:none;font-weight:700;}
  .post-more a:hover{color:var(--blue);}
"""

_LIST_CSS = """
  .blog-head{padding:52px 0 8px;text-align:center;}
  .blog-head h1{font-size:clamp(2rem,4vw,2.6rem);font-weight:800;letter-spacing:-.02em;}
  .blog-head p{color:var(--text-muted);margin-top:10px;font-size:1.05rem;}
  .cat-row{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:26px 0 8px;}
  .cat-chip{border:1px solid var(--border);background:#fff;color:var(--text-muted);
    padding:7px 16px;border-radius:999px;font-size:.86rem;font-weight:700;text-decoration:none;}
  .cat-chip:hover{border-color:var(--blue);color:var(--blue);}
  .cat-chip.is-active{background:var(--blue);border-color:var(--blue);color:#fff;}
  .post-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:26px;
    margin:36px 0 20px;}
  .post-card{border:1px solid var(--border);border-radius:14px;overflow:hidden;background:#fff;
    display:flex;flex-direction:column;text-decoration:none;transition:box-shadow .18s,transform .18s;}
  .post-card:hover{box-shadow:0 10px 30px rgba(17,24,39,.09);transform:translateY(-2px);}
  .post-card-img{aspect-ratio:16/9;background:var(--surface-2);overflow:hidden;}
  .post-card-img img{width:100%;height:100%;object-fit:cover;display:block;}
  .post-card-body{padding:20px 22px 24px;display:flex;flex-direction:column;gap:9px;flex:1;}
  .post-card-cat{font-size:.74rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--blue);}
  .post-card h2{font-size:1.12rem;font-weight:800;line-height:1.35;letter-spacing:-.01em;}
  .post-card p{color:var(--text-muted);font-size:.93rem;flex:1;}
  .post-card-meta{color:var(--text-muted);font-size:.8rem;font-weight:600;}
  .blog-empty{text-align:center;color:var(--text-muted);padding:60px 0 20px;}
"""


def _nav_html() -> str:
    return f"""<nav class="wrap">
  <div class="logo"><a href="{SITE_ORIGIN}/" style="display:flex;align-items:center;gap:10px;text-decoration:none;">
    <img src="{SITE_ORIGIN}/assets/logo_mark.png" alt="CivilProposals" width="28" height="28"> CivilProposals</a></div>
  <div class="nav-links">
    <a href="/blog/">Blog</a>
    <a href="{SITE_ORIGIN}/#pricing">Pricing</a>
    <a class="nav-cta" href="https://app.civilproposals.com">Try it free</a>
  </div>
</nav>"""


def _footer_html() -> str:
    year = _now().year
    return f"""<footer class="site-footer">
  <div class="wrap">
    <div class="logo" style="color:#fff;"><img src="{SITE_ORIGIN}/assets/logo_mark.png" alt="" width="28" height="28"> CivilProposals</div>
    <p style="margin-top:10px;max-width:46em;">AI-assisted tender &amp; proposal preparation, built for civil engineering firms.</p>
    <div class="footer-bottom">
      <div class="footer-links">
        <a href="{SITE_ORIGIN}/">Home</a>
        <a href="/blog/">Blog</a>
        <a href="{SITE_ORIGIN}/security.html">Security &amp; Data Handling</a>
        <a href="{SITE_ORIGIN}/privacy-policy.html">Privacy Policy</a>
        <a href="{SITE_ORIGIN}/terms-of-service.html">Terms of Service</a>
      </div>
      <div>Copyright &copy; {year} CivilProposals. All rights reserved.</div>
    </div>
  </div>
</footer>"""


_ANALYTICS = ('<script defer data-domain="civilproposals.com" '
              'src="https://plausible.io/js/script.tagged-events.js"></script>')

_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
          '<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800'
          '&display=swap" rel="stylesheet">')


def _head(title: str, description: str, canonical: str, og_image: str,
          og_type: str = "website", extra_css: str = "", jsonld: str = "",
          noindex: bool = False) -> str:
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    if og_image:
        image_tags = (f'<meta property="og:image" content="{_attr(og_image)}">\n'
                      f'<meta name="twitter:image" content="{_attr(og_image)}">\n'
                      '<meta name="twitter:card" content="summary_large_image">')
    else:
        image_tags = '<meta name="twitter:card" content="summary">'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape(title)}</title>
<meta name="description" content="{_attr(description)}">
<link rel="canonical" href="{_attr(canonical)}">
{robots}
<link rel="icon" type="image/png" sizes="32x32" href="{SITE_ORIGIN}/assets/favicon-32.png">
<link rel="apple-touch-icon" href="{SITE_ORIGIN}/assets/apple-touch-icon.png">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="CivilProposals">
<meta property="og:title" content="{_attr(title)}">
<meta property="og:description" content="{_attr(description)}">
<meta property="og:url" content="{_attr(canonical)}">
<meta name="twitter:title" content="{_attr(title)}">
<meta name="twitter:description" content="{_attr(description)}">
{image_tags}
{jsonld}
{_FONTS}
{_ANALYTICS}
<style>{_BASE_CSS}{extra_css}</style>
</head>
<body>
{_nav_html()}"""


def render_post_html(post: "db.BlogPost", related: list["db.BlogPost"] | None = None) -> str:
    """The full standalone HTML page for one post."""
    canonical = f"{SITE_ORIGIN}/blog/{post.slug}/"
    title = (post.seo_title or "").strip() or f"{post.title} | CivilProposals"
    description = (post.seo_description or "").strip() or (post.excerpt or "").strip()
    hero = image_url(post.hero_image_key)
    cat_label = CATEGORY_LABELS.get(post.category, "")
    minutes = reading_minutes(post.body_md)

    # Only facts we actually hold go in the structured data -- no invented
    # ratings or review counts, same discipline as index.html's JSON-LD.
    # Built outside the f-string: an expression containing a backslash
    # inside an f-string is a SyntaxError before Python 3.12.
    image_line = (",\n  \"image\": " + _json_str(hero)) if hero else ""
    jsonld = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": {_json_str(post.title)},
  "description": {_json_str(description)},
  "datePublished": {_json_str(_iso(post.published_at))},
  "dateModified": {_json_str(_iso(post.updated_at or post.published_at))},
  "author": {{"@type": "Organization", "name": {_json_str(post.author_name or DEFAULT_AUTHOR)}}},
  "publisher": {{
    "@type": "Organization",
    "name": "CivilProposals",
    "logo": {{"@type": "ImageObject", "url": {_json_str(SITE_ORIGIN + '/assets/logo_mark.png')}}}
  }},
  "mainEntityOfPage": {{"@type": "WebPage", "@id": {_json_str(canonical)}}}{image_line}
}}
</script>"""

    hero_html = ""
    if hero:
        hero_html = (f'<div class="post-hero"><img src="{_attr(hero)}" '
                     f'alt="{_attr(post.title)}" loading="eager" fetchpriority="high"></div>')

    cat_html = ""
    if cat_label:
        cat_html = (f'<a class="post-cat" href="/blog/category/{_attr(post.category)}/">'
                    f'{_escape(cat_label)}</a>')

    related_html = ""
    if related:
        items = "\n".join(
            f'      <li><a href="/blog/{_attr(r.slug)}/">{_escape(r.title)}</a></li>'
            for r in related
        )
        related_html = f"""
  <section class="post-more">
    <h2>Keep reading</h2>
    <ul>
{items}
    </ul>
  </section>"""

    return f"""{_head(title, description, canonical, hero, "article", _POST_CSS, jsonld)}

<article>
  <header class="post-head wrap">
    <div class="post-meta">
      {cat_html}
      <span>{_escape(_fmt_date(post.published_at))}</span>
      <span>{minutes} min read</span>
    </div>
    <h1 class="post-title">{_escape(post.title)}</h1>
    <p class="post-standfirst">{_escape(post.excerpt or "")}</p>
    {hero_html}
  </header>

  <div class="post-body wrap">
{_md_to_html(post.body_md)}
  </div>

  <aside class="post-cta wrap">
    <h2>Turn your next brief into a draft</h2>
    <p>CivilProposals extracts the requirements, builds a weighted structure and drafts a first pass Word document. Your first bid is free.</p>
    <a class="btn-primary plausible-event-name=CTA+Click plausible-event-position=blog-{_attr(post.slug)}"
       href="https://app.civilproposals.com">Upload your first brief free</a>
  </aside>
{related_html}
</article>

{_footer_html()}
</body>
</html>"""


def _card_html(post: "db.BlogPost") -> str:
    hero = image_url(post.hero_image_key)
    cat_label = CATEGORY_LABELS.get(post.category, "")
    img = (f'<div class="post-card-img"><img src="{_attr(hero)}" alt="" loading="lazy"></div>'
           if hero else "")
    cat = f'<span class="post-card-cat">{_escape(cat_label)}</span>' if cat_label else ""
    return f"""    <a class="post-card" href="/blog/{_attr(post.slug)}/">
      {img}
      <div class="post-card-body">
        {cat}
        <h2>{_escape(post.title)}</h2>
        <p>{_escape(post.excerpt or "")}</p>
        <span class="post-card-meta">{_escape(_fmt_date(post.published_at))} &middot; {reading_minutes(post.body_md)} min read</span>
      </div>
    </a>"""


def render_index_html(posts: list["db.BlogPost"], category: str | None = None) -> str:
    """The /blog/ listing, or a /blog/category/<slug>/ listing."""
    cat_label = CATEGORY_LABELS.get(category or "", "")
    if category:
        canonical = f"{SITE_ORIGIN}/blog/category/{category}/"
        title = f"{cat_label} | CivilProposals blog"
        heading = cat_label
        description = (f"Articles on {cat_label.lower()} for civil engineering firms "
                       f"writing tenders and fee proposals.")
    else:
        canonical = f"{SITE_ORIGIN}/blog/"
        title = "Blog: tendering, fees and bid strategy for civil engineers | CivilProposals"
        heading = "Notes on winning civil work"
        description = ("Practical writing on tendering, fee proposals and bid strategy for "
                       "civil engineering firms, from the team building CivilProposals.")

    chips = [f'<a class="cat-chip{"" if category else " is-active"}" href="/blog/">All</a>']
    for slug, label in CATEGORIES:
        active = " is-active" if slug == category else ""
        chips.append(f'<a class="cat-chip{active}" href="/blog/category/{slug}/">{_escape(label)}</a>')

    if posts:
        body = ('  <div class="wrap"><div class="post-grid">\n'
                + "\n".join(_card_html(p) for p in posts)
                + "\n  </div></div>")
    else:
        body = ('  <div class="wrap"><p class="blog-empty">No posts here yet -- '
                'check back shortly.</p></div>')

    return f"""{_head(title, description, canonical, "", "website", _LIST_CSS)}

<header class="blog-head wrap">
  <h1>{_escape(heading)}</h1>
  <p>{_escape(description)}</p>
  <div class="cat-row">
    {"".join(chips)}
  </div>
</header>

{body}

{_footer_html()}
</body>
</html>"""


def render_home_cards_html(posts: list["db.BlogPost"]) -> str:
    """Just the inner HTML of the homepage's blog strip -- the Worker splices
    this into index.html's <div id="blog-cards"> with HTMLRewriter, so the
    homepage never needs rebuilding when a post goes live."""
    if not posts:
        return ""
    return "\n".join(_card_html(p) for p in posts[:3])


def render_404_html() -> str:
    return f"""{_head("Post not found | CivilProposals", "That post doesn't exist.",
                      f"{SITE_ORIGIN}/blog/", "", "website", _LIST_CSS, noindex=True)}
<header class="blog-head wrap">
  <h1>We couldn't find that post</h1>
  <p>It may have moved, or the link may be wrong.</p>
  <div class="cat-row"><a class="cat-chip is-active" href="/blog/">Back to the blog</a></div>
</header>
{_footer_html()}
</body>
</html>"""


def _json_str(value: str) -> str:
    """JSON string literal, safe to embed in a <script> block."""
    import json
    return json.dumps(str(value or "")).replace("</", "<\\/")


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

# The static landing/sitemap.xml lists only the homepage and security.html
# (the legal pages carry noindex on purpose -- see the comment in that file).
# Once the blog exists the sitemap has to be generated, because posts appear
# and disappear without a redeploy. The Worker serves this generated version
# in preference to the static file.
def render_sitemap_xml(posts: list["db.BlogPost"]) -> str:
    entries = [
        f"""  <url>
    <loc>{SITE_ORIGIN}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{SITE_ORIGIN}/blog/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{SITE_ORIGIN}/security.html</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>"""
    ]
    used_categories = {p.category for p in posts if p.category}
    for slug, _label in CATEGORIES:
        if slug in used_categories:
            entries.append(f"""  <url>
    <loc>{SITE_ORIGIN}/blog/category/{slug}/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.5</priority>
  </url>""")
    for post in posts:
        lastmod = _aware(post.updated_at or post.published_at)
        lastmod_tag = f"\n    <lastmod>{lastmod.date().isoformat()}</lastmod>" if lastmod else ""
        entries.append(f"""  <url>
    <loc>{SITE_ORIGIN}/blog/{post.slug}/</loc>{lastmod_tag}
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")
    body = "\n".join(entries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by app/modules/blog.py at publish time and served from KV by
     landing/_worker.js. The static landing/sitemap.xml is the fallback used
     before anything has ever been published. Legal pages stay out on
     purpose: they carry noindex, and listing noindex URLs in a sitemap just
     produces "Submitted URL marked noindex" warnings in Search Console. -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>"""


# ---------------------------------------------------------------------------
# Publishing -- pushing rendered pages to the Worker's KV store
# ---------------------------------------------------------------------------

class PublishError(RuntimeError):
    pass


def _push(kind: str, payload: dict) -> None:
    """One authenticated call to the Worker's publish API.

    Raises PublishError with a readable message on any failure -- the editor
    surfaces it directly, because a publish that silently half-worked is far
    worse than one that visibly failed."""
    if not is_publishing_configured():
        raise PublishError(
            "Publishing isn't configured: set BLOG_PUBLISH_SECRET (and optionally "
            "BLOG_PUBLISH_URL) on the app, matching the Worker's own "
            "`wrangler secret put BLOG_PUBLISH_SECRET`."
        )
    try:
        resp = requests.post(
            f"{PUBLISH_URL}/{kind}",
            json=payload,
            headers={"Authorization": f"Bearer {PUBLISH_SECRET}"},
            timeout=PUBLISH_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise PublishError(f"Couldn't reach the site to publish: {exc}") from exc
    if resp.status_code == 401:
        raise PublishError("The site rejected the publish key -- BLOG_PUBLISH_SECRET doesn't match the Worker's.")
    if not resp.ok:
        raise PublishError(f"Publish failed ({resp.status_code}): {resp.text[:300]}")


def push_page(path: str, html: str) -> None:
    _push("page", {"path": path, "html": html})


def remove_page(path: str) -> None:
    _push("remove", {"path": path})


def push_asset(key: str, content_type: str, data: bytes) -> None:
    _push("asset", {
        "key": key,
        "contentType": content_type,
        "base64": base64.b64encode(data).decode("ascii"),
    })


def push_raw(path: str, content_type: str, body: str) -> None:
    _push("raw", {"path": path, "contentType": content_type, "body": body})


def _related_for(post: "db.BlogPost", pool: list["db.BlogPost"], limit: int = 3) -> list["db.BlogPost"]:
    """Same category first, then anything else recent. Never the post itself."""
    others = [p for p in pool if p.id != post.id]
    same = [p for p in others if p.category and p.category == post.category]
    rest = [p for p in others if p not in same]
    return (same + rest)[:limit]


def publish_all(status_callback=None) -> dict:
    """Re-renders and pushes the entire public blog: every live post, the
    listing, every category listing, the homepage cards, and the sitemap.

    Full re-push rather than incremental on purpose -- the whole blog is a
    few dozen small documents, a complete push takes seconds, and it makes
    the live site exactly reproducible from the database instead of the
    accumulated result of a series of partial updates that might have
    half-failed months ago.

    Returns a summary dict for the editor to display."""
    def say(msg: str) -> None:
        if status_callback:
            status_callback(msg)

    posts = live_posts()

    # Images first: a post page that goes live referencing an image that
    # hasn't been pushed yet would show a broken hero until the next
    # publish.
    say("Uploading images...")
    needed_keys = {p.hero_image_key for p in posts if p.hero_image_key}
    for md_key in _image_keys_in_bodies(posts):
        needed_keys.add(md_key)
    pushed_images = 0
    for key in sorted(k for k in needed_keys if k):
        image = get_image(key)
        if image is None:
            continue
        push_asset(image.key, image.content_type, image.image_bytes)
        pushed_images += 1

    say(f"Publishing {len(posts)} post(s)...")
    for post in posts:
        push_page(f"/blog/{post.slug}/", render_post_html(post, _related_for(post, posts)))

    say("Rebuilding the listing...")
    push_page("/blog/", render_index_html(posts))
    for slug, _label in CATEGORIES:
        in_cat = [p for p in posts if p.category == slug]
        if in_cat:
            push_page(f"/blog/category/{slug}/", render_index_html(in_cat, category=slug))
        else:
            remove_page(f"/blog/category/{slug}/")

    say("Updating the homepage strip and sitemap...")
    push_raw("__cards__", "text/html", render_home_cards_html(posts))
    push_raw("/sitemap.xml", "application/xml", render_sitemap_xml(posts))

    # A styled 404 for /blog/<something-that-does-not-exist>/. Without this
    # the Worker falls back to plain text, which is what a mistyped or
    # retired post URL would otherwise show.
    push_page("/blog/404/", render_404_html())

    # Any post that is no longer live must stop being served. Cheap to do
    # unconditionally: one small delete per non-live post.
    live_slugs = {p.slug for p in posts}
    removed = 0
    for post in list_posts():
        if post.slug not in live_slugs:
            remove_page(f"/blog/{post.slug}/")
            removed += 1

    now = _now()
    with db.get_session() as s:
        for post in s.query(db.BlogPost).filter(db.BlogPost.slug.in_(live_slugs or [""])).all():
            post.last_published_at = now
            # A scheduled post whose time has passed is now simply published.
            if post.status == STATUS_SCHEDULED:
                post.status = STATUS_PUBLISHED
        s.commit()

    say("Done.")
    return {
        "posts": len(posts),
        "images": pushed_images,
        "removed": removed,
        "at": now,
    }


def _image_keys_in_bodies(posts: list["db.BlogPost"]) -> set[str]:
    """Image keys referenced from inside post markdown via /blog/media/<key>."""
    keys: set[str] = set()
    for post in posts:
        for match in re.finditer(r"/blog/media/([A-Za-z0-9._-]+)", post.body_md or ""):
            keys.add(match.group(1))
    return keys


def publish_due_scheduled_posts() -> int:
    """Publishes any scheduled post whose time has arrived. Safe to call on
    a timer (or on app startup); returns how many went live."""
    now = _now()
    due = [p for p in list_posts(status=STATUS_SCHEDULED)
           if p.published_at and _aware(p.published_at) <= now]
    if not due:
        return 0
    publish_all()
    return len(due)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def fetch_stats(days: int = 30) -> dict:
    """Per-post view counts from the Worker's own first-party counter.

    This is deliberately a second, independent source alongside Plausible:
    ad blockers commonly block plausible.io, so its numbers under-report by
    an unknown margin, while a counter incremented inside the Worker sees
    every request that reaches the edge. Neither is perfect -- the KV
    counter can lose increments under burst traffic (see _worker.js) -- so
    the admin panel shows them side by side rather than pretending either
    is exact."""
    if not is_publishing_configured():
        return {"error": "Publishing isn't configured, so stats aren't available yet.", "posts": []}
    try:
        resp = requests.get(
            f"{PUBLISH_URL}/stats",
            params={"days": days},
            headers={"Authorization": f"Bearer {PUBLISH_SECRET}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        return {"error": f"Couldn't reach the site for stats: {exc}", "posts": []}
    if not resp.ok:
        return {"error": f"Stats request failed ({resp.status_code}).", "posts": []}
    try:
        return resp.json()
    except ValueError:
        return {"error": "The site returned an unreadable stats response.", "posts": []}
