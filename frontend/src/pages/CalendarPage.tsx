import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { programsApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge } from "../components/ui";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const weekdayLabels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function monthGridStart(date: Date) {
  const start = new Date(date.getFullYear(), date.getMonth(), 1);
  return addDays(start, -start.getDay());
}

function monthGridEnd(date: Date) {
  return addDays(monthGridStart(date), 41);
}

function dayKey(value: Date | string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

function dayLabel(date: Date) {
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(date);
}

function parseProgramDate(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function statusTone(status?: string | null): "success" | "warning" | "danger" | "info" | "neutral" {
  const normalized = (status || "active").toLowerCase();
  if (normalized === "active") return "success";
  if (normalized === "planning") return "info";
  if (normalized === "paused") return "warning";
  if (normalized === "archived") return "neutral";
  return "info";
}

export default function CalendarPage({ embedded = false }: { embedded?: boolean }) {
  const { roles, scopedUniversityId } = useUniversityScope();
  const canView = roles.some((role) => ["super_admin", "student_admin", "secretary", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director", "alumni_admin"].includes(role));

  const [viewDate, setViewDate] = useState(() => new Date());
  const [selectedProgram, setSelectedProgram] = useState<any | null>(null);

  const gridStart = useMemo(() => monthGridStart(viewDate), [viewDate]);
  const gridEnd = useMemo(() => monthGridEnd(viewDate), [viewDate]);

  const { data: programs } = useQuery({
    queryKey: ["programs", scopedUniversityId, "calendar"],
    queryFn: () => programsApi.list(scopedUniversityId),
    enabled: canView
  });

  const scheduledPrograms = useMemo(
    () =>
      (programs || [])
        .map((program: any) => {
          const start = parseProgramDate(program.start_date);
          if (!start) return null;
          const end = parseProgramDate(program.end_date || program.start_date) || start;
          return {
            ...program,
            start,
            end
          };
        })
        .filter(Boolean) as Array<any>,
    [programs]
  );

  const monthStart = useMemo(() => new Date(viewDate.getFullYear(), viewDate.getMonth(), 1), [viewDate]);
  const monthEnd = useMemo(() => new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 0), [viewDate]);

  const now = Date.now();
  const upcomingPrograms = useMemo(
    () =>
      [...scheduledPrograms]
        .filter((program) => program.end.getTime() >= now && (program.status || "").toLowerCase() !== "archived")
        .sort((left, right) => left.start.getTime() - right.start.getTime())
        .slice(0, 6),
    [now, scheduledPrograms]
  );

  const programsInMonth = useMemo(
    () => scheduledPrograms.filter((program) => program.end >= monthStart && program.start <= monthEnd),
    [monthEnd, monthStart, scheduledPrograms]
  );

  const activeCampuses = useMemo(
    () => new Set(scheduledPrograms.map((program) => program.university_id).filter(Boolean)).size,
    [scheduledPrograms]
  );

  const activeScheduledPrograms = useMemo(
    () => scheduledPrograms.filter((program) => (program.status || "").toLowerCase() !== "archived").length,
    [scheduledPrograms]
  );

  const programsByDay = useMemo(() => {
    const grouped: Record<string, any[]> = {};

    scheduledPrograms.forEach((program) => {
      if (program.end < gridStart || program.start > gridEnd) return;

      const visibleStart = program.start < gridStart ? gridStart : program.start;
      const visibleEnd = program.end > gridEnd ? gridEnd : program.end;

      for (let current = new Date(visibleStart); current <= visibleEnd; current = addDays(current, 1)) {
        const key = dayKey(current);
        grouped[key] = [...(grouped[key] || []), program];
      }
    });

    return grouped;
  }, [gridEnd, gridStart, scheduledPrograms]);

  const calendarDays = useMemo(
    () => Array.from({ length: 42 }, (_, index) => addDays(gridStart, index)),
    [gridStart]
  );
  const headerActions = (
    <>
      <button className="secondary-button" type="button" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1))}>
        Previous month
      </button>
      <button className="secondary-button" type="button" onClick={() => setViewDate(new Date())}>
        Today
      </button>
      <button className="secondary-button" type="button" onClick={() => setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1))}>
        Next month
      </button>
    </>
  );

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  return (
    <div className={embedded ? "space-y-6" : "space-y-8"}>
      {embedded ? (
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
          </div>
          <div className="flex flex-wrap gap-3">
            {headerActions}
          </div>
        </div>
      ) : (
        <PageHeader
          eyebrow="Program calendar"
          title="Programming calendar"
          description="Ministry programs with start and end dates are added to this calendar automatically. Create or update the program dates from the ministry programs workspace."
          actions={headerActions}
        />
      )}

      <div className="grid gap-4 xl:grid-cols-4">
        <MetricCard label="Dated programs" value={formatNumber(scheduledPrograms.length)} helper={`${formatNumber(activeCampuses)} campuses represented`} />
        <MetricCard label="Upcoming programs" value={formatNumber(upcomingPrograms.length)} tone="gold" helper="Programs still ahead on the schedule" />
        <MetricCard label="This month" value={formatNumber(programsInMonth.length)} tone="coral" helper={dayLabel(viewDate)} />
        <MetricCard label="Active schedule" value={formatNumber(activeScheduledPrograms)} tone="ink" helper="Dated ministry programs not archived" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.95fr]">
        <Panel className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Monthly view</p>
              <h3 className="text-xl font-semibold text-slate-950">{dayLabel(viewDate)}</h3>
            </div>
            <p className="text-sm text-slate-500">{formatNumber(programsInMonth.length)} dated programs this month</p>
          </div>

          <div className="overflow-x-auto">
            <div className="calendar-grid min-w-[920px]">
              {weekdayLabels.map((label) => (
                <div key={label} className="calendar-weekday">{label}</div>
              ))}
              {calendarDays.map((date) => {
                const key = dayKey(date);
                const items = programsByDay[key] || [];
                const outsideMonth = date.getMonth() !== viewDate.getMonth();
                return (
                  <div key={key} className={["calendar-cell", outsideMonth ? "calendar-cell-muted" : ""].join(" ").trim()}>
                    <div className="flex items-center justify-between">
                      <span className="calendar-day-number">{date.getDate()}</span>
                      {items.length > 0 ? <span className="calendar-day-count">{items.length}</span> : null}
                    </div>
                    <div className="mt-3 space-y-2">
                      {items.slice(0, 3).map((program: any) => (
                        <button
                          key={`${program.id}-${key}`}
                          type="button"
                          className="calendar-event-chip"
                          onClick={() => setSelectedProgram(program)}
                        >
                          <span className="calendar-event-time">
                            {program.category || (program.status || "Program")}
                          </span>
                          <span className="calendar-event-title">{program.name}</span>
                          <span className="calendar-event-campus">{program.university_name || "All universities and campuses"} / {program.audience || "Students"}</span>
                        </button>
                      ))}
                      {items.length > 3 ? <div className="calendar-more">+{items.length - 3} more</div> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel className="space-y-5">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="eyebrow">Upcoming schedule</p>
                <h3 className="text-xl font-semibold text-slate-950">Programs on deck</h3>
              </div>
              <p className="text-sm text-slate-500">{formatNumber(upcomingPrograms.length)} upcoming</p>
            </div>

            {upcomingPrograms.length === 0 ? (
              <EmptyState
                title="No dated programs"
                description="Create a ministry program and give it a start date to place it on the calendar."
              />
            ) : (
              <div className="space-y-4">
                {upcomingPrograms.map((program: any) => (
                  <article key={program.id} className="rounded-[12px] border border-slate-200/70 bg-white/80 p-5">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <p className="text-sm text-slate-500">{program.university_name || "All universities and campuses"}</p>
                        <h4 className="text-lg font-semibold text-slate-950">{program.name}</h4>
                        <p className="mt-2 text-sm text-slate-600">
                          {program.category || "General ministry program"} / {program.audience || "Students"} / {program.manager_name || "Campus team"}
                        </p>
                      </div>
                      <StatusBadge label={program.status || "active"} tone={statusTone(program.status)} />
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Schedule</p>
                        <p className="mt-1 text-sm font-medium text-slate-900">
                          {formatDate(program.start_date)}
                          {program.end_date && program.end_date !== program.start_date ? ` to ${formatDate(program.end_date)}` : ""}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-slate-500">People served</p>
                        <p className="mt-1 text-sm font-medium text-slate-900">{formatNumber(program.beneficiaries_served)}</p>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button className="secondary-button" type="button" onClick={() => setSelectedProgram(program)}>
                        View details
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>

      <ModalDialog open={Boolean(selectedProgram)} onClose={() => setSelectedProgram(null)} className="modal-shell-page">
        {selectedProgram ? (
          <div className="space-y-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="eyebrow">Program details</p>
                <h3 className="text-2xl font-semibold text-slate-950">{selectedProgram.name}</h3>
                <p className="mt-2 text-sm text-slate-500">{selectedProgram.university_name || "All universities and campuses"}</p>
              </div>
              <button className="secondary-button" type="button" onClick={() => setSelectedProgram(null)}>
                Close
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Category</p>
                <p className="mt-2 text-sm font-medium text-slate-900">{selectedProgram.category || "General ministry program"}</p>
              </div>
              <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Audience</p>
                <p className="mt-2 text-sm font-medium text-slate-900">{selectedProgram.audience || "Students"}</p>
              </div>
              <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Status</p>
                <div className="mt-2">
                  <StatusBadge label={selectedProgram.status || "active"} tone={statusTone(selectedProgram.status)} />
                </div>
              </div>
              <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Schedule</p>
                <p className="mt-2 text-sm font-medium text-slate-900">
                  {formatDate(selectedProgram.start_date)}
                  {selectedProgram.end_date && selectedProgram.end_date !== selectedProgram.start_date ? ` to ${formatDate(selectedProgram.end_date)}` : ""}
                </p>
              </div>
              <div className="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Manager</p>
                <p className="mt-2 text-sm font-medium text-slate-900">{selectedProgram.manager_name || "Campus team"}</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-[12px] border border-slate-200/80 bg-white/85 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">People served</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{formatNumber(selectedProgram.beneficiaries_served)}</p>
              </div>
              <div className="rounded-[12px] border border-slate-200/80 bg-white/85 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Target</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{formatNumber(selectedProgram.target_beneficiaries)}</p>
              </div>
              <div className="rounded-[12px] border border-slate-200/80 bg-white/85 px-4 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Budget</p>
                <p className="mt-2 text-lg font-semibold text-slate-950">{formatCurrency(selectedProgram.annual_budget)}</p>
              </div>
            </div>

            <div className="rounded-[12px] border border-slate-200/80 bg-white/85 px-5 py-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Description</p>
              <p className="mt-3 text-sm leading-7 text-slate-600">{selectedProgram.description || "No description has been provided for this program yet."}</p>
            </div>
          </div>
        ) : null}
      </ModalDialog>
    </div>
  );
}
