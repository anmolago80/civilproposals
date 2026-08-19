"""
modules/pages/15_admin_blog.py

The blog editor. Runs as an ordered page segment (see app.py's docstring --
these files are exec'd in one shared namespace, they are NOT importable
modules), positioned after 10_state_helpers.py and BEFORE 20_chrome.py.

Why before the chrome: when blog mode is active this segment renders the
editor full-width and then st.stop()s, so the sidebar and the ten workflow
tabs never get built at all. Sitting after 20_chrome.py instead would leave
an empty tab bar stranded above the editor. Everything it needs
(current_user, IS_SAAS_MODE, auth, db) is already defined by 00_init.py.

Entering blog mode: the "Write / edit blog" button in the sidebar sets
st.session_state._blog_admin_mode and reruns, or the URL ?admin=blog does
the same thing directly. Leaving it: the "Back to the app" button here.

Everything in this file is behind auth.is_admin_user(). A non-admin who
guesses the query parameter falls straight through to the normal app.
"""

import streamlit as st

from modules import blog

# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

_blog_admin_allowed = bool(IS_SAAS_MODE and current_user and auth.is_admin_user(current_user))  # noqa: F821

if _blog_admin_allowed and st.query_params.get("admin") == "blog":
    st.session_state._blog_admin_mode = True

if _blog_admin_allowed and st.session_state.get("_blog_admin_mode"):

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _exit_blog_mode() -> None:
        st.session_state._blog_admin_mode = False
        st.session_state.pop("_blog_editing_id", None)
        try:
            if "admin" in st.query_params:
                del st.query_params["admin"]
        except Exception:
            pass

    def _status_badge(post) -> str:
        if blog.has_unpublished_changes(post):
            return "🟠 Published (unsaved edits)"
        return {
            blog.STATUS_DRAFT: "⚪ Draft",
            blog.STATUS_SCHEDULED: "🕒 Scheduled",
            blog.STATUS_PUBLISHED: "🟢 Published",
            blog.STATUS_UNPUBLISHED: "🔴 Unpublished",
        }.get(post.status, post.status)

    def _publish_now(spinner_label: str = "Publishing...") -> None:
        """Full re-push of the public blog, with the outcome surfaced
        plainly -- a publish that half-worked is worse than one that
        visibly failed, so errors are shown, never swallowed."""
        try:
            with st.spinner(spinner_label):
                result = blog.publish_all()
        except blog.PublishError as exc:
            st.error(f"**Publish failed.** {exc}")
            return
        except Exception as exc:  # noqa: BLE001 -- last-resort guard
            st.error(f"**Publish failed unexpectedly:** {exc}")
            return
        bits = [f"{result['posts']} post(s) live", f"{result['images']} image(s)"]
        if result["removed"]:
            bits.append(f"{result['removed']} removed")
        st.success("Published — " + ", ".join(bits) + ".")

    # -----------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------

    _hl, _hr = st.columns([4, 1])
    with _hl:
        st.markdown("## Blog")
        st.caption(
            "Posts are stored in the database here, and pushed as finished pages to the "
            "live site when you publish. Readers never touch this app, so the blog stays "
            "up even when this service is redeploying."
        )
    with _hr:
        st.write("")
        if st.button("← Back to the app", use_container_width=True, key="_blog_exit"):
            _exit_blog_mode()
            st.rerun()

    if not blog.is_publishing_configured():
        st.warning(
            "**Publishing isn't switched on yet.** You can write and save posts now, but "
            "nothing can go live until `BLOG_PUBLISH_SECRET` is set on this service and "
            "matches the Worker's own secret (`wrangler secret put BLOG_PUBLISH_SECRET`). "
            "See BLOG_SETUP.md."
        )

    _tab_posts, _tab_editor, _tab_media, _tab_stats = st.tabs(
        ["📄 Posts", "✍️ Write", "🖼️ Images", "📈 Stats"]
    )

    # -----------------------------------------------------------------
    # Posts list
    # -----------------------------------------------------------------

    with _tab_posts:
        _c1, _c2 = st.columns([3, 1])
        with _c1:
            _new_title = st.text_input(
                "New post title", key="_blog_new_title",
                placeholder="How to price a civil engineering tender",
            )
        with _c2:
            st.write("")
            st.write("")
            if st.button("Create draft", type="primary", use_container_width=True, key="_blog_create"):
                if not _new_title.strip():
                    st.warning("Give it a title first — you can change it later.")
                else:
                    _post = blog.create_post(
                        _new_title.strip(),
                        author_id=current_user.id,  # noqa: F821
                        author_name=blog.DEFAULT_AUTHOR,
                    )
                    st.session_state._blog_editing_id = _post.id
                    st.session_state._blog_new_title = ""
                    st.success(f"Draft created at /blog/{_post.slug}/ — open the Write tab.")
                    st.rerun()

        st.divider()

        _all_posts = blog.list_posts()
        if not _all_posts:
            st.info("No posts yet. Create your first draft above.")
        else:
            for _p in _all_posts:
                _row = st.container(border=True)
                with _row:
                    _a, _b, _c = st.columns([5, 2, 2])
                    with _a:
                        st.markdown(f"**{_p.title}**")
                        st.caption(
                            f"/blog/{_p.slug}/ · {blog.CATEGORY_LABELS.get(_p.category, 'No category')}"
                            + (f" · {_p.published_at:%d %b %Y}" if _p.published_at else "")
                        )
                    with _b:
                        st.write(_status_badge(_p))
                    with _c:
                        if st.button("Edit", key=f"_blog_edit_{_p.id}", use_container_width=True):
                            st.session_state._blog_editing_id = _p.id
                            st.rerun()

            st.divider()
            _pc1, _pc2 = st.columns([1, 3])
            with _pc1:
                if st.button("🚀 Publish site", type="primary", use_container_width=True,
                             key="_blog_publish_all",
                             disabled=not blog.is_publishing_configured()):
                    _publish_now("Re-rendering and publishing the whole blog...")
            with _pc2:
                st.caption(
                    "Re-renders every live post, the listing, the category pages, the "
                    "homepage strip and the sitemap. Safe to run any time — it rebuilds "
                    "from the database rather than patching what's already there."
                )

    # -----------------------------------------------------------------
    # Editor
    # -----------------------------------------------------------------

    with _tab_editor:
        _editing_id = st.session_state.get("_blog_editing_id")
        _post = blog.get_post(_editing_id) if _editing_id else None

        if _post is None:
            st.info("Pick a post on the Posts tab, or create a new draft there.")
        else:
            st.markdown(f"#### {_post.title}")
            st.caption(f"{_status_badge(_post)} · last saved {_post.updated_at:%d %b %Y %H:%M} UTC")

            _title = st.text_input("Title", value=_post.title, key=f"_bt_{_post.id}")
            _slug = st.text_input(
                "URL slug", value=_post.slug, key=f"_bs_{_post.id}",
                help="The permanent public address: /blog/<slug>/. Pick the phrase you want "
                     "to rank for, not the headline you happen to like.",
            )
            st.caption(f"→ `{blog.SITE_ORIGIN}/blog/{blog.slugify(_slug) or _post.slug}/`")

            if blog.edit_would_break_links(_post, blog.slugify(_slug)):
                st.warning(
                    "This post has already been live at its current address. Changing the "
                    "slug will break any existing link or search result pointing at the old "
                    "one — the old URL will start returning a 404."
                )

            _excerpt = st.text_area(
                "Excerpt", value=_post.excerpt or "", height=80, key=f"_be_{_post.id}",
                help="Shown on the cards and used as the meta description when no SEO "
                     "description is set. Two sentences is about right.",
            )

            _cc1, _cc2 = st.columns(2)
            with _cc1:
                _cat_slugs = [""] + [s for s, _ in blog.CATEGORIES]
                _cat_index = _cat_slugs.index(_post.category) if _post.category in _cat_slugs else 0
                _category = st.selectbox(
                    "Category", _cat_slugs, index=_cat_index, key=f"_bc_{_post.id}",
                    format_func=lambda s: blog.CATEGORY_LABELS.get(s, "— none —"),
                )
            with _cc2:
                _tags = st.text_input(
                    "Tags", value=_post.tags or "", key=f"_bg_{_post.id}",
                    help="Comma separated, free-form. Used for related-post links.",
                )

            _images = blog.list_images()
            _image_keys = [""] + [i.key for i in _images]
            _hero_index = _image_keys.index(_post.hero_image_key) if _post.hero_image_key in _image_keys else 0
            _hero = st.selectbox(
                "Hero image", _image_keys, index=_hero_index, key=f"_bh_{_post.id}",
                format_func=lambda k: k or "— none —",
                help="Also used as the social sharing image. Upload new ones on the Images tab.",
            )
            if _hero:
                _img = blog.get_image(_hero)
                if _img:
                    st.image(_img.image_bytes, width=320)

            _body = st.text_area(
                "Body (markdown)", value=_post.body_md or "", height=420, key=f"_bb_{_post.id}",
                help="Markdown. Use ## for section headings — the post title is already the "
                     "h1, so starting at ## keeps the heading order valid.",
            )

            with st.expander("SEO overrides (optional)"):
                _seo_title = st.text_input(
                    "SEO title", value=_post.seo_title or "", key=f"_bst_{_post.id}",
                    placeholder=f"{_post.title} | CivilProposals",
                )
                _seo_desc = st.text_area(
                    "SEO description", value=_post.seo_description or "", height=70,
                    key=f"_bsd_{_post.id}", placeholder="Falls back to the excerpt above.",
                )

            with st.expander("Preview", expanded=False):
                st.caption("Rendered body only — the real page adds the header, hero and CTA.")
                st.markdown(_body or "_Nothing written yet._")

            st.divider()

            _s1, _s2, _s3, _s4 = st.columns(4)

            def _collect() -> dict:
                return {
                    "title": _title.strip() or "Untitled post",
                    "excerpt": _excerpt.strip(),
                    "body_md": _body,
                    "category": _category,
                    "tags": _tags.strip(),
                    "hero_image_key": _hero,
                    "seo_title": _seo_title.strip(),
                    "seo_description": _seo_desc.strip(),
                }

            with _s1:
                if st.button("💾 Save draft", use_container_width=True, key=f"_bsave_{_post.id}"):
                    _new_slug = blog.slugify(_slug)
                    _ok, _why = blog.slug_is_valid(_new_slug)
                    if not _ok:
                        st.error(_why)
                    else:
                        _fields = _collect()
                        if _new_slug != _post.slug:
                            _fields["slug"] = blog.unique_slug(_new_slug, exclude_id=_post.id)
                        blog.save_post(_post.id, **_fields)
                        st.success("Saved.")
                        st.rerun()

            with _s2:
                _pub_disabled = not blog.is_publishing_configured()
                if st.button("🚀 Publish", type="primary", use_container_width=True,
                             key=f"_bpub_{_post.id}", disabled=_pub_disabled):
                    _new_slug = blog.slugify(_slug)
                    _ok, _why = blog.slug_is_valid(_new_slug)
                    if not _ok:
                        st.error(_why)
                    elif not _excerpt.strip():
                        st.error("Add an excerpt first — it's the card text and the meta description.")
                    else:
                        _fields = _collect()
                        if _new_slug != _post.slug:
                            _fields["slug"] = blog.unique_slug(_new_slug, exclude_id=_post.id)
                        _fields["status"] = blog.STATUS_PUBLISHED
                        _fields["published_at"] = _post.published_at or blog.now_utc()
                        blog.save_post(_post.id, **_fields)
                        _publish_now()
                        st.rerun()

            with _s3:
                if _post.status in (blog.STATUS_PUBLISHED, blog.STATUS_SCHEDULED):
                    if st.button("Unpublish", use_container_width=True, key=f"_bunp_{_post.id}"):
                        blog.save_post(_post.id, status=blog.STATUS_UNPUBLISHED)
                        _publish_now("Removing from the live site...")
                        st.rerun()
                else:
                    with st.popover("🕒 Schedule", use_container_width=True):
                        _d = st.date_input("Publish on", key=f"_bsd8_{_post.id}")
                        _t = st.time_input("at (UTC)", key=f"_bst8_{_post.id}")
                        if st.button("Set schedule", key=f"_bsch_{_post.id}"):
                            from datetime import datetime as _dt, timezone as _tz
                            blog.save_post(
                                _post.id,
                                status=blog.STATUS_SCHEDULED,
                                published_at=_dt.combine(_d, _t).replace(tzinfo=_tz.utc),
                                **_collect(),
                            )
                            st.success("Scheduled. It goes live at the next publish after that time.")
                            st.rerun()

            with _s4:
                with st.popover("🗑️ Delete", use_container_width=True):
                    st.write("Delete this post permanently? This can't be undone.")
                    if st.button("Yes, delete it", key=f"_bdel_{_post.id}"):
                        _was_live = _post.status in (blog.STATUS_PUBLISHED, blog.STATUS_SCHEDULED)
                        blog.delete_post(_post.id)
                        st.session_state.pop("_blog_editing_id", None)
                        if _was_live and blog.is_publishing_configured():
                            _publish_now("Removing from the live site...")
                        st.rerun()

    # -----------------------------------------------------------------
    # Images
    # -----------------------------------------------------------------

    with _tab_media:
        st.caption(
            "Images live in the database and are pushed to the live site when you publish — "
            "so adding one needs no redeploy. Reference them in a post body with "
            "`![alt text](/blog/media/<key>)`."
        )
        _upload = st.file_uploader(
            "Upload an image", type=["jpg", "jpeg", "png", "webp", "gif"],
            key="_blog_upload",
        )
        if _upload is not None:
            _alt = st.text_input("Alt text (describe the image)", key="_blog_upload_alt")
            if st.button("Add image", type="primary", key="_blog_upload_go"):
                _img = blog.save_image(
                    _upload.name, _upload.type or "image/jpeg", _upload.getvalue(), _alt.strip()
                )
                st.success(f"Added as `{_img.key}` — publish to push it live.")
                st.rerun()

        st.divider()
        _images = blog.list_images()
        if not _images:
            st.info("No images uploaded yet.")
        else:
            _cols = st.columns(3)
            for _i, _img in enumerate(_images):
                with _cols[_i % 3]:
                    st.image(_img.image_bytes, use_container_width=True)
                    st.code(f"![{_img.alt_text or 'image'}](/blog/media/{_img.key})", language="markdown")
                    if st.button("Delete", key=f"_bimgdel_{_img.key}", use_container_width=True):
                        blog.delete_image(_img.key)
                        st.rerun()

    # -----------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------

    with _tab_stats:
        st.caption(
            "Views counted by the site's own edge counter — it sees every request that "
            "reaches Cloudflare, including from readers whose ad blocker blocks Plausible. "
            "It can lose a few counts under sudden bursts, so treat these as close, not exact."
        )
        _days = st.selectbox("Period", [7, 30, 90], index=1, key="_blog_stats_days",
                             format_func=lambda d: f"Last {d} days")
        if st.button("Refresh", key="_blog_stats_refresh"):
            st.rerun()

        _stats = blog.fetch_stats(days=_days)
        if _stats.get("error"):
            st.warning(_stats["error"])
        else:
            _rows = _stats.get("posts", [])
            _total = sum(r.get("views", 0) for r in _rows)
            _m1, _m2 = st.columns(2)
            _m1.metric(f"Blog views (last {_days} days)", _total)
            _m2.metric("Posts live", len(blog.live_posts()))
            if _rows:
                _titles = {p.slug: p.title for p in blog.list_posts()}
                st.dataframe(
                    [
                        {
                            "Post": _titles.get(r.get("slug", ""), r.get("slug", "")),
                            "URL": f"/blog/{r.get('slug','')}/",
                            "Views": r.get("views", 0),
                        }
                        for r in sorted(_rows, key=lambda r: r.get("views", 0), reverse=True)
                    ],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("No views recorded yet in this period.")

        st.divider()
        st.markdown("##### The other two sources worth watching")
        st.markdown(
            "- **Plausible** — where readers came from (Google, LinkedIn, direct) and which "
            "CTAs they clicked. The landing page and every post are already tagged; it starts "
            "collecting as soon as the plausible.io account exists for `civilproposals.com`.\n"
            "- **Google Search Console** — impressions, clicks, average position and the actual "
            "search queries per URL. Free, and the single most useful signal for deciding which "
            "post to improve next. Add `civilproposals.com` as a property and submit "
            f"`{blog.SITE_ORIGIN}/sitemap.xml`."
        )

    # Nothing below this line runs in blog mode: the sidebar, the workflow
    # tabs and every other page segment are skipped entirely.
    st.stop()
