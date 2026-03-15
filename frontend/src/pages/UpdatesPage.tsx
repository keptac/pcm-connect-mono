import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { mandatoryProgramsApi, programUpdatesApi, reportingPeriodsApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

function buildInitialForm(defaultUniversityId?: number | null, defaultReportingPeriod?: string | null) {
  return {
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    event_name: "",
    event_detail: "",
    reporting_period: defaultReportingPeriod || "",
    summary: "",
    outcomes: "",
    challenges: "",
    next_steps: "",
    beneficiaries_reached: "",
    volunteers_involved: "",
    funds_used: "",
    attachments: [] as File[],
    existing_attachments: [] as any[]
  };
}

function findCurrentReportingPeriodCode(periods: any[] | undefined) {
  const today = new Date();
  return periods?.find((period: any) => {
    const start = new Date(`${period.start_date}T00:00:00`);
    const end = new Date(`${period.end_date}T23:59:59`);
    return !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && start <= today && today <= end && period.is_active;
  })?.code || periods?.find((period: any) => period.is_active)?.code || periods?.[0]?.code || "";
}

export default function UpdatesPage() {
  const client = useQueryClient();
  const { roles, canSelectUniversity, scopedUniversityId, defaultUniversityId } = useUniversityScope();
  const canView = roles.some((role) => ["super_admin", "student_admin", "program_manager", "committee_member", "executive", "director", "alumni_admin"].includes(role));

  const { data: updates } = useQuery({
    queryKey: ["program-updates", scopedUniversityId],
    queryFn: () => programUpdatesApi.list({ universityId: scopedUniversityId }),
    enabled: canView
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canView
  });
  const { data: mandatoryEvents } = useQuery({
    queryKey: ["mandatory-programs", "event", true],
    queryFn: () => mandatoryProgramsApi.list({ programType: "event", includeInactive: true }),
    enabled: canView
  });
  const { data: reportingPeriods } = useQuery({
    queryKey: ["reporting-periods", true],
    queryFn: () => reportingPeriodsApi.list(true),
    enabled: canView
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId));
  const [periodFilter, setPeriodFilter] = useState("all");
  const [isDownloadingPack, setIsDownloadingPack] = useState(false);
  const [downloadingUpdateId, setDownloadingUpdateId] = useState<number | null>(null);

  const defaultReportingPeriod = useMemo(() => {
    return findCurrentReportingPeriodCode(reportingPeriods);
  }, [reportingPeriods]);

  const filteredUpdates = useMemo(() => {
    return (updates || []).filter((item: any) => periodFilter === "all" || item.reporting_period === periodFilter);
  }, [periodFilter, updates]);
  const updatesPagination = usePagination(filteredUpdates);
  const selectableEvents = useMemo(() => {
    return (mandatoryEvents || []).filter((item: any) => item.is_active || item.name === form.event_name);
  }, [form.event_name, mandatoryEvents]);
  const selectedEventConfig = useMemo(() => {
    return selectableEvents.find((item: any) => item.name === form.event_name) || null;
  }, [form.event_name, selectableEvents]);
  const eventRequiresDetail = Boolean(selectedEventConfig?.allow_other_detail || form.event_detail);
  const periodLookup = useMemo(
    () => Object.fromEntries((reportingPeriods || []).map((period: any) => [period.code, period])),
    [reportingPeriods]
  );
  const selectableReportingPeriods = useMemo(() => {
    return (reportingPeriods || []).filter((period: any) => period.is_active || period.code === form.reporting_period);
  }, [form.reporting_period, reportingPeriods]);
  const reportingPeriodsForFilter = useMemo(() => {
    const options = new Map<string, { code: string; label: string }>();
    for (const period of reportingPeriods || []) {
      options.set(period.code, { code: period.code, label: period.label || period.code });
    }
    for (const item of updates || []) {
      if (!item.reporting_period || options.has(item.reporting_period)) continue;
      options.set(item.reporting_period, { code: item.reporting_period, label: item.reporting_period });
    }
    return Array.from(options.values());
  }, [reportingPeriods, updates]);

  useEffect(() => {
    if (!defaultReportingPeriod) return;
    setForm((current) => current.reporting_period ? current : { ...current, reporting_period: defaultReportingPeriod });
  }, [defaultReportingPeriod]);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  function resetForm() {
    setSelectedId(null);
    setForm(buildInitialForm(defaultUniversityId, defaultReportingPeriod));
  }

  function openCreateForm() {
    resetForm();
    setIsFormOpen(true);
  }

  async function downloadReportPack() {
    if (filteredUpdates.length === 0 || isDownloadingPack) return;
    setIsDownloadingPack(true);
    try {
      const response = await programUpdatesApi.downloadReportPack({
        universityId: scopedUniversityId,
        reportingPeriod: periodFilter === "all" ? undefined : periodFilter
      });
      const downloadUrl = window.URL.createObjectURL(response.blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = response.filename || `impact-report-pack_${periodFilter === "all" ? "all-periods" : periodFilter}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } finally {
      setIsDownloadingPack(false);
    }
  }

  async function downloadSingleReport(update: any) {
    if (downloadingUpdateId === update.id) return;
    setDownloadingUpdateId(update.id);
    try {
      const response = await programUpdatesApi.downloadReport(update.id);
      const downloadUrl = window.URL.createObjectURL(response.blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = response.filename || `impact-report_${update.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } finally {
      setDownloadingUpdateId(null);
    }
  }

  function hydrateForm(update: any) {
    setSelectedId(update.id);
    setIsFormOpen(true);
    setForm({
      university_id: String(update.university_id),
      event_name: update.event_name || update.title || "",
      event_detail: update.event_detail || "",
      reporting_period: update.reporting_period || defaultReportingPeriod || "",
      summary: update.summary || "",
      outcomes: update.outcomes || "",
      challenges: update.challenges || "",
      next_steps: update.next_steps || "",
      beneficiaries_reached: String(update.beneficiaries_reached || ""),
      volunteers_involved: String(update.volunteers_involved || ""),
      funds_used: String(update.funds_used || ""),
      attachments: [],
      existing_attachments: update.attachments || []
    });
  }

  const totalReached = (updates || []).reduce((total: number, item: any) => total + Number(item.beneficiaries_reached || 0), 0);
  const totalVolunteers = (updates || []).reduce((total: number, item: any) => total + Number(item.volunteers_involved || 0), 0);
  const lockedUniversityName =
    universities?.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus";
  const renderEventLabel = (eventName?: string, allowSpecify?: boolean) => {
    if (!eventName) return "Unspecified event";
    if (allowSpecify && !String(eventName).toLowerCase().includes("specify")) {
      return `${eventName} (Specify)`;
    }
    return eventName;
  };
  const renderReportingPeriodLabel = (periodCode?: string | null) => {
    if (!periodCode) return "No reporting period";
    return periodLookup[periodCode]?.label || periodCode;
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Impact reporting"
        title="Event updates"
        description="Every university or campus can submit structured event updates with outcomes, challenges, reach, and funding usage."
        actions={(
          <>
            <button
              className="secondary-button"
              type="button"
              disabled={filteredUpdates.length === 0 || isDownloadingPack}
              onClick={downloadReportPack}
            >
              {isDownloadingPack ? "Preparing PDF pack..." : "Download PDF pack"}
            </button>
            <button className="primary-button" type="button" onClick={openCreateForm}>
              Submit update
            </button>
          </>
        )}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <MetricCard label="Updates filed" value={formatNumber(updates?.length)} helper="Event-level narrative submissions" />
        <MetricCard label="People reached" value={formatNumber(totalReached)} tone="gold" helper="Cumulative reach recorded in updates" />
        <MetricCard label="Volunteers mobilized" value={formatNumber(totalVolunteers)} tone="coral" helper="Reported through the update feed" />
      </div>

      <div className="grid gap-6">
        <Panel className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Update history</p>
              <h3 className="text-xl font-semibold text-slate-950">What campuses are reporting</h3>
            </div>
            <label className="field-shell min-w-[180px]">
              <span className="field-label">Reporting period</span>
              <select className="field-input" value={periodFilter} onChange={(event) => setPeriodFilter(event.target.value)}>
                <option value="all">All periods</option>
                {reportingPeriodsForFilter.map((period) => (
                  <option key={period.code} value={period.code}>{period.label}</option>
                ))}
              </select>
            </label>
          </div>

          {filteredUpdates.length === 0 ? (
            <EmptyState
              title="No updates in this period"
              description="Once universities and campuses submit updates, they will show up here in a narrative timeline."
            />
          ) : (
            <>
              <div className="table-shell">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>University</th>
                      <th>Period</th>
                      <th>Reach</th>
                      <th>Funds Used</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {updatesPagination.pageItems.map((update: any) => (
                      <tr key={update.id}>
                        <td>
                          <div className="table-primary">
                            {renderEventLabel(update.event_name || update.title, Boolean(update.event_detail))}
                          </div>
                          {update.event_detail ? (
                            <div className="table-secondary">Specified event: {update.event_detail}</div>
                          ) : null}
                          {update.attachments?.length ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {update.attachments.map((attachment: any) => (
                                <a
                                  key={attachment.stored_name || attachment.url}
                                  className="text-xs font-medium text-sky-700 underline underline-offset-2"
                                  href={attachment.url}
                                  rel="noreferrer"
                                  target="_blank"
                                >
                                  {attachment.name}
                                </a>
                              ))}
                            </div>
                          ) : null}
                          <div className="table-secondary">{update.summary}</div>
                          <div className="table-secondary">Outcomes: {update.outcomes || "Not recorded"} / Challenges: {update.challenges || "Not recorded"} / Next: {update.next_steps || "Not recorded"}</div>
                        </td>
                        <td>
                          <div className="table-primary">{update.university_name}</div>
                          {update.program_name ? <div className="table-secondary">Linked ministry program: {update.program_name}</div> : null}
                        </td>
                        <td>
                          <StatusBadge label={renderReportingPeriodLabel(update.reporting_period)} tone="info" />
                          <div className="table-secondary">{formatDate(update.created_at)}</div>
                        </td>
                        <td>
                          <div className="table-primary">{formatNumber(update.beneficiaries_reached)} reached</div>
                          <div className="table-secondary">{formatNumber(update.volunteers_involved)} volunteers</div>
                        </td>
                        <td>{formatCurrency(update.funds_used)}</td>
                        <td>
                          <div className="table-actions">
                            <TableActionButton
                              label="Download PDF report"
                              tone="download"
                              disabled={downloadingUpdateId === update.id}
                              onClick={() => downloadSingleReport(update)}
                            />
                            <TableActionButton label="Edit update" tone="edit" onClick={() => hydrateForm(update)} />
                            <TableActionButton
                              label="Delete update"
                              tone="delete"
                              onClick={async () => {
                                await programUpdatesApi.delete(update.id);
                                await client.invalidateQueries({ queryKey: ["program-updates"] });
                                await client.invalidateQueries({ queryKey: ["programs"] });
                              }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <TablePagination
                pagination={updatesPagination}
                itemLabel="updates"
                onExport={() => exportRowsAsCsv("event-updates", filteredUpdates.map((update: any) => ({
                  event: renderEventLabel(update.event_name || update.title, Boolean(update.event_detail)),
                  specified_event: update.event_detail || "",
                  university_or_campus: update.university_name || "",
                  reporting_period: renderReportingPeriodLabel(update.reporting_period),
                  beneficiaries_reached: update.beneficiaries_reached || 0,
                  volunteers_involved: update.volunteers_involved || 0,
                  funds_used: update.funds_used || 0,
                  summary: update.summary || "",
                  outcomes: update.outcomes || "",
                  challenges: update.challenges || "",
                  next_steps: update.next_steps || "",
                  attachments: (update.attachments || []).map((attachment: any) => attachment.name).join("; "),
                  created_at: formatDate(update.created_at)
                })))}
              />
            </>
          )}
        </Panel>
      </div>

      {isFormOpen ? (
        <div className="modal-overlay" onClick={() => { setIsFormOpen(false); resetForm(); }}>
          <div className="modal-shell" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="eyebrow">Update composer</p>
                <h3 className="text-xl font-semibold text-slate-950">{selectedId ? "Edit update" : "Submit update"}</h3>
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setIsFormOpen(false);
                  resetForm();
                }}
              >
                Close
              </button>
            </div>

            <form
              className="mt-6 grid gap-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const payload = new FormData();
                payload.append("university_id", String(Number(form.university_id)));
                payload.append("title", eventRequiresDetail ? form.event_detail : form.event_name);
                payload.append("event_name", form.event_name);
                if (form.event_detail) payload.append("event_detail", form.event_detail);
                payload.append("reporting_period", form.reporting_period);
                payload.append("summary", form.summary);
                if (form.outcomes) payload.append("outcomes", form.outcomes);
                if (form.challenges) payload.append("challenges", form.challenges);
                if (form.next_steps) payload.append("next_steps", form.next_steps);
                payload.append("beneficiaries_reached", String(Number(form.beneficiaries_reached || 0)));
                payload.append("volunteers_involved", String(Number(form.volunteers_involved || 0)));
                if (form.funds_used) payload.append("funds_used", String(Number(form.funds_used)));
                payload.append("existing_attachments_json", JSON.stringify(form.existing_attachments || []));
                form.attachments.forEach((file) => payload.append("attachments", file));
                if (selectedId) {
                  await programUpdatesApi.update(selectedId, payload);
                } else {
                  await programUpdatesApi.create(payload);
                }
                await client.invalidateQueries({ queryKey: ["program-updates"] });
                await client.invalidateQueries({ queryKey: ["programs"] });
                await client.invalidateQueries({ queryKey: ["analytics-programs"] });
                setIsFormOpen(false);
                resetForm();
              }}
            >
              <div className="grid gap-4 md:grid-cols-2">
                {canSelectUniversity ? (
                  <label className="field-shell">
                    <span className="field-label">University / campus</span>
                    <select className="field-input" value={form.university_id} onChange={(event) => setForm({ ...form, university_id: event.target.value })}>
                      <option value="">Select university or campus</option>
                      {universities?.map((university: any) => (
                        <option key={university.id} value={university.id}>{university.name}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="field-shell">
                    <span className="field-label">University / campus</span>
                    <div className="field-input flex items-center text-slate-600">{lockedUniversityName}</div>
                  </div>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="field-shell">
                  <span className="field-label">Event</span>
                  <select
                    className="field-input"
                    value={form.event_name}
                    onChange={(event) => {
                      const nextEventName = event.target.value;
                      const nextEventConfig = selectableEvents.find((item: any) => item.name === nextEventName);
                      setForm({
                        ...form,
                        event_name: nextEventName,
                        event_detail: nextEventConfig?.allow_other_detail ? form.event_detail : ""
                      });
                    }}
                  >
                    <option value="">Select event</option>
                    {selectableEvents.map((item: any) => (
                      <option key={item.id} value={item.name}>
                        {renderEventLabel(item.name, item.allow_other_detail)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field-shell">
                  <span className="field-label">Reporting period</span>
                  <select className="field-input" value={form.reporting_period} onChange={(event) => setForm({ ...form, reporting_period: event.target.value })}>
                    <option value="">Select reporting period</option>
                    {selectableReportingPeriods.map((period: any) => (
                      <option key={period.code} value={period.code}>
                        {period.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {eventRequiresDetail ? (
                <label className="field-shell">
                  <span className="field-label">Specify event</span>
                  <input
                    className="field-input"
                    value={form.event_detail}
                    onChange={(event) => setForm({ ...form, event_detail: event.target.value })}
                    placeholder="Enter the exact event name"
                  />
                </label>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <label className="field-shell">
                  <span className="field-label">Attach images or documents</span>
                  <input
                    className="field-input"
                    type="file"
                    multiple
                    accept=".jpg,.jpeg,.png,.pdf,.doc,.docx"
                    onChange={(event) => setForm({ ...form, attachments: Array.from(event.target.files || []) })}
                  />
                </label>
                <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                  Add photos, PDFs, or Word documents as evidence for the submitted update.
                </div>
              </div>

              {form.existing_attachments.length > 0 ? (
                <div className="rounded-[12px] border border-slate-200/80 bg-white/80 p-4">
                  <p className="field-label">Current attachments</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {form.existing_attachments.map((attachment: any) => (
                      <div key={attachment.stored_name || attachment.url} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        <a href={attachment.url} target="_blank" rel="noreferrer" className="text-sky-700 underline underline-offset-2">
                          {attachment.name}
                        </a>
                        <button
                          className="text-rose-700"
                          type="button"
                          onClick={() =>
                            setForm({
                              ...form,
                              existing_attachments: form.existing_attachments.filter((item: any) => (item.stored_name || item.url) !== (attachment.stored_name || attachment.url))
                            })
                          }
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {form.attachments.length > 0 ? (
                <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                  {form.attachments.length} new file{form.attachments.length === 1 ? "" : "s"} selected: {form.attachments.map((file) => file.name).join(", ")}
                </div>
              ) : null}

              <label className="field-shell">
                <span className="field-label">Summary</span>
                <textarea className="field-input min-h-[120px]" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
              </label>

              <div className="grid gap-4 md:grid-cols-3">
                <label className="field-shell">
                  <span className="field-label">Outcomes</span>
                  <textarea className="field-input min-h-[110px]" value={form.outcomes} onChange={(event) => setForm({ ...form, outcomes: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Challenges</span>
                  <textarea className="field-input min-h-[110px]" value={form.challenges} onChange={(event) => setForm({ ...form, challenges: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Next steps</span>
                  <textarea className="field-input min-h-[110px]" value={form.next_steps} onChange={(event) => setForm({ ...form, next_steps: event.target.value })} />
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <label className="field-shell">
                  <span className="field-label">Beneficiaries reached</span>
                  <input className="field-input" value={form.beneficiaries_reached} onChange={(event) => setForm({ ...form, beneficiaries_reached: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Volunteers involved</span>
                  <input className="field-input" value={form.volunteers_involved} onChange={(event) => setForm({ ...form, volunteers_involved: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Funds used</span>
                  <input className="field-input" value={form.funds_used} onChange={(event) => setForm({ ...form, funds_used: event.target.value })} />
                </label>
              </div>

              <div className="flex flex-wrap gap-3">
                <button className="primary-button" type="submit">{selectedId ? "Save update" : "Submit update"}</button>
                <button className="secondary-button" type="button" onClick={resetForm}>Reset</button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
