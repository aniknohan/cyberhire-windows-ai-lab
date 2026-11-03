import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import PublicLayout from "@/components/PublicLayout";
import { useConfig } from "@/lib/config";

const UPDATED = "November 3, 2026";

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PublicLayout>
      <article className="mx-auto max-w-3xl px-4 py-14 sm:px-6" data-testid="legal-page">
        <h1 className="font-heading text-3xl font-semibold text-white sm:text-4xl">{title}</h1>
        <p className="mt-2 text-xs text-slate-500">Last updated {UPDATED}</p>
        <div className="mt-8 space-y-5 text-sm leading-relaxed text-slate-300 [&_h2]:mt-8 [&_h2]:font-heading [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-white [&_li]:ml-5 [&_li]:list-disc [&_a]:text-sky-400 [&_a:hover]:underline">
          {children}
        </div>
      </article>
    </PublicLayout>
  );
}

function Contact() {
  const { data } = useConfig();
  return data?.support_email ? <a href={`mailto:${data.support_email}`}>{data.support_email}</a> : <span>the contact address on this website</span>;
}

export function Terms() {
  return (
    <LegalPage title="Terms of Service">
      <p>These terms cover your use of CyberHire, the AI interview-practice service at this website and in the CyberHire apps ("CyberHire", "we", "us"). CyberHire is operated by Anik Nohan. By creating an account you agree to these terms.</p>
      <h2>The service</h2>
      <p>CyberHire simulates job interviews for cybersecurity roles using AI. Companies, interviewers and scenarios are fictional. Scores, hiring decisions and feedback are AI-generated practice guidance: they may contain mistakes and are not a prediction or guarantee of any real hiring outcome.</p>
      <h2>Your account</h2>
      <ul>
        <li>You must be at least 16 years old and give accurate information.</li>
        <li>Keep your password private. You're responsible for activity on your account.</li>
        <li>One person per account. Accounts may not be shared or resold.</li>
      </ul>
      <h2>Subscriptions, free trial and billing</h2>
      <ul>
        <li>CyberHire Pro costs $19.99 per month (plus any applicable tax), billed in advance. Where offered on the website, a yearly plan costs $159 per year. Prices in the Android app are shown by Google Play in your local currency.</li>
        <li>New subscribers get one free trial of 3 days. A payment method is required to start it. Unless you cancel before the trial ends, your subscription starts automatically and you're charged the plan price.</li>
        <li>Subscriptions renew automatically at the end of each billing period until you cancel. You can cancel anytime from your Profile (website) or in Google Play (if you subscribed in the Android app). Cancellation takes effect at the end of the current period, and you keep access until then.</li>
        <li>Website payments are processed by Stripe; in-app purchases are processed by Google Play. We never see or store your full card number.</li>
        <li>We may change prices with at least 30 days' notice before your next renewal.</li>
        <li>Refunds are covered by our <Link to="/refund-policy">Refund policy</Link>.</li>
      </ul>
      <h2>Fair use</h2>
      <p>Plans include generous but limited use so the service stays fast and affordable for everyone: currently up to 3 interviews during the free trial and up to 60 interviews per 30 days on a paid plan, plus practice modules. Automated access, scraping, attempts to extract the question bank or prompts, reverse engineering, abusive or illegal content, and attempts to disrupt the service are not allowed and may lead to suspension.</p>
      <h2>Your content</h2>
      <p>You own what you submit (answers, recordings, resume). You give us permission to store and process it only to provide the service to you, including sending it to our AI providers to generate questions, transcripts and feedback. You can delete recordings, interviews or your whole account at any time.</p>
      <h2>Our content</h2>
      <p>The CyberHire software, question bank, scenarios and design belong to us. Your subscription gives you a personal, non-transferable right to use them for your own interview preparation.</p>
      <h2>Availability and changes</h2>
      <p>We work to keep CyberHire available but can't promise it will be uninterrupted or error-free. We may improve, change or discontinue features. If we discontinue the paid service, we'll refund the unused part of any prepaid period.</p>
      <h2>Disclaimers and liability</h2>
      <p>CyberHire is provided "as is". To the fullest extent the law allows, we aren't liable for indirect or consequential losses, and our total liability for any claim is limited to the amount you paid us in the 12 months before the claim. Nothing in these terms limits rights you have under consumer protection laws that can't be excluded.</p>
      <h2>Ending your account</h2>
      <p>You can delete your account anytime from your Profile. We may suspend accounts that break these terms. We'll tell you about material changes to these terms by email or on the website before they take effect.</p>
      <h2>Contact</h2>
      <p>Questions about these terms: <Contact />.</p>
    </LegalPage>
  );
}

export function Privacy() {
  return (
    <LegalPage title="Privacy Policy">
      <p>This policy explains what CyberHire collects, why, and the choices you have. CyberHire is operated by Anik Nohan, who is responsible for your data.</p>
      <h2>What we collect</h2>
      <ul>
        <li><b>Account:</b> your name, email address and a securely hashed password.</li>
        <li><b>Profile:</b> target role, experience level and, if you choose to upload one, your resume and its summary.</li>
        <li><b>Interview content:</b> the questions you're asked, your answers (transcripts), scores, feedback and reports.</li>
        <li><b>Voice and video:</b> when you answer by voice, the audio is sent for transcription. Recordings are saved to your account only if recording is turned on for that interview, and you can delete them anytime. Your camera video is shown only to you on your own screen; it is never recorded or uploaded.</li>
        <li><b>Billing:</b> your plan, subscription status and payment provider IDs. Card details are handled by Stripe or Google Play, not by us.</li>
        <li><b>Technical:</b> a sign-in cookie, IP address and basic server logs for security and abuse prevention.</li>
      </ul>
      <h2>How we use it</h2>
      <p>Only to run CyberHire for you: conducting and scoring interviews, showing your progress, billing, account emails such as password resets, preventing abuse, and keeping the service secure. We don't sell your data, and we don't use advertising trackers.</p>
      <h2>Who processes it for us</h2>
      <ul>
        <li><b>OpenAI</b> (and Anthropic, if enabled): interview questions, transcription, voices and scoring. Content is sent through their business APIs, which under their API terms is not used to train their models by default.</li>
        <li><b>Stripe</b> and <b>Google Play</b>: payments and subscriptions.</li>
        <li><b>Our hosting and email providers</b>: storing the service's data and sending account emails.</li>
      </ul>
      <h2>Keeping and deleting data</h2>
      <p>We keep your data while your account is open. You can delete individual interviews and recordings, or your whole account, from your Profile. Deleting your account permanently removes your profile, interviews, transcripts and recordings, and cancels any website subscription. Backups are overwritten within 30 days. We keep minimal billing records where the law requires it. See <Link to="/delete-account">how to delete your account</Link>.</p>
      <h2>Your rights</h2>
      <p>Depending on where you live, you may have the right to access, correct, export or delete your personal data, or to object to some processing. Contact us at <Contact /> and we'll respond within 30 days.</p>
      <h2>Security</h2>
      <p>Connections are encrypted (HTTPS), passwords are hashed, and access to your data requires your sign-in. No system is perfectly secure, so please use a strong, unique password.</p>
      <h2>Children</h2>
      <p>CyberHire is not intended for anyone under 16, and we don't knowingly collect their data.</p>
      <h2>Changes</h2>
      <p>We'll post changes here and, for important ones, email you before they take effect.</p>
      <h2>Contact</h2>
      <p><Contact /></p>
    </LegalPage>
  );
}

export function RefundPolicy() {
  return (
    <LegalPage title="Refund Policy">
      <h2>Free trial</h2>
      <p>New subscribers get 3 days free. Cancel any time before the trial ends and you won't be charged anything.</p>
      <h2>Cancelling</h2>
      <p>You can cancel anytime. Your plan stays active until the end of the period you've already paid for, and you won't be charged again. We don't give partial refunds for unused time in a billing period, except where the law requires it.</p>
      <h2>Charged by mistake?</h2>
      <p>If you were charged after forgetting to cancel and haven't used CyberHire since the charge, contact us within 7 days of the charge at <Contact /> and we'll refund it. We also refund duplicate charges and charges caused by our errors.</p>
      <h2>Google Play purchases</h2>
      <p>Subscriptions bought in the Android app are billed by Google. Refunds for those follow Google Play's refund policy; you can request one in Google Play, or contact us and we'll help.</p>
    </LegalPage>
  );
}

export function DeleteAccountInfo() {
  return (
    <LegalPage title="Delete your CyberHire account">
      <p>You can permanently delete your CyberHire account and its data at any time, from the website or the Android app.</p>
      <h2>Steps</h2>
      <ul>
        <li>Sign in at this website (or in the CyberHire Android app).</li>
        <li>Open <b>Profile</b> and scroll to <b>Delete account</b>.</li>
        <li>Type <b>DELETE</b>, enter your password and confirm.</li>
      </ul>
      <h2>What's deleted</h2>
      <p>Your profile, resume, interviews, transcripts, scores, reports and voice recordings are deleted immediately. Any website (Stripe) subscription is cancelled so you won't be charged again. Backups are overwritten within 30 days. We keep minimal payment records only where tax law requires it.</p>
      <h2>Subscribed through Google Play?</h2>
      <p>Deleting your account doesn't cancel a Google Play subscription by itself. Cancel it in the Play Store app → Payments &amp; subscriptions → Subscriptions.</p>
      <h2>Can't sign in?</h2>
      <p>Use <Link to="/forgot-password">Forgot password</Link>, or email <Contact /> from your account's email address and ask us to delete your account.</p>
    </LegalPage>
  );
}
