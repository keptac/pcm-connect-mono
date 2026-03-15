import { useAuthStore } from "../store/auth";

export default function FinancialReportsPage() {
  const { user } = useAuthStore();
  if (!user?.roles?.some((r) => ["super_admin", "student_admin"].includes(r))) {
    return <div className="card p-6">Access denied.</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Reporting</p>
        <h1 className="text-3xl">Financial reporting</h1>
        <p className="text-sm text-slate-500">Configure and submit financial reports for each reporting period.</p>
      </div>
      <div className="card p-6">
        <p className="text-slate-600">Financial reporting module is ready for your specific fields (income, expenses, offerings, outreach costs, etc.). Tell me which fields to include and I will wire them up.</p>
      </div>
    </div>
  );
}
