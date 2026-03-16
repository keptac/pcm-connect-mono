import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { reportsApi, templatesApi, universitiesApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

export default function UploadReportPage() {
  const { user } = useAuthStore();
  if (!user?.roles?.some((r) => ["super_admin", "student_admin", "secretary"].includes(r))) {
    return <div className="card p-6">Access denied.</div>;
  }
  const client = useQueryClient();
  const { data: templates } = useQuery({ queryKey: ["templates"], queryFn: templatesApi.list });
  const { data: universities } = useQuery({ queryKey: ["universities"], queryFn: universitiesApi.list });
  const [file, setFile] = useState<File | null>(null);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [universityId, setUniversityId] = useState("");

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Reporting</p>
        <h1 className="text-3xl">Upload report</h1>
      </div>
      <div className="card p-6 space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <input type="date" className="border rounded-xl p-2" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          <input type="date" className="border rounded-xl p-2" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <select className="border rounded-xl p-2" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
            <option value="">Template</option>
            {templates?.map((tpl: any) => (
              <option key={tpl.id} value={tpl.id}>{tpl.name} v{tpl.version}</option>
            ))}
          </select>
          <select className="border rounded-xl p-2" value={universityId} onChange={(e) => setUniversityId(e.target.value)}>
            <option value="">University</option>
            {universities?.map((uni: any) => (
              <option key={uni.id} value={uni.id}>{uni.name}</option>
            ))}
          </select>
        </div>
        <input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button
          className="btn-primary"
          onClick={async () => {
            if (!file) return;
            await reportsApi.upload({
              period_start: periodStart,
              period_end: periodEnd,
              template_id: templateId ? Number(templateId) : undefined,
              university_id: universityId ? Number(universityId) : undefined,
              file
            });
            client.invalidateQueries({ queryKey: ["reports"] });
          }}
        >
          Upload report
        </button>
      </div>
    </div>
  );
}
