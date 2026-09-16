# YMAL — checkout app project

A Shopify CLI project linked to the **existing** YMAL app (client_id
`3fb7e0036a76ebe343c058e46dbfd921`). It exists to hold Checkout UI extensions,
which can only be built and deployed through Shopify CLI - there is no upload
button in the Shopify admin.

**No extensions yet.** The planned first one is Recently Viewed at checkout:
oldest-first, three products, a size picker on each card, and a card replaced by
the next product when one is added.

Shopify hosts extension code itself. Nothing here runs on the VM.

---

## Run the CLI through `SHOPIFY_FLAG_PATH`, never from this folder's real path

Shopify CLI 4.8 **cannot find `shopify.app.toml` under any path containing
parentheses**. This repo lives under Google Drive at
`…/GoogleDrive-web@pt-infashion.com (25-05-26 14.53)/…`, so running the CLI from
here fails with *"Could not find a Shopify app configuration file"* - with the
file sitting right there.

Isolated on 2026-09-15 by copying this project to three local paths:

| Path | Result |
|---|---|
| spaces **and** parentheses | fails |
| spaces only | works |
| a plain-named symlink, passed to the CLI as `--path` | works |

It was not Google Drive and not the spaces. The same error broke the very first
`app init` attempt.

### `cd` into a symlink is not enough

A symlink with a plain name fixes it - but only when the CLI is **given** that
path. `cd ~/ymal-checkout` and the shell reports `~/ymal-checkout`, while Node's
`process.cwd()` asks the OS and gets the physical path back, parentheses
included. With no `--path`, the CLI defaults to that and fails again. Verified:
`cd` alone fails; `--path "$PWD"` works.

### Setup, once per Mac

```
ln -s "<repo>/checkout" ~/ymal-checkout
echo 'export SHOPIFY_FLAG_PATH="$HOME/ymal-checkout"' >> ~/.zshrc
source ~/.zshrc
```

`SHOPIFY_FLAG_PATH` is the CLI's own environment variable for `--path`, honoured
by `app info`, `app generate extension`, `app dev` and `app deploy`. Set once,
every command works - including the `npm run` scripts in `package.json`, which
cannot take a `--path` flag. Verified with both `npx shopify app info` and
`npm run info`.

The symlink is the same folder, not a copy: an edit made either way is the same
file and shows up in git.

---

## The app this is linked to runs production

The same YMAL app's credentials power the nightly pipeline through the
`client_credentials` grant. Anything this project pushes lands on that app. Read
this section before running `dev` or `deploy`.

### Both `dev` and `deploy` push configuration

- **`deploy`** - Shopify CLI 4.8 has no extensions-only deploy. `deploy --help`
  offers `--allow-deletes`, covering *"removing extensions and configuration"*.
- **`dev`** - the extension-only template's own README says `app dev` *"updates
  remote config"*, and that metaobject and metafield definitions in
  `shopify.app.toml` are *"automatically synced to Shopify when you run
  `shopify app dev` or `shopify app deploy`"*.

So treat **both** as writes to the live app.

`shopify.app.toml` therefore mirrors the live app exactly - values pulled by
`config link` on 2026-09-15. A scope missing from it could be **removed from the
app the pipeline depends on**. Anything added to it will be **created** there.

`include_config_on_deploy = false` is set, but nothing relies on it.

### Preview a deploy before releasing it

```
npx shopify app deploy --no-release
```

This creates a version without releasing it. Read the add / update / remove
summary the CLI prints. Release only if nothing changed except the intended
extension.

### Existing versions contain no extensions

`v0.2` (active, "Embed the interface"), `v0.1` and `ymal-1` were all made in the
Dev Dashboard, which cannot author UI extensions. So a deploy from here removes
nothing today. That stops being true the moment an extension is deployed from
anywhere else, because a deploy drops any extension not present in this folder.

### What the template tried to add, and why it is gone

The extension-only template shipped sample configuration YMAL does not have. On
the first `dev` or `deploy` it would have created, in the live store:

- a FAQ metaobject definition
- an "FAQ" metafield on every product in the admin
- an admin API access-mode change and a Sidekick summary
- an **App Home** extension, replacing what opens when YMAL is clicked in admin
- an **App Tools** extension, AI tools for that FAQ

All removed before anything ran.

### Settings that are off on purpose

| Setting | Why |
|---|---|
| `automatically_update_urls_on_dev = false` | when true, `app dev` rewrites the live app's URL to a temporary tunnel. This stops **only** that - `dev` still syncs other config |
| `include_config_on_deploy = false` | belt-and-braces only - see above |

---

## Commands

With `SHOPIFY_FLAG_PATH` set (see above), from any directory. The CLI is a local
dependency, so prefix with `npx` - or use the matching `npm run` script:

```
npx shopify app info                      # what this is linked to - read-only
npx shopify app generate extension        # add an extension - local files only
npx shopify app deploy --no-release       # preview a deploy
```

### Never pass `--name` to `app init`

`--name` *"creates a new app with this name"*. To link to YMAL, use
`--client-id` only.

### `app init` inside a git repo fails

It runs `git init` and `git checkout -b main` on the new project. Inside an
existing repo those resolve to that repo, which already has `main`, and init
fails. This project was created outside any repo and moved in without its own
`.git`.

## Recently Viewed in checkout

`extensions/ymal-recently-viewed/` — the block that replaces Wiser Checkout
Upsell in the Order summary. Built 2026-09-16, NOT deployed.

    src/Checkout.jsx           the block (Preact + Polaris web components, 2026-01)
    shopify.extension.toml     target purchase.checkout.block.render, api_access

**Oldest first**, and that is the point of it. Every other placement leads with
the most recent product; by checkout those are the ones the shopper passed over,
so this one starts from the oldest the browser still remembers.

**How the list gets there.** A checkout extension is sandboxed on another
origin: no localStorage, no Liquid, no metafields. The storefront writes the
viewed product ids onto the cart as the attribute `YMAL viewed`
(`assets/ymal-recently-viewed.js`), newest first, eligible products only -
eligibility is decided at view time in `snippets/ymal-recently-viewed-recorder.liquid`,
where the metafield can still be read. The block reverses that list.

**Checked here, because it can change between viewing and checking out:** the
product still exists and is published, is in stock, is not already in the order,
and is not another colorway of a style already in the order.

### Before it can work on the live store

1. The live theme needs the current `ymal-recently-viewed.js` and the recorder
   snippet - older copies write no attribute, and the block stays empty.
2. Deploy. On this machine the path needs spelling out, because the CLI
   resolves the ~/ymal-checkout symlink back to a Drive path with parentheses
   in it and then cannot find the config:

       cd ~/ymal-checkout
       npx shopify app deploy --no-release --path "$HOME/ymal-checkout"
       npx shopify app release --version=<version> --path "$HOME/ymal-checkout"

   `--no-release` creates a version without making it live, and needs no
   confirmation flag. `--force` does not exist in CLI 4.8.

   Every deploy now pushes the app CONFIGURATION too - see the note in
   shopify.app.toml. Verify it still matches the live app first.

   Version ymal-4, created 2026-09-16, is this extension. Not released.
3. In the checkout editor, add the block where Wiser's upsell was, and hide
   or remove Wiser Checkout Upsell.

### Known gap

No `network_access`, so this block never reaches the YMAL backend: checkout
impressions and adds do NOT appear in the dashboard. Purchases still do - every
add writes the `YMAL block` line attribute, which the nightly order pass reads
back, with the value `recently_viewed_checkout` to keep it apart from the cart
drawer's.
