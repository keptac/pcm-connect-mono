import { useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { messagesApi, usersMeApi, universitiesApi } from "../api/endpoints";
import pcmLogo from "../images/pcm_logo.png";
import { clearSessionWrappingKey } from "../lib/chatCrypto";
import { useUniversityScope } from "../lib/universityScope";
import { useAuthStore } from "../store/auth";

const networkRoles = ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin", "general_user"];
const missionRoles = ["general_user"];

const navItems = [
  {
    label: "Overview",
    to: "/",
    description: "Network pulse",
    roles: ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "People",
    to: "/people",
    description: "Students, staff, alumni",
    roles: ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
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
    roles: ["super_admin", "student_admin", "program_manager", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "Calendar",
    to: "/calendar",
    description: "Events and dates",
    roles: ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"]
  },
  {
    label: "Broadcasts",
    to: "/broadcasts",
    description: "Shared invitations",
    roles: ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director"]
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
    label: "Updates",
    to: "/updates",
    description: "Impact reporting",
    roles: ["super_admin", "student_admin", "program_manager", "committee_member", "executive", "director", "alumni_admin"]
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
    roles: ["super_admin", "student_admin", "alumni_admin"]
  },
  {
    label: "Admin",
    to: "/admin",
    description: "Audit and system actions",
    roles: ["super_admin"]
  }
];

function formatRoleLabel(role: string) {
  return role.replace(/_/g, " ");
}

export default function DashboardLayout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const token = localStorage.getItem("pcm_access_token");
  const { setUser, setActiveUniversityId } = useAuthStore();
  const { user, roles, isSuperAdmin, scopedUniversityId } = useUniversityScope();
  const canViewMessages = roles.some((role) => networkRoles.includes(role));

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: usersMeApi.me,
    retry: false,
    enabled: Boolean(token)
  });

  const universitiesQuery = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: Boolean(token) && meQuery.isSuccess
  });
  const messageConversationsQuery = useQuery({
    queryKey: ["message-conversations"],
    queryFn: messagesApi.conversations,
    enabled: Boolean(token) && meQuery.isSuccess && canViewMessages,
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

  const visibleNav = navItems.filter((item) => item.roles.some((role) => roles.includes(role)));
  const activeItem = visibleNav.find((item) => item.to === location.pathname) || visibleNav.find((item) => location.pathname.startsWith(item.to) && item.to !== "/");
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
      <aside className="sidebar-shell">
        <div className="space-y-8">
          <div className="rounded-[14px] border border-slate-200/80 bg-white/88 p-5 shadow-[0_16px_40px_rgba(18,36,63,0.08)] backdrop-blur">
            <div className="flex items-center gap-4">
              <div className="grid h-16 w-16 place-items-center rounded-[12px]">
                <img src={pcmLogo} alt="PCM logo" className="h-full w-full object-contain p-1" />
              </div>
              <div>
                <h2 className="sidebar-brand-title text-xl font-semibold text-slate-900">PCM Connect</h2>
                <p className="sidebar-brand-subtitle mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">Campus mission management</p>
              </div>
            </div>

          </div>

          <nav className="space-y-2">
            {visibleNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
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
          <div>
            <p className="eyebrow">Mission control</p>
            <h2 className="text-2xl font-semibold text-slate-950">{activeItem?.label || "Operations"}</h2>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {isSuperAdmin ? (
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
            ) : (
              <div className="rounded-[12px] border border-slate-200/80 bg-white/80 px-4 py-2 text-sm text-slate-600 shadow-[0_10px_24px_rgba(18,36,63,0.05)]">
                {scopeStatusLabel}
              </div>
            )}
          </div>
        </div>

        <div className="page-shell">
          <Outlet />
        </div>

        <footer className="app-footer">
          Managed by North Zimbabwe Conference PCM Communication Department
        </footer>
      </main>
    </div>
  );
}
