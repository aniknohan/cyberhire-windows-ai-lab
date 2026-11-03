import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import AuthCallback from "@/pages/AuthCallback";
import { Toaster } from "@/components/ui/sonner";
import { AuthLoader, RequireAuth, RequirePlan, useMe } from "@/lib/auth";
import { useConfig } from "@/lib/config";
import { IS_NATIVE } from "@/lib/api";
import Landing from "@/pages/Landing";
import { DeleteAccountInfo, Privacy, RefundPolicy, Terms } from "@/pages/Legal";
import { ForgotPassword, ResetPassword } from "@/pages/Account";
import AuthPage from "@/pages/AuthPage";
import Dashboard from "@/pages/Dashboard";
import InterviewSetup from "@/pages/InterviewSetup";
import Lobby from "@/pages/Lobby";
import Room from "@/pages/Room";
import Waiting from "@/pages/Waiting";
import Report from "@/pages/Report";
import History from "@/pages/History";
import { CommunicationSkills, TechnicalSkills } from "@/pages/Skills";
import Practice from "@/pages/Practice";
import Profile from "@/pages/Profile";
import Admin from "@/pages/Admin";
import DrillPage from "@/pages/Drill";
import Pricing, { PaymentCancel, PaymentSuccess } from "@/pages/Pricing";

const guard = (el: React.ReactNode, admin = false) => <RequireAuth admin={admin}>{el}</RequireAuth>;
// Pages that run the AI: on the website they need an active trial or subscription.
const paid = (el: React.ReactNode) => guard(<RequirePlan>{el}</RequirePlan>);

/** "/": the marketing page for visitors on the website, the dashboard for signed-in members. */
function Home() {
  const { data: cfg, isLoading: cfgLoading } = useConfig();
  const { data: me, isLoading } = useMe();
  if (cfgLoading || isLoading) return <AuthLoader />;
  if (!me) return cfg?.mode === "web" && !IS_NATIVE ? <Landing /> : <Navigate to="/login" replace />;
  return paid(<Dashboard />);
}

function DesktopOnlyRedirect({ children }: { children: React.ReactNode }) {
  const { data: cfg, isLoading } = useConfig();
  if (isLoading) return <AuthLoader />;
  return cfg?.mode === "web" ? <>{children}</> : <Navigate to="/" replace />;
}

export default function App() {
  const location = useLocation();
  // Google sign-in return: process the one-time session_id before any route renders.
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <>
      <Routes>
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route path="/" element={<Home />} />
        <Route path="/dashboard" element={paid(<Dashboard />)} />
        <Route path="/interview/new" element={paid(<InterviewSetup />)} />
        <Route path="/interview/:id/lobby" element={paid(<Lobby />)} />
        <Route path="/interview/:id/room" element={paid(<Room />)} />
        <Route path="/interview/:id/waiting" element={guard(<Waiting />)} />
        <Route path="/interview/:id/report" element={guard(<Report />)} />
        <Route path="/history" element={guard(<History />)} />
        <Route path="/skills/communication" element={guard(<CommunicationSkills />)} />
        <Route path="/skills/technical" element={guard(<TechnicalSkills />)} />
        <Route path="/practice" element={paid(<Practice />)} />
        <Route path="/practice/drill/:id" element={paid(<DrillPage />)} />
        <Route path="/pricing" element={<DesktopOnlyRedirect>{guard(<Pricing />)}</DesktopOnlyRedirect>} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/refund-policy" element={<RefundPolicy />} />
        <Route path="/delete-account" element={<DeleteAccountInfo />} />
        <Route path="/payment/success" element={guard(<PaymentSuccess />)} />
        <Route path="/payment/cancel" element={guard(<PaymentCancel />)} />
        <Route path="/profile" element={guard(<Profile />)} />
        <Route path="/admin" element={guard(<Admin />, true)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster richColors />
    </>
  );
}
