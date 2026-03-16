import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi, messagesApi, usersMeApi, universitiesApi } from "../api/endpoints";
import pcmLogo from "../images/pcm_logo.png";
import { canAccessAlumniConnect } from "../lib/alumniConnectAccess";
import { APP_VERSION } from "../lib/appVersion";
import { bootstrapChatKeys, clearSessionWrappingKey, rotateChatWrappingPassword } from "../lib/chatCrypto";
import { useUniversityScope } from "../lib/universityScope";
import { useAuthStore } from "../store/auth";

const networkRoles = ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin", "general_user"];
const missionRoles = ["general_user"];
const helpMenuItems = [
  { label: "Help", to: "/help" },
  { label: "Contact", to: "/help/contact" },
  { label: "Terms & Conditions", to: "/help/terms" },
  { label: "Privacy", to: "/help/privacy" }
];

const navDisplayOrder = new Map([
  ["Overview", 0],
  ["Mission Reports", 1],
  ["Ministry programs", 2],
  ["Funding", 3],
  ["Calendar", 4],
  ["Marketplace", 5],
  ["My profile", 6],
  ["People", 7],
  ["Alumni connect", 8],
  ["Messages", 9],
  ["Broadcasts", 10],
  ["Mission reports", 11],
  ["Universities", 12],
  ["Team", 13],
  ["Admin", 14]
]);

const navItems = [
  {
    label: "Overview",
    to: "/",
    description: "Network pulse",
    roles: ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "People",
    to: "/people",
    description: "Students, staff, alumni",
    roles: ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "Alumni connect",
    to: "/alumni-connect",
    description: "Graduate directory",
    roles: networkRoles
  },
  {
    label: "My profile",
    to: "/my-profile",
    description: "Employment and offers",
    roles: ["general_user"]
  },
  {
    label: "Marketplace",
    to: "/marketplace",
    description: "Offers and needs",
    roles: networkRoles
  },
  {
    label: "Ministry programs",
    to: "/programs",
    description: "Ministry portfolio",
    roles: ["super_admin", "student_admin", "secretary", "program_manager", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "Calendar",
    to: "/calendar",
    description: "Events and dates",
    roles: ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "Broadcasts",
    to: "/broadcasts",
    description: "Shared invitations",
    roles: ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director"]
  },
  {
    label: "Messages",
    to: "/messages",
    description: "Private chat",
    roles: networkRoles
  },
  {
    label: "Mission reports",
    to: "/mission-reports",
    description: "Condensed impact view",
    roles: missionRoles
  },
  {
    label: "Mission Reports",
    to: "/updates",
    description: "Impact reporting",
    roles: ["super_admin", "student_admin", "secretary", "program_manager", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "Funding",
    to: "/funding",
    description: "Income and expenses",
    roles: ["super_admin", "student_admin", "alumni_admin", "finance_officer", "students_finance", "executive", "director"]
  },
  {
    label: "Universities",
    to: "/universities",
    description: "University and campus profiles",
    roles: ["super_admin"]
  },
  {
    label: "Team",
    to: "/team",
    description: "User accounts",
    roles: ["super_admin", "student_admin", "alumni_admin", "service_recovery"]
  },
  {
    label: "Admin",
    to: "/admin",
    description: "Audit and system actions",
    roles: ["super_admin"]
  }
];

const navItemBaseOrder = new Map(navItems.map((item, index) => [item.label, index]));

function formatRoleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function HelpIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <circle cx="10" cy="10" r="7.25" />
      <path d="M7.85 7.6A2.48 2.48 0 0 1 10.1 6.4C11.58 6.4 12.75 7.35 12.75 8.68C12.75 10.65 10.35 10.64 10.35 12.35" />
      <path d="M10 14.7H10.01" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <path d="M3.5 5.5H16.5" />
      <path d="M3.5 10H16.5" />
      <path d="M3.5 14.5H16.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      <path d="M5.5 5.5L14.5 14.5" />
      <path d="M14.5 5.5L5.5 14.5" />
    </svg>
  );
}

export default function DashboardLayout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const token = localStorage.getItem("pcm_access_token");
  const { setUser, setActiveUniversityId } = useAuthStore();
  const { user, roles, isSuperAdmin, canSelectUniversity, scopedUniversityId } = useUniversityScope();
  const canViewMessages = roles.some((role) => networkRoles.includes(role));
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordResetError, setPasswordResetError] = useState("");
  const [passwordResetMessage, setPasswordResetMessage] = useState("");
  const [isResettingPassword, setIsResettingPassword] = useState(false);
  const [isHelpMenuOpen, setIsHelpMenuOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const mustChangePassword = Boolean(user?.force_password_reset);
  const helpMenuRef = useRef<HTMLDivElement | null>(null);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: usersMeApi.me,
    retry: false,
    enabled: Boolean(token)
  });

  const universitiesQuery = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: Boolean(token) && meQuery.isSuccess && !mustChangePassword
  });
  const messageConversationsQuery = useQuery({
    queryKey: ["message-conversations"],
    queryFn: messagesApi.conversations,
    enabled: Boolean(token) && meQuery.isSuccess && canViewMessages && !mustChangePassword,
    refetchInterval: 5_000
  });

  useEffect(() => {
    if (!token) {
      navigate("/login", { replace: true });
    }
  }, [navigate, token]);

  useEffect(() => {
    if (meQuery.data) {
      setUser(meQuery.data);
    }
  }, [meQuery.data, setUser]);

  useEffect(() => {
    if (!mustChangePassword) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordResetError("");
      setPasswordResetMessage("");
    }
  }, [mustChangePassword]);

  useEffect(() => {
    setIsHelpMenuOpen(false);
    setIsSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!helpMenuRef.current?.contains(event.target as Node)) {
        setIsHelpMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  useEffect(() => {
    if (!isSidebarOpen) {
      document.body.style.overflow = "";
      return;
    }

    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isSidebarOpen]);

  useEffect(() => {
    const status = (meQuery.error as any)?.response?.status;
    if (meQuery.isError && meQuery.isFetchedAfterMount && (status === 401 || status === 403)) {
      localStorage.removeItem("pcm_access_token");
      localStorage.removeItem("pcm_refresh_token");
      clearSessionWrappingKey();
      setUser(null);
      queryClient.clear();
      navigate("/login", { replace: true });
    }
  }, [meQuery.error, meQuery.isError, meQuery.isFetchedAfterMount, navigate, queryClient, setUser]);

  if (!token || !user) return null;

  const visibleNav = mustChangePassword
    ? []
    : navItems
        .filter((item) => {
          if (item.to === "/alumni-connect") {
            return canAccessAlumniConnect(user, roles);
          }
          return item.roles.some((role) => roles.includes(role));
        })
        .sort((left, right) => {
          const leftOrder = navDisplayOrder.get(left.label) ?? navItemBaseOrder.get(left.label) ?? Number.MAX_SAFE_INTEGER;
          const rightOrder = navDisplayOrder.get(right.label) ?? navItemBaseOrder.get(right.label) ?? Number.MAX_SAFE_INTEGER;
          return leftOrder - rightOrder;
        });
  const activeItem = visibleNav.find((item) => item.to === location.pathname) || visibleNav.find((item) => location.pathname.startsWith(item.to) && item.to !== "/");
  const activeHelpItem = helpMenuItems.find((item) => item.to === location.pathname);
  const scopedUniversity = universitiesQuery.data?.find((university: any) => university.id === scopedUniversityId);
  const affiliationLabel = user?.member_university_name || scopedUniversity?.name;
  const scopeStatusLabel = isSuperAdmin
    ? null
    : scopedUniversity
      ? `Scoped to ${scopedUniversity.name}`
      : affiliationLabel
        ? `Network-wide access from ${affiliationLabel}`
        : "Network-wide access";
  const unreadMessageCount = (messageConversationsQuery.data || []).reduce(
    (total: number, conversation: any) => total + (conversation.unread_count || 0),
    0
  );
  const unreadMessageLabel = unreadMessageCount > 99 ? "99+" : String(unreadMessageCount);

  return (
    <div className="app-shell">
      <button
        aria-hidden={!isSidebarOpen}
        className={["sidebar-backdrop", isSidebarOpen ? "sidebar-backdrop-open" : ""].join(" ")}
        onClick={() => setIsSidebarOpen(false)}
        type="button"
      />

      <aside className={["sidebar-shell", isSidebarOpen ? "sidebar-shell-open" : ""].join(" ")}>
        <div className="space-y-8">
          <div className="flex items-center justify-between lg:hidden">
            <div>
              <p className="eyebrow">Navigation</p>
              <p className="text-sm font-semibold text-slate-900">PCM Connect</p>
            </div>
            <button
              className="topbar-icon-button"
              type="button"
              aria-label="Close navigation menu"
              onClick={() => setIsSidebarOpen(false)}
            >
              <CloseIcon />
            </button>
          </div>

          <div className="rounded-[14px] border border-slate-200/80 bg-white/88 p-5 shadow-[0_16px_40px_rgba(18,36,63,0.08)] backdrop-blur">
            <div className="flex items-center gap-4">
              <div className="grid h-16 w-16 place-items-center rounded-[12px]">
                <img src={pcmLogo} alt="PCM logo" className="h-full w-full object-contain p-1" />
              </div>
              <div>
                <h2 className="sidebar-brand-title text-xl font-semibold text-slate-900">PCM Connect</h2>
                <p className="sidebar-brand-subtitle mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">Campus mission management</p>
                <p className="sidebar-version mt-2">Version {APP_VERSION}</p>
              </div>
            </div>

          </div>

          <nav className="space-y-2">
            {visibleNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setIsSidebarOpen(false)}
                className={({ isActive }) =>
                  [
                    "nav-tile",
                    isActive ? "nav-tile-active" : "nav-tile-idle"
                  ].join(" ")
                }
              >
                <div className="nav-tile-title">
                  {item.to === "/messages" && unreadMessageCount > 0 ? (
                    <span className="nav-unread-badge" aria-label={`${unreadMessageCount} unread messages`}>
                      {unreadMessageLabel}
                    </span>
                  ) : null}
                  <span className="sidebar-nav-label font-semibold text-slate-900">{item.label}</span>
                </div>
                <span className="sidebar-nav-description text-slate-500">{item.description}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="rounded-[12px] border border-slate-200/20 bg-[linear-gradient(160deg,#12243f,#2f77bd_58%,#7157ba)] px-5 py-4 text-white shadow-[0_18px_44px_rgba(18,36,63,0.24)]">
          <p className="text-xs uppercase tracking-[0.3em] text-white/70">Signed in</p>
          <p className="mt-3 text-lg font-semibold">{user?.name || user?.email || "Loading..."}</p>
          <p className="mt-1 text-sm text-white/78">{roles.map(formatRoleLabel).join(", ") || "No roles"}</p>
          <button
            className="mt-5 inline-flex w-full items-center justify-center rounded-[12px] border border-white/15 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
            onClick={() => {
              localStorage.removeItem("pcm_access_token");
              localStorage.removeItem("pcm_refresh_token");
              clearSessionWrappingKey();
              setUser(null);
              queryClient.clear();
              navigate("/login", { replace: true });
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="content-shell">
        <div className="topbar-shell">
          <div className="flex items-start gap-3">
            <button
              className="topbar-icon-button lg:hidden"
              type="button"
              aria-label="Open navigation menu"
              aria-expanded={isSidebarOpen}
              onClick={() => setIsSidebarOpen(true)}
            >
              <MenuIcon />
            </button>

            <div>
              <p className="eyebrow">Mission control</p>
              <h2 className="text-2xl font-semibold text-slate-950">
                {mustChangePassword && !activeHelpItem ? "Password reset required" : activeItem?.label || activeHelpItem?.label || "Operations"}
              </h2>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {!mustChangePassword && canSelectUniversity ? (
              <label className="field-shell min-w-[220px]">
                <span className="field-label">University / campus scope</span>
                <select
                  className="field-input"
                  value={scopedUniversityId ?? ""}
                  onChange={(event) => setActiveUniversityId(event.target.value ? Number(event.target.value) : null)}
                >
                  <option value="">All universities and campuses</option>
                  {universitiesQuery.data?.map((university: any) => (
                    <option key={university.id} value={university.id}>
                      {university.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : !mustChangePassword ? (
              <div className="rounded-[12px] border border-slate-200/80 bg-white/80 px-4 py-2 text-sm text-slate-600 shadow-[0_10px_24px_rgba(18,36,63,0.05)]">
                {scopeStatusLabel}
              </div>
            ) : null}

            <div className="topbar-menu-shell" ref={helpMenuRef}>
              <button
                className="topbar-icon-button"
                type="button"
                aria-label="Open help menu"
                aria-expanded={isHelpMenuOpen}
                onClick={() => setIsHelpMenuOpen((current) => !current)}
              >
                <HelpIcon />
              </button>

              {isHelpMenuOpen ? (
                <div className="topbar-menu">
                  {helpMenuItems.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) => [
                        "topbar-menu-link",
                        isActive ? "topbar-menu-link-active" : ""
                      ].filter(Boolean).join(" ")}
                    >
                      {item.label}
                    </NavLink>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="page-shell">
          {mustChangePassword && !activeHelpItem ? (
            <section className="panel max-w-2xl space-y-5">
              <div>
                <p className="eyebrow">Security step</p>
                <h3 className="text-xl font-semibold text-slate-950">Change your password to continue</h3>
                <p className="mt-2 max-w-xl text-sm text-slate-600">
                  This account was marked to reset its password at login. Enter the password you just used to sign in, then set a new one before accessing the rest of PCM Connect.
                </p>
              </div>

              <form
                className="grid gap-4"
                onSubmit={async (event) => {
                  event.preventDefault();
                  setPasswordResetError("");
                  setPasswordResetMessage("");

                  if (!currentPassword || !newPassword) {
                    setPasswordResetError("Enter your current password and a new password.");
                    return;
                  }
                  if (newPassword !== confirmPassword) {
                    setPasswordResetError("New password confirmation does not match.");
                    return;
                  }

                  setIsResettingPassword(true);
                  try {
                    const updatedUser = await authApi.changePassword({
                      current_password: currentPassword,
                      new_password: newPassword
                    });

                    try {
                      await rotateChatWrappingPassword(currentPassword, newPassword, messagesApi.getKeyBundle, messagesApi.setKeyBundle);
                    } catch {
                      try {
                        await bootstrapChatKeys(newPassword, messagesApi.getKeyBundle, messagesApi.setKeyBundle);
                      } catch {
                        clearSessionWrappingKey();
                      }
                    }

                    setUser(updatedUser);
                    setCurrentPassword("");
                    setNewPassword("");
                    setConfirmPassword("");
                    setPasswordResetMessage("Password updated. Access has been restored.");
                    await queryClient.invalidateQueries({ queryKey: ["me"] });
                    await queryClient.invalidateQueries({ queryKey: ["message-conversations"] });
                  } catch (error: any) {
                    setPasswordResetError(error?.response?.data?.detail || "Unable to change your password right now.");
                  } finally {
                    setIsResettingPassword(false);
                  }
                }}
              >
                <label className="field-shell">
                  <span className="field-label">Current password</span>
                  <input className="field-input" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
                </label>
                <label className="field-shell">
                  <span className="field-label">New password</span>
                  <input className="field-input" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Confirm new password</span>
                  <input className="field-input" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
                </label>

                {passwordResetMessage ? <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{passwordResetMessage}</p> : null}
                {passwordResetError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{passwordResetError}</p> : null}

                <button className="primary-button w-fit" type="submit" disabled={isResettingPassword}>
                  {isResettingPassword ? "Updating password..." : "Update password"}
                </button>
              </form>
            </section>
          ) : (
            <Outlet />
          )}
        </div>

        <footer className="app-footer">
          Developed by North Zimbabwe Conference PCM Communication Department
        </footer>
      </main>
    </div>
  );
}
