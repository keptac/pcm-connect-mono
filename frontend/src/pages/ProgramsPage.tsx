import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { mandatoryProgramsApi, programUpdatesApi, programsApi, reportingPeriodsApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const NETWORK_SCOPE = "network";
const NETWORK_LABEL = "All universities and campuses";
const audienceOptions = ["Students", "Alumni", "Students and Alumni"];

function normalizeProgramName(value?: string | null) {
  return String(value || "").trim().toLowerCase();
}

function toReportingPeriod(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  return `${parsed.getFullYear()}-Q${Math.floor(parsed.getMonth() / 3) + 1}`;
}

function currentReportingPeriod() {
  const now = new Date();
  return `${now.getFullYear()}-Q${Math.floor(now.getMonth() / 3) + 1}`;
}

function parseIsoDate(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function calculateProgramDurationWeeks(startDateValue?: string | null, endDateValue?: string | null) {
  const startDate = parseIsoDate(startDateValue);
  const endDate = parseIsoDate(endDateValue);
  if (!startDate || !endDate || endDate < startDate) return null;
  const millisecondsPerDay = 1000 * 60 * 60 * 24;
  const durationDays = Math.floor((endDate.getTime() - startDate.getTime()) / millisecondsPerDay) + 1;
  return Number((durationDays / 7).toFixed(1));
}

function formatProgramDurationWeeks(value?: number | string | null) {
  if (value === null || value === undefined || value === "") return "";
  const numericValue = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numericValue)) return "";
  return Number.isInteger(numericValue) ? String(numericValue) : numericValue.toFixed(1).replace(/\.0$/, "");
}

function programFallsInPeriod(program: any, period: any, fallbackCode?: string) {
  if (!period) {
    return toReportingPeriod(program.start_date || program.end_date) === fallbackCode;
  }

  const periodStart = parseIsoDate(period.start_date);
  const periodEnd = parseIsoDate(period.end_date);
  const programStart = parseIsoDate(program.start_date || program.end_date);
  const programEnd = parseIsoDate(program.end_date || program.start_date);
  if (!periodStart || !periodEnd || !programStart || !programEnd) return false;
  return programStart <= periodEnd && programEnd >= periodStart;
}

function buildInitialForm(defaultUniversityId?: number | null, defaultAudience = "Students") {
  return {
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    name: "",
    category: "",
    status: "active",
    description: "",
    audience: defaultAudience,
    manager_name: "",
    target_beneficiaries: "",
    annual_budget: "",
    duration_weeks: "",
    level: "Campus",
    start_date: "",
    end_date: ""
  };
}

function findCurrentReportingPeriodCode(periods: any[] | undefined) {
  const today = new Date();
  return periods?.find((period: any) => {
    const start = parseIsoDate(period.start_date);
    const end = parseIsoDate(period.end_date);
    return period.is_active && start && end && start <= today && today <= end;
  })?.code || periods?.find((period: any) => period.is_active)?.code || periods?.[0]?.code || currentReportingPeriod();
}

function isProgramAwaitingReport(program: any, updateCount: number) {
  if (updateCount > 0) return false;
  const completionDate = parseIsoDate(program.end_date || program.start_date);
  if (!completionDate) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return completionDate < today;
}

function isProgramDeleteLocked(program: any, updateCount: number) {
  if (updateCount === 0) return false;
  const completionDate = parseIsoDate(program.end_date || program.start_date);
  if (!completionDate) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return completionDate < today;
}

export default function ProgramsPage() {
  const client = useQueryClient();
  const { user, roles, canSelectUniversity, scopedUniversityId, defaultUniversityId } = useUniversityScope();
  const canManage = roles.some((role) => ["super_admin", "student_admin", "secretary", "program_manager", "committee_member", "executive", "director", "alumni_admin"].includes(role));
  const isAlumniAdmin = roles.includes("alumni_admin");
  const defaultProgramAudience = isAlumniAdmin ? "Alumni" : "Students";
  const hasGlobalAccess = Boolean(user) && !user.university_id;
  const canSelectProgramScope = canSelectUniversity || hasGlobalAccess;

  const { data: programs } = useQuery({
    queryKey: ["programs", scopedUniversityId],
    queryFn: () => programsApi.list(scopedUniversityId),
    enabled: canManage
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canManage
  });
  const { data: mandatoryPrograms } = useQuery({
    queryKey: ["mandatory-programs", "event"],
    queryFn: () => mandatoryProgramsApi.list({ programType: "event" }),
    enabled: canManage && hasGlobalAccess
  });
  const { data: reportingPeriods } = useQuery({
    queryKey: ["reporting-periods", true],
    queryFn: () => reportingPeriodsApi.list(true),
    enabled: canManage && hasGlobalAccess
  });
  const { data: updates } = useQuery({
    queryKey: ["program-updates", scopedUniversityId],
    queryFn: () => programUpdatesApi.list({ universityId: scopedUniversityId }),
    enabled: canManage
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId, defaultProgramAudience));
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeView, setActiveView] = useState<"portfolio" | "coverage">("portfolio");
  const [coveragePeriod, setCoveragePeriod] = useState(currentReportingPeriod);

  const filteredPrograms = useMemo(() => {
    return (programs || []).filter((program: any) => statusFilter === "all" || program.status === statusFilter);
  }, [programs, statusFilter]);
  const programPagination = usePagination(filteredPrograms);
  const mandatoryEventCatalog = useMemo(() => {
    const unique = new Map<string, any>();
    for (const item of mandatoryPrograms || []) {
      if (item.program_type !== "event" || item.allow_other_detail) continue;
      const key = normalizeProgramName(item.name);
      if (!key || unique.has(key)) continue;
      unique.set(key, item);
    }
    return Array.from(unique.entries())
      .map(([key, item]) => ({ key, name: item.name }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [mandatoryPrograms]);
  const defaultCoveragePeriod = useMemo(() => {
    return findCurrentReportingPeriodCode(reportingPeriods);
  }, [reportingPeriods]);
  const coveragePeriodOptions = useMemo(() => {
    const values = new Map<string, { code: string; label: string }>();
    for (const period of reportingPeriods || []) {
      values.set(period.code, { code: period.code, label: period.label || period.code });
    }
    if (!values.size) {
      values.set(currentReportingPeriod(), { code: currentReportingPeriod(), label: currentReportingPeriod() });
    }
    for (const program of programs || []) {
      const period = toReportingPeriod(program.start_date || program.end_date);
      if (period && !values.has(period)) {
        values.set(period, { code: period, label: period });
      }
    }
    return Array.from(values.values());
  }, [programs, reportingPeriods]);
  const selectedCoveragePeriod = useMemo(
    () => coveragePeriodOptions.find((period) => period.code === coveragePeriod) || null,
    [coveragePeriod, coveragePeriodOptions]
  );

  useEffect(() => {
    if (!coveragePeriodOptions.length) return;
    if (coveragePeriodOptions.some((period) => period.code === coveragePeriod)) return;
    setCoveragePeriod(defaultCoveragePeriod);
  }, [coveragePeriod, coveragePeriodOptions, defaultCoveragePeriod]);

  const coverageRows = useMemo(() => {
    if (!hasGlobalAccess || mandatoryEventCatalog.length === 0) return [];

    const visibleUniversities = (universities || []).filter((university: any) => !scopedUniversityId || university.id === scopedUniversityId);
    const programsInPeriod = (programs || []).filter((program: any) => {
      return program.status !== "archived" && programFallsInPeriod(program, selectedCoveragePeriod, coveragePeriod);
    });
    const mandatoryEventKeys = new Set(mandatoryEventCatalog.map((item) => item.key));
    const networkScheduled = new Set(
      programsInPeriod
        .filter((program: any) => !program.university_id)
        .map((program: any) => normalizeProgramName(program.name))
        .filter((name: string) => mandatoryEventKeys.has(name))
    );

    return visibleUniversities
      .map((university: any) => {
        const campusPrograms = programsInPeriod.filter((program: any) => program.university_id === university.id);
        const scheduledNames = new Set<string>([
          ...Array.from(networkScheduled),
          ...campusPrograms.map((program: any) => normalizeProgramName(program.name)).filter((name: string) => mandatoryEventKeys.has(name))
        ]);
        const matchingScheduledPrograms = programsInPeriod.filter((program: any) => {
          const normalizedName = normalizeProgramName(program.name);
          if (!mandatoryEventKeys.has(normalizedName)) return false;
          return !program.university_id || program.university_id === university.id;
        });
        const scheduledMandatory = mandatoryEventCatalog.filter((item) => scheduledNames.has(item.key)).map((item) => item.name);
        const missingMandatory = mandatoryEventCatalog.filter((item) => !scheduledNames.has(item.key)).map((item) => item.name);
        const latestScheduledDate = matchingScheduledPrograms
          .map((program: any) => program.start_date || program.end_date)
          .filter(Boolean)
          .sort((left: string, right: string) => right.localeCompare(left))[0] || null;

        return {
          ...university,
          scheduledMandatory,
          missingMandatory,
          scheduledCount: scheduledMandatory.length,
          missingCount: missingMandatory.length,
          latestScheduledDate
        };
      })
      .sort((left: any, right: any) => (
        right.missingCount - left.missingCount ||
        left.scheduledCount - right.scheduledCount ||
        String(left.name || "").localeCompare(String(right.name || ""))
      ));
  }, [coveragePeriod, hasGlobalAccess, mandatoryEventCatalog, programs, scopedUniversityId, selectedCoveragePeriod, universities]);
  const incompleteCoverageRows = useMemo(
    () => coverageRows.filter((row: any) => row.missingCount > 0),
    [coverageRows]
  );
  const coveragePagination = usePagination(incompleteCoverageRows);

  if (!canManage) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  function resetForm() {
    setSelectedId(null);
    setForm(buildInitialForm(defaultUniversityId, defaultProgramAudience));
  }

  function closeForm() {
    setIsFormOpen(false);
    resetForm();
  }

  function openCreateForm() {
    resetForm();
    setIsFormOpen(true);
  }

  function hydrateForm(program: any) {
    const calculatedDuration = calculateProgramDurationWeeks(program.start_date, program.end_date);
    setSelectedId(program.id);
    setForm({
      university_id: program.university_id ? String(program.university_id) : NETWORK_SCOPE,
      name: program.name || "",
      category: program.category || "",
      status: program.status || "active",
      description: program.description || "",
      audience: program.audience || "Students",
      manager_name: program.manager_name || "",
      target_beneficiaries: program.target_beneficiaries ? String(program.target_beneficiaries) : "",
      annual_budget: program.annual_budget ? String(program.annual_budget) : "",
      duration_weeks: calculatedDuration !== null ? formatProgramDurationWeeks(calculatedDuration) : formatProgramDurationWeeks(program.duration_weeks),
      level: program.level === "Chapter" ? "Campus" : (program.level || "Campus"),
      start_date: program.start_date || "",
      end_date: program.end_date || ""
    });
    setIsFormOpen(true);
  }

  function canManageProgram(program: any) {
    if (!program.university_id) return hasGlobalAccess;
    if (isAlumniAdmin) {
      return ["Alumni", "Students and Alumni"].includes(program.audience || "Students");
    }
    return true;
  }

  function handleProgramDateChange(field: "start_date" | "end_date", value: string) {
    setForm((current) => {
      const nextForm = { ...current, [field]: value };
      const calculatedDuration = calculateProgramDurationWeeks(nextForm.start_date, nextForm.end_date);
      return {
        ...nextForm,
        duration_weeks: calculatedDuration === null ? "" : formatProgramDurationWeeks(calculatedDuration)
      };
    });
  }

  const activePrograms = programs?.filter((program: any) => program.status === "active").length || 0;
  const plannedBudget = (programs || []).reduce((total: number, program: any) => total + Number(program.annual_budget || 0), 0);
  const totalServed = (programs || []).reduce((total: number, program: any) => total + Number(program.beneficiaries_served || 0), 0);
  const campusesWithFullCoverage = coverageRows.filter((row: any) => row.missingCount === 0).length;
  const selectedScopeLabel =
    form.university_id === NETWORK_SCOPE
      ? NETWORK_LABEL
      : (universities?.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus");

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Ministry portfolio"
        title="Ministry programs"
        description="Each university, campus, or regional unit can own, update, and report student and alumni ministry programs separately from academic programs of study."
        actions={(
          <button className="primary-button" type="button" onClick={openCreateForm}>
            Create a program
          </button>
        )}
      />

      {hasGlobalAccess ? (
        <div className="flex flex-wrap items-center gap-3">
          <button
            className={activeView === "portfolio" ? "primary-button" : "secondary-button"}
            type="button"
            onClick={() => setActiveView("portfolio")}
          >
            Portfolio
          </button>
          <button
            className={activeView === "coverage" ? "primary-button" : "secondary-button"}
            type="button"
            onClick={() => setActiveView("coverage")}
          >
            Mandatory coverage
          </button>
        </div>
      ) : null}

      {hasGlobalAccess && activeView === "coverage" ? (
        <>
          <div className="grid gap-4 lg:grid-cols-4">
            <MetricCard label="Campuses in view" value={formatNumber(coverageRows.length)} helper="Universities and campuses checked for the selected period" />
            <MetricCard label="Missing coverage" value={formatNumber(incompleteCoverageRows.length)} tone="coral" helper={`${selectedCoveragePeriod?.label || coveragePeriod} still has missing mandatory schedules`} />
            <MetricCard label="Fully covered" value={formatNumber(campusesWithFullCoverage)} tone="gold" helper="Campuses that scheduled every mandatory event" />
            <MetricCard label="Mandatory events" value={formatNumber(mandatoryEventCatalog.length)} tone="ink" helper="Active mandatory programs configured by super admin" />
          </div>

          <Panel className="space-y-5">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Mandatory coverage</p>
                <h3 className="text-xl font-semibold text-slate-950">Campuses missing scheduled mandatory programs</h3>
                <p className="mt-2 text-sm text-slate-600">This view compares dated ministry programs against the mandatory event list for the selected reporting period.</p>
              </div>
              <label className="field-shell min-w-[180px]">
                <span className="field-label">Reporting period</span>
                <select className="field-input" value={coveragePeriod} onChange={(event) => setCoveragePeriod(event.target.value)}>
                  {coveragePeriodOptions.map((period) => (
                    <option key={period.code} value={period.code}>{period.label}</option>
                  ))}
                </select>
              </label>
            </div>

            {mandatoryEventCatalog.length === 0 ? (
              <EmptyState
                title="No mandatory programs configured"
                description="Create mandatory event programs in Admin first, then this compliance view will show campus scheduling gaps."
              />
            ) : incompleteCoverageRows.length === 0 ? (
              <EmptyState
                title="All campuses are covered"
                description={`Every university or campus in this view has dated ministry programs for all mandatory events in ${selectedCoveragePeriod?.label || coveragePeriod}.`}
              />
            ) : (
              <>
                <div className="table-shell">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>University / Campus</th>
                        <th>Conference / Union</th>
                        <th>Scheduled</th>
                        <th>Missing</th>
                        <th>Coverage</th>
                        <th>Latest scheduled date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {coveragePagination.pageItems.map((campus: any) => (
                        <tr key={campus.id}>
                          <td>
                            <div className="table-primary">{campus.name}</div>
                            <div className="table-secondary">{campus.short_code || "No short code"} / {campus.region || "Region not set"}</div>
                          </td>
                          <td>
                            <div className="table-primary">{campus.conference_name || "Conference not set"}</div>
                            <div className="table-secondary">{campus.union_name || "Union not set"}</div>
                          </td>
                          <td>
                            <div className="table-primary">{campus.scheduledCount} of {mandatoryEventCatalog.length} scheduled</div>
                            <div className="table-secondary">{campus.scheduledMandatory.join(", ") || "No mandatory events scheduled yet"}</div>
                          </td>
                          <td>
                            <div className="table-primary">{campus.missingCount} remaining</div>
                            <div className="table-secondary">{campus.missingMandatory.join(", ")}</div>
                          </td>
                          <td>
                            <StatusBadge
                              label={`${campus.scheduledCount}/${mandatoryEventCatalog.length}`}
                              tone={campus.missingCount === 0 ? "success" : "warning"}
                            />
                          </td>
                          <td>{formatDate(campus.latestScheduledDate)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <TablePagination
                  pagination={coveragePagination}
                  itemLabel="campuses"
                  onExport={() => exportRowsAsCsv("mandatory-program-coverage", incompleteCoverageRows.map((campus: any) => ({
                    reporting_period: selectedCoveragePeriod?.label || coveragePeriod,
                    university_or_campus: campus.name,
                    short_code: campus.short_code || "",
                    conference: campus.conference_name || "",
                    union: campus.union_name || "",
                    scheduled_count: `${campus.scheduledCount}/${mandatoryEventCatalog.length}`,
                    scheduled_events: campus.scheduledMandatory.join("; "),
                    missing_count: campus.missingCount,
                    missing_events: campus.missingMandatory.join("; "),
                    latest_scheduled_date: formatDate(campus.latestScheduledDate)
                  })))}
                />
              </>
            )}
          </Panel>
        </>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <MetricCard label="Ministry programs" value={formatNumber(programs?.length)} helper={`${formatNumber(activePrograms)} marked active`} />
            <MetricCard label="People served" value={formatNumber(totalServed)} tone="gold" helper="Based on current program records" />
            <MetricCard label="Planned budget" value={formatCurrency(plannedBudget)} tone="ink" helper="Annual budgets across visible ministry programs" />
          </div>

          <Panel className="space-y-5">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Ministry program feed</p>
                <h3 className="text-xl font-semibold text-slate-950">Portfolio by status</h3>
              </div>
              <label className="field-shell min-w-[180px]">
                <span className="field-label">Status filter</span>
                <select className="field-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="all">All ministry programs</option>
                  <option value="active">Active</option>
                  <option value="planning">Planning</option>
                  <option value="paused">Paused</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
            </div>

            {filteredPrograms.length === 0 ? (
              <EmptyState
                title="No ministry programs yet"
                description="Create a ministry program to start tracking beneficiaries, budgets, and updates."
              />
            ) : (
              <>
                <div className="table-shell">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Ministry Program</th>
                        <th>University / Campus</th>
                        <th>Audience</th>
                        <th>Status</th>
                        <th>Reach</th>
                        <th>Budget</th>
                        <th>Updates</th>
                        <th>Latest</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {programPagination.pageItems.map((program: any) => {
                        const relatedUpdates = (updates || []).filter((update: any) => update.program_id === program.id);
                        const reportOverdue = isProgramAwaitingReport(program, relatedUpdates.length);
                        const deleteLocked = isProgramDeleteLocked(program, relatedUpdates.length);
                        return (
                          <tr key={program.id}>
                            <td>
                              <div className="table-primary">{program.name}</div>
                              <div className="table-secondary">{program.category || "General"} / {program.manager_name || "Unassigned"}</div>
                              <div className="table-secondary">{program.description || "No description yet."}</div>
                            </td>
                            <td>
                              <div className="table-primary">{program.university_name || NETWORK_LABEL}</div>
                              <div className="table-secondary">
                                {!program.university_id ? "Network-wide ministry program" : `${program.level === "Chapter" ? "Campus" : (program.level || "Campus")} level`}
                              </div>
                            </td>
                            <td>
                              <StatusBadge
                                label={program.audience || "Students"}
                                tone={program.audience === "Alumni" ? "info" : program.audience === "Students and Alumni" ? "success" : "neutral"}
                              />
                            </td>
                            <td>
                              <StatusBadge
                                label={program.status || "active"}
                                tone={program.status === "active" ? "success" : program.status === "paused" ? "warning" : "neutral"}
                              />
                            </td>
                            <td>
                              <div className="table-primary">{formatNumber(program.beneficiaries_served)} served</div>
                              <div className="table-secondary">Target {formatNumber(program.target_beneficiaries)}</div>
                            </td>
                            <td>{formatCurrency(program.annual_budget)}</td>
                            <td>
                              <div className={`table-primary ${reportOverdue ? "text-rose-700" : ""}`}>{formatNumber(relatedUpdates.length)}</div>
                              <div className={`table-secondary ${reportOverdue ? "text-rose-600" : ""}`}>
                                {reportOverdue ? "Report overdue" : relatedUpdates.length > 0 ? "Submitted" : "Awaiting report"}
                              </div>
                            </td>
                            <td>{formatDate(program.last_update_at)}</td>
                            <td>
                              <div className="table-actions">
                                {canManageProgram(program) ? (
                                  <>
                                    <TableActionButton label="Edit program" tone="edit" onClick={() => hydrateForm(program)} />
                                    {deleteLocked ? (
                                      <StatusBadge label="Locked after report" tone="warning" />
                                    ) : (
                                      <TableActionButton
                                        label="Delete program"
                                        tone="delete"
                                        onClick={async () => {
                                          await programsApi.delete(program.id);
                                          await client.invalidateQueries({ queryKey: ["programs"] });
                                          await client.invalidateQueries({ queryKey: ["analytics-programs"] });
                                        }}
                                      />
                                    )}
                                  </>
                                ) : (
                                  <StatusBadge label="View only" tone="neutral" />
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
                  pagination={programPagination}
                  itemLabel="programs"
                  onExport={() => exportRowsAsCsv("ministry-programs", filteredPrograms.map((program: any) => {
                    const relatedUpdates = (updates || []).filter((update: any) => update.program_id === program.id);
                    return {
                      ministry_program: program.name,
                      university_or_campus: program.university_name || NETWORK_LABEL,
                      level: !program.university_id ? "Network-wide ministry program" : `${program.level === "Chapter" ? "Campus" : (program.level || "Campus")} level`,
                      category: program.category || "General",
                      manager: program.manager_name || "Unassigned",
                      audience: program.audience || "Students",
                      status: program.status || "active",
                      people_served: program.beneficiaries_served || 0,
                      target_beneficiaries: program.target_beneficiaries || 0,
                      annual_budget: program.annual_budget || 0,
                      duration_weeks: program.duration_weeks || "",
                      update_count: relatedUpdates.length,
                      report_status: isProgramAwaitingReport(program, relatedUpdates.length) ? "Report overdue" : relatedUpdates.length > 0 ? "Submitted" : "Awaiting report",
                      latest_update: formatDate(program.last_update_at)
                    };
                  }))}
                />
              </>
            )}
          </Panel>
        </>
      )}

      <ModalDialog open={isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Ministry program editor</p>
              <h3 className="text-xl font-semibold text-slate-950">{selectedId ? "Update a ministry program" : "Create a program"}</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              const calculatedDurationWeeks = calculateProgramDurationWeeks(form.start_date, form.end_date);
              const payload = {
                ...form,
                university_id: form.university_id === NETWORK_SCOPE ? null : Number(form.university_id),
                target_beneficiaries: form.target_beneficiaries ? Number(form.target_beneficiaries) : null,
                annual_budget: form.annual_budget ? Number(form.annual_budget) : null,
                duration_weeks: calculatedDurationWeeks ?? (form.duration_weeks ? Number(form.duration_weeks) : null),
                start_date: form.start_date || null,
                end_date: form.end_date || null
              };

              if (selectedId) {
                await programsApi.update(selectedId, payload);
              } else {
                await programsApi.create(payload);
              }
              await client.invalidateQueries({ queryKey: ["programs"] });
              await client.invalidateQueries({ queryKey: ["analytics-programs"] });
              closeForm();
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              {canSelectProgramScope ? (
                <label className="field-shell">
                  <span className="field-label">Program scope</span>
                  <select
                    className="field-input"
                    required
                    value={form.university_id}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setForm((current) => ({
                        ...current,
                        university_id: nextValue,
                        level: nextValue === NETWORK_SCOPE ? "Network" : (current.level === "Network" ? "Campus" : current.level)
                      }));
                    }}
                  >
                    <option value="">Select university or campus</option>
                    {hasGlobalAccess ? <option value={NETWORK_SCOPE}>{NETWORK_LABEL}</option> : null}
                    {universities?.map((university: any) => (
                      <option key={university.id} value={university.id}>{university.name}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="field-shell">
                  <span className="field-label">University / campus</span>
                  <div className="field-input flex items-center text-slate-600">{selectedScopeLabel}</div>
                </div>
              )}
              <label className="field-shell">
                <span className="field-label">Ministry program name</span>
                <input className="field-input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Category</span>
                <input className="field-input" value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} placeholder="Leadership, Outreach..." />
              </label>
              <label className="field-shell">
                <span className="field-label">Audience</span>
                <select
                  className="field-input"
                  value={form.audience}
                  onChange={(event) => setForm({ ...form, audience: event.target.value })}
                >
                  {(isAlumniAdmin ? audienceOptions.filter((option) => option !== "Students") : audienceOptions).map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">Status</span>
                <select className="field-input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                  <option value="active">Active</option>
                  <option value="planning">Planning</option>
                  <option value="paused">Paused</option>
                  <option value="archived">Archived</option>
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">Manager</span>
                <input className="field-input" value={form.manager_name} onChange={(event) => setForm({ ...form, manager_name: event.target.value })} />
              </label>
            </div>

            <label className="field-shell">
              <span className="field-label">Ministry program description</span>
              <textarea className="field-input min-h-[120px]" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Target beneficiaries</span>
                <input className="field-input" value={form.target_beneficiaries} onChange={(event) => setForm({ ...form, target_beneficiaries: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Program budget</span>
                <input className="field-input" value={form.annual_budget} onChange={(event) => setForm({ ...form, annual_budget: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Duration (weeks)</span>
                <input
                  className="field-input"
                  placeholder="Calculated from the start and end dates"
                  value={form.duration_weeks}
                  readOnly
                />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Level</span>
                <select className="field-input" value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value })}>
                  <option value="Network">Network</option>
                  <option value="Campus">Campus</option>
                  <option value="University">University</option>
                  <option value="Regional">Regional</option>
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">Start date</span>
                <input
                  className="field-input"
                  type="date"
                  max={form.end_date || undefined}
                  value={form.start_date}
                  onChange={(event) => handleProgramDateChange("start_date", event.target.value)}
                />
              </label>
              <label className="field-shell">
                <span className="field-label">End date</span>
                <input
                  className="field-input"
                  type="date"
                  min={form.start_date || undefined}
                  value={form.end_date}
                  onChange={(event) => handleProgramDateChange("end_date", event.target.value)}
                />
              </label>
            </div>

            <div className="flex flex-wrap gap-3">
              <button className="primary-button" type="submit">{selectedId ? "Save ministry program" : "Create ministry program"}</button>
              <button className="secondary-button" type="button" onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </div>
  );
}
