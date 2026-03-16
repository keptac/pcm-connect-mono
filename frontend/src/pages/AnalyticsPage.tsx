import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

export default function AnalyticsPage() {
  const { user } = useAuthStore();
  if (!user?.roles?.some((r) => ["super_admin", "student_admin", "secretary"].includes(r))) {
    return <div className="card p-6">Access denied.</div>;
  }

  const [groupBy, setGroupBy] = useState("status");
  const [period, setPeriod] = useState("2026-01");
  const [reportId, setReportId] = useState("");
  const { data } = useQuery({ queryKey: ["analytics", groupBy], queryFn: () => analyticsApi.membership(groupBy) });
  const { data: compliance } = useQuery({ queryKey: ["compliance", period], queryFn: () => analyticsApi.compliance(period) });
  const { data: summary } = useQuery({
    queryKey: ["report-summary", reportId],
    queryFn: () => analyticsApi.reportSummary(Number(reportId)),
    enabled: !!reportId
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Analytics</p>
        <h1 className="text-3xl">Membership analytics</h1>
      </div>
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg">Group by</h3>
          <div className="flex items-center gap-3">
            <select className="border rounded-xl p-2" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
              <option value="status">Status</option>
              <option value="program">Program</option>
              <option value="university">University</option>
            </select>
            <button
              className="btn-outline"
              onClick={() => {
                if (!data?.length) return;
                const header = "label,count";
                const lines = data.map((item: any) => `${item.label},${item.count}`);
                const blob = new Blob([`${header}\n${lines.join("\n")}`], { type: "text/csv;charset=utf-8;" });
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = `membership_${groupBy}.csv`;
                link.click();
              }}
            >
              Export CSV
            </button>
          </div>
        </div>
        <div className="space-y-3">
          {data?.map((item: any) => (
            <div key={item.label} className="flex items-center justify-between border-b border-slate-100 pb-2">
              <p className="font-medium">{item.label}</p>
              <span className="text-sm text-slate-500">{item.count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-6">
          <h3 className="text-lg mb-4">Report compliance</h3>
          <input
            className="border rounded-xl p-2 mb-3 w-full"
            placeholder="YYYY-MM"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          />
          <p className="text-sm text-slate-500">Submitted: {compliance?.submitted?.length ?? 0}</p>
          <p className="text-sm text-slate-500">Missing: {compliance?.missing?.length ?? 0}</p>
          <div className="text-xs text-slate-400 mt-2">
            Missing IDs: {compliance?.missing?.join(", ") || "—"}
          </div>
        </div>
        <div className="card p-6">
          <h3 className="text-lg mb-4">Report summary</h3>
          <input
            className="border rounded-xl p-2 mb-3 w-full"
            placeholder="Uploaded report ID"
            value={reportId}
            onChange={(e) => setReportId(e.target.value)}
          />
          {summary && (
            <pre className="text-xs bg-slate-50 p-3 rounded-xl">{JSON.stringify(summary, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
