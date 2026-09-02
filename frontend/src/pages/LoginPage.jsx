import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Eye, EyeOff, LockKeyhole, User, Sparkles } from "lucide-react";
import BrandLogo from "../components/shared/BrandLogo";

const LoginPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showTransition, setShowTransition] = useState(false);
  const [error, setError] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const me = await login(email, password);
      setShowTransition(true);
      const dest = me?.role === "admin" ? "/dashboard" : "/my-dashboard";
      setTimeout(() => {
        navigate(dest, { replace: true });
      }, 1100);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Invalid credentials");
      toast.error("Login failed. Please check your credentials.");
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page min-h-screen overflow-hidden text-[var(--executive-text-strong)]">
      <AnimatePresence>
        {showTransition && (
          <motion.div
            className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-white"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <BrandLogo variant="splash" darkBackground={false} className="mb-8" />
            <div className="h-1 w-48 overflow-hidden rounded-full bg-[rgb(var(--mist-rgb)/1)]">
              <motion.div
                className="h-full"
                style={{
                  background: "linear-gradient(135deg, #4A7AB5 0%, #2563A8 50%, #1B4F8C 100%)",
                }}
                initial={{ width: "0%" }}
                animate={{ width: "100%" }}
                transition={{ duration: 0.8 }}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        <section
          className="relative hidden min-h-screen overflow-hidden px-10 py-10 text-white lg:flex lg:flex-col lg:justify-between"
          style={{
            background: `
              radial-gradient(ellipse 66% 56% at 92% 6%, rgba(74,122,181,0.85) 0%, rgba(37,99,168,0.55) 26%, rgba(27,79,140,0.32) 52%, transparent 70%),
              radial-gradient(ellipse 64% 54% at 82% 60%, rgba(13,42,74,0.99) 0%, rgba(10,22,40,0.88) 30%, rgba(7,14,28,0.54) 58%, transparent 78%),
              radial-gradient(ellipse 44% 36% at 90% 96%, rgba(37,99,168,0.55) 0%, rgba(27,79,140,0.32) 44%, transparent 64%),
              radial-gradient(ellipse 30% 24% at 15% 82%, rgba(27,79,140,0.28) 0%, transparent 56%),
              radial-gradient(ellipse 50% 44% at 50% 50%, rgba(10,22,40,0.22) 0%, transparent 65%),
              linear-gradient(142deg, #050910 0%, #0A1628 26%, #0D2A4A 62%, #04070f 100%)
            `,
          }}
        >
          <div className="absolute inset-0 opacity-[0.16]" style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.18) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.18) 1px, transparent 1px)",
            backgroundSize: "42px 42px",
          }} />
          <div className="relative z-10">
            <BrandLogo variant="sidebar" darkBackground className="h-14 max-w-[13rem]" />
          </div>

          <motion.div
            className="relative z-10 max-w-xl"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
          >
            <span className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-white/80 backdrop-blur">
              <Sparkles size={14} />
              Executive Console
            </span>
            <h1 className="text-5xl font-bold leading-tight text-white">
              Sales intelligence with a quieter command center.
            </h1>
            <p className="mt-5 max-w-lg text-base text-white/68">
              Track conversations, lead quality, campaigns, and team performance from one polished workspace.
            </p>
          </motion.div>

          <div className="relative z-10 grid grid-cols-3 gap-3 text-sm text-white/70">
            {["Leads", "Calls", "Campaigns"].map((item) => (
              <div key={item} className="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 backdrop-blur">
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="login-form-panel relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10 sm:px-6 lg:px-10">
          <div
            className="absolute -right-40 top-12 h-[34rem] w-[34rem] rounded-full blur-3xl"
            style={{ background: "rgb(var(--lavender-rgb) / 0.24)" }}
          />
          <div
            className="absolute -bottom-48 left-1/4 h-[28rem] w-[28rem] rounded-full blur-3xl"
            style={{ background: "rgb(var(--success-rgb) / 0.13)" }}
          />

          <motion.div
            className="relative z-10 w-full max-w-md"
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55 }}
          >
            <div className="mb-7 flex flex-col items-center text-center" data-testid="login-logo">
              <div className="login-logo-badge">
                <BrandLogo
                  variant="sidebar"
                  darkBackground
                  className="h-12 max-w-[11.5rem]"
                  testId="login-logo"
                />
              </div>
              <span
                className="mt-5 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.20em]"
                style={{
                  background: "rgb(var(--royal-rgb)/0.08)",
                  border: "1px solid rgb(var(--royal-rgb)/0.14)",
                  color: "rgb(var(--royal-rgb)/1)",
                }}
              >
                Secure Access
              </span>
            </div>

            <div className="login-card p-6 sm:p-8">
              <div className="mb-7">
                <h1 className="login-title text-2xl font-bold" data-testid="login-title">
                  Sign in
                </h1>
                <p className="login-copy mt-2 text-sm">
                  Continue to your workspace.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="login-label mb-2 block text-sm font-medium">User Name</label>
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--executive-text-muted)]" />
                    <input
                      type="text"
                      autoComplete="username"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="login-input h-12 w-full rounded-xl px-11 text-sm outline-none transition"
                      placeholder="Team Hindu"
                      required
                      data-testid="login-email-input"
                    />
                  </div>
                </div>

                <div>
                  <label className="login-label mb-2 block text-sm font-medium">Password</label>
                  <div className="relative">
                    <LockKeyhole className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--executive-text-muted)]" />
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="login-input h-12 w-full rounded-xl px-11 pr-12 text-sm outline-none transition"
                      placeholder="Enter your password"
                      required
                      data-testid="login-password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-4 top-1/2 -translate-y-1/2 text-[var(--executive-text-muted)] transition hover:text-[var(--executive-accent)]"
                      data-testid="toggle-password-btn"
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl border border-[rgb(var(--danger-rgb)/0.20)] bg-[rgb(var(--danger-rgb)/0.08)] px-4 py-3 text-center text-sm text-[var(--executive-error)]"
                    data-testid="login-error"
                  >
                    {error}
                  </motion.div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="login-btn h-12 w-full rounded-xl text-sm font-semibold text-white outline-none transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60"
                  style={{
                    background: "linear-gradient(135deg, #4A7AB5 0%, #2563A8 50%, #1B4F8C 100%)",
                    boxShadow: "0 12px 32px rgba(27,79,140,0.32)",
                  }}
                  data-testid="login-submit-btn"
                >
                  {isLoading ? "Signing in..." : "Sign in"}
                </button>
              </form>
            </div>
          </motion.div>
        </section>
      </main>
    </div>
  );
};

export default LoginPage;
