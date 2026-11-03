# 07 — Launching the paid website

The website is the same CyberHire app running in **website mode** (`SOC_MODE=web`):

- Visitors see a landing page and pricing.
- People sign up, then start a **3-day free trial with a card**. Stripe charges **$19.99/month** or **$159/year** when the trial ends, unless they cancel first.
- The AI runs on **your** OpenAI key, with fair-use limits: 3 interviews during the trial and 60 per 30 days on a paid plan.

You need four accounts: Render (hosting), Stripe (payments), OpenAI (the AI) and, optionally, Resend (password-reset emails).

## 1. OpenAI: protect your bill
1. At [platform.openai.com](https://platform.openai.com) → **Settings → Limits**, set a **monthly budget**, for example $50 to start, and raise it as subscribers grow.
2. Create a new API key just for the website (**API keys → Create new secret key**) and keep it for step 3.

Rough cost: $0.05–$0.20 per interview, so even heavy subscribers cost you a few dollars a month out of $19.99.

## 2. Stripe: get paid
1. Create an account at [stripe.com](https://stripe.com) and complete **Activate payments**: business details, your bank account for payouts, and ID.
2. Start in **Test mode** (toggle at the top). Developers → API keys → copy the **Secret key** (`sk_test_…`).
3. **Settings → Billing → Customer portal** → turn on "Customers can cancel subscriptions", "update payment methods" and "switch plans" (Monthly ↔ Yearly) → **Save**. The site's "Manage billing" button opens this page.
4. **Settings → Billing → Subscriptions and emails**: turn on emails for upcoming renewals and trial endings, and for failed payments. Many countries' rules require reminding people before a trial converts.

You don't need to create the product or prices. The website creates **CyberHire Pro** with the $19.99 and $159 prices automatically the first time it starts.

## 3. Render: put the site online
1. Create an account at [render.com](https://render.com) and connect your GitHub.
2. **New → Blueprint** → choose `cyberhire-windows-ai-lab`. Render reads `render.yaml` and creates the `cyberhire` service with a 5 GB disk (the Starter plan, about $7/month plus a little for the disk).
3. Fill in the values it asks for:

| Setting | Value |
|---|---|
| `PUBLIC_URL` | Your site address, for example `https://cyberhire.onrender.com` at first and your own domain later |
| `OPENAI_API_KEY` | The key from step 1 |
| `STRIPE_SECRET_KEY` | `sk_test_…` (switch to `sk_live_…` at launch) |
| `STRIPE_WEBHOOK_SECRET` | Leave blank for now (step 4) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Your own login (password of 10+ characters). It gets free full access and the Admin page. |
| `SUPPORT_EMAIL` | Where customers can reach you. It's shown on the site and the legal pages. |
| `RESEND_API_KEY` / `EMAIL_FROM` | Optional, see step 5 |
| `ANTHROPIC_API_KEY` | Optional |

4. **Apply**. The first build takes about 5–10 minutes. When it's live, open the address and you should see the landing page.

## 4. Stripe webhook: let Stripe tell the site about payments
1. Stripe → **Developers → Webhooks → Add endpoint**.
2. Endpoint URL: `https://YOUR-SITE/api/stripe/webhook`
3. Events: `checkout.session.completed`, `checkout.session.expired`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`.
4. Copy the **Signing secret** (`whsec_…`) into Render → your service → **Environment** → `STRIPE_WEBHOOK_SECRET` → **Save** (Render redeploys).

## 5. Password-reset emails (recommended)
1. Create a free account at [resend.com](https://resend.com), add and verify your domain (or use the test sender while trying it out), and create an API key.
2. In Render set `RESEND_API_KEY` and `EMAIL_FROM`, for example `CyberHire <no-reply@yourdomain.com>`.

Without this, "Forgot password" still accepts requests but no email is sent; the link appears only in your Render logs.

## 6. Test everything in Stripe test mode
1. Open your site → **Start free trial** → sign up → choose Monthly.
2. On Stripe's checkout use the test card **4242 4242 4242 4242**, any future date and any CVC.
3. You should land on "Your free trial has started", see **TRIAL · 3 DAYS LEFT** in the header, and be able to start an interview.
4. **Profile → Manage billing** opens Stripe's page. Try cancelling: the header keeps working until the trial ends.
5. Optional: in Stripe use a **test clock** to fast-forward a subscription past the trial and watch it turn into a paid month.

## 7. Go live
1. Stripe: switch off Test mode, copy the **live** secret key, create the **live** webhook (step 4 again in live mode), and turn on the customer portal in live mode.
2. Render: replace `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` with the live values.
3. Custom domain (optional): buy one (about $10–15/year), then in Render → **Settings → Custom domains** add it and follow the DNS steps. Update `PUBLIC_URL` and the Stripe webhook URL to the new domain.
4. Read the **Terms**, **Privacy** and **Refund** pages on your site. They're a solid starting template written for how CyberHire works, but have them checked for your country and situation.

## Running costs at a glance
| Item | Cost |
|---|---|
| Render Starter + 5 GB disk | ~$8/month |
| OpenAI | ~$0.05–0.20 per interview (capped by your budget) |
| Stripe | ~2.9% + 30¢ per successful US card charge |
| Resend | Free for low volume |
| Domain | ~$10–15/year (optional) |

## Changing the defaults
In Render → Environment you can change `TRIAL_DAYS`, `TRIAL_INTERVIEW_LIMIT` and `MONTHLY_INTERVIEW_LIMIT`. Prices live in `backend/lib/stripe_catalog.py` and `backend/routers/billing.py`.

## Growing past one server
The site stores data on its Render disk by default, which is fine for the first several hundred members. When you grow, create a free **MongoDB Atlas** cluster and set `MONGO_URL`. The app switches to MongoDB automatically (move existing data first).
