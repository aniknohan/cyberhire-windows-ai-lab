# 08 — Launching CyberHire on Google Play

**How it works:** the Play Store app is the full CyberHire app. People sign up, start a **3-day free trial** through Google Play, and then pay **$19.99/month** unless they cancel. Your server (on Render) runs the AI with **your** OpenAI key and checks every subscription with Google before unlocking anything.

| Item | Value |
|---|---|
| Package name | `io.github.aniknohan.cyberhire` |
| Subscription product ID | `cyberhire_pro` |
| Base plan ID | `monthly` (auto-renewing, 1 month, $19.99) |
| Free trial offer ID | `free-trial` (3 days, new customers) |
| Server address built into the app | `https://cyberhire.onrender.com` (`play-app/config.json`) |

Do the steps in order. Step 1 has to come first, because the app needs the server.

---

## Step 1 — Put the server online (Render, ~$8/month)
1. On [platform.openai.com](https://platform.openai.com) → **Settings → Limits**, set a monthly budget (e.g. $50). Create an API key for the server.
2. Create an account at [render.com](https://render.com) and sign in with GitHub.
3. **New → Blueprint** → pick `cyberhire-windows-ai-lab` → keep the service name **cyberhire**.
4. Fill in:
   - `PUBLIC_URL`: `https://cyberhire.onrender.com`
   - `OPENAI_API_KEY`: your key
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD`: your own login (password of 10+ characters)
   - `SUPPORT_EMAIL`: where users and Google can contact you
   - `FREE_ACCESS_EMAILS`: an email you'll create for Google's reviewer, e.g. `playreview.cyberhire@gmail.com`
   - `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`: leave empty for now (step 5)
   - Leave all Stripe fields empty.
5. **Apply** and wait for "Live". Open `https://cyberhire.onrender.com/api/` and you should see `{"message":"CyberHire API"}`.

**If Render gives a different address** (because "cyberhire" was taken), send it to Claude and the app will be rebuilt to point at it.

## Step 2 — Create the app in Play Console
1. [play.google.com/console](https://play.google.com/console) → pay the $25 registration and verify your identity, if you haven't already.
2. **Create app** → App name **CyberHire** → **App** → **Free** (subscriptions are in-app purchases) → accept the declarations.
3. **Test and release → Testing → Internal testing → Create new release**.
   - Accept **Play App Signing**: Google keeps the app signing key, and your upload key only signs uploads.
   - Upload **CyberHire-1.0.0.aab** → release name `1.0.0` → **Save → Review → Start rollout**.
   - Add yourself as an internal tester (create an email list with your Gmail) and open the opt-in link on your phone.

## Step 3 — Create the $19.99 subscription with a 3-day free trial
1. **Monetize with Play → Products → Subscriptions → Create subscription**.
   - Product ID: **`cyberhire_pro`** (exactly this)
   - Name: **CyberHire Pro**
2. **Add base plan**:
   - Base plan ID: **`monthly`**, **Auto-renewing**, billing period **1 month**, grace period as offered
   - **Set prices** → United States **$19.99** → let Google convert for other countries → **Activate**
3. In the base plan → **Add offer**:
   - Offer ID: **`free-trial`**
   - Eligibility: **New customer acquisition → Never had this subscription**
   - Phase: **Free trial**, **3 days**
   - **Activate**
4. Fill in the subscription's benefits and description (shown in Google's purchase screen):
   - Unlimited AI interview practice
   - SOC investigation rounds
   - Reports and coaching

## Step 4 — Let yourself test purchases for free
1. Play Console → **Settings (gear) → License testing** → add your Gmail → **Save**.
2. On your Pixel, install the app from the internal-testing link, sign up, then **Start 3-day free trial**. As a license tester you're never charged, and test subscriptions renew every few minutes so you can watch the whole cycle.

## Step 5 — Let the server check subscriptions with Google
1. [console.cloud.google.com](https://console.cloud.google.com) → create a project (e.g. "cyberhire-play").
2. **APIs & Services → Library** → enable **Google Play Android Developer API**.
3. **IAM & Admin → Service accounts → Create service account** (name: `cyberhire-play`) → **Done**.
4. Open it → **Keys → Add key → Create new key → JSON** → a file downloads. Keep it private.
5. Play Console → **Users and permissions → Invite new users** → paste the service account's email (ends in `iam.gserviceaccount.com`).
   - **App permissions** → add CyberHire → tick **View financial data, orders and cancellation survey responses** and **Manage orders and subscriptions** → **Invite user**.
6. Render → your service → **Environment** → `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` → paste the **entire contents** of the JSON file → **Save**.

Google can take up to 24 hours to activate a new service account's access. If a test purchase says "Couldn't check the subscription with Google Play", wait and tap **Restore purchase** later.

## Step 6 — Store listing and app content
- **Main store listing**: short description, full description, app icon (512×512: `play-app/assets/icon-only.png`), feature graphic (1024×500) and at least 2 phone screenshots (take them on your Pixel).
- **App content**:
  - Privacy policy: `https://cyberhire.onrender.com/privacy`
  - App access: **All or some functionality is restricted** → give the reviewer login (the email in `FREE_ACCESS_EMAILS` plus its password; create that account in the app first)
  - Ads: **No**
  - Content rating: complete the questionnaire (Education / Reference; no violence etc.)
  - Target audience: **18 and over**
  - Data safety:
    - Collected: **Name, Email, Purchase history, Voice or sound recordings, Other user-generated content (answers), App interactions**
    - Purpose: App functionality / Account management
    - Encrypted in transit: **Yes**
    - Deletion: **Yes** → `https://cyberhire.onrender.com/delete-account`
    - Shared with third parties: **No** (OpenAI and Google act as your service providers)
  - Account deletion URL: `https://cyberhire.onrender.com/delete-account`
  - Government / financial / health features: **No**
  - **AI-generated content**: the app has a **Report** (flag) button in the header and the interview call. Reports are saved on the server and emailed to `SUPPORT_EMAIL` when email is set up.

## Step 7 — Closed test with 12 testers for 14 days, then production
1. **Testing → Closed testing → Create track** → upload the same `.aab` (or a newer build) → add **at least 12 testers** (email list) → roll out.
2. Testers must opt in and keep the app installed and used for **14 days in a row**.
3. Then **Dashboard → Apply for production** → answer the questions → Google reviews (usually a few days).
4. When approved, **Production → Create release** → upload the latest `.aab` → roll out.

## Updates
Every new version needs a higher version code. The build does this automatically.

- Ask Claude for a new build.
- Provide the upload key files (`cyberhire-upload-key.jks` and the password text) so the bundle can be signed.
- Upload the new `.aab` in Play Console.

To build in GitHub instead, add two repository secrets under **Settings → Secrets and variables → Actions**:
- `PLAY_UPLOAD_KEYSTORE_B64`: the base64 of the `.jks` file
- `PLAY_UPLOAD_KEY_PASSWORD`: the password

With those set, the **Build Google Play app** workflow produces an already signed `.aab`.
