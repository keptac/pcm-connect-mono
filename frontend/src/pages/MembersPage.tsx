import { useDeferredValue, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Papa from "papaparse";

import { academicProgramsApi, analyticsApi, membersApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatDate, formatNumber } from "../lib/format";
import { useUniversityScope } from "../lib/universityScope";

const employmentOptions = [
  "Employed",
  "Not employed",
  "Entrepreneur",
  "Job seeking",
  "Further studies",
  "Volunteer service",
  "Other"
];

const memberTypes = ["Student", "Staff", "Alumni", "Volunteer", "Partner"];
const fullPeopleAccessRoles = ["super_admin", "program_manager", "finance_officer", "students_finance", "committee_member", "executive", "director"];

function buildInitialForm(defaultUniversityId?: number | null, defaultStatus = "Student") {
  return {
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    gender: "",
    university_id: defaultUniversityId ? String(defaultUniversityId) : "",
    program_of_study_id: "",
    start_year: "",
    expected_graduation_date: "",
    status: defaultStatus,
    employment_status: "",
    employer_name: "",
    current_city: "",
    active: true
  };
}

export default function MembersPage() {
  const client = useQueryClient();
  const { roles, canSelectUniversity, scopedUniversityId, defaultUniversityId, isUniversityScoped } = useUniversityScope();
  const canView = roles.some((role) => [...fullPeopleAccessRoles, "alumni_admin", "student_admin"].includes(role));
  const hasFullPeopleAccess = roles.some((role) => fullPeopleAccessRoles.includes(role));
  const hasAlumniAdmin = !hasFullPeopleAccess && roles.includes("alumni_admin");
  const hasStudentAdmin = !hasFullPeopleAccess && roles.includes("student_admin");
  const visibleMemberTypes = hasFullPeopleAccess
    ? memberTypes
    : Array.from(new Set([
        ...(hasStudentAdmin ? ["Student"] : []),
        ...(hasAlumniAdmin ? ["Alumni", "Student", "Staff"] : [])
      ]));
  const writableMemberTypes = hasFullPeopleAccess
    ? memberTypes
    : Array.from(new Set([
        ...(hasStudentAdmin ? ["Student"] : []),
        ...(hasAlumniAdmin ? ["Alumni"] : [])
      ]));
  const defaultMemberType = writableMemberTypes[0] || "Student";

  const { data: members } = useQuery({
    queryKey: ["members", scopedUniversityId],
    queryFn: () => membersApi.list(scopedUniversityId),
    enabled: canView
  });
  const { data: academicPrograms } = useQuery({
    queryKey: ["academic-programs", scopedUniversityId],
    queryFn: () => academicProgramsApi.list(scopedUniversityId),
    enabled: canView
  });
  const { data: universities } = useQuery({
    queryKey: ["universities"],
    queryFn: universitiesApi.list,
    enabled: canView
  });
  const { data: breakdown } = useQuery({
    queryKey: ["people-breakdown", scopedUniversityId],
    queryFn: () => analyticsApi.people("status", scopedUniversityId),
    enabled: canView
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState(() => buildInitialForm(defaultUniversityId, defaultMemberType));
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showForm, setShowForm] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [previewRows, setPreviewRows] = useState<any[]>([]);
  const [duplicateRows, setDuplicateRows] = useState<any[]>([]);

  const deferredSearch = useDeferredValue(search);

  const universityLookup = useMemo(
    () => Object.fromEntries((universities || []).map((university: any) => [university.id, university.name])),
    [universities]
  );
  const programOfStudyLookup = useMemo(
    () => Object.fromEntries((academicPrograms || []).map((program: any) => [program.id, program.name])),
    [academicPrograms]
  );
  const availableProgramsOfStudy = useMemo(() => {
    if (!form.university_id) return canSelectUniversity ? [] : academicPrograms || [];
    return (academicPrograms || []).filter((program: any) => program.university_id === Number(form.university_id));
  }, [academicPrograms, canSelectUniversity, form.university_id]);

  const filteredMembers = useMemo(() => {
    const source = members || [];
    return source.filter((member: any) => {
      const haystack = [
        member.first_name,
        member.last_name,
        member.email,
        member.phone,
        member.status,
        member.program_of_study_name,
        member.employment_status,
        member.employer_name,
        member.current_city
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const matchesSearch = haystack.includes(deferredSearch.toLowerCase());
      const matchesStatus = statusFilter === "all" || member.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [deferredSearch, members, statusFilter]);
  const membersPagination = usePagination(filteredMembers);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  function resetForm() {
    setSelectedId(null);
    setForm(buildInitialForm(defaultUniversityId, defaultMemberType));
  }

  function openCreateForm() {
    resetForm();
    setShowForm(true);
    setShowUpload(false);
  }

  function hydrateForm(member: any) {
    setSelectedId(member.id);
    setForm({
      first_name: member.first_name || "",
      last_name: member.last_name || "",
      email: member.email || "",
      phone: member.phone || "",
      gender: member.gender || "",
      university_id: String(member.university_id || ""),
      program_of_study_id: member.program_of_study_id ? String(member.program_of_study_id) : "",
      start_year: member.start_year ? String(member.start_year) : "",
      expected_graduation_date: member.expected_graduation_date || "",
      status: member.status || "Student",
      employment_status: member.employment_status || "",
      employer_name: member.employer_name || "",
      current_city: member.current_city || "",
      active: member.active ?? true
    });
    setShowForm(true);
    setShowUpload(false);
  }

  function runDuplicateCheck(rows: any[]) {
    const seen = new Set<string>();
    const duplicates: any[] = [];
    rows.forEach((row) => {
      const key = `${row.first_name || ""}-${row.last_name || ""}-${row.email || ""}-${row.phone || ""}`.toLowerCase();
      if (seen.has(key)) duplicates.push(row);
      seen.add(key);
    });
    setDuplicateRows(duplicates);
  }

  const totalCount = members?.length || 0;
  const studentCount = members?.filter((member: any) => member.status === "Student").length || 0;
  const staffCount = members?.filter((member: any) => member.status === "Staff").length || 0;
  const alumniCount = members?.filter((member: any) => member.status === "Alumni").length || 0;
  const employedAlumniCount =
    members?.filter((member: any) => member.status === "Alumni" && member.employment_status === "Employed").length || 0;

  const statusOptions = Array.from(new Set((members || []).map((member: any) => member.status).filter(Boolean)));
  const showAlumniFields = form.status === "Alumni";
  const isMemberTypeLocked = writableMemberTypes.length === 1;
  const canWriteMemberType = (status?: string | null) => hasFullPeopleAccess || writableMemberTypes.includes(status || "Student");
  const lockedUniversityName =
    universities?.find((university: any) => university.id === Number(form.university_id || defaultUniversityId))?.name || "Your university or campus";

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="People operations"
        title="Cross-campus people registry"
        description="Manage students, staff, alumni, volunteers, and partners across all campuses, with academic programs of study and optional alumni destination tracking."
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <MetricCard label="Total people" value={formatNumber(totalCount)} helper="All records in the network register" />
        <MetricCard label="Students" value={formatNumber(studentCount)} tone="gold" helper="Current student cohort in view" />
        <MetricCard label="Staff" value={formatNumber(staffCount)} tone="coral" helper="Campus staff and coordinators" />
        <MetricCard label="Alumni outcomes" value={formatNumber(alumniCount)} tone="ink" helper={`${formatNumber(employedAlumniCount)} marked employed`} />
      </div>

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">People registry</p>
            <h3 className="text-xl font-semibold text-slate-950">All members across campuses</h3>
            <p className="mt-2 text-sm text-slate-600">Add individuals or import a campus roster, then manage students, staff, and alumni from one table.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="primary-button" type="button" onClick={openCreateForm}>
              Add member
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                setShowUpload((current) => !current);
                setShowForm(false);
              }}
            >
              Bulk upload
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {["all", ...visibleMemberTypes].map((value) => (
            <button
              key={value}
              className={statusFilter === value ? "primary-button" : "secondary-button"}
              type="button"
              onClick={() => setStatusFilter(value)}
            >
              {value === "all" ? "All people" : value}
            </button>
          ))}
        </div>

        <ModalDialog
          open={showForm}
          onClose={() => {
            setShowForm(false);
            resetForm();
          }}
          className="modal-shell-page"
        >
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="eyebrow">Member editor</p>
                <h4 className="text-lg font-semibold text-slate-950">{selectedId ? "Update member" : "Create member"}</h4>
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
              >
                Close
              </button>
            </div>

            <form
              className="grid gap-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const payload = {
                  ...form,
                  status: isMemberTypeLocked ? defaultMemberType : form.status,
                  university_id: Number(form.university_id),
                  program_of_study_id: form.program_of_study_id ? Number(form.program_of_study_id) : null,
                  start_year: form.start_year ? Number(form.start_year) : null,
                  expected_graduation_date: form.expected_graduation_date || null,
                  employment_status: showAlumniFields ? form.employment_status || null : null,
                  employer_name: showAlumniFields ? form.employer_name || null : null,
                  current_city: showAlumniFields ? form.current_city || null : null
                };

                if (selectedId) {
                  await membersApi.update(selectedId, payload);
                } else {
                  await membersApi.create(payload);
                }

                await client.invalidateQueries({ queryKey: ["members"] });
                await client.invalidateQueries({ queryKey: ["people-breakdown"] });
                await client.invalidateQueries({ queryKey: ["analytics-overview"] });
                resetForm();
                setShowForm(false);
              }}
            >
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <label className="field-shell">
                  <span className="field-label">First name</span>
                  <input className="field-input" value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Last name</span>
                  <input className="field-input" value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Email</span>
                  <input className="field-input" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Phone</span>
                  <input className="field-input" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {canSelectUniversity ? (
                  <label className="field-shell">
                    <span className="field-label">University / campus</span>
                    <select className="field-input" value={form.university_id} onChange={(event) => setForm({ ...form, university_id: event.target.value, program_of_study_id: "" })}>
                      <option value="">Select university or campus</option>
                      {universities?.map((university: any) => (
                        <option key={university.id} value={university.id}>{university.name}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="field-shell">
                    <span className="field-label">University / campus</span>
                    <div className="field-input flex items-center text-slate-600">{lockedUniversityName}</div>
                  </div>
                )}
                <label className="field-shell">
                  <span className="field-label">Program of study</span>
                  <select
                    className="field-input"
                    value={form.program_of_study_id}
                    disabled={canSelectUniversity && !form.university_id}
                    onChange={(event) => setForm({ ...form, program_of_study_id: event.target.value })}
                  >
                    <option value="">{canSelectUniversity && !form.university_id ? "Select university or campus first" : "Unassigned"}</option>
                    {availableProgramsOfStudy.map((program: any) => (
                      <option key={program.id} value={program.id}>{program.name}</option>
                    ))}
                  </select>
                </label>
                {isMemberTypeLocked ? (
                  <div className="field-shell">
                    <span className="field-label">Member type</span>
                    <div className="field-input flex items-center text-slate-600">{defaultMemberType}</div>
                  </div>
                ) : (
                  <label className="field-shell">
                    <span className="field-label">Member type</span>
                    <select className="field-input" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                      {writableMemberTypes.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="field-shell">
                  <span className="field-label">Gender</span>
                  <input className="field-input" value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })} />
                </label>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <label className="field-shell">
                  <span className="field-label">Start year</span>
                  <input className="field-input" value={form.start_year} onChange={(event) => setForm({ ...form, start_year: event.target.value })} />
                </label>
                <label className="field-shell">
                  <span className="field-label">Expected graduation / exit</span>
                  <input className="field-input" type="date" value={form.expected_graduation_date} onChange={(event) => setForm({ ...form, expected_graduation_date: event.target.value })} />
                </label>
                <label className="field-shell field-checkbox">
                  <span className="field-label">Active in system</span>
                  <input type="checkbox" checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} />
                </label>
              </div>

              {showAlumniFields ? (
                <div className="grid gap-4 rounded-[12px] border border-amber-200 bg-amber-50/70 p-4 md:grid-cols-3">
                  <label className="field-shell">
                    <span className="field-label">Employment status</span>
                    <select className="field-input" value={form.employment_status} onChange={(event) => setForm({ ...form, employment_status: event.target.value })}>
                      <option value="">Optional</option>
                      {employmentOptions.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Employer / business</span>
                    <input className="field-input" value={form.employer_name} onChange={(event) => setForm({ ...form, employer_name: event.target.value })} placeholder="Optional" />
                  </label>
                  <label className="field-shell">
                    <span className="field-label">Current city / location</span>
                    <input className="field-input" value={form.current_city} onChange={(event) => setForm({ ...form, current_city: event.target.value })} placeholder="Optional" />
                  </label>
                </div>
              ) : null}

              <div className="flex flex-wrap items-center gap-3">
                <button className="primary-button" type="submit">{selectedId ? "Save changes" : "Create member"}</button>
                <button className="secondary-button" type="button" onClick={resetForm}>Reset</button>
              </div>
            </form>
          </div>
        </ModalDialog>

        {showUpload ? (
          <div className="rounded-[12px] border border-slate-200/80 bg-white/80 p-5">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="eyebrow">Bulk upload</p>
                <h4 className="text-lg font-semibold text-slate-950">Import people from CSV</h4>
              </div>
              <button className="secondary-button" type="button" onClick={() => setShowUpload(false)}>
                Close
              </button>
            </div>

            <label className="field-shell">
              <span className="field-label">CSV file</span>
              <input
                className="field-input"
                type="file"
                accept=".csv"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  Papa.parse(file, {
                    header: true,
                    complete: (results) => {
                      const rows = results.data as any[];
                      setPreviewRows(rows);
                      runDuplicateCheck(rows);
                    }
                  });
                }}
              />
            </label>

            <div className="mt-4 rounded-[12px] bg-slate-50 px-5 py-4 text-sm text-slate-600">
              Include columns such as <code>first_name</code>, <code>last_name</code>, <code>email</code>, <code>status</code>, and optional fields like <code>program_of_study_name</code>, <code>program_of_study_id</code>, <code>employment_status</code>, <code>employer_name</code>, and <code>current_city</code>.
              {isUniversityScoped ? (
                <> Your university or campus is picked automatically from your login.</>
              ) : (
                <> Add <code>university_id</code> when uploading a cross-campus file.</>
              )}
              {!hasFullPeopleAccess ? (
                <> Member type will be assigned automatically as <code>{defaultMemberType}</code> for your role.</>
              ) : null}
            </div>

            {previewRows.length > 0 ? (
              <div className="mt-5 space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[14px] bg-amber-50 px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-amber-900/65">Preview rows</p>
                    <p className="mt-2 text-2xl font-semibold text-amber-950">{formatNumber(previewRows.length)}</p>
                  </div>
                  <div className="rounded-[14px] bg-rose-50 px-4 py-4">
                    <p className="text-xs uppercase tracking-[0.18em] text-rose-900/65">Potential duplicates</p>
                    <p className="mt-2 text-2xl font-semibold text-rose-950">{formatNumber(duplicateRows.length)}</p>
                  </div>
                </div>
                <button
                  className="primary-button"
                  onClick={async () => {
                    const fileInput = document.querySelector<HTMLInputElement>("input[type='file']");
                    const file = fileInput?.files?.[0];
                    if (!file) return;
                    await membersApi.bulkUpload(file);
                    await client.invalidateQueries({ queryKey: ["members"] });
                    await client.invalidateQueries({ queryKey: ["people-breakdown"] });
                    await client.invalidateQueries({ queryKey: ["analytics-overview"] });
                    setPreviewRows([]);
                    setDuplicateRows([]);
                    setShowUpload(false);
                  }}
                >
                  Upload records
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="field-shell">
              <span className="field-label">Search</span>
              <input className="field-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email, phone, employer, city" />
            </label>
            <label className="field-shell">
              <span className="field-label">Type filter</span>
              <select className="field-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All people</option>
                {statusOptions.map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="text-sm text-slate-500">{formatNumber(filteredMembers.length)} people showing</div>
        </div>

        {filteredMembers.length === 0 ? (
          <EmptyState
            title="No people match this filter"
            description="Change the filters, add a person, or import a CSV to populate the registry."
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Person</th>
                    <th>Campus</th>
                    <th>Program of Study</th>
                    <th>Type</th>
                    <th>Employment</th>
                    <th>Location</th>
                    <th>Updated</th>
                    {writableMemberTypes.length > 0 ? <th>Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {membersPagination.pageItems.map((member: any) => (
                    <tr key={member.id}>
                      <td>
                        <div className="table-primary">{member.first_name} {member.last_name}</div>
                        <div className="table-secondary">{member.email || member.phone || "No contact"}</div>
                      </td>
                      <td>
                        <div className="table-primary">{universityLookup[member.university_id] || `#${member.university_id}`}</div>
                      </td>
                      <td>
                        <div className="table-primary">
                          {member.program_of_study_name || (member.program_of_study_id ? (programOfStudyLookup[member.program_of_study_id] || `#${member.program_of_study_id}`) : "Unassigned")}
                        </div>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-2">
                          <StatusBadge label={member.status || "Unknown"} tone={member.active ? "success" : "warning"} />
                          {!member.active ? <StatusBadge label="Inactive" tone="warning" /> : null}
                        </div>
                      </td>
                      <td>
                        <div className="table-primary">{member.employment_status || "Not captured"}</div>
                        <div className="table-secondary">{member.employer_name || " "}</div>
                      </td>
                      <td>
                        <div className="table-primary">{member.current_city || "Not captured"}</div>
                      </td>
                      <td>
                        <div className="table-primary">{formatDate(member.updated_at)}</div>
                      </td>
                      {writableMemberTypes.length > 0 ? (
                        <td>
                          {canWriteMemberType(member.status) ? (
                            <div className="flex flex-wrap gap-2">
                              <TableActionButton label="Edit member" tone="edit" onClick={() => hydrateForm(member)} />
                              <button
                                className="secondary-button"
                                type="button"
                                onClick={async () => {
                                  await membersApi.update(member.id, { active: !member.active });
                                  await client.invalidateQueries({ queryKey: ["members"] });
                                  await client.invalidateQueries({ queryKey: ["analytics-overview"] });
                                }}
                              >
                                {member.active ? "Deactivate" : "Reactivate"}
                              </button>
                              <TableActionButton
                                label="Delete member"
                                tone="delete"
                                onClick={async () => {
                                  await membersApi.delete(member.id);
                                  await client.invalidateQueries({ queryKey: ["members"] });
                                  await client.invalidateQueries({ queryKey: ["people-breakdown"] });
                                  await client.invalidateQueries({ queryKey: ["analytics-overview"] });
                                }}
                              />
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">Read only</span>
                          )}
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={membersPagination}
              itemLabel="people"
              onExport={() => exportRowsAsCsv("people-registry", filteredMembers.map((member: any) => ({
                first_name: member.first_name || "",
                last_name: member.last_name || "",
                email: member.email || "",
                phone: member.phone || "",
                gender: member.gender || "",
                university_or_campus: universityLookup[member.university_id] || `University #${member.university_id}`,
                program_of_study: member.program_of_study_name || (member.program_of_study_id ? (programOfStudyLookup[member.program_of_study_id] || `#${member.program_of_study_id}`) : ""),
                member_type: member.status || "",
                start_year: member.start_year || "",
                expected_graduation_or_exit: member.expected_graduation_date || "",
                employment_status: member.employment_status || "",
                employer_name: member.employer_name || "",
                current_city: member.current_city || "",
                active: member.active ? "active" : "inactive",
                updated_at: formatDate(member.updated_at)
              })))}
            />
          </>
        )}
      </Panel>
    </div>
  );
}
