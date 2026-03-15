import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { universitiesApi, usersApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const roleOptions = [
  "super_admin",
  "student_admin",
  "program_manager",
  "finance_officer",
  "students_finance",
  "committee_member",
  "executive",
  "director",
  "alumni_admin"
];
const globalOnlyRoles = ["super_admin", "executive", "director"];

function formatRoleLabel(role: string) {
  return role.replace(/_/g, " ");
}

function buildInitialForm(defaultUniversityId?: number | null, defaultRoles: string[] = ["student_admin"]) {
  return {
    email: "",
    name: "",
    password: "",
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    roles: defaultRoles
  };
}

export default function UsersPage() {
  const client = useQueryClient();
  const { roles, isSuperAdmin, canSelectUniversity, defaultUniversityId } = useUniversityScope();
  const canManageTeam = roles.some((role) => ["super_admin", "student_admin", "alumni_admin"].includes(role));

  const { data: users } = useQuery({
    queryKey: ["users"],
    queryFn: usersApi.list,
    enabled: canManageTeam
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canManageTeam
  });

  const universityLookup = useMemo(
    () => Object.fromEntries((universities || []).map((university: any) => [university.id, university.name])),
    [universities]
  );
  const usersPagination = usePagination(users);
  const lockedUniversityName = defaultUniversityId ? universityLookup[defaultUniversityId] : "";

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId, ["student_admin"]));
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
    setForm(buildInitialForm(defaultUniversityId, defaultProvisionRole));
  }

  function closeForm() {
    setIsFormOpen(false);
    resetForm();
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Team administration"
        title="Users and roles"
        description={isSuperAdmin ? "Create global or scoped teammate accounts, including finance people, then assign the right university or campus scope." : "Provision teammate accounts for your university or campus, including finance people and other role-based users."}
        actions={(
          <button className="primary-button" type="button" onClick={() => setIsFormOpen(true)}>
            Provision a teammate
          </button>
        )}
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Accounts" value={formatNumber(users?.length)} helper={isSuperAdmin ? "All users currently provisioned" : "Visible users in your university or campus"} />
        <MetricCard label="Finance people" value={formatNumber(users?.filter((item: any) => item.roles.some((role: string) => ["finance_officer", "students_finance"].includes(role))).length)} tone="ink" helper="Users assigned finance responsibility" />
        <MetricCard label="Campus-affiliated users" value={formatNumber(users?.filter((item: any) => item.university_id || item.member_university_id).length)} tone="gold" helper="Assigned to or linked with a university or campus" />
        <MetricCard label="Donor interest" value={formatNumber(users?.filter((item: any) => item.donor_interest).length)} tone="coral" helper="Users open to donor engagement" />
      </div>

      <Panel className="space-y-5">
        <div>
          <p className="eyebrow">Current accounts</p>
          <h3 className="text-xl font-semibold text-slate-950">Team access map</h3>
        </div>

        {!users?.length ? (
          <EmptyState
            title="No users found"
            description="Use the top button to provision the first teammate or finance user in this scope."
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
                    <th>Status</th>
                    <th>Profile</th>
                  </tr>
                </thead>
                <tbody>
                  {usersPagination.pageItems.map((item: any) => (
                    <tr key={item.id}>
                      <td>
                        <div className="table-primary">{item.name || item.email}</div>
                        <div className="table-secondary">{item.email}</div>
                      </td>
                      <td>
                        <div className="table-primary">
                          {item.university_id
                            ? (universityLookup[item.university_id] || `University #${item.university_id}`)
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
                        <StatusBadge label={item.is_active ? "active" : "inactive"} tone={item.is_active ? "success" : "warning"} />
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={usersPagination}
              itemLabel="users"
              onExport={() => exportRowsAsCsv("team-users", (users || []).map((item: any) => ({
                name: item.name || "",
                email: item.email || "",
                scope: item.university_id
                  ? (universityLookup[item.university_id] || `University #${item.university_id}`)
                  : item.member_university_name || "Global scope",
                scope_type: item.university_id ? "University-scoped account" : item.member_university_id ? "Member-linked network account" : "Network-wide account",
                roles: (item.roles || []).map((role: string) => formatRoleLabel(role)).join("; "),
                status: item.is_active ? "active" : "inactive",
                member_status: item.member_status || "",
                donor_interest: item.donor_interest ? "yes" : "no"
              })))}
            />
          </>
        )}
      </Panel>

      <ModalDialog open={isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Create an account</p>
              <h3 className="text-xl font-semibold text-slate-950">Provision a teammate</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              await usersApi.create({
                ...form,
                university_id: form.university_id ? Number(form.university_id) : null
              });
              await client.invalidateQueries({ queryKey: ["users"] });
              closeForm();
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
              <span className="field-label">Password</span>
              <input className="field-input" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
            </label>
            {canSelectUniversity ? (
              <label className="field-shell">
                <span className="field-label">University / campus scope</span>
                <select className="field-input" value={form.university_id} onChange={(event) => setForm({ ...form, university_id: event.target.value })}>
                  <option value="">Global access</option>
                  {universities?.map((university: any) => (
                    <option key={university.id} value={university.id}>{university.name}</option>
                  ))}
                </select>
              </label>
            ) : (
              <div className="field-shell">
                <span className="field-label">University / campus scope</span>
                <div className="field-input flex items-center text-slate-600">
                  {lockedUniversityName || "Your university or campus"}
                </div>
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

            <div className="md:col-span-2">
              <button className="primary-button" type="submit">Create user</button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </div>
  );
}
