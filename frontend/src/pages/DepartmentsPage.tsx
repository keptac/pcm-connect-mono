import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { departmentsApi, universitiesApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

export default function DepartmentsPage() {
  const { user } = useAuthStore();
  if (!user?.roles?.includes("super_admin")) {
    return <div className="card p-6">Admin access required.</div>;
  }
  const client = useQueryClient();
  const { data: departments } = useQuery({ queryKey: ["departments"], queryFn: departmentsApi.list });
  const { data: universities } = useQuery({ queryKey: ["universities"], queryFn: universitiesApi.list });
  const [form, setForm] = useState({ name: "", university_id: "" });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Admin</p>
        <h1 className="text-3xl">Departments</h1>
      </div>
      <div className="grid md:grid-cols-[1fr_1.2fr] gap-6">
        <div className="card p-6">
          <h3 className="text-lg mb-4">Add department</h3>
          <form
            className="grid gap-3"
            onSubmit={async (event) => {
              event.preventDefault();
              await departmentsApi.create({ name: form.name, university_id: Number(form.university_id) });
              client.invalidateQueries({ queryKey: ["departments"] });
            }}
          >
            <input className="border rounded-xl p-2" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <select className="border rounded-xl p-2" value={form.university_id} onChange={(e) => setForm({ ...form, university_id: e.target.value })}>
              <option value="">University</option>
              {universities?.map((uni: any) => (
                <option key={uni.id} value={uni.id}>{uni.name}</option>
              ))}
            </select>
            <button className="btn-primary">Create</button>
          </form>
        </div>
        <div className="card p-6">
          <h3 className="text-lg mb-4">Existing departments</h3>
          <div className="space-y-3">
            {departments?.map((dept: any) => (
              <div key={dept.id} className="flex items-center justify-between border-b border-slate-100 pb-2">
                <p className="font-medium">{dept.name}</p>
                <span className="text-xs text-slate-400">University #{dept.university_id}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
