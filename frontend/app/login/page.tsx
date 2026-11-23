"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, NetworkError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const demoAccounts = [
  { email: "admin@clouddesk.demo", label: "Administrator" },
  { email: "sam.agent@clouddesk.demo", label: "Support agent" },
  { email: "vic.viewer@clouddesk.demo", label: "Read-only viewer" },
];

export default function LoginPage() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState(demoAccounts[1].email);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setSessionExpired(new URLSearchParams(window.location.search).get("reason") === "expired");
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await signIn(email);
      router.replace("/dashboard");
    } catch (reason) {
      if (reason instanceof ApiError || reason instanceof NetworkError) {
        setError(reason.message);
      } else {
        setError("Sign in failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark" aria-hidden="true">C</div>
          <div>
            <div className="brand-name" style={{ color: "var(--ink)" }}>CloudDesk</div>
            <div className="brand-subtitle" style={{ color: "var(--muted)" }}>Support operations</div>
          </div>
        </div>
        <h1 id="login-title">Welcome back</h1>
        <p className="page-description">Sign in to review support activity.</p>
        {sessionExpired && (
          <p className="login-error" role="status">Your session expired. Please sign in again.</p>
        )}
        {error && <p className="login-error" role="alert">{error}</p>}
        <form className="login-form" onSubmit={handleSubmit}>
          <div>
            <label className="field-label" htmlFor="demo-account">Demo account</label>
            <select
              className="text-input"
              id="demo-account"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            >
              {demoAccounts.map((account) => (
                <option key={account.email} value={account.email}>
                  {account.label} — {account.email}
                </option>
              ))}
            </select>
          </div>
          <p className="helper-text">
            Demo sign-in is available only when the backend is configured with
            demo mode enabled. It does not ask for a password.
          </p>
          <button className="button button-primary" type="submit" disabled={submitting}>
            {submitting ? "Signing in..." : "Continue"}
          </button>
        </form>
      </section>
    </main>
  );
}
