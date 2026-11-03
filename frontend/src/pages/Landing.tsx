import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, Brain, FileSearch, Gavel, Mic, ShieldCheck, Target, Video } from "lucide-react";
import PublicLayout from "@/components/PublicLayout";
import { PlanCards } from "@/pages/Pricing";
import { useConfig } from "@/lib/config";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const FEATURES = [
  { icon: Video, title: "Real interview loop", text: "Recruiter screen, technical round, live SOC investigation and hiring manager, with 8 interviewers who each sound and think differently." },
  { icon: Mic, title: "Answer out loud", text: "Interviewers speak their questions and you answer by voice, just like a video call. Typing works too." },
  { icon: FileSearch, title: "Live alert investigations", text: "Triage phishing, password spraying, PowerShell abuse, beaconing and ransomware precursors with evidence on screen." },
  { icon: Brain, title: "Follow-ups that dig deeper", text: "The interviewer reacts to what you actually said: asks why, challenges vague answers and raises the difficulty when you're doing well." },
  { icon: BarChart3, title: "Two scores, not one", text: "Technical job readiness and professional communication are scored separately, with pace, filler words and clarity measured from your voice." },
  { icon: Gavel, title: "A real hiring decision", text: "Strong Hire to No Hire with the reasons, your strengths and gaps, and a 5-step plan for what to practise next." },
];

const STEPS = [
  { n: "1", title: "Pick the job", text: "SOC Analyst L1–L3, Incident Response, Threat Detection and more. Choose a company type and a tool focus such as Splunk or Active Directory." },
  { n: "2", title: "Do the interview", text: "Join the call, meet your interviewers and answer out loud. Use Coach mode for instant feedback, or Real mode for the full pressure." },
  { n: "3", title: "Get your report", text: "See your hiring decision, scores for every answer, stronger model answers and the exact topics to study before the real thing." },
];

const FAQ = [
  { q: "How does the free trial work?", a: "Choose monthly or yearly and add a card. You're not charged for the first 3 days. If you cancel before the trial ends, you pay nothing; otherwise your plan starts automatically." },
  { q: "Can I cancel anytime?", a: "Yes. Cancel anytime from your Profile (Manage billing). You keep access until the end of the period you've paid for." },
  { q: "Who is CyberHire for?", a: "People preparing for SOC Analyst and other blue-team cybersecurity interviews, from career changers going for their first L1 role to analysts moving up to L2 and L3." },
  { q: "Do I need an API key or any setup?", a: "No. Everything is included in your plan. You only need a browser with a microphone; a camera is optional." },
  { q: "Is my data private?", a: "Your interviews, recordings and reports are private to your account, and you can delete recordings or your whole account at any time. See the Privacy policy." },
  { q: "Are the companies and interviewers real?", a: "No. Companies and interviewers are fictional, generated for practice. The questions and scenarios reflect what real SOC hiring teams ask." },
];

export default function Landing() {
  const nav = useNavigate();
  const { data: cfg } = useConfig();
  const trialDays = cfg?.trial_days ?? 3;
  return (
    <PublicLayout>
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(56,189,248,0.12),transparent_60%)]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pt-16 pb-12 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-24">
          <div>
            <div className="mb-4 font-mono text-[11px] uppercase tracking-[0.2em] text-sky-400/90">AI interview simulator for cybersecurity</div>
            <h1 className="font-heading text-4xl leading-[1.05] font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl" data-testid="landing-title">
              Walk into your SOC interview like you've already done it.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-slate-300">
              Practise realistic voice interviews with a recruiter, senior analyst, incident response lead and SOC manager. Get scored, get a hiring decision, and know exactly what to fix.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/register" className={cn(buttonVariants({ size: "lg" }), "h-12 px-6 text-base")} data-testid="hero-cta">
                Start your {trialDays}-day free trial <ArrowRight />
              </Link>
              <a href="#how" className={cn(buttonVariants({ size: "lg", variant: "secondary" }), "h-12 px-6 text-base")}>See how it works</a>
            </div>
            <p className="mt-3 text-xs text-slate-500">Then $19.99/month or $159/year. Cancel anytime before the trial ends and pay nothing.</p>
          </div>
          <div className="relative">
            <div className="absolute -inset-4 rounded-3xl bg-sky-500/10 blur-2xl" />
            <img src="/screens/room.jpg" alt="A CyberHire live interview with an interviewer asking about a Splunk alert" className="relative rounded-2xl border border-white/10 shadow-2xl" />
          </div>
        </div>
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-4 px-4 pb-16 text-center sm:grid-cols-4 sm:px-6">
          {[["638", "SOC interview questions"], ["4", "interview rounds"], ["8", "AI interviewers"], ["5", "live investigation scenarios"]].map(([n, l]) => (
            <div key={l} className="rounded-xl border border-white/[0.06] bg-white/[0.02] py-4">
              <div className="font-heading text-3xl font-semibold text-white">{n}</div>
              <div className="text-xs text-slate-400">{l}</div>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="border-t border-white/[0.06] py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">Everything a real SOC interview throws at you</h2>
          <p className="mt-3 max-w-2xl text-slate-400">Built around how security operations teams actually hire: methodology, judgement and clear communication, not just definitions.</p>
          <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6">
                <f.icon className="size-6 text-sky-400" />
                <h3 className="mt-4 font-heading text-lg font-semibold text-white">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="border-t border-white/[0.06] py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-2">
          <div>
            <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">How it works</h2>
            <div className="mt-8 space-y-6">
              {STEPS.map((s) => (
                <div key={s.n} className="flex gap-4">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-sky-500/15 font-mono text-sm text-sky-300">{s.n}</div>
                  <div>
                    <h3 className="font-heading text-lg font-semibold text-white">{s.title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-slate-400">{s.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <img src="/screens/report.jpg" alt="A CyberHire interview report with a hire decision and scores" className="rounded-2xl border border-white/10 shadow-2xl" loading="lazy" />
        </div>
      </section>

      <section className="border-t border-white/[0.06] py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-[1.4fr_1fr]">
          <img src="/screens/dashboard.jpg" alt="The CyberHire dashboard with readiness and communication scores" className="rounded-2xl border border-white/10 shadow-2xl" loading="lazy" />
          <div>
            <Target className="size-6 text-sky-400" />
            <h2 className="mt-4 font-heading text-3xl font-semibold text-white">Watch your readiness climb</h2>
            <p className="mt-3 text-slate-400">Your dashboard tracks job readiness and communication over time, shows your strongest and weakest topics, and future interviewers deliberately revisit the areas you struggled with.</p>
          </div>
        </div>
      </section>

      <section id="pricing" className="border-t border-white/[0.06] py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">Simple pricing</h2>
          <p className="mt-3 mb-10 max-w-2xl text-slate-400">Start with {trialDays} days free. Cancel anytime.</p>
          <PlanCards onChoose={() => nav("/register")} ctaFor={() => `Start ${trialDays}-day free trial`} />
          <div className="mt-6 flex items-center gap-2 text-xs text-slate-500"><ShieldCheck className="size-4" /> Secure payments by Stripe. One free trial per person.</div>
        </div>
      </section>

      <section id="faq" className="border-t border-white/[0.06] py-20">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <h2 className="font-heading text-3xl font-semibold text-white sm:text-4xl">Questions</h2>
          <div className="mt-8 divide-y divide-white/[0.06] rounded-2xl border border-white/[0.06]">
            {FAQ.map((f) => (
              <details key={f.q} className="group p-5">
                <summary className="cursor-pointer list-none font-medium text-white marker:hidden">{f.q}</summary>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{f.a}</p>
              </details>
            ))}
          </div>
          <div className="mt-12 text-center">
            <Link to="/register" className={cn(buttonVariants({ size: "lg" }), "h-12 px-6 text-base")}>Start your free trial <ArrowRight /></Link>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
