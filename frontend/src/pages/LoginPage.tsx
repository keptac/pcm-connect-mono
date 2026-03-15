import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi, messagesApi, universitiesApi } from "../api/endpoints";
import adventistSymbolWhite from "../images/adventist-symbol--white.png";
import heroImage from "../images/background-image-1.jpg";
import pcmLogo from "../images/pcm_logo.png";
import { bootstrapChatKeys, clearSessionWrappingKey } from "../lib/chatCrypto";

type GeneralLookupMatch = {
  member_id: string;
  member_number?: string | null;
  first_name: string;
  last_name: string;
  university_name?: string | null;
  status: string;
  start_year?: number | null;
  program_of_study_name?: string | null;
  email_hint?: string | null;
};

async function persistSession(
  accessToken: string,
  refreshToken: string,
  password: string,
  queryClient: ReturnType<typeof useQueryClient>,
  options?: { deferChatBootstrap?: boolean },
) {
  localStorage.setItem("pcm_access_token", accessToken);
  localStorage.setItem("pcm_refresh_token", refreshToken);
  queryClient.clear();
  clearSessionWrappingKey();
  if (options?.deferChatBootstrap) {
    return;
  }
  try {
    await bootstrapChatKeys(password, messagesApi.getKeyBundle, messagesApi.setKeyBundle);
  } catch {
    clearSessionWrappingKey();
  }
}

export default function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"login" | "register">("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const [lastName, setLastName] = useState("");
  const [selectedUniversityId, setSelectedUniversityId] = useState("");
  const [startYear, setStartYear] = useState("");
  const [matches, setMatches] = useState<GeneralLookupMatch[]>([]);
  const [selectedMemberId, setSelectedMemberId] = useState("");
  const [registrationEmail, setRegistrationEmail] = useState("");
  const [registrationPassword, setRegistrationPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [donorInterest, setDonorInterest] = useState(false);
  const [registrationError, setRegistrationError] = useState("");
  const [registrationInfo, setRegistrationInfo] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const universitiesQuery = useQuery({
    queryKey: ["public-universities"],
    queryFn: universitiesApi.listPublic,
    enabled: mode === "register"
  });

  function resetRegistration() {
    setMatches([]);
    setSelectedMemberId("");
    setRegistrationEmail("");
    setRegistrationPassword("");
    setConfirmPassword("");
    setDonorInterest(false);
    setRegistrationError("");
    setRegistrationInfo("");
  }

  return (
    <div className="login-shell">
      <div className="login-backdrop" style={{ backgroundImage: `url(${heroImage})` }} />
      <div className="login-overlay" />
      <img className="login-corner-symbol" src={adventistSymbolWhite} alt="Adventist symbol" />
      <div className="login-grid">
        <section className="login-story">
          <div className="login-brand">
            <div className="login-brand-mark">
              <img className="login-brand-logo" src={pcmLogo} alt="PCM logo" />
            </div>
            <div>
              <p className="eyebrow text-white/70">Public Campus Ministries</p>
              <h2 className="login-brand-title">PCM Connect</h2>
            </div>
          </div>

          <div className="login-story-copy space-y-5">
            <p className="login-kicker">One mission network. Every campus in view.</p>
            <h1 className="login-title">Campus | Church | Community.</h1>
            <p className="login-copy">
              Sign in to manage public campuses with one shared workspace for students, alumni, staff, calendar events,
              finance receipting, ministry reporting, and trusted networking across the PCM circle.
            </p>
          </div>
        </section>

        <section className="login-card">
          <div className="login-card-head">
            <img className="login-card-logo" src={pcmLogo} alt="PCM logo" />
            <div className="space-y-2">
              <p className="eyebrow">Secure access</p>
              <h2 className="text-3xl font-semibold text-slate-950">
                {mode === "login" ? "Sign in" : "General user registration"}
              </h2>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-2 gap-2 rounded-[16px] bg-slate-100 p-2">
            <button
              className={mode === "login" ? "primary-button justify-center" : "secondary-button justify-center"}
              type="button"
              onClick={() => {
                setMode("login");
                setError("");
              }}
            >
              Sign in
            </button>
            <button
              className={mode === "register" ? "primary-button justify-center" : "secondary-button justify-center"}
              type="button"
              onClick={() => {
                setMode("register");
                setRegistrationError("");
              }}
            >
              Register
            </button>
          </div>

          {mode === "login" ? (
            <form
              className="mt-8 grid gap-4"
              onSubmit={async (event) => {
                event.preventDefault();
                setError("");
                try {
                  const data = await authApi.login(email, password);
                  await persistSession(data.access_token, data.refresh_token, password, queryClient, {
                    deferChatBootstrap: Boolean(data.password_reset_required)
                  });
                  navigate("/", { replace: true });
                } catch (err: any) {
                  setError(err?.response?.data?.detail || "Login failed");
                }
              }}
            >
              <label className="field-shell">
                <span className="field-label">Email or member ID</span>
                <input
                  className="field-input"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="admin@pcm.local"
                />
              </label>

              <label className="field-shell">
                <span className="field-label">Password</span>
                <input
                  className="field-input"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                />
              </label>

              {error ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}

              <button className="primary-button w-full justify-center" type="submit">
                Continue to dashboard
              </button>
            </form>
          ) : (
            <div className="mt-8 space-y-5">
              <form
                className="grid gap-4"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setRegistrationError("");
                  setRegistrationInfo("");
                  setMatches([]);
                  setSelectedMemberId("");

                  try {
                    const data = await authApi.lookupGeneralUser({
                      last_name: lastName,
                      university_id: Number(selectedUniversityId),
                      start_year: Number(startYear)
                    });
                    setMatches(data);
                    if (data.length === 0) {
                      setRegistrationError("No non-student PCM record matched that exact surname, university or campus, and joining year.");
                    } else {
                      setSelectedMemberId(data[0].member_id);
                      setRegistrationInfo("These three items matched an existing PCM record. Select the profile, then set your password.");
                    }
                  } catch (err: any) {
                    setRegistrationError(err?.response?.data?.detail || "Unable to search for a matching record.");
                  }
                }}
              >
                <label className="field-shell">
                  <span className="field-label">Surname</span>
                  <input
                    className="field-input"
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                    placeholder="Enter your last name"
                  />
                </label>

                <label className="field-shell">
                  <span className="field-label">University / campus</span>
                  <select
                    className="field-input"
                    value={selectedUniversityId}
                    onChange={(event) => setSelectedUniversityId(event.target.value)}
                  >
                    <option value="">Select a university or campus</option>
                    {universitiesQuery.data?.map((university: any) => (
                      <option key={university.id} value={university.id}>{university.name}</option>
                    ))}
                  </select>
                </label>

                <label className="field-shell">
                  <span className="field-label">Year joined university</span>
                  <input
                    className="field-input"
                    inputMode="numeric"
                    value={startYear}
                    onChange={(event) => setStartYear(event.target.value)}
                    placeholder="2021"
                  />
                </label>

                <button className="secondary-button w-full justify-center" type="submit" disabled={!lastName || !selectedUniversityId || !startYear}>
                  Find my PCM record
                </button>
              </form>

              <p className="text-sm text-slate-500">
                Use the exact surname on your PCM record together with the exact university or campus and year you joined.
              </p>

              {registrationInfo ? <p className="rounded-2xl bg-sky-50 px-4 py-3 text-sm text-sky-700">{registrationInfo}</p> : null}
              {registrationError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{registrationError}</p> : null}

              {matches.length > 0 ? (
                <form
                  className="grid gap-4"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    setRegistrationError("");
                    if (!selectedMemberId) {
                      setRegistrationError("Select the matching PCM record first.");
                      return;
                    }
                    if (!registrationEmail.trim()) {
                      setRegistrationError("Enter the email you want to use for sign in.");
                      return;
                    }
                    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registrationEmail.trim())) {
                      setRegistrationError("Enter a valid email address.");
                      return;
                    }
                    if (!registrationPassword || registrationPassword.length < 8) {
                      setRegistrationError("Use a password with at least 8 characters.");
                      return;
                    }
                    if (registrationPassword !== confirmPassword) {
                      setRegistrationError("Passwords do not match.");
                      return;
                    }

                    setIsSubmitting(true);
                    try {
                      const session = await authApi.registerGeneralUser({
                        member_id: selectedMemberId,
                        email: registrationEmail,
                        password: registrationPassword,
                        donor_interest: donorInterest
                      });
                      await persistSession(session.access_token, session.refresh_token, registrationPassword, queryClient);
                      navigate("/", { replace: true });
                    } catch (err: any) {
                      setRegistrationError(err?.response?.data?.detail || "Unable to complete registration.");
                    } finally {
                      setIsSubmitting(false);
                    }
                  }}
                >
                  <div className="space-y-3">
                    {matches.map((match) => (
                      <label
                        key={match.member_id}
                        className={[
                          "block cursor-pointer rounded-[16px] border px-4 py-4 transition",
                          selectedMemberId === match.member_id ? "border-sky-400 bg-sky-50" : "border-slate-200 bg-white"
                        ].join(" ")}
                      >
                        <div className="flex items-start gap-3">
                          <input
                            type="radio"
                            checked={selectedMemberId === match.member_id}
                            onChange={() => setSelectedMemberId(match.member_id)}
                          />
                          <div className="space-y-1">
                            <p className="font-semibold text-slate-900">{match.first_name} {match.last_name}</p>
                            <p className="text-sm text-slate-600">
                              {match.university_name} | {match.status} | Joined {match.start_year || "not captured"}
                            </p>
                            <p className="text-sm text-slate-500">
                              {match.program_of_study_name || "Programme not captured"}
                              {match.email_hint ? ` | Email on file: ${match.email_hint}` : ""}
                            </p>
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>

                  <label className="field-shell">
                    <span className="field-label">Email for sign in</span>
                    <input
                      className="field-input"
                      type="email"
                      value={registrationEmail}
                      onChange={(event) => setRegistrationEmail(event.target.value)}
                      placeholder="you@example.com"
                    />
                  </label>

                  <p className="text-sm text-slate-500">
                    This email will update your PCM record and will be the email you use to sign in later.
                  </p>

                  <label className="field-shell">
                    <span className="field-label">Password</span>
                    <input
                      className="field-input"
                      type="password"
                      value={registrationPassword}
                      onChange={(event) => setRegistrationPassword(event.target.value)}
                      placeholder="Choose a password"
                    />
                  </label>

                  <label className="field-shell">
                    <span className="field-label">Confirm password</span>
                    <input
                      className="field-input"
                      type="password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                      placeholder="Repeat your password"
                    />
                  </label>

                  <label className="flex items-start gap-3 rounded-[16px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={donorInterest}
                      onChange={(event) => setDonorInterest(event.target.checked)}
                    />
                    <span>
                      I am open to being engaged as a donor. This flag is visible to PCM users with network-wide visibility.
                    </span>
                  </label>

                  <div className="flex gap-3">
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={resetRegistration}
                    >
                      Search again
                    </button>
                    <button className="primary-button flex-1 justify-center" type="submit" disabled={isSubmitting}>
                      {isSubmitting ? "Creating account..." : "Create my account"}
                    </button>
                  </div>
                </form>
              ) : null}
            </div>
          )}
        </section>
      </div>

      <footer className="login-footer">
        Managed by North Zimbabwe Conference PCM Communication Department
      </footer>
    </div>
  );
}
