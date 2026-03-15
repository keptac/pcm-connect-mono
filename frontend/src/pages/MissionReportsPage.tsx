import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { programUpdatesApi, reportingPeriodsApi } from "../api/endpoints";
import { EmptyState, MetricCard, PageHeader, Panel, StatusBadge, TablePagination, usePagination } from "../components/ui";
import { formatCurrency, formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const missionReportRoles = ["general_user"];

export default function MissionReportsPage() {
  const { roles, scopedUniversityId } = useUniversityScope();
  const canView = roles.some((role) => missionReportRoles.includes(role));
  const [periodFilter, setPeriodFilter] = useState("all");

  const { data: reportingPeriods } = useQuery({
    queryKey: ["reporting-periods", true],
    queryFn: () => reportingPeriodsApi.list(true),
    enabled: canView
  });
  const { data: reports } = useQuery({
    queryKey: ["condensed-mission-reports", scopedUniversityId, periodFilter],
    queryFn: () => programUpdatesApi.condensed({
      universityId: scopedUniversityId,
      reportingPeriod: periodFilter === "all" ? undefined : periodFilter
    }),
    enabled: canView
  });

  const pagination = usePagination(reports);
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
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Consolidated view</p>
            <h3 className="text-xl font-semibold text-slate-950">Mandatory-program highlights</h3>
          </div>
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

        {!reports?.length ? (
          <EmptyState
            title="No condensed mission reports found"
            description="Once campuses file mandatory-program updates, the consolidated highlights will appear here."
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
            <TablePagination pagination={pagination} itemLabel="report groups" />
          </>
        )}
      </Panel>
    </div>
  );
}
