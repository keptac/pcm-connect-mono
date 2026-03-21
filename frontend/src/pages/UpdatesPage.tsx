import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { mandatoryProgramsApi, programUpdatesApi, reportingPeriodsApi, universitiesApi } from "../api/endpoints";
import { UniversitySelectOptions } from "../components/UniversitySelectOptions";
import { EmptyState, MetricCard, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, TableSearchField, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { matchesTableSearch } from "../lib/tableSearch";
import { useUniversityScope } from "../lib/universityScope";

function isPcmOfficeUniversity(university?: { name?: string | null } | null) {
  return (university?.name || "").trim().toLowerCase().startsWith("pcm office");
}

function buildInitialForm(defaultUniversityId?: number | null, defaultReportingPeriod?: string | null) {
  return {
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    event_name: "",
    event_detail: "",
    reporting_period: defaultReportingPeriod || "",
    reporting_date: "",
    summary: "",
    outcomes: "",
    challenges: "",
    next_steps: "",
    beneficiaries_reached: "",
    volunteers_involved: "",
    funds_used: "",
    attachments: [] as File[],
    existing_attachments: [] as any[],
    meeting_minutes_attachments: [] as File[],
    existing_minutes_attachments: [] as any[],
    meeting_minutes_date: "",
    meeting_minutes_venue: "",
    meeting_minutes_notes: ""
  };
}

function clearMeetingMinutesFields<T extends {
  meeting_minutes_attachments: File[];
  existing_minutes_attachments: any[];
  meeting_minutes_date: string;
  meeting_minutes_venue: string;
  meeting_minutes_notes: string;
}>(form: T): T {
  return {
    ...form,
    meeting_minutes_attachments: [],
    existing_minutes_attachments: [],
    meeting_minutes_date: "",
    meeting_minutes_venue: "",
    meeting_minutes_notes: ""
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

function splitAttachments(attachments: any[] | undefined) {
  const supporting: any[] = [];
  const minutes: any[] = [];
  for (const attachment of attachments || []) {
    if (attachment?.category === "minutes") {
      minutes.push(attachment);
    } else {
      supporting.push(attachment);
    }
  }
  return { supporting, minutes };
}

function formatMeetingMinutesLabel(attachment: any) {
  const parts = ["Meeting minutes"];
  if (attachment?.meeting_date) parts.push(formatDate(attachment.meeting_date));
  if (attachment?.venue) parts.push(attachment.venue);
  return parts.join(" · ");
}

function isMeetingEventName(eventName?: string | null) {
  return (eventName || "").trim().toLowerCase() === "meeting";
}

export default function UpdatesPage() {
  const client = useQueryClient();
  const { roles, canSelectUniversity, scopedUniversityId, defaultUniversityId, scopeKey, scopeParams } = useUniversityScope();
  const canView = roles.some((role) => ["super_admin", "student_admin", "secretary", "program_manager", "committee_member", "executive", "director", "alumni_admin"].includes(role));

  const { data: updates } = useQuery({
    queryKey: ["program-updates", scopeKey],
    queryFn: () => programUpdatesApi.list(scopeParams),
    enabled: canView
  });
  const { data: universities } = useQuery({
    queryKey: ["universities", scopeKey],
    queryFn: () => universitiesApi.list(scopeParams),
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
  const [isDownloadingConsolidated, setIsDownloadingConsolidated] = useState(false);
  const [downloadingUpdateId, setDownloadingUpdateId] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  const defaultReportingPeriod = useMemo(() => {
    return findCurrentReportingPeriodCode(reportingPeriods);
  }, [reportingPeriods]);
  const orderedUniversities = useMemo(() => {
    return [...(universities || [])].sort((left: any, right: any) => {
      const leftIsPcmOffice = isPcmOfficeUniversity(left);
      const rightIsPcmOffice = isPcmOfficeUniversity(right);
      if (leftIsPcmOffice !== rightIsPcmOffice) {
        return leftIsPcmOffice ? -1 : 1;
      }
      return String(left?.name || "").localeCompare(String(right?.name || ""));
    });
  }, [universities]);

  const filteredUpdates = useMemo(() => {
    return (updates || []).filter((item: any) => {
      const attachmentGroups = splitAttachments(item.attachments);
      const matchesPeriod = periodFilter === "all" || item.reporting_period === periodFilter;
      const matchesSearch = matchesTableSearch(search, [
        item.event_name,
        item.title,
        item.event_detail,
        item.university_name,
        item.program_name,
        item.reporting_period,
        item.reporting_period_label,
        item.reporting_date,
        item.summary,
        item.outcomes,
        item.challenges,
        item.next_steps,
        item.beneficiaries_reached,
        item.volunteers_involved,
        item.funds_used,
        attachmentGroups.supporting,
        attachmentGroups.minutes
      ]);
      return matchesPeriod && matchesSearch;
    });
  }, [periodFilter, search, updates]);
  const updatesPagination = usePagination(filteredUpdates);
  const selectableEvents = useMemo(() => {
    return (mandatoryEvents || []).filter((item: any) => item.is_active || item.name === form.event_name);
  }, [form.event_name, mandatoryEvents]);
  const selectedEventConfig = useMemo(() => {
    return selectableEvents.find((item: any) => item.name === form.event_name) || null;
  }, [form.event_name, selectableEvents]);
  const eventRequiresDetail = Boolean(selectedEventConfig?.allow_other_detail || form.event_detail);
  const isMeetingEvent = isMeetingEventName(form.event_name);
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
        ...scopeParams,
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

  async function downloadConsolidatedReport() {
    if (filteredUpdates.length === 0 || isDownloadingConsolidated) return;
    setIsDownloadingConsolidated(true);
    try {
      const response = await programUpdatesApi.downloadConsolidatedReport({
        ...scopeParams,
        reportingPeriod: periodFilter === "all" ? undefined : periodFilter
      });
      const downloadUrl = window.URL.createObjectURL(response.blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = response.filename || `impact-report-consolidated_${periodFilter === "all" ? "all-periods" : periodFilter}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } finally {
      setIsDownloadingConsolidated(false);
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
    const attachmentGroups = splitAttachments(update.attachments);
    const firstMinutesAttachment = attachmentGroups.minutes[0];
    setSelectedId(update.id);
    setIsFormOpen(true);
    setForm({
      university_id: String(update.university_id),
      event_name: update.event_name || update.title || "",
      event_detail: update.event_detail || "",
      reporting_period: update.reporting_period || defaultReportingPeriod || "",
      reporting_date: update.reporting_date || "",
      summary: update.summary || "",
      outcomes: update.outcomes || "",
      challenges: update.challenges || "",
      next_steps: update.next_steps || "",
      beneficiaries_reached: String(update.beneficiaries_reached || ""),
      volunteers_involved: String(update.volunteers_involved || ""),
      funds_used: String(update.funds_used || ""),
      attachments: [],
      existing_attachments: attachmentGroups.supporting,
      meeting_minutes_attachments: [],
      existing_minutes_attachments: attachmentGroups.minutes,
      meeting_minutes_date: firstMinutesAttachment?.meeting_date || "",
      meeting_minutes_venue: firstMinutesAttachment?.venue || "",
      meeting_minutes_notes: firstMinutesAttachment?.notes || ""
    });
  }

  const totalReached = (updates || []).reduce((total: number, item: any) => total + Number(item.beneficiaries_reached || 0), 0);
  const totalVolunteers = (updates || []).reduce((total: number, item: any) => total + Number(item.volunteers_involved || 0), 0);
  const lockedUniversityName =
    orderedUniversities.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus";
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
        title="Program reports"
        description="Every university or campus can submit structured program reports with outcomes, challenges, reach, and funding usage."
        actions={(
          <>
            <button
              className="secondary-button"
              type="button"
              disabled={filteredUpdates.length === 0 || isDownloadingConsolidated}
              onClick={downloadConsolidatedReport}
            >
              {isDownloadingConsolidated ? "Preparing consolidated report..." : "Download consolidated report"}
            </button>
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
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="eyebrow">Update history</p>
              <h3 className="text-xl font-semibold text-slate-950">What campuses are reporting</h3>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <TableSearchField
                value={search}
                onChange={setSearch}
                placeholder="Search event, campus, period, narrative, or minutes"
              />
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
          </div>

          {filteredUpdates.length === 0 ? (
            <EmptyState
              title={updates?.length ? "No updates match this search" : "No updates in this period"}
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
                    {updatesPagination.pageItems.map((update: any) => {
                      const attachmentGroups = splitAttachments(update.attachments);
                      return (
                        <tr key={update.id}>
                          <td>
                            <div className="table-primary">
                              {renderEventLabel(update.event_name || update.title, Boolean(update.event_detail))}
                            </div>
                            {update.event_detail ? (
                              <div className="table-secondary">Specified event: {update.event_detail}</div>
                            ) : null}
                            {attachmentGroups.minutes.length ? (
                              <div className="mt-2 space-y-2">
                                {attachmentGroups.minutes.map((attachment: any) => (
                                  <div key={attachment.stored_name || attachment.url} className="rounded-[12px] border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                                    <div className="font-semibold text-slate-900">{formatMeetingMinutesLabel(attachment)}</div>
                                    <a
                                      className="mt-1 inline-block font-medium text-sky-700 underline underline-offset-2"
                                      href={attachment.url}
                                      rel="noreferrer"
                                      target="_blank"
                                    >
                                      {attachment.name}
                                    </a>
                                    {attachment.notes ? <div className="mt-1">{attachment.notes}</div> : null}
                                  </div>
                                ))}
                              </div>
                            ) : null}
                            {attachmentGroups.supporting.length ? (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {attachmentGroups.supporting.map((attachment: any) => (
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
                            <div className="table-secondary">{formatDate(update.reporting_date || update.created_at)}</div>
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
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <TablePagination
                pagination={updatesPagination}
                itemLabel="updates"
                onExport={() => exportRowsAsCsv("event-updates", filteredUpdates.map((update: any) => {
                  const attachmentGroups = splitAttachments(update.attachments);
                  const firstMinutesAttachment = attachmentGroups.minutes[0];
                  return {
                    event: renderEventLabel(update.event_name || update.title, Boolean(update.event_detail)),
                    specified_event: update.event_detail || "",
                    university_or_campus: update.university_name || "",
                    reporting_period: renderReportingPeriodLabel(update.reporting_period),
                    reporting_date: formatDate(update.reporting_date || update.created_at),
                    beneficiaries_reached: update.beneficiaries_reached || 0,
                    volunteers_involved: update.volunteers_involved || 0,
                    funds_used: update.funds_used || 0,
                    summary: update.summary || "",
                    outcomes: update.outcomes || "",
                    challenges: update.challenges || "",
                    next_steps: update.next_steps || "",
                    supporting_attachments: attachmentGroups.supporting.map((attachment: any) => attachment.name).join("; "),
                    meeting_minutes_files: attachmentGroups.minutes.map((attachment: any) => attachment.name).join("; "),
                    meeting_minutes_date: firstMinutesAttachment?.meeting_date || "",
                    meeting_minutes_venue: firstMinutesAttachment?.venue || "",
                    meeting_minutes_notes: firstMinutesAttachment?.notes || ""
                  };
                }))}
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
                const hasMeetingMinutes = isMeetingEvent && (form.meeting_minutes_attachments.length > 0 || form.existing_minutes_attachments.length > 0);
                if (isMeetingEvent && !hasMeetingMinutes) {
                  window.alert("Meeting updates require uploaded minutes.");
                  return;
                }
                if (hasMeetingMinutes && (!form.meeting_minutes_date || !form.meeting_minutes_venue)) {
                  window.alert("Meeting minutes require both the meeting date and venue.");
                  return;
                }
                if (!form.reporting_date) {
                  window.alert("Reporting date is required.");
                  return;
                }
                const resolvedUniversityId = Number(form.university_id || scopedUniversityId || defaultUniversityId || "");
                if (!resolvedUniversityId) {
                  window.alert("Select a university or campus, or switch into a scope before submitting.");
                  return;
                }
                const payload = new FormData();
                payload.append("university_id", String(resolvedUniversityId));
                payload.append("title", eventRequiresDetail ? form.event_detail : form.event_name);
                payload.append("event_name", form.event_name);
                if (form.event_detail) payload.append("event_detail", form.event_detail);
                payload.append("reporting_period", form.reporting_period);
                payload.append("reporting_date", form.reporting_date);
                payload.append("summary", form.summary);
                if (isMeetingEvent) {
                  payload.append("outcomes", "");
                  payload.append("challenges", "");
                  payload.append("next_steps", "");
                  payload.append("beneficiaries_reached", "0");
                  payload.append("volunteers_involved", "0");
                  payload.append("funds_used", "");
                } else {
                  if (form.outcomes) payload.append("outcomes", form.outcomes);
                  if (form.challenges) payload.append("challenges", form.challenges);
                  if (form.next_steps) payload.append("next_steps", form.next_steps);
                  payload.append("beneficiaries_reached", String(Number(form.beneficiaries_reached || 0)));
                  payload.append("volunteers_involved", String(Number(form.volunteers_involved || 0)));
                  if (form.funds_used) payload.append("funds_used", String(Number(form.funds_used)));
                }
                payload.append(
                  "existing_attachments_json",
                  JSON.stringify(isMeetingEvent ? [...(form.existing_minutes_attachments || [])] : [...(form.existing_attachments || [])])
                );
                if (!isMeetingEvent) {
                  form.attachments.forEach((file) => payload.append("attachments", file));
                }
                if (isMeetingEvent && hasMeetingMinutes) {
                  payload.append("meeting_minutes_date", form.meeting_minutes_date);
                  payload.append("meeting_minutes_venue", form.meeting_minutes_venue);
                  if (form.meeting_minutes_notes) payload.append("meeting_minutes_notes", form.meeting_minutes_notes);
                }
                if (isMeetingEvent) {
                  form.meeting_minutes_attachments.forEach((file) => payload.append("meeting_minutes_attachments", file));
                }
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
                      <UniversitySelectOptions
                        universities={orderedUniversities}
                        emptyOptionLabel="Select university or campus"
                        preserveGroupOrder
                      />
                    </select>
                  </label>
                ) : (
                  <div className="field-shell">
                    <span className="field-label">University / campus</span>
                    <div className="field-input flex items-center text-slate-600">{lockedUniversityName}</div>
                  </div>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <label className="field-shell">
                  <span className="field-label">Event</span>
                  <select
                    className="field-input"
                    value={form.event_name}
                    onChange={(event) => {
                      const nextEventName = event.target.value;
                      const nextEventConfig = selectableEvents.find((item: any) => item.name === nextEventName);
                      const nextForm = {
                        ...form,
                        event_name: nextEventName,
                        event_detail: nextEventConfig?.allow_other_detail ? form.event_detail : ""
                      };
                      setForm(isMeetingEventName(nextEventName) ? nextForm : clearMeetingMinutesFields(nextForm));
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
                <label className="field-shell">
                  <span className="field-label">Reporting date</span>
                  <input
                    className="field-input"
                    type="date"
                    value={form.reporting_date}
                    onChange={(event) => setForm({ ...form, reporting_date: event.target.value })}
                    required
                  />
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

              {/* {isMeetingEvent ? (
                <div className="rounded-[12px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Meeting updates only keep the summary and the approved meeting minutes. Supporting files, narrative breakdowns, reach, missionaries, and funds used are cleared on save.
                </div>
              ) : null} */}

              {isMeetingEvent ? (
                <div className="rounded-[16px] border border-slate-200/80 bg-slate-50/70 p-4">
                  <div className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
                    <div className="space-y-2">
                      <p className="field-label">Meeting minutes</p>
                      <p className="text-sm text-slate-600">Upload the approved minutes for this update and capture the meeting details with them.</p>
                    </div>
                    <label className="field-shell">
                      <span className="field-label">Minutes file</span>
                      <input
                        className="field-input"
                        type="file"
                        multiple
                        accept=".pdf,.doc,.docx"
                        onChange={(event) => setForm({ ...form, meeting_minutes_attachments: Array.from(event.target.files || []) })}
                      />
                    </label>
                  </div>

                  <div className="mt-4 grid gap-4 md:grid-cols-3">
                    <label className="field-shell">
                      <span className="field-label">Date of meeting</span>
                      <input
                        className="field-input"
                        type="date"
                        value={form.meeting_minutes_date}
                        onChange={(event) => setForm({ ...form, meeting_minutes_date: event.target.value })}
                      />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">Venue</span>
                      <input
                        className="field-input"
                        value={form.meeting_minutes_venue}
                        onChange={(event) => setForm({ ...form, meeting_minutes_venue: event.target.value })}
                        placeholder="Where the meeting was held"
                      />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">Notes</span>
                      <input
                        className="field-input"
                        value={form.meeting_minutes_notes}
                        onChange={(event) => setForm({ ...form, meeting_minutes_notes: event.target.value })}
                        placeholder="Optional context for the minutes"
                      />
                    </label>
                  </div>

                  {form.existing_minutes_attachments.length > 0 ? (
                    <div className="mt-4 rounded-[12px] border border-slate-200/80 bg-white/80 p-4">
                      <p className="field-label">Current meeting minutes</p>
                      <div className="mt-3 space-y-2">
                        {form.existing_minutes_attachments.map((attachment: any) => (
                          <div key={attachment.stored_name || attachment.url} className="flex flex-wrap items-center gap-2 rounded-[12px] border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                            <span className="font-medium text-slate-900">{formatMeetingMinutesLabel(attachment)}</span>
                            <a href={attachment.url} target="_blank" rel="noreferrer" className="text-sky-700 underline underline-offset-2">
                              {attachment.name}
                            </a>
                            <button
                              className="text-rose-700"
                              type="button"
                              onClick={() => {
                                const nextMinutes = form.existing_minutes_attachments.filter((item: any) => (item.stored_name || item.url) !== (attachment.stored_name || attachment.url));
                                setForm({
                                  ...form,
                                  existing_minutes_attachments: nextMinutes,
                                  meeting_minutes_date: nextMinutes.length > 0 || form.meeting_minutes_attachments.length > 0 ? form.meeting_minutes_date : "",
                                  meeting_minutes_venue: nextMinutes.length > 0 || form.meeting_minutes_attachments.length > 0 ? form.meeting_minutes_venue : "",
                                  meeting_minutes_notes: nextMinutes.length > 0 || form.meeting_minutes_attachments.length > 0 ? form.meeting_minutes_notes : ""
                                });
                              }}
                            >
                              Remove
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {form.meeting_minutes_attachments.length > 0 ? (
                    <div className="mt-4 rounded-[12px] border border-slate-200/80 bg-white/80 px-4 py-3 text-sm text-slate-600">
                      {form.meeting_minutes_attachments.length} new meeting minute file{form.meeting_minutes_attachments.length === 1 ? "" : "s"} selected: {form.meeting_minutes_attachments.map((file) => file.name).join(", ")}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {!isMeetingEvent ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="field-shell">
                    <span className="field-label">Attach images or supporting documents</span>
                    <input
                      className="field-input"
                      type="file"
                      multiple
                      accept=".jpg,.jpeg,.png,.pdf,.doc,.docx"
                      onChange={(event) => setForm({ ...form, attachments: Array.from(event.target.files || []) })}
                    />
                  </label>
                  <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                    Add photos, PDFs, or Word documents as supporting evidence for the submitted update.
                  </div>
                </div>
              ) : null}

              {!isMeetingEvent && form.existing_attachments.length > 0 ? (
                <div className="rounded-[12px] border border-slate-200/80 bg-white/80 p-4">
                  <p className="field-label">Current supporting attachments</p>
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

              {!isMeetingEvent && form.attachments.length > 0 ? (
                <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
                  {form.attachments.length} new supporting file{form.attachments.length === 1 ? "" : "s"} selected: {form.attachments.map((file) => file.name).join(", ")}
                </div>
              ) : null}

              <label className="field-shell">
                <span className="field-label">Report Details</span>
                <textarea className="field-input min-h-[120px]" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })} />
              </label>

              {!isMeetingEvent ? (
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
                    <span className="field-label">Next/Recommended steps</span>
                    <textarea className="field-input min-h-[110px]" value={form.next_steps} onChange={(event) => setForm({ ...form, next_steps: event.target.value })} />
                  </label>
                </div>
              ) : null}

              {!isMeetingEvent ? (
                <div className="grid gap-4 md:grid-cols-3">
                  <label className="field-shell">
                    <span className="field-label">Total baptisms</span>
                    <input className="field-input" value={form.beneficiaries_reached} onChange={(event) => setForm({ ...form, beneficiaries_reached: event.target.value })} />
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Average missionaries involved</span>
                    <input className="field-input" value={form.volunteers_involved} onChange={(event) => setForm({ ...form, volunteers_involved: event.target.value })} />
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Estimate funds used</span>
                    <input className="field-input" value={form.funds_used} onChange={(event) => setForm({ ...form, funds_used: event.target.value })} />
                  </label>
                </div>
              ) : null}

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
