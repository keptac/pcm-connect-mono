import { useState } from "react";
import { reportsApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

type ProgramEntry = {
  name: string;
  description: string;
  visitors: number | "";
  baptisms: number | "";
  images: File[];
};

export default function ReportFormPage() {
  const { user } = useAuthStore();
  if (!user?.roles?.some((r) => ["super_admin", "student_admin"].includes(r))) {
    return <div className="card p-6">Access denied.</div>;
  }

  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [studentsCount, setStudentsCount] = useState("");
  const [programs, setPrograms] = useState<ProgramEntry[]>([
    { name: "", description: "", visitors: "", baptisms: "", images: [] }
  ]);
  const [message, setMessage] = useState("");

  function addProgram() {
    setPrograms([...programs, { name: "", description: "", visitors: "", baptisms: "", images: [] }]);
  }

  function updateProgram(index: number, data: Partial<ProgramEntry>) {
    const updated = [...programs];
    updated[index] = { ...updated[index], ...data };
    setPrograms(updated);
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Reporting</p>
        <h1 className="text-3xl">Submit report form</h1>
        <p className="text-sm text-slate-500">University is auto-scoped to your login.</p>
      </div>

      <div className="card p-6 space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <input type="date" className="border rounded-xl p-2" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          <input type="date" className="border rounded-xl p-2" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
        </div>
        <input
          className="border rounded-xl p-2"
          placeholder="Number of students"
          value={studentsCount}
          onChange={(e) => setStudentsCount(e.target.value)}
        />
      </div>

      <div className="space-y-4">
        {programs.map((program, index) => (
          <div key={index} className="card p-6 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-lg">Program / Event {index + 1}</h3>
            </div>
            <input
              className="border rounded-xl p-2"
              placeholder="Program name"
              value={program.name}
              onChange={(e) => updateProgram(index, { name: e.target.value })}
            />
            <textarea
              className="border rounded-xl p-2 h-24"
              placeholder="Program description"
              value={program.description}
              onChange={(e) => updateProgram(index, { description: e.target.value })}
            />
            <div className="grid md:grid-cols-2 gap-4">
              <input
                className="border rounded-xl p-2"
                placeholder="Number of visitors"
                value={program.visitors}
                onChange={(e) => updateProgram(index, { visitors: Number(e.target.value) || "" })}
              />
              <input
                className="border rounded-xl p-2"
                placeholder="Number of baptisms"
                value={program.baptisms}
                onChange={(e) => updateProgram(index, { baptisms: Number(e.target.value) || "" })}
              />
            </div>
            <div>
              <label className="text-sm text-slate-600">Program images</label>
              <input
                type="file"
                multiple
                className="border rounded-xl p-2 w-full"
                onChange={(e) => updateProgram(index, { images: Array.from(e.target.files || []) })}
              />
              {program.images.length > 0 && (
                <p className="text-xs text-slate-500 mt-2">
                  Selected: {program.images.map((img) => img.name).join(", ")}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <button className="btn-outline" onClick={addProgram}>Add program/event</button>
        <button
          className="btn-primary"
          onClick={async () => {
            const form = new FormData();
            form.append("period_start", periodStart);
            form.append("period_end", periodEnd);
            form.append("students_count", String(Number(studentsCount) || 0));
            form.append("programs_count", String(programs.length));

            const allImages: File[] = [];
            const programsWithIndices = programs.map((program) => {
              const image_indices: number[] = [];
              program.images.forEach((img) => {
                image_indices.push(allImages.length);
                allImages.push(img);
              });
              return {
                name: program.name,
                description: program.description,
                visitors: program.visitors || 0,
                baptisms: program.baptisms || 0,
                image_indices
              };
            });
            form.append("programs_json", JSON.stringify(programsWithIndices));
            allImages.forEach((img) => form.append("images", img));
            await reportsApi.submitForm(form);
            setMessage("Report submitted.");
          }}
        >
          Submit report
        </button>
        {message && <span className="text-sm text-green-600">{message}</span>}
      </div>
    </div>
  );
}
