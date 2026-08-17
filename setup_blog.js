#!/usr/bin/env node
/*
 * setup_blog.js -- one-shot setup for the CivilProposals blog.
 *
 * Run from the repo root:
 *
 *     node setup_blog.js
 *
 * What it does, in order:
 *   1. checks you're logged in to Cloudflare
 *   2. creates the BLOG KV namespace (skipped if the id is already filled in)
 *   3. writes that id into wrangler.toml AND landing/wrangler.toml
 *   4. generates a publish secret and stores it as a Cloudflare Worker secret
 *   5. deploys the Worker
 *   6. prints the one thing it cannot do for you -- the Railway variable
 *
 * Safe to re-run. Every step checks whether it's already been done, so a
 * partial run (network dropped, wrong password, closed the window) is fixed
 * by running it again rather than by unpicking what happened.
 *
 * Flags:
 *   --dry-run     show what would happen, change nothing, call nothing
 *   --no-deploy   do everything except the final `wrangler deploy`
 */

"use strict";

const { spawnSync } = require("node:child_process");
const { randomBytes } = require("node:crypto");
const { readFileSync, writeFileSync, existsSync } = require("node:fs");
const { join, resolve } = require("node:path");

const ROOT = __dirname;
const DRY = process.argv.includes("--dry-run");
const NO_DEPLOY = process.argv.includes("--no-deploy");

const PLACEHOLDER = "REPLACE_WITH_KV_NAMESPACE_ID";
const TOMLS = [join(ROOT, "wrangler.toml"), join(ROOT, "landing", "wrangler.toml")];

// Windows terminals handle these fine; they degrade to plain text elsewhere.
const c = {
  b: (s) => `\x1b[1m${s}\x1b[0m`,
  g: (s) => `\x1b[32m${s}\x1b[0m`,
  y: (s) => `\x1b[33m${s}\x1b[0m`,
  r: (s) => `\x1b[31m${s}\x1b[0m`,
  d: (s) => `\x1b[90m${s}\x1b[0m`,
};

let step = 0;
const say = (msg) => console.log(`\n${c.b(`[${++step}]`)} ${c.b(msg)}`);
const ok = (msg) => console.log(`    ${c.g("OK")}  ${msg}`);
const info = (msg) => console.log(`    ${c.d(msg)}`);
const warn = (msg) => console.log(`    ${c.y("!")}   ${msg}`);

function die(msg, hint) {
  console.error(`\n${c.r("STOPPED")}  ${msg}`);
  if (hint) console.error(`\n${hint}\n`);
  process.exit(1);
}

// `shell: true` is required on Windows for npx to resolve at all.
function run(cmd, { input, capture = true, allowFail = false } = {}) {
  if (DRY) {
    info(`would run: ${cmd}`);
    return { status: 0, stdout: "", stderr: "", skipped: true };
  }
  const r = spawnSync(cmd, {
    shell: true,
    input,
    encoding: "utf8",
    stdio: capture ? ["pipe", "pipe", "pipe"] : "inherit",
  });
  const out = `${r.stdout || ""}${r.stderr || ""}`;
  if (r.status !== 0 && !allowFail) {
    die(`\`${cmd}\` failed.`, out.trim() || "No output from the command.");
  }
  return { status: r.status, stdout: r.stdout || "", stderr: r.stderr || "", out };
}

// ---------------------------------------------------------------------------

console.log(c.b("\nCivilProposals blog -- setup"));
console.log(c.d(`repo: ${ROOT}`));
if (DRY) console.log(c.y("DRY RUN -- nothing will be changed or called."));

for (const f of TOMLS) {
  if (!existsSync(f)) {
    die(`Can't find ${f}`, "Run this from the civilproposals-saas folder:\n\n    cd /d \"C:\\Proposal Writer\\civilproposals-saas\"\n    node setup_blog.js");
  }
}

// --- 1. Cloudflare login ---------------------------------------------------

say("Checking your Cloudflare login");
const who = run("npx wrangler whoami", { allowFail: true });
if (!DRY && who.status !== 0) {
  info("Not logged in -- opening the browser login now.");
  run("npx wrangler login", { capture: false });
  const retry = run("npx wrangler whoami", { allowFail: true });
  if (retry.status !== 0) {
    die("Still not logged in to Cloudflare.", "Run `npx wrangler login` on its own, finish the browser step, then run this again.");
  }
}
if (!DRY) {
  const email = (who.stdout.match(/[\w.+-]+@[\w.-]+/) || [])[0];
  ok(email ? `Logged in as ${email}` : "Logged in");
}

// --- 2. KV namespace -------------------------------------------------------

say("Creating the BLOG KV namespace");

const rootToml = readFileSync(TOMLS[0], "utf8");
const already = rootToml.match(/binding\s*=\s*"BLOG"[\s\S]{0,120}?id\s*=\s*"([0-9a-f]{32})"/);

let kvId = already ? already[1] : null;

if (kvId) {
  ok(`Already set up (${kvId}) -- skipping.`);
} else {
  // Wrangler v3+ uses "kv namespace create"; v2 used "kv:namespace create".
  let res = run("npx wrangler kv namespace create BLOG", { allowFail: true });
  if (res.status !== 0) {
    info("Trying the older wrangler syntax...");
    res = run("npx wrangler kv:namespace create BLOG", { allowFail: true });
  }
  if (!DRY) {
    if (res.status !== 0) {
      die("Couldn't create the KV namespace.", res.out.trim());
    }
    const found = res.out.match(/["']?id["']?\s*[:=]\s*["']([0-9a-f]{32})["']/i)
      || res.out.match(/\b([0-9a-f]{32})\b/);
    if (!found) {
      die("Created the namespace but couldn't read its id from wrangler's output.",
        `${res.out.trim()}\n\nPaste the id into both wrangler.toml files by hand, replacing ${PLACEHOLDER}, then run this again.`);
    }
    kvId = found[1];
    ok(`Created: ${kvId}`);
  } else {
    kvId = "0".repeat(32);
  }
}

// --- 3. Write the id into both configs -------------------------------------

say("Writing the namespace id into both wrangler.toml files");
for (const f of TOMLS) {
  const before = readFileSync(f, "utf8");
  if (!before.includes(PLACEHOLDER)) {
    ok(`${f.replace(ROOT, ".")} -- already done`);
    continue;
  }
  const after = before.split(PLACEHOLDER).join(kvId);
  if (DRY) {
    info(`would update ${f.replace(ROOT, ".")}`);
  } else {
    writeFileSync(f, after);
    ok(`${f.replace(ROOT, ".")} -- updated`);
  }
}

// --- 4. Publish secret -----------------------------------------------------

say("Setting the publish secret on Cloudflare");

const existing = run("npx wrangler secret list", { allowFail: true });
const hasSecret = !DRY && existing.status === 0 && existing.out.includes("BLOG_PUBLISH_SECRET");

let secret = null;
if (hasSecret) {
  warn("BLOG_PUBLISH_SECRET already exists on Cloudflare -- leaving it alone.");
  info("If Railway doesn't have the SAME value, publishing returns 401.");
  info("To reset both sides, delete it first:  npx wrangler secret delete BLOG_PUBLISH_SECRET");
} else {
  secret = randomBytes(32).toString("hex");
  // Wrangler reads the value from stdin when it isn't a TTY, so this stays
  // non-interactive -- the whole point of a one-command setup.
  run("npx wrangler secret put BLOG_PUBLISH_SECRET", { input: `${secret}\n` });
  ok("Stored on Cloudflare.");
}

// --- 5. Deploy -------------------------------------------------------------

if (NO_DEPLOY) {
  say("Skipping deploy (--no-deploy)");
  info("Deploy later with:  npx wrangler deploy");
} else {
  say("Deploying the Worker and landing page");
  run("npx wrangler deploy", { capture: false });
  ok("Deployed.");
}

// --- 6. What's left --------------------------------------------------------

console.log(`\n${c.b("=".repeat(66))}`);
console.log(c.b("  Two things left, both on Railway"));
console.log(c.b("=".repeat(66)));

if (secret) {
  console.log(`
  1. Add this variable to your Railway service (Variables -> New Variable):

       ${c.b("BLOG_PUBLISH_SECRET")} = ${c.g(secret)}

     It must match exactly. Copy it now -- it isn't stored anywhere you can
     read it back, and this is the only time it's printed.`);
} else {
  console.log(`
  1. Make sure Railway's ${c.b("BLOG_PUBLISH_SECRET")} matches the one already on
     Cloudflare. If you don't know it, delete and re-run:

       npx wrangler secret delete BLOG_PUBLISH_SECRET
       node setup_blog.js`);
}

console.log(`
  2. Push, so Railway rebuilds with the new blog code:

       git add -A
       git commit -m "Add blog: admin editor, edge-served pages, view stats"
       git push

  Then log in at app.civilproposals.com, click "Write / edit blog" in the
  sidebar, and publish your first post.

  ${c.d("Check: https://civilproposals.com/blog/ should return 404 until you")}
  ${c.d("publish (the blog exists, it's just empty). A 503 means the KV id")}
  ${c.d("didn't make it into wrangler.toml -- re-run this script.")}
`);
