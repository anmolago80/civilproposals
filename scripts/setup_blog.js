#!/usr/bin/env node
/*
 * setup_blog.js -- one-shot setup for the CivilProposals blog.
 *
 *     node scripts/setup_blog.js
 *
 * Steps:
 *   1. check the Cloudflare login
 *   2. create the BLOG KV namespace  (skipped if already done)
 *   3. write its id into wrangler.toml AND landing/wrangler.toml
 *   4. generate a publish secret and store it as a Worker secret
 *   5. deploy the Worker
 *   6. print the Railway variable, which is the one thing it can't set
 *
 * Safe to re-run: every step checks whether it's already been done.
 *
 * Flags:
 *   --kv-id=<32 hex>   skip step 2 and use a namespace you made in the
 *                      dashboard (use this if the CLI won't create one)
 *   --dry-run          show what would happen, change nothing
 *   --no-deploy        everything except the final `wrangler deploy`
 *
 * TWO WINDOWS-SPECIFIC THINGS THIS WORKS AROUND
 *
 *   a) Piped stdio to a shelled-out child crashes Node on Windows with
 *      "Assertion failed: !(handle->flags & UV_HANDLE_CLOSING) ...
 *      src\win\async.c". So nothing here pipes: output is captured by
 *      redirecting to a temp file, and stdin is fed from a temp file.
 *
 *   b) `[[kv_namespaces]] id = "REPLACE_WITH_..."` is not a valid id, and
 *      wrangler parses the whole config before running ANY command --
 *      including the very command that creates the namespace. So the block
 *      is commented out for the duration of step 2 and restored after
 *      (in a finally, so an interrupted run doesn't leave it commented).
 */

"use strict";

const { spawnSync } = require("node:child_process");
const { randomBytes } = require("node:crypto");
const { readFileSync, writeFileSync, existsSync, unlinkSync, mkdtempSync } = require("node:fs");
const { join } = require("node:path");
const { tmpdir } = require("node:os");

// The repo root, one level up from this script's own scripts/ directory --
// every path below (both wrangler.toml files, the deploy) is relative to
// the root, not to wherever this file happens to live.
const ROOT = join(__dirname, "..");
const ARGS = process.argv.slice(2);
const DRY = ARGS.includes("--dry-run");
const NO_DEPLOY = ARGS.includes("--no-deploy");
const KV_ID_ARG = (ARGS.find((a) => a.startsWith("--kv-id=")) || "").split("=")[1] || null;

const PLACEHOLDER = "REPLACE_WITH_KV_NAMESPACE_ID";
const MARK = "#__KVTMP__";
const TOMLS = [join(ROOT, "wrangler.toml"), join(ROOT, "landing", "wrangler.toml")];
const TMP = mkdtempSync(join(tmpdir(), "cpblog-"));

const c = {
  b: (s) => `\x1b[1m${s}\x1b[0m`,
  g: (s) => `\x1b[32m${s}\x1b[0m`,
  y: (s) => `\x1b[33m${s}\x1b[0m`,
  r: (s) => `\x1b[31m${s}\x1b[0m`,
  d: (s) => `\x1b[90m${s}\x1b[0m`,
};

let step = 0;
const say = (m) => console.log(`\n${c.b(`[${++step}]`)} ${c.b(m)}`);
const ok = (m) => console.log(`    ${c.g("OK")}  ${m}`);
const info = (m) => console.log(`    ${c.d(m)}`);
const warn = (m) => console.log(`    ${c.y("!")}   ${m}`);

/* Set while the [[kv_namespaces]] block is temporarily commented out, so
 * that ANY exit path puts the config files back. A plain try/finally isn't
 * enough: die() calls process.exit(), which terminates immediately and
 * never runs finally blocks -- that would leave both wrangler.toml files
 * commented out and the next run confused about its own state. */
let restoreTomls = null;

function cleanup() {
  if (restoreTomls) {
    const fn = restoreTomls;
    restoreTomls = null;
    try {
      fn();
    } catch {}
  }
}
process.on("exit", cleanup);
process.on("SIGINT", () => {
  cleanup();
  process.exit(130);
});

function die(msg, hint) {
  cleanup();
  console.error(`\n${c.r("STOPPED")}  ${msg}`);
  if (hint) console.error(`\n${hint}\n`);
  process.exit(1);
}

let tmpSeq = 0;

/* Runs a command and returns its combined output.
 * Output is captured via shell redirection to a file, never via a pipe --
 * see note (a) at the top. stdin likewise comes from a file when needed.
 *
 * `raw: true` turns capture OFF entirely: the command inherits the real
 * terminal. That matters more than it sounds. Redirecting stdout makes it
 * a file rather than a TTY, and wrangler checks exactly that to decide
 * whether it's running interactively -- with output redirected it refuses
 * to open the browser and demands a CLOUDFLARE_API_TOKEN instead. So
 * anything that may need to prompt the user (login, deploy) runs raw, and
 * only commands whose output we actually have to parse get redirected. */
function run(cmd, { stdinText, allowFail = false, show = false, raw = false } = {}) {
  if (DRY) {
    info(`would run: ${cmd}`);
    return { status: 0, out: "" };
  }

  if (raw) {
    const r = spawnSync(cmd, { shell: true, stdio: "inherit" });
    if (r.status !== 0 && !allowFail) die(`\`${cmd}\` failed.`);
    return { status: r.status, out: "" };
  }

  const outFile = join(TMP, `out${++tmpSeq}.txt`);
  let full = cmd;

  if (stdinText !== undefined) {
    const inFile = join(TMP, `in${tmpSeq}.txt`);
    writeFileSync(inFile, stdinText);
    full += ` < "${inFile}"`;
  }
  full += ` > "${outFile}" 2>&1`;

  const r = spawnSync(full, { shell: true, stdio: "inherit" });

  let out = "";
  try {
    out = readFileSync(outFile, "utf8");
  } catch {
    /* no output file -- treat as empty */
  }
  try {
    unlinkSync(outFile);
  } catch {}

  if (show && out.trim()) console.log(c.d(out.trim().split("\n").map((l) => `    ${l}`).join("\n")));

  if (r.status !== 0 && !allowFail) {
    die(`\`${cmd}\` failed.`, out.trim() || "No output was produced.");
  }
  return { status: r.status, out };
}

/* Comments out the [[kv_namespaces]] block so wrangler can parse the config
 * while the id is still a placeholder. */
function setKvBlockCommented(text, commented) {
  const lines = text.split("\n");
  const out = [];
  let inBlock = false;
  for (const raw of lines) {
    const line = raw.startsWith(MARK) ? raw.slice(MARK.length) : raw;
    const bare = line.trim();
    if (bare === "[[kv_namespaces]]") inBlock = true;
    else if (inBlock && bare === "") inBlock = false;
    out.push(commented && (inBlock || bare === "[[kv_namespaces]]") ? MARK + line : line);
  }
  return out.join("\n");
}

const readToml = (f) => readFileSync(f, "utf8");
const writeToml = (f, t) => {
  if (!DRY) writeFileSync(f, t);
};

// ---------------------------------------------------------------------------

console.log(c.b("\nCivilProposals blog -- setup"));
console.log(c.d(`repo: ${ROOT}`));
if (DRY) console.log(c.y("DRY RUN -- nothing will be changed or called."));

for (const f of TOMLS) {
  if (!existsSync(f)) {
    die(`Can't find ${f}`, 'Run this from the repo folder:\n\n    cd /d "C:\\Proposal Writer\\civilproposals-saas"\n    node setup_blog.js');
  }
}

// --- 1. login --------------------------------------------------------------

say("Checking your Cloudflare login");

/* Windows `set` is unforgiving in ways that produce a confusing error much
 * later. `set X="abc"` stores the quotes as part of the value; `set X = abc`
 * creates a variable called "X " whose value is " abc". Either way wrangler
 * sends a malformed Authorization header and Cloudflare answers with
 * "Invalid format for Authorization header [code: 6111]" on an unrelated
 * endpoint, which points nowhere useful. So: clean the value, sanity-check
 * its shape, and prove it works before going any further. */
const rawToken = process.env.CLOUDFLARE_API_TOKEN;

if (rawToken !== undefined) {
  let token = rawToken.trim();
  const hadQuotes = /^(".*"|'.*')$/.test(token);
  if (hadQuotes) token = token.slice(1, -1).trim();

  if (!token) {
    die("CLOUDFLARE_API_TOKEN is set but empty.",
      "Clear it and use the browser login instead:\n\n    set CLOUDFLARE_API_TOKEN=\n    node setup_blog.js");
  }
  if (/^(your_token_here|your-token-here|PASTE.*|<.*>)$/i.test(token)) {
    die(`CLOUDFLARE_API_TOKEN is still the placeholder text ("${token}").`,
      "Either paste a real token, or clear it and use the browser login:\n\n    set CLOUDFLARE_API_TOKEN=\n    node setup_blog.js");
  }
  if (!/^[A-Za-z0-9_-]{30,}$/.test(token)) {
    die(
      `CLOUDFLARE_API_TOKEN doesn't look like a Cloudflare API token (${token.length} characters, unexpected symbols).`,
      `${c.b("A token is ~40 characters of letters, digits, _ and - with no quotes.")}

  Check what's actually stored:

       echo %CLOUDFLARE_API_TOKEN%

  Set it WITHOUT quotes and WITHOUT spaces around the "=":

       ${c.g("set CLOUDFLARE_API_TOKEN=abc123...")}        (correct)
       ${c.r('set CLOUDFLARE_API_TOKEN="abc123..."')}      (wrong -- quotes are kept)
       ${c.r("set CLOUDFLARE_API_TOKEN = abc123...")}      (wrong -- spaces are kept)

  Or drop the token route entirely and use the browser login:

       set CLOUDFLARE_API_TOKEN=
       npx wrangler login
       node setup_blog.js`
    );
  }

  if (hadQuotes || token !== rawToken) {
    warn("Trimmed stray quotes/whitespace from CLOUDFLARE_API_TOKEN.");
  }
  process.env.CLOUDFLARE_API_TOKEN = token;   // children inherit the cleaned value

  // Prove the token works now, rather than letting it fail three steps later.
  const check = run("npx wrangler whoami", { allowFail: true });
  if (!DRY && check.status !== 0) {
    die(
      "That CLOUDFLARE_API_TOKEN was rejected by Cloudflare.",
      `${check.out.trim().split("\n").slice(-8).join("\n")}

  ${c.b("Most likely:")} the token lacks Workers permissions, or it's expired.
  Create a fresh one at:

       https://dash.cloudflare.com/profile/api-tokens

  Click "Create Token" and use the ${c.b('"Edit Cloudflare Workers"')} template --
  a Global API Key will NOT work here, and neither will a token scoped
  only to DNS or Zone permissions.

  Or skip tokens altogether and use the browser login:

       set CLOUDFLARE_API_TOKEN=
       npx wrangler login
       node setup_blog.js`
    );
  }
  ok("CLOUDFLARE_API_TOKEN accepted.");
} else {
  let who = run("npx wrangler whoami", { allowFail: true });
  if (!DRY && who.status !== 0) {
    console.log("");
    warn("Not logged in to Cloudflare. Opening the browser now --");
    warn("approve the request there, then come back to this window.");
    console.log("");
    // Raw: wrangler will not start the browser flow if its output is
    // redirected, because it treats that as a non-interactive shell.
    run("npx wrangler login", { allowFail: true, raw: true });
    who = run("npx wrangler whoami", { allowFail: true });
    if (who.status !== 0) {
      die(
        "Still not logged in to Cloudflare.",
        `${c.b("Two ways forward:")}

  ${c.b("A. Log in by hand")} (usually just works):

       npx wrangler login

     Finish the browser step, then re-run:  node setup_blog.js

  ${c.b("B. Use an API token")} if the browser flow won't complete
     (common on locked-down machines or over remote desktop):

       1. https://dash.cloudflare.com/profile/api-tokens -> Create Token
       2. Use the "Edit Cloudflare Workers" template
       3. Then run, in this same window:

            set CLOUDFLARE_API_TOKEN=your_token_here
            node setup_blog.js`
      );
    }
  }
  if (!DRY) {
    const email = (who.out.match(/[\w.+-]+@[\w.-]+\.\w+/) || [])[0];
    ok(email ? `Logged in as ${email}` : "Logged in");
  }
}

// --- 2. KV namespace -------------------------------------------------------

say("Creating the BLOG KV namespace");

const existingId = (readToml(TOMLS[0]).match(/binding\s*=\s*"BLOG"[\s\S]{0,120}?id\s*=\s*"([0-9a-fA-F]{32})"/) || [])[1];
let kvId = KV_ID_ARG || existingId || null;

if (KV_ID_ARG) {
  if (!/^[0-9a-fA-F]{32}$/.test(KV_ID_ARG)) {
    die(`--kv-id must be 32 hex characters. Got: ${KV_ID_ARG}`);
  }
  ok(`Using the id you passed in: ${kvId}`);
} else if (existingId) {
  ok(`Already set up (${kvId}) -- skipping.`);
} else if (DRY) {
  kvId = "0".repeat(32);
} else {
  // Comment the block out first -- see note (b) at the top of this file.
  const originals = TOMLS.map((f) => readToml(f));
  restoreTomls = () => {
    TOMLS.forEach((f) => {
      try {
        writeFileSync(f, setKvBlockCommented(readFileSync(f, "utf8"), false));
      } catch {}
    });
  };
  try {
    TOMLS.forEach((f, i) => writeToml(f, setKvBlockCommented(originals[i], true)));

    let res = run("npx wrangler kv namespace create BLOG", { allowFail: true });
    if (res.status !== 0) {
      info("That syntax was rejected; trying the older one...");
      const first = res.out;
      res = run("npx wrangler kv:namespace create BLOG", { allowFail: true });
      if (res.status !== 0) {
        console.error(`\n${c.r("Both attempts failed.")}\n`);
        console.error(c.b("  wrangler kv namespace create BLOG"));
        console.error(c.d(first.trim().split("\n").slice(-14).map((l) => `    ${l}`).join("\n")));
        die(
          "Couldn't create the KV namespace from the command line.",
          `${c.b("Do it in the dashboard instead -- 30 seconds:")}

  1. Open  https://dash.cloudflare.com  ->  Storage & Databases  ->  KV
  2. Click "Create a namespace", name it exactly:  BLOG
  3. Copy the Namespace ID it shows (32 hex characters)
  4. Run:

       node setup_blog.js --kv-id=PASTE_THE_ID_HERE

  Everything else in this script then continues as normal.`
        );
      }
    }
    const found = res.out.match(/["']?id["']?\s*[:=]\s*["']([0-9a-fA-F]{32})["']/i) || res.out.match(/\b([0-9a-fA-F]{32})\b/);
    if (!found) {
      die("Created the namespace but couldn't read its id from wrangler's output.",
        `${res.out.trim()}\n\nCopy the id from above and run:\n\n    node setup_blog.js --kv-id=<the id>`);
    }
    kvId = found[1];
    ok(`Created: ${kvId}`);
  } finally {
    cleanup();   // un-comment the block, whatever happened above
  }
}

// --- 3. write the id into both configs -------------------------------------

say("Writing the namespace id into both wrangler.toml files");
for (const f of TOMLS) {
  const before = readToml(f);
  const short = f.replace(ROOT, ".");
  if (!before.includes(PLACEHOLDER)) {
    ok(`${short} -- already done`);
    continue;
  }
  writeToml(f, before.split(PLACEHOLDER).join(kvId));
  ok(DRY ? `${short} -- would update` : `${short} -- updated`);
}

// --- 4. publish secret -----------------------------------------------------

say("Setting the publish secret on Cloudflare");

const secretList = run("npx wrangler secret list", { allowFail: true });
const hasSecret = !DRY && secretList.status === 0 && secretList.out.includes("BLOG_PUBLISH_SECRET");

let secret = null;
if (hasSecret) {
  warn("BLOG_PUBLISH_SECRET already exists on Cloudflare -- leaving it alone.");
  info("If Railway doesn't hold the SAME value, Publish returns 401.");
  info("To reset both sides:  npx wrangler secret delete BLOG_PUBLISH_SECRET");
} else {
  secret = randomBytes(32).toString("hex");
  run("npx wrangler secret put BLOG_PUBLISH_SECRET", { stdinText: `${secret}\n` });
  ok("Stored on Cloudflare.");
}

// --- 5. deploy -------------------------------------------------------------

if (NO_DEPLOY) {
  say("Skipping deploy (--no-deploy)");
  info("Deploy later with:  npx wrangler deploy");
} else {
  say("Deploying the Worker and landing page");
  // Raw so you see wrangler's live progress, and so it can prompt if it
  // ever needs to (a redirected deploy would fail instead of asking).
  run("npx wrangler deploy", { raw: true });
  ok("Deployed.");
}

// --- 6. what's left --------------------------------------------------------

console.log(`\n${c.b("=".repeat(66))}`);
console.log(c.b("  Two things left, both yours to do"));
console.log(c.b("=".repeat(66)));

if (secret) {
  console.log(`
  1. Add this to your Railway service (Variables -> New Variable):

       ${c.b("BLOG_PUBLISH_SECRET")} = ${c.g(secret)}

     Copy it now. This is the only time it's shown -- Cloudflare won't
     display it again, and it isn't written to any file.`);
} else {
  console.log(`
  1. Check Railway's ${c.b("BLOG_PUBLISH_SECRET")} matches the one already on
     Cloudflare. If you don't know it any more:

       npx wrangler secret delete BLOG_PUBLISH_SECRET
       node setup_blog.js`);
}

console.log(`
  2. Commit the updated config and push:

       git add -A && git commit -m "Blog: set KV namespace id" && git push

  Then log in at app.civilproposals.com -> "Write / edit blog" in the
  sidebar -> write a post -> Publish.

  ${c.d("Check: https://civilproposals.com/blog/ returns 404 until you publish")}
  ${c.d("your first post (the blog is live, just empty). A 503 means the KV")}
  ${c.d("id didn't reach wrangler.toml -- re-run this script.")}
`);
