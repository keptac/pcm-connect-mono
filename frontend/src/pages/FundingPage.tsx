import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fundingApi, programsApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const inflowCategories = ["Donation", "Zunde", "Offering", "Subscriptions", "Other"];
const outflowCategories = ["Programme Delivery", "Transport", "Administration", "Welfare", "Events", "Other"];
const HQ_SCOPE = "hq";
const financeViewOptions = [
  { value: "all", label: "All Finance" },
  { value: "hq", label: "PCM HQ" },
  { value: "alumni", label: "Alumni" },
  { value: "students", label: "Students" }
];

function buildInitialForm(defaultUniversityId?: number | null, canUseHq = false) {
  return {
    university_id: defaultUniversityId ? String(defaultUniversityId) : (canUseHq ? HQ_SCOPE : ""),
    program_id: "",
    source_name: "",
    flow_direction: "inflow",
    receipt_category: "Donation",
    category_detail: "",
    reporting_window: "monthly",
    amount: "",
    currency: "USD",
    transaction_date: "",
    channel: "",
    designation: "",
    notes: ""
  };
}

function normalizeDirection(entry: any) {
  return entry.flow_direction || (entry.entry_type === "expense" ? "outflow" : "inflow");
}

function normalizeCategory(entry: any) {
  if (entry.receipt_category) return entry.receipt_category;
  if (entry.entry_type === "donation") return "Donation";
  if (entry.entry_type === "zunde") return "Zunde";
  if (entry.entry_type === "offering") return "Offering";
  if (entry.entry_type === "subscription" || entry.entry_type === "subscriptions") return "Subscriptions";
  return "Other";
}

function formatMonthLabel(key: string) {
  const [year, month] = key.split("-");
  const date = new Date(Number(year), Number(month) - 1, 1);
  return new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(date);
}

function periodKey(dateValue: string, mode: "monthly" | "weekly") {
  const date = new Date(`${dateValue}T00:00:00`);
  if (mode === "monthly") {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  }
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  return date.toISOString().slice(0, 10);
}

function periodLabel(key: string, mode: "monthly" | "weekly") {
  if (mode === "monthly") return formatMonthLabel(key);
  return `Week of ${formatDate(key)}`;
}

function normalizeProgramAudience(program?: any) {
  return program?.audience || "Students";
}

function matchesAudienceFilter(audience: string, filter: string) {
  if (filter === "all") return true;
  if (filter === "alumni") return audience === "Alumni" || audience === "Students and Alumni";
  if (filter === "students") return audience === "Students" || audience === "Students and Alumni";
  return true;
}

export default function FundingPage() {
  const client = useQueryClient();
  const { roles, canSelectUniversity, scopedUniversityId, defaultUniversityId, isUniversityScoped } = useUniversityScope();
  const canView = roles.some((role) => ["super_admin", "student_admin", "alumni_admin", "finance_officer", "students_finance", "executive", "director"].includes(role));
  const canManageRecords = roles.some((role) => ["super_admin", "finance_officer", "students_finance"].includes(role));
  const canUseHq = roles.includes("super_admin") && !isUniversityScoped;

  const { data: funding } = useQuery({
    queryKey: ["funding", canUseHq ? "all" : scopedUniversityId],
    queryFn: () => fundingApi.list(canUseHq ? null : scopedUniversityId),
    enabled: canView
  });
  const { data: programs } = useQuery({
    queryKey: ["programs", canUseHq ? "all-finance" : scopedUniversityId],
    queryFn: () => programsApi.list(canUseHq ? null : scopedUniversityId),
    enabled: canView
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canView
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId, canUseHq));
  const [financeView, setFinanceView] = useState<"all" | "hq" | "alumni" | "students">("all");
  const [directionFilter, setDirectionFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [periodMode, setPeriodMode] = useState<"monthly" | "weekly">("monthly");

  const selectedUniversityId = form.university_id && form.university_id !== HQ_SCOPE ? Number(form.university_id) : null;
  const isHqScope = form.university_id === HQ_SCOPE;

  const visiblePrograms = useMemo(() => {
    if (!selectedUniversityId) return [];
    return (programs || []).filter((program: any) => program.university_id === selectedUniversityId);
  }, [programs, selectedUniversityId]);

  const universityLookup = useMemo(
    () => Object.fromEntries((universities || []).map((university: any) => [university.id, university.name])),
    [universities]
  );
  const programMetaLookup = useMemo(
    () => Object.fromEntries((programs || []).map((program: any) => [program.id, program])),
    [programs]
  );
  const programLookup = useMemo(
    () => Object.fromEntries((programs || []).map((program: any) => [program.id, program.name])),
    [programs]
  );
  const scopePrograms = useMemo(() => {
    if (!canUseHq) return programs || [];
    if (financeView === "hq") return [];
    if (scopedUniversityId) {
      return (programs || []).filter((program: any) => program.university_id === scopedUniversityId);
    }
    return (programs || []).filter((program: any) => Boolean(program.university_id));
  }, [canUseHq, financeView, programs, scopedUniversityId]);
  const scopeFunding = useMemo(() => {
    if (!canUseHq) return funding || [];
    if (financeView === "hq") {
      return (funding || []).filter((entry: any) => !entry.university_id);
    }
    if (scopedUniversityId) {
      return (funding || []).filter((entry: any) => entry.university_id === scopedUniversityId);
    }
    return (funding || []).filter((entry: any) => Boolean(entry.university_id));
  }, [canUseHq, financeView, funding, scopedUniversityId]);
  const filteredPrograms = useMemo(
    () => scopePrograms.filter((program: any) => financeView === "all" || financeView === "hq" ? true : matchesAudienceFilter(normalizeProgramAudience(program), financeView)),
    [financeView, scopePrograms]
  );

  const filteredFunding = useMemo(() => {
    return scopeFunding.filter((entry: any) => {
      const direction = normalizeDirection(entry);
      const category = normalizeCategory(entry);
      const programAudience = entry.program_id ? normalizeProgramAudience(programMetaLookup[entry.program_id]) : null;
      const matchesDirection = directionFilter === "all" || direction === directionFilter;
      const matchesCategory = categoryFilter === "all" || category === categoryFilter;
      const matchesAudience = financeView === "all" || financeView === "hq" || (programAudience ? matchesAudienceFilter(programAudience, financeView) : false);
      return matchesDirection && matchesCategory && matchesAudience;
    });
  }, [categoryFilter, directionFilter, financeView, programMetaLookup, scopeFunding]);
  const fundingPagination = usePagination(filteredFunding);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  const inflowTotal = filteredFunding
    .filter((entry: any) => normalizeDirection(entry) === "inflow")
    .reduce((total: number, entry: any) => total + Number(entry.amount || 0), 0);
  const outflowTotal = filteredFunding
    .filter((entry: any) => normalizeDirection(entry) === "outflow")
    .reduce((total: number, entry: any) => total + Number(entry.amount || 0), 0);
  const plannedBudget = filteredPrograms.reduce((total: number, program: any) => total + Number(program.annual_budget || 0), 0);
  const receiptCount = filteredFunding.filter((entry: any) => normalizeDirection(entry) === "inflow").length;
  const expenditureCount = filteredFunding.filter((entry: any) => normalizeDirection(entry) === "outflow").length;

  const allCategories = useMemo(() => {
    const seed = new Set<string>([...inflowCategories, ...outflowCategories]);
    filteredFunding.forEach((entry: any) => seed.add(normalizeCategory(entry)));
    return Array.from(seed);
  }, [filteredFunding]);

  const categoryRows = useMemo(() => {
    return allCategories
      .map((category) => ({
        label: category,
        inflow: filteredFunding
          .filter((entry: any) => normalizeDirection(entry) === "inflow" && normalizeCategory(entry) === category)
          .reduce((total: number, entry: any) => total + Number(entry.amount || 0), 0),
        outflow: filteredFunding
          .filter((entry: any) => normalizeDirection(entry) === "outflow" && normalizeCategory(entry) === category)
          .reduce((total: number, entry: any) => total + Number(entry.amount || 0), 0)
      }))
      .filter((row) => row.inflow > 0 || row.outflow > 0);
  }, [allCategories, filteredFunding]);

  const periodRows = useMemo(() => {
    const grouped = new Map<string, { inflow: number; outflow: number }>();
    filteredFunding.forEach((entry: any) => {
      const key = periodKey(entry.transaction_date, periodMode);
      const current = grouped.get(key) || { inflow: 0, outflow: 0 };
      if (normalizeDirection(entry) === "outflow") {
        current.outflow += Number(entry.amount || 0);
      } else {
        current.inflow += Number(entry.amount || 0);
      }
      grouped.set(key, current);
    });

    return Array.from(grouped.entries())
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, value]) => ({
        key,
        label: periodLabel(key, periodMode),
        inflow: value.inflow,
        outflow: value.outflow
      }));
  }, [filteredFunding, periodMode]);

  const maxCategoryAmount = Math.max(1, ...categoryRows.flatMap((row) => [row.inflow, row.outflow]));
  const maxPeriodAmount = Math.max(1, ...periodRows.flatMap((row) => [row.inflow, row.outflow]));

  function resetForm() {
    setSelectedId(null);
    setForm(buildInitialForm(defaultUniversityId, canUseHq));
  }

  function closeForm() {
    setIsFormOpen(false);
    resetForm();
  }

  function openCreateForm() {
    if (!canManageRecords) return;
    resetForm();
    setIsFormOpen(true);
  }

  function hydrateForm(entry: any) {
    if (!canManageRecords) return;
    const direction = normalizeDirection(entry);
    const category = normalizeCategory(entry);
    setSelectedId(entry.id);
    setForm({
      university_id: entry.university_id ? String(entry.university_id) : HQ_SCOPE,
      program_id: entry.program_id ? String(entry.program_id) : "",
      source_name: entry.source_name || "",
      flow_direction: direction,
      receipt_category: category,
      category_detail: entry.category_detail || "",
      reporting_window: entry.reporting_window || "monthly",
      amount: String(entry.amount || ""),
      currency: entry.currency || "USD",
      transaction_date: entry.transaction_date || "",
      channel: entry.channel || "",
      designation: entry.designation || "",
      notes: entry.notes || ""
    });
    setIsFormOpen(true);
  }

  const availableCategories = form.flow_direction === "outflow" ? outflowCategories : inflowCategories;
  const isOtherCategory = form.receipt_category === "Other";
  const lockedUniversityName =
    universities?.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus";

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Treasury operations"
        title="Finance dashboard"
        description="Record weekly or monthly cash receipts and expenditures for university, campus, and regional treasuries "
        actions={canManageRecords ? (
          <button className="primary-button" type="button" onClick={openCreateForm}>
            Record a treasury entry
          </button>
        ) : undefined}
      />

      <div className="flex flex-wrap items-center gap-3">
        {(canUseHq ? financeViewOptions : financeViewOptions.filter((option) => option.value !== "hq")).map((option) => (
          <button
            key={option.value}
            className={financeView === option.value ? "primary-button" : "secondary-button"}
            type="button"
            onClick={() => setFinanceView(option.value as "all" | "hq" | "alumni" | "students")}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Cash inflow" value={formatCurrency(inflowTotal)} helper={`${formatNumber(receiptCount)} receipt entries`} />
        <MetricCard label="Cash outflow" value={formatCurrency(outflowTotal)} tone="coral" helper={`${formatNumber(expenditureCount)} expenditure entries`} />
        <MetricCard label="Budget" value={formatCurrency(plannedBudget)} tone="gold" helper="Annual budgets across visible ministry programs" />
        <MetricCard label="Net cash position" value={formatCurrency(inflowTotal - outflowTotal)} tone="ink" helper="Inflow less outflow in current scope" />
        <MetricCard label="Records in scope" value={formatNumber(filteredFunding.length)} tone="gold" helper="Treasury entries across the visible university or campus scope" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[9fr_3fr]">
        <Panel className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Category comparison</p>
              <h3 className="text-xl font-semibold text-slate-950">Cash by category</h3>
            </div>
            <div className="finance-chart-legend">
              <span className="finance-chart-legend-item">
                <span className="finance-chart-legend-swatch finance-chart-legend-swatch-inflow" />
                Inflow
              </span>
              <span className="finance-chart-legend-item">
                <span className="finance-chart-legend-swatch finance-chart-legend-swatch-outflow" />
                Outflow
              </span>
            </div>
          </div>

          {categoryRows.length === 0 ? (
            <EmptyState
              title="No category data yet"
              description="Record receipts or expenditures to populate the category graph."
            />
          ) : (
            <div className="finance-chart-scroll">
              <div
                className="finance-chart finance-chart-wide"
                style={{ minWidth: `${Math.max(categoryRows.length * 124, 720)}px` }}
              >
              {categoryRows.map((row) => (
                <div key={row.label} className="finance-chart-group">
                  <div className="finance-chart-columns">
                    <div className="finance-chart-column">
                      <span className="finance-chart-value">{formatCurrency(row.inflow)}</span>
                      <div className="finance-chart-track-vertical">
                        <div
                          className="finance-chart-bar finance-chart-bar-inflow"
                          style={{ height: `${Math.max((row.inflow / maxCategoryAmount) * 100, row.inflow > 0 ? 6 : 0)}%` }}
                        />
                      </div>
                    </div>
                    <div className="finance-chart-column">
                      <span className="finance-chart-value">{formatCurrency(row.outflow)}</span>
                      <div className="finance-chart-track-vertical">
                        <div
                          className="finance-chart-bar finance-chart-bar-outflow"
                          style={{ height: `${Math.max((row.outflow / maxCategoryAmount) * 100, row.outflow > 0 ? 6 : 0)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="finance-chart-labels">
                    <div className="finance-chart-label">{row.label}</div>
                    <div className="finance-chart-caption">{formatCurrency(row.inflow)} in / {formatCurrency(row.outflow)} out</div>
                  </div>
                </div>
              ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Cash movement</p>
            </div>
            <div className="flex gap-2">
              <button className={periodMode === "weekly" ? "primary-button" : "secondary-button"} type="button" onClick={() => setPeriodMode("weekly")}>
                Weekly
              </button>
              <button className={periodMode === "monthly" ? "primary-button" : "secondary-button"} type="button" onClick={() => setPeriodMode("monthly")}>
                Monthly
              </button>
            </div>
          </div>

          {periodRows.length === 0 ? (
            <EmptyState
              title="No treasury movement yet"
              description="Once records are saved, weekly and monthly movement will appear here."
            />
          ) : (
            <div className="finance-chart-scroll finance-chart-scroll-compact">
              <div
                className="finance-chart finance-chart-compact"
                style={{ minWidth: `${Math.max(periodRows.length * 96, 320)}px` }}
              >
              {periodRows.map((row) => (
                <div key={row.key} className="finance-chart-group finance-chart-group-compact">
                  <div className="finance-chart-columns">
                    <div className="finance-chart-column">
                      <span className="finance-chart-value">{formatCurrency(row.inflow)}</span>
                      <div className="finance-chart-track-vertical">
                        <div
                          className="finance-chart-bar finance-chart-bar-inflow"
                          style={{ height: `${Math.max((row.inflow / maxPeriodAmount) * 100, row.inflow > 0 ? 6 : 0)}%` }}
                        />
                      </div>
                    </div>
                    <div className="finance-chart-column">
                      <span className="finance-chart-value">{formatCurrency(row.outflow)}</span>
                      <div className="finance-chart-track-vertical">
                        <div
                          className="finance-chart-bar finance-chart-bar-outflow"
                          style={{ height: `${Math.max((row.outflow / maxPeriodAmount) * 100, row.outflow > 0 ? 6 : 0)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="finance-chart-labels">
                    <div className="finance-chart-label">{row.label}</div>
                    <div className="finance-chart-caption">{formatCurrency(row.inflow)} / {formatCurrency(row.outflow)}</div>
                  </div>
                </div>
              ))}
              </div>
            </div>
          )}
        </Panel>
      </div>

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Treasury ledger</p>
            <h3 className="text-xl font-semibold text-slate-950">Receipts and expenditures</h3>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="field-shell min-w-[180px]">
              <span className="field-label">Direction</span>
              <select className="field-input" value={directionFilter} onChange={(event) => setDirectionFilter(event.target.value)}>
                <option value="all">All</option>
                <option value="inflow">Inflow</option>
                <option value="outflow">Outflow</option>
              </select>
            </label>
            <label className="field-shell min-w-[180px]">
              <span className="field-label">Category</span>
              <select className="field-input" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                <option value="all">All categories</option>
                {allCategories.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {filteredFunding.length === 0 ? (
          <EmptyState
            title="No treasury records yet"
            description={canManageRecords ? "Record a receipt or expenditure to create the university or campus cash history." : "Treasury records will appear here once finance officers or super admins submit them."}
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Source / Payee</th>
                    <th>Scope</th>
                    <th>Direction</th>
                    <th>Category</th>
                    <th>Amount</th>
                    <th>Window</th>
                    {canManageRecords ? <th>Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {fundingPagination.pageItems.map((entry: any) => {
                    const direction = normalizeDirection(entry);
                    const category = normalizeCategory(entry);
                    return (
                      <tr key={entry.id}>
                        <td>{formatDate(entry.transaction_date)}</td>
                        <td>
                          <div className="table-primary">{entry.source_name}</div>
                          <div className="table-secondary">{entry.designation || "No designation"} / {entry.channel || "No channel"}</div>
                          {entry.notes ? <div className="table-secondary">{entry.notes}</div> : null}
                        </td>
                        <td>
                          <div className="table-primary">
                            {entry.university_id ? (universityLookup[entry.university_id] || entry.university_name) : "PCM HQ / National Office"}
                          </div>
                          <div className="table-secondary">
                            {entry.program_id
                              ? `${programLookup[entry.program_id] || entry.program_name} / ${normalizeProgramAudience(programMetaLookup[entry.program_id])}`
                              : "General treasury"}
                          </div>
                        </td>
                        <td>
                          <StatusBadge label={direction} tone={direction === "outflow" ? "danger" : "success"} />
                        </td>
                        <td>
                          <StatusBadge label={category === "Other" && entry.category_detail ? `Other: ${entry.category_detail}` : category} tone="info" />
                        </td>
                        <td>{formatCurrency(entry.amount, entry.currency)}</td>
                        <td>{entry.reporting_window || "monthly"}</td>
                        {canManageRecords ? (
                          <td>
                            <div className="table-actions">
                              <TableActionButton label="Edit treasury entry" tone="edit" onClick={() => hydrateForm(entry)} />
                              <TableActionButton
                                label="Delete treasury entry"
                                tone="delete"
                                onClick={async () => {
                                  await fundingApi.delete(entry.id);
                                  await client.invalidateQueries({ queryKey: ["funding"] });
                                  await client.invalidateQueries({ queryKey: ["analytics-funding"] });
                                  await client.invalidateQueries({ queryKey: ["analytics-overview"] });
                                }}
                              />
                            </div>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={fundingPagination}
              itemLabel="entries"
              onExport={() => exportRowsAsCsv("finance-ledger", filteredFunding.map((entry: any) => {
                const direction = normalizeDirection(entry);
                const category = normalizeCategory(entry);
                return {
                  date: formatDate(entry.transaction_date),
                  source: entry.source_name || "",
                  university_or_campus: entry.university_id ? (universityLookup[entry.university_id] || entry.university_name) : "PCM HQ / National Office",
                  program: entry.program_id ? (programLookup[entry.program_id] || entry.program_name) : "General treasury",
                  audience: entry.program_id ? normalizeProgramAudience(programMetaLookup[entry.program_id]) : "",
                  direction,
                  category: category === "Other" && entry.category_detail ? `Other: ${entry.category_detail}` : category,
                  amount: entry.amount || 0,
                  currency: entry.currency || "USD",
                  reporting_window: entry.reporting_window || "monthly",
                  channel: entry.channel || "",
                  designation: entry.designation || "",
                  notes: entry.notes || ""
                };
              }))}
            />
          </>
        )}
      </Panel>

      <ModalDialog open={canManageRecords && isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Receipting and expenditure</p>
              <h3 className="text-xl font-semibold text-slate-950">{selectedId ? "Edit treasury record" : "Record a treasury entry"}</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              const payload = {
                university_id: isHqScope ? null : (form.university_id ? Number(form.university_id) : null),
                program_id: !isHqScope && form.program_id ? Number(form.program_id) : null,
                source_name: form.source_name,
                flow_direction: form.flow_direction,
                receipt_category: form.receipt_category,
                category_detail: isOtherCategory ? form.category_detail : null,
                reporting_window: form.reporting_window,
                entry_type: form.flow_direction === "outflow" ? "expense" : form.receipt_category.toLowerCase().replace(/\s+/g, "_"),
                amount: Number(form.amount),
                currency: form.currency,
                transaction_date: form.transaction_date,
                channel: form.channel || null,
                designation: form.designation || null,
                notes: form.notes || null
              };
              if (selectedId) {
                await fundingApi.update(selectedId, payload);
              } else {
                await fundingApi.create(payload);
              }
              await client.invalidateQueries({ queryKey: ["funding"] });
              await client.invalidateQueries({ queryKey: ["analytics-funding"] });
              await client.invalidateQueries({ queryKey: ["analytics-overview"] });
              closeForm();
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              {canSelectUniversity ? (
                <label className="field-shell">
                  <span className="field-label">{canUseHq ? "Treasury scope" : "University / campus"}</span>
                  <select
                    className="field-input"
                    value={form.university_id}
                    onChange={(event) => setForm({ ...form, university_id: event.target.value, program_id: "" })}
                  >
                    {canUseHq ? <option value={HQ_SCOPE}>PCM HQ / National Office</option> : <option value="">Select university or campus</option>}
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
              <label className="field-shell">
                <span className="field-label">Ministry program</span>
                <select
                  className="field-input"
                  value={form.program_id}
                  onChange={(event) => setForm({ ...form, program_id: event.target.value })}
                  disabled={isHqScope}
                >
                  <option value="">{isHqScope ? "HQ treasury entry" : "General treasury"}</option>
                  {visiblePrograms.map((program: any) => (
                    <option key={program.id} value={program.id}>{program.name}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Cash direction</span>
                <select
                  className="field-input"
                  value={form.flow_direction}
                  onChange={(event) => {
                    const nextDirection = event.target.value;
                    setForm({
                      ...form,
                      flow_direction: nextDirection,
                      receipt_category: nextDirection === "outflow" ? outflowCategories[0] : inflowCategories[0],
                      category_detail: ""
                    });
                  }}
                >
                  <option value="inflow">Inflow</option>
                  <option value="outflow">Outflow</option>
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">Reporting window</span>
                <select className="field-input" value={form.reporting_window} onChange={(event) => setForm({ ...form, reporting_window: event.target.value })}>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">{form.flow_direction === "inflow" ? "Receipt category" : "Expense category"}</span>
                <select className="field-input" value={form.receipt_category} onChange={(event) => setForm({ ...form, receipt_category: event.target.value, category_detail: "" })}>
                  {availableCategories.map((category) => (
                    <option key={category} value={category}>{category}</option>
                  ))}
                </select>
              </label>
            </div>

            {isOtherCategory ? (
              <label className="field-shell">
                <span className="field-label">Other category (specify)</span>
                <input className="field-input" value={form.category_detail} onChange={(event) => setForm({ ...form, category_detail: event.target.value })} placeholder="Specify the category" />
              </label>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-shell">
                <span className="field-label">{form.flow_direction === "inflow" ? "Source / receipt from" : "Payee / expense to"}</span>
                <input className="field-input" value={form.source_name} onChange={(event) => setForm({ ...form, source_name: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Purpose / designation</span>
                <input className="field-input" value={form.designation} onChange={(event) => setForm({ ...form, designation: event.target.value })} placeholder="General support, outreach, transport..." />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Amount</span>
                <input className="field-input" inputMode="decimal" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Currency</span>
                <input className="field-input" value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Transaction date</span>
                <input className="field-input" type="date" value={form.transaction_date} onChange={(event) => setForm({ ...form, transaction_date: event.target.value })} />
              </label>
            </div>

            <label className="field-shell">
              <span className="field-label">Channel</span>
              <input className="field-input" value={form.channel} onChange={(event) => setForm({ ...form, channel: event.target.value })} placeholder="cash, bank transfer, mobile money..." />
            </label>

            <label className="field-shell">
              <span className="field-label">Notes</span>
              <textarea className="field-input min-h-[120px]" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
            </label>

            <div className="flex flex-wrap gap-3">
              <button className="primary-button" type="submit">{selectedId ? "Save treasury record" : "Record treasury entry"}</button>
              <button className="secondary-button" type="button" onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
      </ModalDialog>
    </div>
  );
}
