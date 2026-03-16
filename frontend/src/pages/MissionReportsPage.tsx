import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { programUpdatesApi, reportingPeriodsApi } from "../api/endpoints";
import { EmptyState, MetricCard, PageHeader, Panel, StatusBadge, TablePagination, TableSearchField, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { matchesTableSearch } from "../lib/tableSearch";
import { useUniversityScope } from "../lib/universityScope";

const missionReportRoles = ["general_user"];

export default function MissionReportsPage() {
  const { roles, scopeKey, scopeParams } = useUniversityScope();
  const canView = roles.some((role) => missionReportRoles.includes(role));
  const [periodFilter, setPeriodFilter] = useState("all");
  const [search, setSearch] = useState("");

  const { data: reportingPeriods } = useQuery({
    queryKey: ["reporting-periods", true],
    queryFn: () => reportingPeriodsApi.list(true),
    enabled: canView
  });
  const { data: reports } = useQuery({
    queryKey: ["condensed-mission-reports", scopeKey, periodFilter],
    queryFn: () => programUpdatesApi.condensed({
      ...scopeParams,
      reportingPeriod: periodFilter === "all" ? undefined : periodFilter
    }),
    enabled: canView
  });

  const totalReach = (reports || []).reduce((sum: number, item: any) => sum + Number(item.total_beneficiaries_reached || 0), 0);
  const totalVolunteers = (reports || []).reduce((sum: number, item: any) => sum + Number(item.total_volunteers_involved || 0), 0);
  const totalCampuses = (reports || []).reduce((sum: number, item: any) => sum + Number(item.university_count || 0), 0);

  const periodOptions = useMemo(() => {
    const source = new Map<string, string>();
    for (const period of reportingPeriods || []) {
      source.set(period.code, period.label || period.code);
    }
    for (const report of reports || []) {
      if (!source.has(report.reporting_period)) {
        source.set(report.reporting_period, report.reporting_period_label || report.reporting_period);
      }
    }
    return Array.from(source.entries());
  }, [reportingPeriods, reports]);
  const filteredReports = useMemo(() => {
    return (reports || []).filter((report: any) => matchesTableSearch(search, [
      report.event_name,
      report.reporting_period,
      report.reporting_period_label,
      report.university_count,
      report.update_count,
      report.total_beneficiaries_reached,
      report.total_volunteers_involved,
      report.total_funds_used,
      report.highlights,
      formatDate(report.latest_update_at)
    ]));
  }, [reports, search]);
  const pagination = usePagination(filteredReports);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Mission intelligence"
        title="Condensed mission reports"
        description="A network-level summary of mandatory-program reporting, grouped by reporting period and event so general users can stay informed without entering the reporting workflow."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <MetricCard label="Mandatory report groups" value={formatNumber(reports?.length)} helper="Grouped by period and event" />
        <MetricCard label="People reached" value={formatNumber(totalReach)} tone="gold" helper="Combined beneficiary reach" />
        <MetricCard label="Volunteer mobilization" value={formatNumber(totalVolunteers)} tone="coral" helper={`${formatNumber(totalCampuses)} campus contributions represented`} />
      </div>

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Consolidated view</p>
            <h3 className="text-xl font-semibold text-slate-950">Mandatory-program highlights</h3>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <TableSearchField
              value={search}
              onChange={setSearch}
              placeholder="Search event, period, highlight, or totals"
            />
            <label className="field-shell min-w-[200px]">
              <span className="field-label">Reporting period</span>
              <select className="field-input" value={periodFilter} onChange={(event) => setPeriodFilter(event.target.value)}>
                <option value="all">All periods</option>
                {periodOptions.map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {!filteredReports.length ? (
          <EmptyState
            title={reports?.length ? "No condensed reports match this search" : "No condensed mission reports found"}
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Reporting period</th>
                    <th>Coverage</th>
                    <th>Reach</th>
                    <th>Highlights</th>
                  </tr>
                </thead>
                <tbody>
                  {pagination.pageItems.map((report: any) => (
                    <tr key={`${report.reporting_period}-${report.event_name}`}>
                      <td>
                        <div className="table-primary">{report.event_name}</div>
                        <div className="table-secondary">Latest update {formatDate(report.latest_update_at)}</div>
                      </td>
                      <td>
                        <StatusBadge label={report.reporting_period_label || report.reporting_period} tone="info" />
                      </td>
                      <td>
                        <div className="table-primary">{formatNumber(report.university_count)} campuses</div>
                        <div className="table-secondary">{formatNumber(report.update_count)} submitted updates</div>
                      </td>
                      <td>
                        <div className="table-primary">{formatNumber(report.total_beneficiaries_reached)} reached</div>
                        <div className="table-secondary">{formatNumber(report.total_volunteers_involved)} volunteers | {formatCurrency(report.total_funds_used)}</div>
                      </td>
                      <td>
                        <div className="space-y-2">
                          {(report.highlights || []).map((highlight: string) => (
                            <p key={highlight} className="text-sm text-slate-600">{highlight}</p>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={pagination}
              itemLabel="report groups"
              onExport={() => exportRowsAsCsv("condensed-mission-reports", filteredReports.map((report: any) => ({
                event: report.event_name || "",
                reporting_period: report.reporting_period_label || report.reporting_period || "",
                campus_count: report.university_count || 0,
                update_count: report.update_count || 0,
                people_reached: report.total_beneficiaries_reached || 0,
                volunteers: report.total_volunteers_involved || 0,
                funds_used: report.total_funds_used || 0,
                latest_update: formatDate(report.latest_update_at),
                highlights: (report.highlights || []).join("; ")
              })))}
            />
          </>
        )}
      </Panel>
    </div>
  );
}
