# GitHub SOP — ymal-project

**Repo:** https://github.com/Wooden-Ships-Knits/ymal-project.git

---

## 1. Branch model

```
main                    ← production. never pushed to directly.
 └── feat/dev-environment   ← integration branch. everything lands here first.
      ├── feat/phase1-eligible-products
      ├── feat/backend-scaffold
      └── feat/<whatever>
```

| Branch | Rule |
|---|---|
| `main` | **Never commit or push directly.** Only receives merges from `feat/dev-environment`, and only when it is stable. |
| `feat/dev-environment` | Integration branch. All feature work merges here first. This is what we break, not `main`. |
| `feat/<name>` | One branch per unit of work. Branched from `feat/dev-environment`, merged back into it. |

**The rule in one line:** every push goes to a `feat/*` branch, and reaches
`main` only by way of `feat/dev-environment`.

---

## 2. Naming

```
feat/<short-kebab-description>
```

Examples:

```
feat/phase1-eligible-products
feat/copurchase-scoring
feat/theme-widget
fix/sale-marker-case-sensitivity
docs/strategy-update
```

Keep it short and descriptive. The phase number helps when it applies.

---

## 3. Daily workflow

### Start work

```bash
git checkout feat/dev-environment
git pull origin feat/dev-environment

git checkout -b feat/phase1-eligible-products
```

Always branch **from** `feat/dev-environment`, never from `main`.

### While working

```bash
git add <files>
git commit -m "feat: fetch active products and resolve Bali eligibility"
```

Commit message prefixes:

| Prefix | Use |
|---|---|
| `feat:` | new capability |
| `fix:` | bug fix |
| `docs:` | documentation only |
| `refactor:` | restructure, no behavior change |
| `chore:` | deps, config, tooling |

### Push

```bash
git push -u origin feat/phase1-eligible-products
```

### Merge into the integration branch

```bash
git checkout feat/dev-environment
git pull origin feat/dev-environment
git merge feat/phase1-eligible-products
git push origin feat/dev-environment
```

Or open a PR on GitHub targeting `feat/dev-environment` — preferred when
someone else should look at it first.

### Clean up

```bash
git branch -d feat/phase1-eligible-products
git push origin --delete feat/phase1-eligible-products
```

---

## 4. Promoting to main

Only when `feat/dev-environment` is stable and tested.

```bash
git checkout main
git pull origin main
git merge feat/dev-environment
git push origin main
```

Prefer a PR (`feat/dev-environment` → `main`) so the diff gets a read before it
lands.

**Before promoting, confirm:**
- [ ] Scripts run end to end without errors
- [ ] No secrets in the diff
- [ ] Docs updated if behavior changed
- [ ] `memory.md` checkpoint written if a phase completed

---

## 5. First-time setup

The repo is empty, so `main` and `feat/dev-environment` have to be created once.

```bash
cd ymal-project

git init
git remote add origin https://github.com/Wooden-Ships-Knits/ymal-project.git

# confirm .env is ignored BEFORE the first commit
git status --short | grep -q '\.env$' && echo "STOP — .env is not ignored"

git add .
git commit -m "chore: monorepo scaffold, docs, and phase 1 backend"

git branch -M main
git push -u origin main

git checkout -b feat/dev-environment
git push -u origin feat/dev-environment
```

After this, `main` is never touched directly again.

### Recommended: protect main on GitHub

Settings → Branches → Add rule for `main`:
- Require a pull request before merging
- Do not allow direct pushes

This makes the SOP enforced rather than remembered.

---

## 6. Secrets

**Never commit:**
- `.env` (already in `.gitignore`)
- Access tokens, client secrets, API keys
- `credentials/` service-account JSON

Before any first push to a new branch:

```bash
git diff --cached | grep -iE 'shpat_|shpca_|client_secret|api_key|password'
```

**If a secret is ever committed:** rotate it in the Shopify dev dashboard
immediately. Removing it in a later commit does **not** help — it stays in the
history and the repo is what leaked.

> ⚠️ A live-looking token was found committed in a sibling project
> (`Collection VO Automatic Sort/Setup/set_sy.py`, trailing comment). It should
> be rotated. Do not repeat that pattern here.

---

## 7. What not to commit

`.gitignore` covers these, but for clarity:

- `backend/data/` — regenerable pipeline output, and it contains catalog data
- `__pycache__/`, `.venv/`
- `node_modules/`
- `.DS_Store` — Google Drive and macOS both scatter these
- `.ipynb` — notebooks (per existing team convention)

---

## 8. Quick reference

```bash
# new work
git checkout feat/dev-environment && git pull
git checkout -b feat/<name>

# save + share
git add . && git commit -m "feat: ..."
git push -u origin feat/<name>

# land it
git checkout feat/dev-environment && git pull
git merge feat/<name> && git push origin feat/dev-environment

# never
git push origin main        # ✗
git commit  (while on main) # ✗
```
