# paper — landing page

Static site, zero build step. Deploy to Vercel from the repo root:

```bash
cd ui
vercel deploy --prod
```

(or in the Vercel dashboard: **New Project → import sayantan94/newspaper →
Root Directory: `ui` → Framework preset: Other** — no build command, no output
directory needed.)

## Attach your domain

Vercel → the project → **Settings → Domains → Add**. Add your domain (or a
subdomain like `paper.yourdomain.com`), then add the DNS record Vercel shows
you at your registrar (CNAME `paper` → `cname.vercel-dns.com`, or an A record
for an apex domain). Propagation is usually minutes.

## Regenerating the screenshots

The images in `assets/` come from the repo root:

```bash
uv run python docs/make_images.py
cp docs/edition.svg docs/print-edition.png ui/assets/
```
