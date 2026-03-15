import { type FormEvent, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { broadcastsApi, programsApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatDateTime, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const visibilityOptions = ["network", "targeted"];
const statusOptions = ["open", "confirmed", "closed"];
const responseOptions = ["accepted", "interested", "declined"];

function buildInitialForm(defaultUniversityId?: number | null) {
  return {
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    program_id: "",
    title: "",
    summary: "",
    venue: "",
    contact_name: "",
    contact_email: "",
    visibility: "network",
    status: "open",
    starts_at: "",
    ends_at: "",
    invited_university_ids: [] as string[]
  };
}

function toLocalInputValue(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const adjusted = new Date(date.getTime() - (date.getTimezoneOffset() * 60_000));
  return adjusted.toISOString().slice(0, 16);
}

function badgeTone(value?: string | null): "success" | "warning" | "danger" | "info" | "neutral" {
  if (value === "accepted" || value === "confirmed" || value === "host") return "success";
  if (value === "interested" || value === "open" || value === "network") return "info";
  if (value === "declined" || value === "closed") return "danger";
  if (value === "invited" || value === "targeted") return "warning";
  return "neutral";
}

export default function BroadcastsPage() {
  const client = useQueryClient();
  const { user, roles, canSelectUniversity, scopedUniversityId, defaultUniversityId } = useUniversityScope();
  const canView = roles.some((role) => ["super_admin", "student_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director"].includes(role));
  const canManage = canView;

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId));
  const [ownershipFilter, setOwnershipFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const { data: broadcasts } = useQuery({
    queryKey: ["broadcasts", scopedUniversityId],
    queryFn: () => broadcastsApi.list({ universityId: scopedUniversityId }),
    enabled: canView
  });
  const { data: programs } = useQuery({
    queryKey: ["programs", scopedUniversityId],
    queryFn: () => programsApi.list(scopedUniversityId),
    enabled: canView
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canView
  });

  const visiblePrograms = useMemo(() => {
    if (!form.university_id) return programs || [];
    return (programs || []).filter((program: any) => program.university_id === Number(form.university_id));
  }, [form.university_id, programs]);

  const hostScopeUniversityId = user?.university_id ?? scopedUniversityId;
  const filteredBroadcasts = useMemo(() => {
    return [...(broadcasts || [])]
      .filter((broadcast: any) => {
        const isHosted = hostScopeUniversityId ? broadcast.university_id === hostScopeUniversityId : false;
        const matchesOwnership =
          ownershipFilter === "all" ||
          (ownershipFilter === "hosted" && isHosted) ||
          (ownershipFilter === "invited" && !isHosted);
        const matchesStatus = statusFilter === "all" || broadcast.status === statusFilter || broadcast.my_invite_status === statusFilter;
        return matchesOwnership && matchesStatus;
      })
      .sort((left: any, right: any) => {
        const leftTime = left.starts_at ? new Date(left.starts_at).getTime() : 0;
        const rightTime = right.starts_at ? new Date(right.starts_at).getTime() : 0;
        return leftTime - rightTime;
      });
  }, [broadcasts, hostScopeUniversityId, ownershipFilter, statusFilter]);
  const broadcastsPagination = usePagination(filteredBroadcasts);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  const hostedCount = (broadcasts || []).filter((broadcast: any) => broadcast.university_id === hostScopeUniversityId).length;
  const awaitingCount = (broadcasts || []).filter((broadcast: any) => ["invited", "open"].includes(broadcast.my_invite_status || "")).length;
  const networkCount = (broadcasts || []).filter((broadcast: any) => broadcast.visibility === "network").length;
  const targetReach = (broadcasts || []).reduce((total: number, broadcast: any) => total + (broadcast.invites?.length || 0), 0);
  const lockedUniversityName =
    universities?.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus";

  function resetForm() {
    setSelectedId(null);
    setForm(buildInitialForm(defaultUniversityId));
  }

  function closeForm() {
    setIsFormOpen(false);
    resetForm();
  }

  function openCreateForm() {
    resetForm();
    setIsFormOpen(true);
  }

  function hydrateForm(broadcast: any) {
    setSelectedId(broadcast.id);
    setForm({
      university_id: String(broadcast.university_id),
      program_id: broadcast.program_id ? String(broadcast.program_id) : "",
      title: broadcast.title || "",
      summary: broadcast.summary || "",
      venue: broadcast.venue || "",
      contact_name: broadcast.contact_name || "",
      contact_email: broadcast.contact_email || "",
      visibility: broadcast.visibility || "network",
      status: broadcast.status || "open",
      starts_at: toLocalInputValue(broadcast.starts_at),
      ends_at: toLocalInputValue(broadcast.ends_at),
      invited_university_ids: (broadcast.invites || []).map((invite: any) => String(invite.university_id))
    });
    setIsFormOpen(true);
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      university_id: Number(form.university_id),
      program_id: form.program_id ? Number(form.program_id) : null,
      title: form.title,
      summary: form.summary,
      venue: form.venue || null,
      contact_name: form.contact_name || null,
      contact_email: form.contact_email || null,
      visibility: form.visibility,
      status: form.status,
      starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
      ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
      invited_university_ids: form.visibility === "targeted" ? form.invited_university_ids.map((value) => Number(value)) : []
    };

    if (selectedId) {
      await broadcastsApi.update(selectedId, payload);
    } else {
      await broadcastsApi.create(payload);
    }

    await client.invalidateQueries({ queryKey: ["broadcasts"] });
    closeForm();
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Network programming"
        title="Broadcasts"
        description="Universities can broadcast major ministry programs and events, invite selected campuses, and let the wider PCM network see shared opportunities and campus-led gatherings."
        actions={(
          <button className="primary-button" type="button" onClick={openCreateForm}>
            Create broadcast
          </button>
        )}
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <MetricCard label="Visible broadcasts" value={formatNumber(broadcasts?.length)} helper="All open programming in your current scope" />
        <MetricCard label="Hosted by your campus" value={formatNumber(hostedCount)} tone="ink" helper="Broadcasts published from your university or campus" />
        <MetricCard label="Awaiting a response" value={formatNumber(awaitingCount)} tone="gold" helper="Invites or open broadcasts still pending" />
        <MetricCard label="Campus reach" value={formatNumber(targetReach)} tone="coral" helper={`${formatNumber(networkCount)} network-wide broadcasts`} />
      </div>

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Live feed</p>
            <h3 className="text-xl font-semibold text-slate-950">Broadcast network</h3>
            <p className="mt-1 text-sm text-slate-500">Open invitations, targeted campus calls, and network-wide program announcements.</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="field-shell min-w-[150px]">
              <span className="field-label">Ownership</span>
              <select className="field-input" value={ownershipFilter} onChange={(event) => setOwnershipFilter(event.target.value)}>
                <option value="all">All broadcasts</option>
                <option value="hosted">Hosted by my campus</option>
                <option value="invited">Invitations for my campus</option>
              </select>
            </label>
            <label className="field-shell min-w-[150px]">
              <span className="field-label">Status</span>
              <select className="field-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option>
                <option value="open">Open</option>
                <option value="invited">Invited</option>
                <option value="accepted">Accepted</option>
                <option value="interested">Interested</option>
                <option value="declined">Declined</option>
              </select>
            </label>
          </div>
        </div>

        {filteredBroadcasts.length === 0 ? (
          <EmptyState
            title="No broadcasts yet"
            description="Create a network-wide or targeted program broadcast to invite other campuses into the activity."
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Broadcast</th>
                    <th>Host</th>
                    <th>Timing</th>
                    <th>Visibility</th>
                    <th>Invites</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {broadcastsPagination.pageItems.map((broadcast: any) => {
                    const isHost = roles.includes("super_admin") || broadcast.university_id === user?.university_id;
                    return (
                      <tr key={broadcast.id}>
                        <td>
                          <div className="table-primary">{broadcast.title}</div>
                          <div className="table-secondary">{broadcast.summary}</div>
                        </td>
                        <td>
                          <div className="table-primary">{broadcast.university_name}</div>
                          <div className="table-secondary">{broadcast.program_name || "General broadcast"} / {broadcast.venue || "Venue not set"}</div>
                        </td>
                        <td>
                          <div className="table-primary">{broadcast.starts_at ? formatDateTime(broadcast.starts_at) : "Start not set"}</div>
                          <div className="table-secondary">{broadcast.ends_at ? formatDateTime(broadcast.ends_at) : "End not set"}</div>
                        </td>
                        <td>
                          <div className="flex flex-wrap gap-2">
                            <StatusBadge label={broadcast.visibility} tone={badgeTone(broadcast.visibility)} />
                            <StatusBadge label={broadcast.status} tone={badgeTone(broadcast.status)} />
                            {broadcast.my_invite_status ? <StatusBadge label={broadcast.my_invite_status} tone={badgeTone(broadcast.my_invite_status)} /> : null}
                          </div>
                        </td>
                        <td>
                          <div className="table-primary">{formatNumber(broadcast.invites?.length || 0)} campuses</div>
                          <div className="table-secondary">
                            {(broadcast.invites || []).slice(0, 2).map((invite: any) => `${invite.university_name} (${invite.status})`).join(" / ") || "Network-wide open"}
                          </div>
                        </td>
                        <td>
                          <div className="table-actions">
                            {isHost ? (
                              <>
                                <TableActionButton label="Edit broadcast" tone="edit" onClick={() => hydrateForm(broadcast)} />
                                <TableActionButton
                                  label="Delete broadcast"
                                  tone="delete"
                                  onClick={async () => {
                                    await broadcastsApi.delete(broadcast.id);
                                    await client.invalidateQueries({ queryKey: ["broadcasts"] });
                                    if (selectedId === broadcast.id) {
                                      resetForm();
                                    }
                                  }}
                                />
                              </>
                            ) : (
                              responseOptions.map((response) => (
                                <button
                                  key={response}
                                  className="secondary-button"
                                  type="button"
                                  onClick={async () => {
                                    await broadcastsApi.respond(broadcast.id, { status: response });
                                    await client.invalidateQueries({ queryKey: ["broadcasts"] });
                                  }}
                                >
                                  {response === "accepted" ? "Accept" : response === "interested" ? "Interested" : "Decline"}
                                </button>
                              ))
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={broadcastsPagination}
              itemLabel="broadcasts"
              onExport={() => exportRowsAsCsv("broadcasts", filteredBroadcasts.map((broadcast: any) => ({
                title: broadcast.title || "",
                university_or_campus: broadcast.university_name || "",
                program: broadcast.program_name || "General broadcast",
                venue: broadcast.venue || "",
                starts_at: broadcast.starts_at ? formatDateTime(broadcast.starts_at) : "Start not set",
                ends_at: broadcast.ends_at ? formatDateTime(broadcast.ends_at) : "End not set",
                visibility: broadcast.visibility || "",
                status: broadcast.status || "",
                my_status: broadcast.my_invite_status || "",
                invited_campuses: (broadcast.invites || []).map((invite: any) => `${invite.university_name} (${invite.status})`).join("; ")
              })))}
            />
          </>
        )}
      </Panel>

      <ModalDialog open={isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Broadcast editor</p>
              <h3 className="text-xl font-semibold text-slate-950">{selectedId ? "Update broadcast" : "Create broadcast"}</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form className="grid gap-4" onSubmit={submitForm}>
            <div className="grid gap-4 md:grid-cols-2">
              {canSelectUniversity ? (
                <label className="field-shell">
                  <span className="field-label">Host university</span>
                  <select
                    className="field-input"
                    value={form.university_id}
                    onChange={(event) => setForm({ ...form, university_id: event.target.value, program_id: "", invited_university_ids: [] })}
                    required
                  >
                    <option value="">Select university or campus</option>
                    {universities?.map((university: any) => (
                      <option key={university.id} value={university.id}>{university.name}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="field-shell">
                  <span className="field-label">Host university</span>
                  <div className="field-input flex items-center text-slate-600">{lockedUniversityName}</div>
                </div>
              )}

              <label className="field-shell">
                <span className="field-label">Linked ministry program</span>
                <select className="field-input" value={form.program_id} onChange={(event) => setForm({ ...form, program_id: event.target.value })}>
                  <option value="">General broadcast</option>
                  {visiblePrograms.map((program: any) => (
                    <option key={program.id} value={program.id}>{program.name}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-shell">
                <span className="field-label">Broadcast title</span>
                <input className="field-input" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
              </label>
              <label className="field-shell">
                <span className="field-label">Venue</span>
                <input className="field-input" value={form.venue} onChange={(event) => setForm({ ...form, venue: event.target.value })} placeholder="Campus hall, auditorium, online..." />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-shell">
                <span className="field-label">Contact name</span>
                <input className="field-input" value={form.contact_name} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Contact email</span>
                <input className="field-input" type="email" value={form.contact_email} onChange={(event) => setForm({ ...form, contact_email: event.target.value })} />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-shell">
                <span className="field-label">Visibility</span>
                <select className="field-input" value={form.visibility} onChange={(event) => setForm({ ...form, visibility: event.target.value, invited_university_ids: [] })}>
                  {visibilityOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">Broadcast status</span>
                <select className="field-input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                  {statusOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-shell">
                <span className="field-label">Starts at</span>
                <input className="field-input" type="datetime-local" value={form.starts_at} onChange={(event) => setForm({ ...form, starts_at: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Ends at</span>
                <input className="field-input" type="datetime-local" value={form.ends_at} onChange={(event) => setForm({ ...form, ends_at: event.target.value })} />
              </label>
            </div>

            <label className="field-shell">
              <span className="field-label">Summary</span>
              <textarea className="field-input min-h-[132px]" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} required />
            </label>

            {form.visibility === "targeted" ? (
              <div className="space-y-3">
                <div>
                  <p className="field-label">Invite universities</p>
                  <p className="mt-1 text-sm text-slate-500">Select the campuses you want to invite directly into this broadcast.</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {universities
                    ?.filter((university: any) => String(university.id) !== form.university_id)
                    .map((university: any) => {
                      const checked = form.invited_university_ids.includes(String(university.id));
                      return (
                        <label key={university.id} className="field-shell field-checkbox">
                          <span className="text-sm font-medium text-slate-800">{university.name}</span>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) =>
                              setForm({
                                ...form,
                                invited_university_ids: event.target.checked
                                  ? [...form.invited_university_ids, String(university.id)]
                                  : form.invited_university_ids.filter((value) => value !== String(university.id))
                              })
                            }
                          />
                        </label>
                      );
                    })}
                </div>
              </div>
            ) : null}

            {canManage ? (
              <button className="primary-button justify-center" type="submit">
                {selectedId ? "Save broadcast" : "Publish broadcast"}
              </button>
            ) : null}
          </form>
        </div>
      </ModalDialog>
    </div>
  );
}
