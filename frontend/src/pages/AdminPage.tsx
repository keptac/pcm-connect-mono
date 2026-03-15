import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { adminApi, conferencesApi, mandatoryProgramsApi, reportingPeriodsApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatDate, formatNumber } from "../lib/format";
import { useAuthStore } from "../store/auth";

export default function AdminPage() {
  const client = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.roles?.includes("super_admin");
  const [activeSection, setActiveSection] = useState<"conferences" | "reporting_periods" | "mandatory_programs">("conferences");
  const [selectedMandatoryId, setSelectedMandatoryId] = useState<number | null>(null);
  const [selectedConferenceId, setSelectedConferenceId] = useState<number | null>(null);
  const [selectedReportingPeriodId, setSelectedReportingPeriodId] = useState<number | null>(null);
  const [isTransitionDialogOpen, setIsTransitionDialogOpen] = useState(false);
  const [isAuditLogDialogOpen, setIsAuditLogDialogOpen] = useState(false);
  const [transitionState, setTransitionState] = useState<"confirm" | "running" | "complete" | "error">("confirm");
  const [transitionProgress, setTransitionProgress] = useState(0);
  const [transitionUpdatedCount, setTransitionUpdatedCount] = useState<number | null>(null);
  const [transitionError, setTransitionError] = useState("");
  const [mandatoryForm, setMandatoryForm] = useState({
    name: "",
    sort_order: "0",
    is_active: true,
    allow_other_detail: false
  });
  const [conferenceForm, setConferenceForm] = useState({
    name: "",
    union_name: "Zimbabwe Union Conference",
    is_active: true
  });
  const [reportingPeriodForm, setReportingPeriodForm] = useState({
    code: "",
    label: "",
    start_date: "",
    end_date: "",
    sort_order: "0",
    is_active: true
  });

  const { data: logs } = useQuery({
    queryKey: ["audit-logs"],
    queryFn: adminApi.auditLogs,
    enabled: isAdmin
  });
  const { data: mandatoryPrograms } = useQuery({
    queryKey: ["mandatory-programs", "event", true],
    queryFn: () => mandatoryProgramsApi.list({ programType: "event", includeInactive: true }),
    enabled: isAdmin
  });
  const { data: conferences } = useQuery({
    queryKey: ["conferences"],
    queryFn: () => conferencesApi.list(false),
    enabled: isAdmin
  });
  const { data: reportingPeriods } = useQuery({
    queryKey: ["reporting-periods", true],
    queryFn: () => reportingPeriodsApi.list(true),
    enabled: isAdmin
  });
  const conferencesPagination = usePagination(conferences);
  const reportingPeriodsPagination = usePagination(reportingPeriods);
  const mandatoryProgramsPagination = usePagination(mandatoryPrograms);
  const auditLogsPagination = usePagination(logs, 12);

  useEffect(() => {
    if (transitionState !== "running") return undefined;

    const intervalId = window.setInterval(() => {
      setTransitionProgress((current) => {
        if (current >= 92) return current;
        return Math.min(current + Math.max(4, (92 - current) * 0.14), 92);
      });
    }, 180);

    return () => window.clearInterval(intervalId);
  }, [transitionState]);

  if (!isAdmin) {
    return <Panel><p className="text-sm text-slate-600">Admin access required.</p></Panel>;
  }

  function resetMandatoryForm() {
    setSelectedMandatoryId(null);
    setMandatoryForm({
      name: "",
      sort_order: "0",
      is_active: true,
      allow_other_detail: false
    });
  }

  function resetConferenceForm() {
    setSelectedConferenceId(null);
    setConferenceForm({
      name: "",
      union_name: "Zimbabwe Union Conference",
      is_active: true
    });
  }

  function resetReportingPeriodForm() {
    setSelectedReportingPeriodId(null);
    setReportingPeriodForm({
      code: "",
      label: "",
      start_date: "",
      end_date: "",
      sort_order: "0",
      is_active: true
    });
  }

  function resetTransitionDialog() {
    setIsTransitionDialogOpen(false);
    setTransitionState("confirm");
    setTransitionProgress(0);
    setTransitionUpdatedCount(null);
    setTransitionError("");
  }

  async function runTransitionJob() {
    setTransitionState("running");
    setTransitionProgress(10);
    setTransitionUpdatedCount(null);
    setTransitionError("");

    try {
      await new Promise((resolve) => window.setTimeout(resolve, 180));
      const result = await adminApi.runAlumni();
      await Promise.all([
        client.invalidateQueries({ queryKey: ["audit-logs"] }),
        client.invalidateQueries({ queryKey: ["members"] }),
        client.invalidateQueries({ queryKey: ["people-breakdown"] }),
        client.invalidateQueries({ queryKey: ["analytics-overview"] }),
        client.invalidateQueries({ queryKey: ["alumni-connect"] })
      ]);
      setTransitionProgress(100);
      setTransitionUpdatedCount(Number(result?.updated || 0));
      setTransitionState("complete");
    } catch (error: any) {
      setTransitionError(error?.response?.data?.detail || "Unable to run the alumni transition job right now.");
      setTransitionState("error");
    }
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-4 lg:grid-cols-4">
        <MetricCard label="Audit entries" value={formatNumber(logs?.length)} helper="Recent actions available in the audit trail" />
        <MetricCard label="Mandatory events" value={formatNumber(mandatoryPrograms?.length)} tone="gold" helper="Configured update events across the network" />
        <MetricCard label="Reporting periods" value={formatNumber(reportingPeriods?.length)} tone="coral" helper="Configured submission windows for updates and coverage" />
        <MetricCard label="Conferences" value={formatNumber(conferences?.length)} tone="ink" helper="Conference and union structure across the network" />
      </div>

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-wrap gap-3">
            <button
              className="secondary-button"
              type="button"
              onClick={() => setIsTransitionDialogOpen(true)}
            >
              Run transition job
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => setIsAuditLogDialogOpen(true)}
            >
              Open audit logs
            </button>
            <button
              className={activeSection === "conferences" ? "primary-button" : "secondary-button"}
              type="button"
              onClick={() => setActiveSection("conferences")}
            >
              Conference directory
            </button>
            <button
              className={activeSection === "reporting_periods" ? "primary-button" : "secondary-button"}
              type="button"
              onClick={() => setActiveSection("reporting_periods")}
            >
              Reporting Periods
            </button>
            <button
              className={activeSection === "mandatory_programs" ? "primary-button" : "secondary-button"}
              type="button"
              onClick={() => setActiveSection("mandatory_programs")}
            >
              Mandatory programs
            </button>
          </div>
        </div>

        {activeSection === "conferences" ? (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="eyebrow">Conference directory</p>
                <h3 className="text-xl font-semibold text-slate-950">Conference and union setup</h3>
                <p className="mt-1 text-sm text-slate-500">Each campus or university belongs to a conference, and every conference belongs to a union.</p>
              </div>
              {selectedConferenceId ? (
                <button className="secondary-button" type="button" onClick={resetConferenceForm}>
                  Clear
                </button>
              ) : null}
            </div>

            <div className="grid items-start gap-6 xl:grid-cols-[0.82fr_1.18fr]">
              <div className="space-y-5 rounded-[12px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
                <div>
                  <p className="eyebrow">Conference editor</p>
                  <h4 className="text-lg font-semibold text-slate-950">{selectedConferenceId ? "Update conference" : "Add conference"}</h4>
                </div>
                <form
                  className="grid gap-4"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    const payload = {
                      name: conferenceForm.name,
                      union_name: conferenceForm.union_name,
                      is_active: conferenceForm.is_active
                    };
                    if (selectedConferenceId) {
                      await conferencesApi.update(selectedConferenceId, payload);
                    } else {
                      await conferencesApi.create(payload);
                    }
                    await client.invalidateQueries({ queryKey: ["conferences"] });
                    await client.invalidateQueries({ queryKey: ["universities"] });
                    resetConferenceForm();
                  }}
                >
                  <label className="field-shell">
                    <span className="field-label">Conference name</span>
                    <input className="field-input" value={conferenceForm.name} onChange={(event) => setConferenceForm({ ...conferenceForm, name: event.target.value })} placeholder="North Zimbabwe Conference" />
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Union name</span>
                    <input className="field-input" value={conferenceForm.union_name} onChange={(event) => setConferenceForm({ ...conferenceForm, union_name: event.target.value })} placeholder="Zimbabwe Union Conference" />
                  </label>
                  <label className="field-shell field-checkbox">
                    <span className="field-label">Active conference</span>
                    <input type="checkbox" checked={conferenceForm.is_active} onChange={(event) => setConferenceForm({ ...conferenceForm, is_active: event.target.checked })} />
                  </label>
                  <button className="primary-button" type="submit">
                    {selectedConferenceId ? "Save conference" : "Add conference"}
                  </button>
                </form>
              </div>

              {!conferences?.length ? (
                <EmptyState
                  title="No conferences configured"
                  description="Add conferences here so campuses can be enrolled under the correct conference and union."
                />
              ) : (
                <div className="space-y-5 rounded-[12px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
                  <div>
                    <p className="eyebrow">Conference directory</p>
                    <h4 className="text-lg font-semibold text-slate-950">Configured conferences</h4>
                  </div>
                  <div className="table-shell">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Conference</th>
                          <th>Union</th>
                          <th>Campuses</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {conferencesPagination.pageItems.map((conference: any) => (
                          <tr key={conference.id}>
                            <td>
                              <div className="table-primary">{conference.name}</div>
                            </td>
                            <td>{conference.union_name}</td>
                            <td>{formatNumber(conference.campus_count)}</td>
                            <td>
                              <StatusBadge label={conference.is_active ? "active" : "inactive"} tone={conference.is_active ? "success" : "warning"} />
                            </td>
                            <td>
                              <div className="table-actions">
                                <TableActionButton
                                  label="Edit conference"
                                  tone="edit"
                                  onClick={() => {
                                    setSelectedConferenceId(conference.id);
                                    setConferenceForm({
                                      name: conference.name || "",
                                      union_name: conference.union_name || "",
                                      is_active: conference.is_active ?? true
                                    });
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
                    pagination={conferencesPagination}
                    itemLabel="conferences"
                    onExport={() => exportRowsAsCsv("conference-directory", (conferences || []).map((conference: any) => ({
                      conference: conference.name,
                      union: conference.union_name || "",
                      campus_count: conference.campus_count || 0,
                      status: conference.is_active ? "active" : "inactive"
                    })))}
                  />
                </div>
              )}
            </div>
          </div>
        ) : null}

        {activeSection === "reporting_periods" ? (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="eyebrow">Reporting periods</p>
                <h3 className="text-xl font-semibold text-slate-950">Configured reporting windows</h3>
                <p className="mt-1 text-sm text-slate-500">Updates and ministry compliance checks now use these centrally managed periods.</p>
              </div>
              {selectedReportingPeriodId ? (
                <button className="secondary-button" type="button" onClick={resetReportingPeriodForm}>
                  Clear
                </button>
              ) : null}
            </div>

            <div className="grid items-start gap-6 xl:grid-cols-[0.92fr_1.08fr]">
              <div className="space-y-5 rounded-[12px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
                <div>
                  <p className="eyebrow">Reporting period editor</p>
                  <h4 className="text-lg font-semibold text-slate-950">{selectedReportingPeriodId ? "Update reporting period" : "Add reporting period"}</h4>
                </div>
                <form
                  className="grid gap-4"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    const payload = {
                      code: reportingPeriodForm.code,
                      label: reportingPeriodForm.label,
                      start_date: reportingPeriodForm.start_date,
                      end_date: reportingPeriodForm.end_date,
                      sort_order: Number(reportingPeriodForm.sort_order || 0),
                      is_active: reportingPeriodForm.is_active
                    };
                    if (selectedReportingPeriodId) {
                      await reportingPeriodsApi.update(selectedReportingPeriodId, payload);
                    } else {
                      await reportingPeriodsApi.create(payload);
                    }
                    await client.invalidateQueries({ queryKey: ["reporting-periods"] });
                    resetReportingPeriodForm();
                  }}
                >
                  <label className="field-shell">
                    <span className="field-label">Period code</span>
                    <input className="field-input" value={reportingPeriodForm.code} onChange={(event) => setReportingPeriodForm({ ...reportingPeriodForm, code: event.target.value })} placeholder="2026-Q1" />
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Display label</span>
                    <input className="field-input" value={reportingPeriodForm.label} onChange={(event) => setReportingPeriodForm({ ...reportingPeriodForm, label: event.target.value })} placeholder="2026 Quarter 1" />
                  </label>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="field-shell">
                      <span className="field-label">Start date</span>
                      <input className="field-input" type="date" value={reportingPeriodForm.start_date} onChange={(event) => setReportingPeriodForm({ ...reportingPeriodForm, start_date: event.target.value })} />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">End date</span>
                      <input className="field-input" type="date" value={reportingPeriodForm.end_date} onChange={(event) => setReportingPeriodForm({ ...reportingPeriodForm, end_date: event.target.value })} />
                    </label>
                  </div>
                  <label className="field-shell">
                    <span className="field-label">Display order</span>
                    <input className="field-input" inputMode="numeric" value={reportingPeriodForm.sort_order} onChange={(event) => setReportingPeriodForm({ ...reportingPeriodForm, sort_order: event.target.value })} />
                  </label>
                  <label className="field-shell field-checkbox">
                    <span className="field-label">Active reporting period</span>
                    <input type="checkbox" checked={reportingPeriodForm.is_active} onChange={(event) => setReportingPeriodForm({ ...reportingPeriodForm, is_active: event.target.checked })} />
                  </label>
                  <button className="primary-button" type="submit">
                    {selectedReportingPeriodId ? "Save reporting period" : "Add reporting period"}
                  </button>
                </form>
              </div>

              {!reportingPeriods?.length ? (
                <EmptyState
                  title="No reporting periods configured"
                  description="Add reporting periods here so update submission and campus coverage checks use controlled reporting windows."
                />
              ) : (
                <div className="space-y-5 rounded-[12px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
                  <div>
                    <p className="eyebrow">Reporting period directory</p>
                    <h4 className="text-lg font-semibold text-slate-950">Configured reporting windows</h4>
                  </div>
                  <div className="table-shell">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Code</th>
                          <th>Label</th>
                          <th>Window</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reportingPeriodsPagination.pageItems.map((period: any) => (
                          <tr key={period.id}>
                            <td>
                              <div className="table-primary">{period.code}</div>
                            </td>
                            <td>{period.label}</td>
                            <td>{formatDate(period.start_date)} to {formatDate(period.end_date)}</td>
                            <td>
                              <StatusBadge label={period.is_active ? "active" : "inactive"} tone={period.is_active ? "success" : "warning"} />
                            </td>
                            <td>
                              <div className="table-actions">
                                <TableActionButton
                                  label="Edit reporting period"
                                  tone="edit"
                                  onClick={() => {
                                    setSelectedReportingPeriodId(period.id);
                                    setReportingPeriodForm({
                                      code: period.code || "",
                                      label: period.label || "",
                                      start_date: period.start_date || "",
                                      end_date: period.end_date || "",
                                      sort_order: String(period.sort_order || 0),
                                      is_active: period.is_active ?? true
                                    });
                                  }}
                                />
                                <TableActionButton
                                  label="Delete reporting period"
                                  tone="delete"
                                  onClick={async () => {
                                    await reportingPeriodsApi.delete(period.id);
                                    await client.invalidateQueries({ queryKey: ["reporting-periods"] });
                                    if (selectedReportingPeriodId === period.id) {
                                      resetReportingPeriodForm();
                                    }
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
                    pagination={reportingPeriodsPagination}
                    itemLabel="reporting periods"
                    onExport={() => exportRowsAsCsv("reporting-periods", (reportingPeriods || []).map((period: any) => ({
                      code: period.code,
                      label: period.label || "",
                      start_date: formatDate(period.start_date),
                      end_date: formatDate(period.end_date),
                      sort_order: period.sort_order || 0,
                      status: period.is_active ? "active" : "inactive"
                    })))}
                  />
                </div>
              )}
            </div>
          </div>
        ) : null}

        {activeSection === "mandatory_programs" ? (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="eyebrow">Mandatory programs</p>
                <h3 className="text-xl font-semibold text-slate-950">Update event configuration</h3>
                <p className="mt-1 text-sm text-slate-500">These event options appear in the university and campus update composer.</p>
              </div>
              {selectedMandatoryId ? (
                <button className="secondary-button" type="button" onClick={resetMandatoryForm}>
                  Clear
                </button>
              ) : null}
            </div>

            <div className="grid items-start gap-6 xl:grid-cols-[0.88fr_1.12fr]">
              <div className="space-y-5 rounded-[12px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
                <div>
                  <p className="eyebrow">Mandatory program editor</p>
                  <h4 className="text-lg font-semibold text-slate-950">{selectedMandatoryId ? "Update event option" : "Add event option"}</h4>
                </div>
                <form
                  className="grid gap-4"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    const payload = {
                      name: mandatoryForm.name,
                      program_type: "event",
                      sort_order: Number(mandatoryForm.sort_order || 0),
                      is_active: mandatoryForm.is_active,
                      allow_other_detail: mandatoryForm.allow_other_detail
                    };
                    if (selectedMandatoryId) {
                      await mandatoryProgramsApi.update(selectedMandatoryId, payload);
                    } else {
                      await mandatoryProgramsApi.create(payload);
                    }
                    await client.invalidateQueries({ queryKey: ["mandatory-programs"] });
                    resetMandatoryForm();
                  }}
                >
                  <label className="field-shell">
                    <span className="field-label">Event name</span>
                    <input className="field-input" value={mandatoryForm.name} onChange={(event) => setMandatoryForm({ ...mandatoryForm, name: event.target.value })} placeholder="Health expo" />
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Display order</span>
                    <input className="field-input" inputMode="numeric" value={mandatoryForm.sort_order} onChange={(event) => setMandatoryForm({ ...mandatoryForm, sort_order: event.target.value })} />
                  </label>
                  <label className="field-shell field-checkbox">
                    <span className="field-label">Active option</span>
                    <input type="checkbox" checked={mandatoryForm.is_active} onChange={(event) => setMandatoryForm({ ...mandatoryForm, is_active: event.target.checked })} />
                  </label>
                  <label className="field-shell field-checkbox">
                    <span className="field-label">Requires specify text</span>
                    <input type="checkbox" checked={mandatoryForm.allow_other_detail} onChange={(event) => setMandatoryForm({ ...mandatoryForm, allow_other_detail: event.target.checked })} />
                  </label>
                  <button className="primary-button" type="submit">
                    {selectedMandatoryId ? "Save event option" : "Add event option"}
                  </button>
                </form>
              </div>

              {!mandatoryPrograms?.length ? (
                <EmptyState
                  title="No mandatory events configured"
                  description="Create the event list here so universities and campuses can submit updates against controlled event types."
                />
              ) : (
                <div className="space-y-5 rounded-[12px] border border-slate-200/80 bg-white/85 p-5 shadow-[0_18px_45px_rgba(15,23,42,0.06)]">
                  <div>
                    <p className="eyebrow">Mandatory program directory</p>
                    <h4 className="text-lg font-semibold text-slate-950">Configured event options</h4>
                  </div>
                  <div className="table-shell">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Event</th>
                          <th>Order</th>
                          <th>Status</th>
                          <th>Specify</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mandatoryProgramsPagination.pageItems.map((item: any) => (
                          <tr key={item.id}>
                            <td>
                              <div className="table-primary">{item.name}</div>
                              <div className="table-secondary">Type: {item.program_type}</div>
                            </td>
                            <td>{formatNumber(item.sort_order)}</td>
                            <td>
                              <StatusBadge label={item.is_active ? "active" : "inactive"} tone={item.is_active ? "success" : "warning"} />
                            </td>
                            <td>
                              <StatusBadge label={item.allow_other_detail ? "specify enabled" : "fixed option"} tone={item.allow_other_detail ? "info" : "neutral"} />
                            </td>
                            <td>
                              <div className="table-actions">
                                <TableActionButton
                                  label="Edit mandatory program"
                                  tone="edit"
                                  onClick={() => {
                                    setSelectedMandatoryId(item.id);
                                    setMandatoryForm({
                                      name: item.name || "",
                                      sort_order: String(item.sort_order || 0),
                                      is_active: item.is_active ?? true,
                                      allow_other_detail: item.allow_other_detail ?? false
                                    });
                                  }}
                                />
                                <TableActionButton
                                  label="Delete mandatory program"
                                  tone="delete"
                                  onClick={async () => {
                                    await mandatoryProgramsApi.delete(item.id);
                                    await client.invalidateQueries({ queryKey: ["mandatory-programs"] });
                                    if (selectedMandatoryId === item.id) {
                                      resetMandatoryForm();
                                    }
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
                    pagination={mandatoryProgramsPagination}
                    itemLabel="events"
                    onExport={() => exportRowsAsCsv("mandatory-programs", (mandatoryPrograms || []).map((item: any) => ({
                      event: item.name,
                      program_type: item.program_type || "",
                      display_order: item.sort_order || 0,
                      status: item.is_active ? "active" : "inactive",
                      specify_text: item.allow_other_detail ? "enabled" : "fixed option"
                    })))}
                  />
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Panel>

      <ModalDialog open={isTransitionDialogOpen} onClose={transitionState === "running" ? () => {} : resetTransitionDialog}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Transition job</p>
              <h3 className="text-xl font-semibold text-slate-950">Run the alumni transition</h3>
            </div>
            {transitionState !== "running" ? (
              <button className="secondary-button" type="button" onClick={resetTransitionDialog}>Close</button>
            ) : null}
          </div>

          {transitionState === "confirm" ? (
            <>
              <p className="text-sm leading-6 text-slate-600">
                This action will scan member records and promote anyone whose engagement has reached the alumni stage. Continue only if you want to run the transition now.
              </p>
              <div className="flex flex-wrap gap-3">
                <button className="primary-button" type="button" onClick={runTransitionJob}>
                  Confirm and run
                </button>
                <button className="secondary-button" type="button" onClick={resetTransitionDialog}>
                  Cancel
                </button>
              </div>
            </>
          ) : null}

          {transitionState === "running" ? (
            <div className="space-y-4">
              <p className="text-sm leading-6 text-slate-600">
                Running alumni transitions across the current network records. Please wait while the system processes eligible members.
              </p>
              <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/90 px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-medium text-slate-700">Transition progress</span>
                  <span className="text-sm text-slate-500">{Math.round(transitionProgress)}%</span>
                </div>
                <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${transitionProgress}%`,
                      background: "linear-gradient(135deg, var(--pcm-blue-deep), var(--pcm-violet), var(--pcm-magenta))"
                    }}
                  />
                </div>
              </div>
            </div>
          ) : null}

          {transitionState === "complete" ? (
            <div className="space-y-4">
              <div className="rounded-[12px] border border-emerald-200 bg-emerald-50/80 px-4 py-4">
                <p className="text-sm font-medium text-emerald-900">Transition complete</p>
                <p className="mt-2 text-sm text-emerald-800">
                  {formatNumber(transitionUpdatedCount)} member records were moved into alumni status.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => {
                    resetTransitionDialog();
                    setIsAuditLogDialogOpen(true);
                  }}
                >
                  View system activity log
                </button>
                <button className="secondary-button" type="button" onClick={resetTransitionDialog}>
                  Close
                </button>
              </div>
            </div>
          ) : null}

          {transitionState === "error" ? (
            <div className="space-y-4">
              <div className="rounded-[12px] border border-rose-200 bg-rose-50/80 px-4 py-4">
                <p className="text-sm font-medium text-rose-900">Transition failed</p>
                <p className="mt-2 text-sm text-rose-800">{transitionError}</p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button className="primary-button" type="button" onClick={runTransitionJob}>
                  Try again
                </button>
                <button className="secondary-button" type="button" onClick={resetTransitionDialog}>
                  Close
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </ModalDialog>

      <ModalDialog open={isAuditLogDialogOpen} onClose={() => setIsAuditLogDialogOpen(false)} className="modal-shell-page">
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">System activity log</p>
              <h3 className="text-xl font-semibold text-slate-950">Recent system activity</h3>
            </div>
            <button className="secondary-button" type="button" onClick={() => setIsAuditLogDialogOpen(false)}>
              Close
            </button>
          </div>

          {!logs?.length ? (
            <EmptyState
              title="No audit entries yet"
              description="As soon as administrators make changes, the system activity log will appear here."
            />
          ) : (
            <>
              <div className="table-shell">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Action</th>
                      <th>Entity</th>
                      <th>Actor</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogsPagination.pageItems.map((log: any) => (
                      <tr key={log.id}>
                        <td>{formatDate(log.created_at)}</td>
                        <td>
                          <div className="table-primary">{log.action}</div>
                        </td>
                        <td>
                          <div className="table-primary">{log.entity}</div>
                          <div className="table-secondary">{log.entity_id || "No entity id"}</div>
                        </td>
                        <td>#{log.actor_user_id || "system"}</td>
                        <td>
                          <div className="table-secondary">
                            {log.meta && Object.keys(log.meta).length > 0 ? JSON.stringify(log.meta) : "No additional metadata"}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <TablePagination
                pagination={auditLogsPagination}
                itemLabel="audit entries"
                onExport={() => exportRowsAsCsv("admin-audit-log", (logs || []).map((log: any) => ({
                  when: formatDate(log.created_at),
                  action: log.action,
                  entity: log.entity,
                  entity_id: log.entity_id || "",
                  actor: log.actor_user_id || "system",
                  details: log.meta && Object.keys(log.meta).length > 0 ? JSON.stringify(log.meta) : "No additional metadata"
                })))}
              />
            </>
          )}
        </div>
      </ModalDialog>
    </div>
  );
}
