import { type FormEvent, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { reportsApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, PageHeader, Panel, StatusBadge } from "../components/ui";
import { formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

type ReportEntry = {
  name: string;
  category: string;
  event_date: string;
  description: string;
  visitors: number | "";
  baptisms: number | "";
  images: File[];
};

function buildEntry(): ReportEntry {
  return {
    name: "",
    category: "",
    event_date: "",
    description: "",
    visitors: "",
    baptisms: "",
    images: []
  };
}

function buildInitialForm(defaultUniversityId?: number | null) {
  return {
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    report_type: "semester_form",
    period_start: "",
    period_end: "",
    students_count: "",
    entries: [buildEntry()]
  };
}

export default function ReportsPage() {
  const client = useQueryClient();
  const { roles, canSelectUniversity, scopedUniversityId, defaultUniversityId } = useUniversityScope();
  const canManage = roles.some((role) => ["super_admin", "student_admin", "secretary"].includes(role));

  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId));
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canManage
  });
  const { data: reports } = useQuery({
    queryKey: ["reports", scopedUniversityId],
    queryFn: () => reportsApi.list(scopedUniversityId),
    enabled: canManage
  });
  const { data: rows } = useQuery({
    queryKey: ["report-rows", selectedId],
    queryFn: () => reportsApi.rows(selectedId as number),
    enabled: !!selectedId && canManage
  });

  const universityLookup = useMemo(
    () => Object.fromEntries((universities || []).map((university: any) => [university.id, university.name])),
    [universities]
  );
  const selectedReport = (reports || []).find((report: any) => report.id === selectedId);
  const summaryRow = (rows || []).find((row: any) => row.row_index === 0);
  const detailRows = (rows || []).filter((row: any) => row.row_index > 0);
  const lockedUniversityName =
    universities?.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus";

  if (!canManage) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  const processedReports = (reports || []).filter((report: any) => report.status === "processed").length;
  const totalPeopleReported = (rows || [])
    .filter((row: any) => row.row_index > 0)
    .reduce((total: number, row: any) => total + Number(row.data?.visitors || 0), 0);

  function resetForm() {
    setForm(buildInitialForm(defaultUniversityId));
    setErrorMessage("");
  }

  function addEntry() {
    setForm((current) => ({ ...current, entries: [...current.entries, buildEntry()] }));
  }

  function removeEntry(index: number) {
    setForm((current) => ({
      ...current,
      entries: current.entries.filter((_, currentIndex) => currentIndex !== index)
    }));
  }

  function updateEntry(index: number, partial: Partial<ReportEntry>) {
    setForm((current) => ({
      ...current,
      entries: current.entries.map((entry, currentIndex) => (
        currentIndex === index ? { ...entry, ...partial } : entry
      ))
    }));
  }

  function exportRows() {
    if (!rows?.length) return;
    const allKeys = Array.from(new Set(rows.flatMap((row: any) => Object.keys(row.data || {}))));
    const csvRows = [
      allKeys.join(","),
      ...rows.map((row: any) => allKeys.map((key) => JSON.stringify(row.data?.[key] ?? "")).join(","))
    ];
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `report-${selectedId || "rows"}.csv`;
    link.click();
  }

  async function submitReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");

    const submittedEntries = form.entries.filter((entry) => (
      entry.name.trim() ||
      entry.description.trim() ||
      entry.category.trim() ||
      entry.event_date ||
      entry.visitors ||
      entry.baptisms ||
      entry.images.length
    ));

    if (!form.period_start || !form.period_end) {
      setErrorMessage("Add a reporting start and end date.");
      return;
    }
    if (!form.university_id) {
      setErrorMessage("Select a university or campus before submitting.");
      return;
    }
    if (!submittedEntries.length) {
      setErrorMessage("Add at least one program or event entry.");
      return;
    }

    setIsSubmitting(true);

    try {
      const body = new FormData();
      body.append("university_id", form.university_id);
      body.append("report_type", form.report_type);
      body.append("period_start", form.period_start);
      body.append("period_end", form.period_end);
      body.append("students_count", String(Number(form.students_count) || 0));
      body.append("programs_count", String(submittedEntries.length));

      const allImages: File[] = [];
      const entriesPayload = submittedEntries.map((entry) => {
        const image_indices: number[] = [];
        entry.images.forEach((image) => {
          image_indices.push(allImages.length);
          allImages.push(image);
        });
        return {
          name: entry.name,
          category: entry.category,
          event_date: entry.event_date || null,
          description: entry.description,
          visitors: Number(entry.visitors) || 0,
          baptisms: Number(entry.baptisms) || 0,
          image_indices
        };
      });

      body.append("programs_json", JSON.stringify(entriesPayload));
      allImages.forEach((image) => body.append("images", image));

      const response = await reportsApi.submitForm(body);
      await client.invalidateQueries({ queryKey: ["reports"] });
      setSelectedId(response.id);
      resetForm();
      setSuccessMessage("Report submitted successfully.");
    } catch (error: any) {
      setErrorMessage(error?.response?.data?.detail || "Unable to submit report right now.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Reporting"
        title="Report center"
        description="Submit structured university reports, attach evidence images, and review parsed submissions in one workspace."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <MetricCard label="Reports submitted" value={formatNumber(reports?.length)} helper={`${formatNumber(processedReports)} processed successfully`} />
        <MetricCard label="Entries in focus" value={formatNumber(detailRows.length || form.entries.length)} tone="gold" helper="Program and event rows in the active draft or selected report" />
        <MetricCard label="People reported" value={formatNumber(totalPeopleReported)} tone="coral" helper="Visitors counted in the selected report rows" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel className="space-y-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="eyebrow">Form submission</p>
              <h3 className="text-xl font-semibold text-slate-950">University / campus report form</h3>
              <p className="mt-2 text-sm text-slate-600">Capture the reporting window, student reach, and each program or event delivered in that period.</p>
            </div>
            <button className="secondary-button" type="button" onClick={resetForm}>
              Reset form
            </button>
          </div>

          <form className="grid gap-5" onSubmit={submitReport}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {canSelectUniversity ? (
                <label className="field-shell">
                  <span className="field-label">University / campus</span>
                  <select
                    className="field-input"
                    value={form.university_id}
                    onChange={(event) => setForm((current) => ({ ...current, university_id: event.target.value }))}
                  >
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
              <label className="field-shell">
                <span className="field-label">Report type</span>
                <select className="field-input" value={form.report_type} onChange={(event) => setForm((current) => ({ ...current, report_type: event.target.value }))}>
                  <option value="semester_form">Semester form</option>
                  <option value="monthly_chapter_report">Monthly campus report</option>
                  <option value="event_report">Event report</option>
                </select>
              </label>
              <label className="field-shell">
                <span className="field-label">Period start</span>
                <input className="field-input" type="date" value={form.period_start} onChange={(event) => setForm((current) => ({ ...current, period_start: event.target.value }))} />
              </label>
              <label className="field-shell">
                <span className="field-label">Period end</span>
                <input className="field-input" type="date" value={form.period_end} onChange={(event) => setForm((current) => ({ ...current, period_end: event.target.value }))} />
              </label>
            </div>

            <label className="field-shell max-w-sm">
              <span className="field-label">Students engaged in period</span>
              <input
                className="field-input"
                inputMode="numeric"
                value={form.students_count}
                onChange={(event) => setForm((current) => ({ ...current, students_count: event.target.value }))}
                placeholder="0"
              />
            </label>

            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Program entries</p>
                  <h4 className="text-lg font-semibold text-slate-950">Programs and events reported</h4>
                </div>
                <button className="secondary-button" type="button" onClick={addEntry}>
                  Add entry
                </button>
              </div>

              {form.entries.map((entry, index) => (
                <div key={index} className="rounded-[12px] border border-slate-200/80 bg-white/85 p-5">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <div>
                      <p className="eyebrow">Entry {index + 1}</p>
                      <h5 className="text-base font-semibold text-slate-950">{entry.name || "Program or event"}</h5>
                    </div>
                    {form.entries.length > 1 ? (
                      <button className="secondary-button text-rose-700" type="button" onClick={() => removeEntry(index)}>
                        Remove
                      </button>
                    ) : null}
                  </div>

                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <label className="field-shell xl:col-span-2">
                      <span className="field-label">Program / event name</span>
                      <input className="field-input" value={entry.name} onChange={(event) => updateEntry(index, { name: event.target.value })} />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">Category</span>
                      <input className="field-input" value={entry.category} onChange={(event) => updateEntry(index, { category: event.target.value })} placeholder="Outreach, discipleship..." />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">Event date</span>
                      <input className="field-input" type="date" value={entry.event_date} onChange={(event) => updateEntry(index, { event_date: event.target.value })} />
                    </label>
                  </div>

                  <label className="field-shell mt-4">
                    <span className="field-label">Description / outcomes</span>
                    <textarea className="field-input min-h-[110px]" value={entry.description} onChange={(event) => updateEntry(index, { description: event.target.value })} />
                  </label>

                  <div className="mt-4 grid gap-4 md:grid-cols-3">
                    <label className="field-shell">
                      <span className="field-label">Visitors</span>
                      <input className="field-input" inputMode="numeric" value={entry.visitors} onChange={(event) => updateEntry(index, { visitors: Number(event.target.value) || "" })} />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">Baptisms</span>
                      <input className="field-input" inputMode="numeric" value={entry.baptisms} onChange={(event) => updateEntry(index, { baptisms: Number(event.target.value) || "" })} />
                    </label>
                    <label className="field-shell">
                      <span className="field-label">Evidence images</span>
                      <input className="field-input" type="file" multiple onChange={(event) => updateEntry(index, { images: Array.from(event.target.files || []) })} />
                    </label>
                  </div>

                  {entry.images.length > 0 ? (
                    <p className="mt-3 text-sm text-slate-500">
                      {entry.images.length} image{entry.images.length === 1 ? "" : "s"} selected: {entry.images.map((image) => image.name).join(", ")}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>

            {errorMessage ? <p className="text-sm font-medium text-rose-700">{errorMessage}</p> : null}
            {successMessage ? <p className="text-sm font-medium text-emerald-700">{successMessage}</p> : null}

            <div className="flex flex-wrap gap-3">
              <button className="primary-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Submitting..." : "Submit report"}
              </button>
              <div className="rounded-full border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                Images are attached per entry and stored with the report submission.
              </div>
            </div>
          </form>
        </Panel>

        <div className="space-y-6">
          <Panel className="space-y-5">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Submission history</p>
                <h3 className="text-xl font-semibold text-slate-950">Submitted reports</h3>
              </div>
              <p className="text-sm text-slate-500">{formatNumber(reports?.length)} in scope</p>
            </div>

            {!reports?.length ? (
              <EmptyState
                title="No reports yet"
                description="Once a university or campus submits its first report, it will appear here for review."
              />
            ) : (
              <div className="space-y-3">
                {reports.map((report: any) => (
                  <button
                    key={report.id}
                    type="button"
                    className={[
                      "w-full rounded-[12px] border p-4 text-left transition",
                      selectedId === report.id
                        ? "border-emerald-300 bg-emerald-50/70 shadow-[0_18px_35px_rgba(16,185,129,0.12)]"
                        : "border-slate-200/80 bg-white/80 hover:border-slate-300 hover:bg-slate-50"
                    ].join(" ")}
                    onClick={() => setSelectedId(report.id)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm text-slate-500">
                          {report.university_id ? (universityLookup[report.university_id] || `University #${report.university_id}`) : "No university set"}
                        </p>
                        <h4 className="mt-1 text-base font-semibold text-slate-950">{report.original_filename}</h4>
                        <p className="mt-2 text-sm text-slate-600">
                          {formatDate(report.period_start)} to {formatDate(report.period_end)}
                        </p>
                      </div>
                      <StatusBadge label={report.status || "uploaded"} tone={report.status === "processed" ? "success" : "warning"} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Panel>

          <Panel className="space-y-5">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Parsed report</p>
                <h3 className="text-xl font-semibold text-slate-950">Review submitted rows</h3>
              </div>
              {rows?.length ? (
                <button className="secondary-button" type="button" onClick={exportRows}>
                  Export CSV
                </button>
              ) : null}
            </div>

            {!selectedId ? (
              <EmptyState
                title="Select a report"
                description="Choose a submission from the history panel to inspect the parsed summary and entry rows."
              />
            ) : (
              <div className="space-y-4">
                <div className="rounded-[12px] bg-slate-50 px-5 py-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Selected report</p>
                  <p className="mt-2 text-lg font-semibold text-slate-950">{selectedReport?.original_filename}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    {selectedReport?.period_start ? `${formatDate(selectedReport.period_start)} to ${formatDate(selectedReport.period_end)}` : "No period set"}
                  </p>
                </div>

                {summaryRow ? (
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-[14px] bg-emerald-50 px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-emerald-900/70">Students</p>
                      <p className="mt-2 text-2xl font-semibold text-emerald-950">{formatNumber(summaryRow.data?.students_count)}</p>
                    </div>
                    <div className="rounded-[14px] bg-amber-50 px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-amber-900/70">Entries</p>
                      <p className="mt-2 text-2xl font-semibold text-amber-950">{formatNumber(summaryRow.data?.programs_count)}</p>
                    </div>
                    <div className="rounded-[14px] bg-slate-950 px-4 py-4 text-white">
                      <p className="text-xs uppercase tracking-[0.18em] text-white/70">Status</p>
                      <p className="mt-2 text-2xl font-semibold">{selectedReport?.status || "processed"}</p>
                    </div>
                  </div>
                ) : null}

                {detailRows.length === 0 ? (
                  <EmptyState
                    title="No parsed entry rows"
                    description="This report did not produce any program or event rows."
                  />
                ) : (
                  <div className="space-y-4">
                    {detailRows.map((row: any) => (
                      <article key={row.id} className="rounded-[12px] border border-slate-200/70 bg-white/80 p-5">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-sm text-slate-500">{row.data?.category || "General activity"}</p>
                            <h4 className="text-lg font-semibold text-slate-950">{row.data?.name || `Entry ${row.row_index}`}</h4>
                          </div>
                          <StatusBadge label={row.is_valid ? "Valid" : "Needs review"} tone={row.is_valid ? "success" : "warning"} />
                        </div>

                        <p className="mt-3 text-sm leading-6 text-slate-600">{row.data?.description || "No description submitted."}</p>

                        <div className="mt-4 grid gap-3 md:grid-cols-3">
                          <div>
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Event date</p>
                            <p className="mt-1 text-sm font-medium text-slate-900">{row.data?.event_date ? formatDate(row.data.event_date) : "Not set"}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Visitors</p>
                            <p className="mt-1 text-sm font-medium text-slate-900">{formatNumber(row.data?.visitors)}</p>
                          </div>
                          <div>
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Baptisms</p>
                            <p className="mt-1 text-sm font-medium text-slate-900">{formatNumber(row.data?.baptisms)}</p>
                          </div>
                        </div>

                        {row.validation_errors?.length ? (
                          <p className="mt-4 text-sm font-medium text-rose-700">Validation errors: {row.validation_errors.join(", ")}</p>
                        ) : null}
                      </article>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
