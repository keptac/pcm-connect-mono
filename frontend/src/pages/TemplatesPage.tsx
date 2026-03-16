import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

export default function TemplatesPage() {
  const { user } = useAuthStore();
  if (!user?.roles?.some((r) => ["super_admin", "student_admin", "secretary"].includes(r))) {
    return <div className="card p-6">Access denied.</div>;
  }
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: ["templates"], queryFn: templatesApi.list });
  const [form, setForm] = useState({ name: "", version: "", columns: "metric,value,category" });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Templates</p>
        <h1 className="text-3xl">Report templates</h1>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className="card p-6">
          <h3 className="text-xl mb-4">Create template</h3>
          <form
            className="grid gap-3"
            onSubmit={async (event) => {
              event.preventDefault();
              await templatesApi.create({
                name: form.name,
                version: form.version,
                columns: form.columns.split(",").map((c) => c.trim())
              });
              client.invalidateQueries({ queryKey: ["templates"] });
            }}
          >
            <input className="border rounded-xl p-2" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <input className="border rounded-xl p-2" placeholder="Version" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} />
            <input className="border rounded-xl p-2" placeholder="Columns (comma-separated)" value={form.columns} onChange={(e) => setForm({ ...form, columns: e.target.value })} />
            <button className="btn-primary">Create</button>
          </form>
        </div>
        <div className="card p-6">
          <h3 className="text-xl mb-4">Available templates</h3>
          <div className="space-y-3">
            {data?.map((tpl: any) => (
              <div key={tpl.id} className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{tpl.name} v{tpl.version}</p>
                  <p className="text-xs text-slate-500">{tpl.columns.join(", ")}</p>
                </div>
                <a className="btn-outline" href={templatesApi.downloadUrl(tpl.id)}>
                  Download
                </a>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
