import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { analyticsApi, programsApi } from "../api/endpoints";
import { EmptyState, MetricCard, PageHeader, Panel, StatusBadge } from "../components/ui";
import { formatCompactCurrency, formatCurrency, formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

export default function OverviewPage() {
  const { scopeKey, scopeParams } = useUniversityScope();

  const overviewQuery = useQuery({
    queryKey: ["analytics-overview", scopeKey],
    queryFn: () => analyticsApi.overview(scopeParams)
  });
  const universitiesQuery = useQuery({
    queryKey: ["analytics-universities", scopeKey],
    queryFn: () => analyticsApi.universities(scopeParams)
  });
  const programsQuery = useQuery({
    queryKey: ["analytics-programs", scopeKey],
    queryFn: () => analyticsApi.programs(scopeParams)
  });
  const fundingQuery = useQuery({
    queryKey: ["analytics-funding", scopeKey],
    queryFn: () => analyticsApi.funding(scopeParams)
  });
  const scheduledProgramsQuery = useQuery({
    queryKey: ["programs", scopeKey, "overview-schedule"],
    queryFn: () => programsApi.list(scopeParams)
  });

  const overview = overviewQuery.data;
  const universities = universitiesQuery.data || [];
  const programs = programsQuery.data || [];
  const funding = fundingQuery.data;
  const topCampuses = useMemo(
    () =>
      [...universities]
        .sort((left: any, right: any) => {
          if ((right.people_served || 0) !== (left.people_served || 0)) {
            return (right.people_served || 0) - (left.people_served || 0);
          }
          if ((right.active_programs || 0) !== (left.active_programs || 0)) {
            return (right.active_programs || 0) - (left.active_programs || 0);
          }
          if ((right.active_members || 0) !== (left.active_members || 0)) {
            return (right.active_members || 0) - (left.active_members || 0);
          }
          return (right.funding_total || 0) - (left.funding_total || 0);
        })
        .slice(0, 5),
    [universities]
  );
  const topPrograms = [...programs]
    .sort((left, right) => (right.beneficiaries_served || 0) - (left.beneficiaries_served || 0))
    .slice(0, 3);
  const plannedBudget = (programs || []).reduce((total: number, program: any) => total + Number(program.annual_budget || 0), 0);
  const upcomingPrograms = useMemo(
    () =>
      [...(scheduledProgramsQuery.data || [])]
        .filter((program: any) => {
          if (!program.start_date) return false;
          const endDate = new Date(`${program.end_date || program.start_date}T23:59:59`);
          return endDate.getTime() >= Date.now() && (program.status || "").toLowerCase() !== "archived";
        })
        .sort((left: any, right: any) => new Date(`${left.start_date}T00:00:00`).getTime() - new Date(`${right.start_date}T00:00:00`).getTime())
        .slice(0, 4),
    [scheduledProgramsQuery.data]
  );
  const fundingMixCards = [
    {
      label: "Budget",
      value: plannedBudget,
      toneClassName: "bg-sky-50",
      labelClassName: "text-sky-900/70",
      valueClassName: "text-sky-950"
    },
    {
      label: "Income",
      value: funding?.income_total,
      toneClassName: "bg-emerald-50",
      labelClassName: "text-emerald-900/70",
      valueClassName: "text-emerald-950"
    },
    {
      label: "Expense",
      value: funding?.expense_total,
      toneClassName: "bg-amber-50",
      labelClassName: "text-amber-900/70",
      valueClassName: "text-amber-950"
    },
    {
      label: "Net",
      value: funding?.net_total,
      toneClassName: "bg-slate-950 text-white",
      labelClassName: "text-white/70",
      valueClassName: "text-white"
    }
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Executive overview"
        title="Network operations"
        description="Track students, staff, alumni, funding, and campus scheduling across the university network."
      />

      <div className="grid gap-4 xl:grid-cols-3 2xl:grid-cols-6">
        <MetricCard label="Active campuses" value={formatNumber(overview?.active_universities)} helper="Universities and campuses currently reporting" />
        <MetricCard label="Live programs" value={formatNumber(overview?.active_programs)} tone="gold" helper={`${formatNumber(overview?.scheduled_events)} dated programs on record`} />
        <MetricCard label="Students" value={formatNumber(overview?.students_count)} helper="Current student records across campuses" />
        <MetricCard label="Staff" value={formatNumber(overview?.staff_count)} tone="coral" helper="Campus coordinators and support staff" />
        <MetricCard label="Alumni" value={formatNumber(overview?.alumni_count)} helper="Graduates still connected to the network" />
        <MetricCard label="Upcoming schedule" value={formatNumber(overview?.upcoming_events)} tone="ink" helper={`${formatCurrency(overview?.net_total)} net funding`} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
        <Panel className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Campus performance</p>
              <h3 className="text-xl font-semibold text-slate-950">Where the network is strongest</h3>
            </div>
            <p className="text-sm text-slate-500">Top {Math.min(topCampuses.length, 5)} of {universities.length} in view</p>
          </div>

          {universities.length === 0 ? (
            <EmptyState
              title="No campus data yet"
              description="Create or seed universities to start tracking campus-level delivery and funding."
            />
          ) : (
            <div className="max-h-[30rem] space-y-4 overflow-y-auto pr-2">
              {topCampuses.map((university: any) => {
                const serviceRatio = Math.min(
                  100,
                  Math.round(((university.people_served || 0) / Math.max(university.active_members || 1, 1)) * 100)
                );
                return (
                  <div key={university.university_id} className="rounded-[12px] border border-slate-200/70 bg-white/70 p-5">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <h4 className="text-lg font-semibold text-slate-900">{university.university_name}</h4>
                        <p className="text-sm text-slate-500">
                          {university.active_programs} programs, {university.active_members} active people, latest update {formatDate(university.latest_update_at)}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-slate-500">Net funding</p>
                        <p className="text-xl font-semibold text-slate-900">{formatCurrency(university.funding_total)}</p>
                      </div>
                    </div>
                    <div className="mt-4">
                      <div className="mb-2 flex items-center justify-between text-xs uppercase tracking-[0.18em] text-slate-500">
                        <span>Delivery intensity</span>
                        <span>{serviceRatio}%</span>
                      </div>
                      <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-[linear-gradient(90deg,#115e59,#f59e0b)]" style={{ width: `${serviceRatio}%` }} />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>

        <Panel className="space-y-5">
          <div>
            <p className="eyebrow">Funding posture</p>
            <h3 className="text-xl font-semibold text-slate-950">Funding mix</h3>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {fundingMixCards.map((card) => (
              <div key={card.label} className={`rounded-[12px] px-4 py-4 ${card.toneClassName}`}>
                <p className={`text-sm ${card.labelClassName}`}>{card.label}</p>
                <p
                  className={`mt-1 text-lg font-normal tracking-[-0.02em] ${card.valueClassName}`}
                  title={formatCurrency(card.value)}
                >
                  {formatCompactCurrency(card.value)}
                </p>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            {(funding?.by_type || []).map((item: any) => (
              <div key={item.label} className="flex items-center justify-between border-b border-slate-200/70 pb-3 text-sm">
                <span className="font-medium capitalize text-slate-800">{item.label.replaceAll("_", " ")}</span>
                <span className="text-slate-600">{formatCurrency(item.amount)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <Panel className="space-y-5">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Ministry program focus</p>
              <h3 className="text-xl font-semibold text-slate-950">Top delivery ministry programs</h3>
            </div>
            <p className="text-sm text-slate-500">{programs.length} ministry programs in portfolio</p>
          </div>
          {topPrograms.length === 0 ? (
            <EmptyState
              title="No ministry programs yet"
              description="Ministry programs will appear here as soon as a university or campus creates them."
            />
          ) : (
            <div className="grid gap-4">
              {topPrograms.map((program: any) => (
                <div key={program.program_id} className="rounded-[12px] border border-slate-200/70 bg-white/75 p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <p className="text-sm text-slate-500">{program.university_name || "All universities and campuses"}</p>
                      <h4 className="text-lg font-semibold text-slate-900">{program.program_name}</h4>
                      <p className="text-sm text-slate-500">{program.category || "General"} ministry program led by {program.manager_name || "campus team"}</p>
                    </div>
                    <StatusBadge
                      label={program.status || "active"}
                      tone={(program.status || "").toLowerCase() === "active" ? "success" : "warning"}
                    />
                  </div>
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Served</p>
                      <p className="mt-1 text-lg font-semibold text-slate-900">{formatNumber(program.beneficiaries_served)}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Budget</p>
                      <p className="mt-1 text-lg font-semibold text-slate-900">{formatCurrency(program.annual_budget)}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Updates</p>
                      <p className="mt-1 text-lg font-semibold text-slate-900">{formatNumber(program.update_count)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <div className="space-y-6">
          <Panel className="space-y-5">
            <div>
              <p className="eyebrow">Upcoming schedule</p>
              <h3 className="text-xl font-semibold text-slate-950">Programs on deck</h3>
            </div>

            {upcomingPrograms.length === 0 ? (
              <EmptyState
                title="No upcoming programs"
                description="Create ministry programs with start dates in the Programs workspace to populate the schedule."
              />
            ) : (
              <div className="space-y-4">
                {upcomingPrograms.map((program: any) => (
                  <article key={program.id} className="rounded-[12px] border border-slate-200/70 bg-white/70 p-5">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-sm text-slate-500">{program.university_name || "All universities and campuses"}</p>
                        <h4 className="mt-1 text-lg font-semibold text-slate-900">{program.name}</h4>
                      </div>
                      <StatusBadge
                        label={program.status || "active"}
                        tone={(program.status || "").toLowerCase() === "active" ? "success" : (program.status || "").toLowerCase() === "planning" ? "info" : "warning"}
                      />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-600">{program.category || "General ministry program"} / {program.manager_name || "Campus team"}</p>
                    <div className="mt-4 flex flex-wrap gap-3 text-xs uppercase tracking-[0.18em] text-slate-500">
                      <span>{formatDate(program.start_date)}</span>
                      {program.end_date && program.end_date !== program.start_date ? <span>to {formatDate(program.end_date)}</span> : null}
                      <span>{formatNumber(program.beneficiaries_served)} served</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
