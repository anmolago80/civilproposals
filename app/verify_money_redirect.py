"""Regression test for the Stripe redirect money path.

Written during the Round 6 audit, because the fix it protects had none.

The bug this exists to prevent: handle_checkout_redirect() is the ONLY
code path that ever applies a Checkout Session -- billing.py is
deliberately webhook-free (see its module docstring) -- and it runs in
00_init.py BEFORE require_login(). An identity guard that returned early
on "the logged-in user doesn't match client_reference_id" therefore
didn't just withhold a confirmation message, it skipped the purchase
itself, and the caller then cleared the session_id out of the URL, so
there was no retry path either. A customer was charged and got nothing.

The invariant, in one line: money follows client_reference_id, never
"whoever happens to be looking". Identity only decides what is safe to
RETURN.

FIX BRIEF ROUND 7, Part 1: extended past the original 5 scenarios (a/b/
b2/c/d, all mode="payment") with the three cases the brief named as
possibly missing, since handle_checkout_redirect() has other branches
none of the above ever touch:
  (e) mode="subscription" -- activates the monthly plan, never credits
      bid_credits.
  (f) metadata.topup_project_key against a trial-funded project --
      auth.apply_project_bid_topup()'s "upgraded_trial" branch.
  (g) metadata.topup_project_key against a project with no ProposalUsage
      row at all -- the "no_project" fallback, which must still credit a
      plain bid rather than lose the $50.
  (h) an async payment (bank debit, some wallets) that reads "unpaid" on
      the first redirect and "paid" on a later one, SAME session_id --
      proves the early "not paid yet" return doesn't poison the
      ProcessedCheckoutSession idempotency row, so the later, real
      settlement still applies.

Run from app/:  python verify_money_redirect.py
Uses a throwaway SQLite file and a fake Stripe session -- no network, no
Stripe key, no production data.
"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:////tmp/verify_money_redirect.db"
os.environ.setdefault("APP_SECRET_KEY", "test-only-not-a-real-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("STRIPE_PRICE_ID", "price_fake")
os.environ.setdefault("STRIPE_BID_PRICE_ID", "price_bid_fake")
if os.path.exists("/tmp/verify_money_redirect.db"):
    os.remove("/tmp/verify_money_redirect.db")
sys.path.insert(0, ".")

from modules import auth, billing, db  # noqa: E402

db.init_db()

_failures: list[str] = []
_count = 0


def check(label: str, ok: bool) -> None:
    global _count
    _count += 1
    print(("PASS  " if ok else "FAIL  ") + label)
    if not ok:
        _failures.append(label)


def credits(user_id: str) -> int:
    with db.get_session() as s:
        return s.query(db.User).filter(db.User.id == user_id).first().bid_credits or 0


buyer = auth.create_user("_money_buyer@example.invalid", "pw12345678")
viewer = auth.create_user("_money_viewer@example.invalid", "pw12345678")

# Fake Stripe + fake "who is logged in", so every branch is reachable
# without a network call or a real session cookie.
_state = {
    "buyer_id": None, "paid": True, "mode": "payment",
    "metadata": {}, "subscription_id": None,
}
_logged_in = {"user": None}

billing.stripe.checkout.Session.retrieve = lambda sid, **kw: {
    "payment_status": "paid" if _state["paid"] else "unpaid",
    "mode": _state["mode"],
    "client_reference_id": _state["buyer_id"],
    "customer": "cus_fake",
    "subscription": _state["subscription_id"],
    "metadata": _state["metadata"],
    "id": sid,
}
auth.current_user = lambda: _logged_in["user"]


def redirect(session_id: str, buyer_id: str, logged_in_as, paid: bool = True,
             mode: str = "payment", metadata: dict | None = None,
             subscription_id: str | None = None):
    _state["buyer_id"] = buyer_id
    _state["paid"] = paid
    _state["mode"] = mode
    _state["metadata"] = metadata or {}
    _state["subscription_id"] = subscription_id
    _logged_in["user"] = logged_in_as
    return billing.handle_checkout_redirect(session_id)


# (a) The ordinary case: the buyer is logged in when Stripe redirects back.
before = credits(buyer.id)
r = redirect("cs_ordinary", buyer.id, buyer)
check("(a) the purchase is applied when the buyer is logged in",
      r.applied and credits(buyer.id) == before + 1)
check("(a) the buyer's User comes back", r.user is not None and r.user.id == buyer.id)

# (b) THE REGRESSION: nobody is logged in in this browser tab.
before = credits(buyer.id)
r = redirect("cs_nobody", buyer.id, None)
check("(b) the purchase is STILL applied when nobody is logged in",
      r.applied and credits(buyer.id) == before + 1)
check("(b) no User object is handed back", r.user is None)

# (b2) ...and reloading that same URL once logged in resolves it, exactly once.
before = credits(buyer.id)
r = redirect("cs_nobody", buyer.id, buyer)
check("(b2) replaying the same session_id resolves the User",
      r.applied and r.user is not None and r.user.id == buyer.id)
check("(b2) replaying does NOT credit a second time", credits(buyer.id) == before)

# (c) A DIFFERENT account is logged in. Money must follow the buyer.
before_buyer, before_viewer = credits(buyer.id), credits(viewer.id)
r = redirect("cs_wrong_viewer", buyer.id, viewer)
check("(c) the purchase is applied to the BUYER, not the viewer",
      r.applied and credits(buyer.id) == before_buyer + 1)
check("(c) the viewer is not credited", credits(viewer.id) == before_viewer)
check("(c) no foreign User object leaks into the viewer's request", r.user is None)

# (d) A genuinely unpaid session applies nothing -- the only case where the
#     caller is allowed to clear the session_id out of the URL.
before = credits(buyer.id)
r = redirect("cs_unpaid", buyer.id, buyer, paid=False)
check("(d) an unpaid session applies nothing",
      not r.applied and r.user is None and credits(buyer.id) == before)

# (e) A subscription checkout activates the monthly plan -- a completely
# different branch of handle_checkout_redirect() from (a)-(d), which are
# all mode="payment". Never exercised until now.
sub_buyer = auth.create_user("_money_sub_buyer@example.invalid", "pw12345678")
before = credits(sub_buyer.id)
r = redirect("cs_subscription", sub_buyer.id, sub_buyer,
             mode="subscription", subscription_id="sub_fake123")
check("(e) a subscription checkout is applied and returns the buyer",
      r.applied and r.user is not None and r.user.id == sub_buyer.id)
with db.get_session() as s:
    refreshed = s.query(db.User).filter(db.User.id == sub_buyer.id).first()
    check("(e) subscription_status becomes active", refreshed.subscription_status == "active")
    check("(e) stripe_subscription_id is recorded", refreshed.stripe_subscription_id == "sub_fake123")
check("(e) a subscription checkout does NOT touch bid_credits", credits(sub_buyer.id) == before)

# (f) A topup_project_key payment against a project that's currently
# trial-funded upgrades it to paid and opens its pass allowance --
# auth.apply_project_bid_topup()'s "upgraded_trial" branch, reached only
# through this metadata path, never by an ordinary bid purchase.
topup_buyer = auth.create_user("_money_topup_buyer@example.invalid", "pw12345678")
TOPUP_PROJECT_KEY = "acme-bridge-widening"
with db.get_session() as s:
    s.add(db.ProposalUsage(user_id=topup_buyer.id, project_key=TOPUP_PROJECT_KEY,
                            project_name="Acme Bridge Widening", funded_by="trial"))
    s.commit()

before = credits(topup_buyer.id)
r = redirect("cs_topup", topup_buyer.id, topup_buyer,
             metadata={"topup_project_key": TOPUP_PROJECT_KEY})
check("(f) a project topup is applied and returns the buyer",
      r.applied and r.user is not None and r.user.id == topup_buyer.id)
check("(f) purchase_kind is reported as topup", r.purchase_kind == "topup")
check("(f) a topup does NOT also add a generic bid credit", credits(topup_buyer.id) == before)
with db.get_session() as s:
    usage = s.query(db.ProposalUsage).filter(
        db.ProposalUsage.user_id == topup_buyer.id,
        db.ProposalUsage.project_key == TOPUP_PROJECT_KEY).first()
    passes = s.query(db.ProjectPasses).filter(
        db.ProjectPasses.user_id == topup_buyer.id,
        db.ProjectPasses.project_key == TOPUP_PROJECT_KEY).first()
    check("(f) the project's trial funding is upgraded to credit", usage.funded_by == "credit")
    check("(f) the project gets a 5-pass allowance with 1 already spent",
          passes is not None and passes.passes_purchased == 5 and passes.passes_used == 1)

# (g) A topup_project_key that doesn't match any recorded project must
# never lose the $50 -- it falls back to a plain account-level bid credit
# (apply_project_bid_topup's "no_project" case) rather than vanishing.
noproject_buyer = auth.create_user("_money_noproject_buyer@example.invalid", "pw12345678")
before = credits(noproject_buyer.id)
r = redirect("cs_topup_noproject", noproject_buyer.id, noproject_buyer,
             metadata={"topup_project_key": "does-not-exist"})
check("(g) an orphaned topup falls back to a plain bid credit",
      r.applied and credits(noproject_buyer.id) == before + 1)
check("(g) an orphaned topup reports no specific purchase_kind", r.purchase_kind is None)

# (h) An async payment method (bank debit, some wallets) can complete the
# Checkout FORM immediately while payment_status stays "unpaid" for hours,
# then settle later. Redirect to the SAME session_id twice: once while
# still unpaid (must apply nothing -- and per handle_checkout_redirect's
# early return on an unpaid status, must NOT touch ProcessedCheckoutSession,
# or the real settlement below would be mistaken for an already-processed
# replay and silently dropped), then again once it has actually settled.
async_buyer = auth.create_user("_money_async_buyer@example.invalid", "pw12345678")
before = credits(async_buyer.id)
r = redirect("cs_async_settle", async_buyer.id, async_buyer, paid=False)
check("(h) an async-pending session applies nothing on the first redirect",
      not r.applied and credits(async_buyer.id) == before)

r = redirect("cs_async_settle", async_buyer.id, async_buyer, paid=True)
check("(h) the SAME session_id applies once it actually settles",
      r.applied and credits(async_buyer.id) == before + 1)

before = credits(async_buyer.id)
r = redirect("cs_async_settle", async_buyer.id, async_buyer, paid=True)
check("(h) replaying the now-settled session does not double-credit",
      credits(async_buyer.id) == before)

print("-" * 72)
print(f"{_count - len(_failures)}/{_count} checks passed")
if _failures:
    print("\nFAILED:")
    for f in _failures:
        print("  - " + f)
sys.exit(1 if _failures else 0)
