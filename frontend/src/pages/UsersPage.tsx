import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { universitiesApi, usersApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";
import { useAuthStore } from "../store/auth";

const DEFAULT_TENURE_MONTHS = 24;
const roleOptions = [
  "super_admin",
  "student_admin",
  "secretary",
  "program_manager",
  "finance_officer",
  "students_finance",
  "committee_member",
  "executive",
  "director",
  "alumni_admin"
];
const globalOnlyRoles = ["super_admin", "executive", "director"];

function todayIsoDate() {
  const now = new Date();
  const offsetMs = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 10);
}

function formatRoleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function KeyIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
      <path d="M11.75 8.25A3.75 3.75 0 1 1 4.25 8.25A3.75 3.75 0 0 1 11.75 8.25Z" />
      <path d="M11.5 8.25H17.25" />
      <path d="M14.25 8.25V10.5" />
      <path d="M16.25 8.25V9.75" />
    </svg>
  );
}

function buildInitialForm(defaultUniversityId?: number | null, defaultRoles: string[] = ["student_admin"]) {
  return {
    email: "",
    name: "",
    password: "",
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    roles: defaultRoles,
    force_password_reset: true,
    tenure_months: String(DEFAULT_TENURE_MONTHS),
    tenure_starts_on: todayIsoDate()
  };
}

function buildEditForm(user: any) {
  return {
    email: user.email || "",
    name: user.name || "",
    password: "",
    university_id: user.university_id ? String(user.university_id) : "",
    roles: user.roles?.length ? user.roles : ["student_admin"],
    force_password_reset: Boolean(user.force_password_reset),
    tenure_months: String(user.tenure_months || DEFAULT_TENURE_MONTHS),
    tenure_starts_on: user.tenure_starts_on || todayIsoDate()
  };
}

function isTenureExpired(user: any) {
  return Boolean(user.tenure_ends_on && user.tenure_ends_on <= todayIsoDate());
}

function isManagedTeammate(user: any) {
  return Boolean(user.subject_to_tenure || user.roles?.includes("super_admin"));
}

export default function UsersPage() {
  const client = useQueryClient();
  const currentUser = useAuthStore((state) => state.user);
  const { roles, isSuperAdmin, canSelectUniversity, defaultUniversityId } = useUniversityScope();
  const canManageTeam = roles.some((role) => ["super_admin", "student_admin", "secretary", "alumni_admin", "service_recovery"].includes(role));
  const canProvisionTeam = roles.some((role) => ["super_admin", "student_admin", "secretary", "alumni_admin"].includes(role));
  const canRecoverPasswords = roles.some((role) => ["super_admin", "service_recovery"].includes(role));

  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: usersApi.list,
    enabled: canManageTeam
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canProvisionTeam
  });

  const universityLookup = useMemo(
    () => Object.fromEntries((universities || []).map((university: any) => [university.id, university.name])),
    [universities]
  );
  const usersPagination = usePagination(users);
  const lockedUniversityName = defaultUniversityId ? (universityLookup[defaultUniversityId] || currentUser?.university_name || "") : "";
  const lockedScopeLabel = lockedUniversityName || "Your university or campus";

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any | null>(null);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId, ["student_admin"]));
  const [formError, setFormError] = useState("");
  const [pageError, setPageError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [actionUserId, setActionUserId] = useState<number | null>(null);
  const [recoveryUser, setRecoveryUser] = useState<any | null>(null);
  const [recoveryPassword, setRecoveryPassword] = useState("");
  const [recoveryForceReset, setRecoveryForceReset] = useState(true);
  const [recoveryError, setRecoveryError] = useState("");
  const [isRecoveringPassword, setIsRecoveringPassword] = useState(false);

  const selectedRole = form.roles[0] || "";
  const tenureExemptRole = selectedRole === "super_admin";
  const availableRoleOptions = useMemo(() => {
    const baseRoles = isSuperAdmin ? roleOptions : roleOptions.filter((role) => role !== "super_admin");
    if (!form.university_id && isSuperAdmin) return baseRoles;
    return baseRoles.filter((role) => !globalOnlyRoles.includes(role));
  }, [form.university_id, isSuperAdmin]);
  const defaultProvisionRole = useMemo(
    () => availableRoleOptions.includes("student_admin") ? ["student_admin"] : [availableRoleOptions[0]].filter(Boolean),
    [availableRoleOptions]
  );

  useEffect(() => {
    setForm((current) => {
      const nextRoles = current.roles.filter((role) => availableRoleOptions.includes(role));
      if (nextRoles.length === current.roles.length && nextRoles.every((role, index) => role === current.roles[index])) {
        return current;
      }
      return {
        ...current,
        roles: nextRoles.length ? nextRoles : defaultProvisionRole
      };
    });
  }, [availableRoleOptions, defaultProvisionRole]);

  if (!canManageTeam) {
    return <Panel><p className="text-sm text-slate-600">Admin access required.</p></Panel>;
  }

  function resetForm() {
    setForm(selectedUser ? buildEditForm(selectedUser) : buildInitialForm(defaultUniversityId, defaultProvisionRole));
    setFormError("");
  }

  function closeForm() {
    setIsFormOpen(false);
    setSelectedUser(null);
    setForm(buildInitialForm(defaultUniversityId, defaultProvisionRole));
    setFormError("");
  }

  function openCreateForm() {
    setSelectedUser(null);
    setForm(buildInitialForm(defaultUniversityId, defaultProvisionRole));
    setFormError("");
    setIsFormOpen(true);
  }

  function openEditForm(user: any) {
    setSelectedUser(user);
    setForm(buildEditForm(user));
    setFormError("");
    setIsFormOpen(true);
  }

  function closeRecoveryForm() {
    setRecoveryUser(null);
    setRecoveryPassword("");
    setRecoveryForceReset(true);
    setRecoveryError("");
  }

  function openRecoveryForm(user: any) {
    setRecoveryUser(user);
    setRecoveryPassword("");
    setRecoveryForceReset(true);
    setRecoveryError("");
  }

  async function refreshTeamQueries() {
    await client.invalidateQueries({ queryKey: ["users"] });
    await client.invalidateQueries({ queryKey: ["me"] });
  }

  async function toggleActive(user: any) {
    setPageError("");
    if (!user.is_active && isTenureExpired(user)) {
      openEditForm(user);
      setFormError("Extend the tenure before reactivating this account.");
      return;
    }

    setActionUserId(user.id);
    try {
      await usersApi.update(user.id, {
        is_active: !user.is_active
      });
      await refreshTeamQueries();
    } catch (error: any) {
      setPageError(error?.response?.data?.detail || "Unable to update that account right now.");
    } finally {
      setActionUserId(null);
    }
  }

  const activeAccounts = (users || []).filter((item: any) => item.is_active).length;
  const disabledAccounts = (users || []).filter((item: any) => !item.is_active).length;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Team administration"
        title="Users and roles"
        description={canProvisionTeam
          ? (isSuperAdmin
            ? "Create global or scoped teammate accounts, assign a tenure, then manage edits or disable access as offices change hands."
            : "Provision teammate accounts for your university or campus, assign their term of office, then edit or disable access as leadership changes.")
          : "Recovery-only access. Use this account to reset a user password and force a password change at their next sign-in."}
        actions={canProvisionTeam ? (
          <button className="primary-button" type="button" onClick={openCreateForm}>
            Provision a teammate
          </button>
        ) : null}
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Accounts" value={formatNumber(users?.length)} helper={isSuperAdmin ? "All visible team and member-linked accounts" : "Visible users in your university or campus"} />
        <MetricCard label="Active accounts" value={formatNumber(activeAccounts)} tone="ink" helper="Users who can still sign in" />
        <MetricCard label="Disabled accounts" value={formatNumber(disabledAccounts)} tone="coral" helper="Removed automatically after 3 months disabled" />
        <MetricCard label="Finance people" value={formatNumber(users?.filter((item: any) => item.roles.some((role: string) => ["finance_officer", "students_finance"].includes(role))).length)} tone="gold" helper="Users assigned finance responsibility" />
      </div>

      <Panel className="space-y-5">
        <div>
          <p className="eyebrow">Current accounts</p>
          <h3 className="text-xl font-semibold text-slate-950">Team access map</h3>
        </div>

        {pageError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{pageError}</p> : null}

        {!users?.length ? (
          <EmptyState
            title="No users found"
            description={canProvisionTeam ? "Use the top button to provision the first teammate or finance user in this scope." : "No recoverable users are visible in this scope."}
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Scope</th>
                    <th>Roles</th>
                    <th>Tenure</th>
                    <th>Status</th>
                    <th>Profile</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {usersPagination.pageItems.map((item: any) => {
                    const managedTeammate = isManagedTeammate(item);
                    const isSuperAdminRole = item.roles.includes("super_admin");
                    const canToggle = canProvisionTeam && managedTeammate && item.id !== currentUser?.id;
                    const canRecover = canRecoverPasswords && item.id !== currentUser?.id;
                    const needsTenureExtension = !item.is_active && isTenureExpired(item);

                    return (
                      <tr key={item.id}>
                        <td>
                          <div className="table-primary">{item.name || item.email}</div>
                          <div className="table-secondary">{item.email}</div>
                        </td>
                        <td>
                          <div className="table-primary">
                            {item.university_id
                              ? (item.university_name || universityLookup[item.university_id] || `University #${item.university_id}`)
                              : item.member_university_name || "Global scope"}
                          </div>
                          <div className="table-secondary">
                            {item.university_id
                              ? "University-scoped account"
                              : item.member_university_id
                                ? "Member-linked network account"
                                : "Network-wide account"}
                          </div>
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-2">
                            {item.roles.map((role: string) => (
                              <StatusBadge
                                key={role}
                                label={formatRoleLabel(role)}
                                tone={role === "super_admin" ? "info" : ["finance_officer", "students_finance"].includes(role) ? "warning" : "neutral"}
                              />
                            ))}
                          </div>
                        </td>
                        <td>
                          {isSuperAdminRole ? (
                            <>
                              <div className="table-primary">Super admin</div>
                              <div className="table-secondary">Role exempt from tenure</div>
                            </>
                          ) : item.subject_to_tenure ? (
                            <>
                              <div className="table-primary">{formatDate(item.tenure_starts_on)} to {formatDate(item.tenure_ends_on)}</div>
                              <div className="table-secondary">{item.tenure_months || DEFAULT_TENURE_MONTHS} month term</div>
                            </>
                          ) : (
                            <>
                              <div className="table-primary">Not tenure-tracked</div>
                              <div className="table-secondary">Member-linked or self-service account</div>
                            </>
                          )}
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-2">
                            <StatusBadge label={item.is_active ? "active" : "inactive"} tone={item.is_active ? "success" : "warning"} />
                            {item.subject_to_tenure && isTenureExpired(item) ? <StatusBadge label="tenure ended" tone="danger" /> : null}
                          </div>
                          {!item.is_active && item.deletion_due_at ? (
                            <div className="table-secondary mt-2">Removed from team list after {formatDate(item.deletion_due_at)}</div>
                          ) : null}
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-2">
                            {item.member_status ? (
                              <StatusBadge label={item.member_status} tone={item.member_status === "Student" ? "warning" : "info"} />
                            ) : null}
                            {item.donor_interest ? (
                              <StatusBadge label="Donor interest" tone="success" />
                            ) : null}
                          </div>
                        </td>
                        <td>
                          {managedTeammate || canRecover ? (
                            <div className="table-actions">
                              {canProvisionTeam && managedTeammate ? (
                                <TableActionButton label="Edit user" tone="edit" onClick={() => openEditForm(item)} />
                              ) : null}
                              {canToggle ? (
                                <button
                                  className="secondary-button"
                                  type="button"
                                  disabled={actionUserId === item.id}
                                  onClick={() => {
                                    if (needsTenureExtension) {
                                      openEditForm(item);
                                      setFormError("Extend the tenure before reactivating this account.");
                                      return;
                                    }
                                    void toggleActive(item);
                                  }}
                                >
                                  {!item.is_active && needsTenureExtension ? "Extend tenure" : item.is_active ? "Disable" : "Reactivate"}
                                </button>
                              ) : null}
                              {canRecover ? (
                                <button
                                  className="secondary-button inline-flex items-center gap-2"
                                  type="button"
                                  disabled={actionUserId === item.id}
                                  onClick={() => openRecoveryForm(item)}
                                >
                                  <KeyIcon />
                                  <span>Reset password</span>
                                </button>
                              ) : null}
                              {!canToggle && !canRecover ? (
                                <StatusBadge label={item.id === currentUser?.id ? "Current session" : "Protected"} tone="info" />
                              ) : null}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">Managed elsewhere</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={usersPagination}
              itemLabel="users"
              onExport={canProvisionTeam ? () => exportRowsAsCsv("team-users", (users || []).map((item: any) => ({
                name: item.name || "",
                email: item.email || "",
                scope: item.university_id
                  ? (item.university_name || universityLookup[item.university_id] || `University #${item.university_id}`)
                  : item.member_university_name || "Global scope",
                roles: (item.roles || []).map((role: string) => formatRoleLabel(role)).join("; "),
                tenure: item.roles.includes("super_admin")
                  ? "Super admin role exemption"
                  : item.subject_to_tenure
                    ? `${formatDate(item.tenure_starts_on)} to ${formatDate(item.tenure_ends_on)}`
                    : "Not tenure-tracked",
                tenure_months: item.tenure_months || "",
                status: item.is_active ? "active" : "inactive",
                deletion_due_at: item.deletion_due_at ? formatDate(item.deletion_due_at) : "",
                scope_type: item.university_id ? "University-scoped account" : item.member_university_id ? "Member-linked network account" : "Network-wide account",
                member_status: item.member_status || "",
                donor_interest: item.donor_interest ? "yes" : "no"
              }))) : undefined}
            />
          </>
        )}
      </Panel>

      <ModalDialog open={isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">{selectedUser ? "Edit account" : "Create an account"}</p>
              <h3 className="text-xl font-semibold text-slate-950">{selectedUser ? "Update a teammate" : "Provision a teammate"}</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              setFormError("");
              setPageError("");

              if (!selectedUser && !form.password) {
                setFormError("Set a password for the new account.");
                return;
              }

              setIsSaving(true);
              try {
                const payload: Record<string, unknown> = {
                  email: form.email,
                  name: form.name || null,
                  roles: form.roles,
                  force_password_reset: form.force_password_reset,
                  university_id: canSelectUniversity
                    ? (form.university_id ? Number(form.university_id) : null)
                    : (defaultUniversityId ?? selectedUser?.university_id ?? null),
                  tenure_months: tenureExemptRole ? undefined : Number(form.tenure_months || DEFAULT_TENURE_MONTHS),
                  tenure_starts_on: tenureExemptRole ? undefined : (form.tenure_starts_on || todayIsoDate())
                };

                if (selectedRole === "super_admin") {
                  payload.university_id = null;
                }

                if (form.password) {
                  payload.password = form.password;
                }

                if (selectedUser) {
                  await usersApi.update(selectedUser.id, payload);
                } else {
                  await usersApi.create(payload);
                }

                await refreshTeamQueries();
                closeForm();
              } catch (error: any) {
                setFormError(error?.response?.data?.detail || "Unable to save that account right now.");
              } finally {
                setIsSaving(false);
              }
            }}
          >
            <label className="field-shell">
              <span className="field-label">Name</span>
              <input className="field-input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label className="field-shell">
              <span className="field-label">Email</span>
              <input className="field-input" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            </label>
            <label className="field-shell">
              <span className="field-label">{selectedUser ? "Reset password" : "Password"}</span>
              <input className="field-input" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder={selectedUser ? "Leave blank to keep current password" : "Create a password"} />
            </label>
            {canSelectUniversity ? (
              <label className="field-shell">
                <span className="field-label">University / campus scope</span>
                <select className="field-input" value={selectedRole === "super_admin" ? "" : form.university_id} onChange={(event) => setForm({ ...form, university_id: event.target.value })}>
                  <option value="">Global access</option>
                  {universities?.map((university: any) => (
                    <option key={university.id} value={university.id}>{university.name}</option>
                  ))}
                </select>
              </label>
            ) : (
              <div className="field-shell">
                <span className="field-label">University / campus scope</span>
                <div className="field-input flex items-center text-slate-600">{selectedRole === "super_admin" ? "Global access" : lockedScopeLabel}</div>
              </div>
            )}

            <label className="field-shell md:col-span-2">
              <span className="field-label">Role</span>
              <select
                className="field-input"
                value={form.roles[0] || ""}
                onChange={(event) => setForm((current) => ({ ...current, roles: event.target.value ? [event.target.value] : [] }))}
              >
                {availableRoleOptions.map((role) => (
                  <option key={role} value={role}>
                    {formatRoleLabel(role)}
                  </option>
                ))}
              </select>
            </label>

            {tenureExemptRole ? (
              <div className="field-shell md:col-span-2">
                <span className="field-label">Tenure</span>
                <div className="field-input flex items-center text-slate-600">Accounts with the super admin role are exempt from tenure expiry and automatic removal.</div>
              </div>
            ) : (
              <>
                <label className="field-shell md:col-span-2 field-checkbox">
                  <span className="field-label">Require password change at next login</span>
                  <input
                    type="checkbox"
                    checked={form.force_password_reset}
                    onChange={(event) => setForm({ ...form, force_password_reset: event.target.checked })}
                  />
                </label>
                <label className="field-shell">
                  <span className="field-label">Tenure in months</span>
                  <input
                    className="field-input"
                    inputMode="numeric"
                    value={form.tenure_months}
                    onChange={(event) => setForm({ ...form, tenure_months: event.target.value })}
                    placeholder="24"
                  />
                </label>
                <label className="field-shell">
                  <span className="field-label">Tenure start date</span>
                  <input className="field-input" type="date" value={form.tenure_starts_on} onChange={(event) => setForm({ ...form, tenure_starts_on: event.target.value })} />
                </label>
                <div className="md:col-span-2 rounded-[16px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  Standard term of office is {DEFAULT_TENURE_MONTHS} months. When the tenure ends the account is disabled automatically.
                </div>
              </>
            )}

            {formError ? <p className="md:col-span-2 rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{formError}</p> : null}

            <div className="flex flex-wrap gap-3 md:col-span-2">
              <button className="primary-button" type="submit" disabled={isSaving}>{selectedUser ? "Save user" : "Create user"}</button>
              <button className="secondary-button" type="button" onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
      </ModalDialog>

      <ModalDialog open={Boolean(recoveryUser)} onClose={closeRecoveryForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Password reset</p>
              <h3 className="text-xl font-semibold text-slate-950">Reset account password</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeRecoveryForm}>Close</button>
          </div>

          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              if (!recoveryUser) return;
              setRecoveryError("");

              if (recoveryPassword.length < 8) {
                setRecoveryError("Set a temporary password with at least 8 characters.");
                return;
              }

              setIsRecoveringPassword(true);
              setActionUserId(recoveryUser.id);
              try {
                await usersApi.recoverPassword(recoveryUser.id, {
                  new_password: recoveryPassword,
                  force_password_reset: recoveryForceReset
                });
                await refreshTeamQueries();
                closeRecoveryForm();
              } catch (error: any) {
                setRecoveryError(error?.response?.data?.detail || "Unable to recover that account right now.");
              } finally {
                setIsRecoveringPassword(false);
                setActionUserId(null);
              }
            }}
          >
            <div className="rounded-[16px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Resetting access for <span className="font-semibold text-slate-950">{recoveryUser?.name || recoveryUser?.email}</span>. Share the temporary password securely and keep password change at next login enabled unless you have a specific reason not to.
            </div>

            <label className="field-shell">
              <span className="field-label">Temporary password</span>
              <input
                className="field-input"
                type="password"
                value={recoveryPassword}
                onChange={(event) => setRecoveryPassword(event.target.value)}
                placeholder="Set a temporary password"
              />
            </label>

            <label className="field-shell field-checkbox">
              <span className="field-label">Require password change at next login</span>
              <input
                type="checkbox"
                checked={recoveryForceReset}
                onChange={(event) => setRecoveryForceReset(event.target.checked)}
              />
            </label>

            {recoveryError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{recoveryError}</p> : null}

            <div className="flex flex-wrap gap-3">
              <button className="primary-button" type="submit" disabled={isRecoveringPassword}>
                {isRecoveringPassword ? "Updating password..." : "Reset password"}
              </button>
              <button className="secondary-button" type="button" onClick={closeRecoveryForm}>Cancel</button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </div>
  );
}
