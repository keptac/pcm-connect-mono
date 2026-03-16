import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";

import { conferencesApi, universitiesApi } from "../api/endpoints";
import { EmptyState, MetricCard, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, TableSearchField, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { formatNumber } from "../lib/format";
import { matchesTableSearch } from "../lib/tableSearch";
import { useUniversityScope } from "../lib/universityScope";
import { useAuthStore } from "../store/auth";

const initialForm = {
  name: "",
  short_code: "",
  country: "",
  city: "",
  region: "",
  conference_id: "",
  mission_focus: "",
  contact_name: "",
  contact_email: "",
  contact_phone: "",
  is_active: true
};

export default function UniversitiesPage() {
  const client = useQueryClient();
  const { user } = useAuthStore();
  const { scopeKey, scopeParams } = useUniversityScope();
  const roles = user?.roles || [];
  const canView = roles.includes("super_admin");
  const canCreate = roles.includes("super_admin");

  const { data: universities } = useQuery({
    queryKey: ["universities", scopeKey],
    queryFn: () => universitiesApi.list(scopeParams),
    enabled: canView
  });
  const { data: conferences } = useQuery({
    queryKey: ["conferences"],
    queryFn: () => conferencesApi.list(true),
    enabled: canView
  });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [deleteError, setDeleteError] = useState("");
  const [isDeletingId, setIsDeletingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");

  const currentList = useMemo(() => {
    if (roles.includes("super_admin")) return universities || [];
    return (universities || []).filter((item: any) => item.id === user?.university_id);
  }, [roles, universities, user?.university_id]);
  const filteredUniversities = useMemo(() => {
    return currentList.filter((university: any) => matchesTableSearch(search, [
      university.name,
      university.short_code,
      university.conference_name,
      university.union_name,
      university.city,
      university.country,
      university.region,
      university.mission_focus,
      university.contact_name,
      university.contact_email,
      university.contact_phone,
      university.program_count,
      university.member_count,
      university.is_active ? "active" : "inactive"
    ]));
  }, [currentList, search]);
  const universitiesPagination = usePagination(filteredUniversities);

  if (!canView) {
    return <Navigate to="/" replace />;
  }

  function hydrateForm(university: any) {
    setSelectedId(university.id);
    setForm({
      name: university.name || "",
      short_code: university.short_code || "",
      country: university.country || "",
      city: university.city || "",
      region: university.region || "",
      conference_id: university.conference_id ? String(university.conference_id) : "",
      mission_focus: university.mission_focus || "",
      contact_name: university.contact_name || "",
      contact_email: university.contact_email || "",
      contact_phone: university.contact_phone || "",
      is_active: university.is_active ?? true
    });
    setIsFormOpen(true);
  }

  function resetForm() {
    setSelectedId(null);
    setForm(initialForm);
  }

  function closeForm() {
    setIsFormOpen(false);
    resetForm();
  }

  function closeDeleteError() {
    setDeleteError("");
    setIsDeletingId(null);
  }

  function openCreateForm() {
    resetForm();
    setIsFormOpen(true);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Campus directory"
        title="Universities and campuses"
        description="Maintain the profile for each university, campus, or regional unit, including conference, union, location, mission focus, and the primary contact person."
        actions={canCreate ? (
          <button className="primary-button" type="button" onClick={openCreateForm}>
            Enrol university or campus
          </button>
        ) : undefined}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <MetricCard label="Units listed" value={formatNumber(currentList.length)} helper="Visible within your access scope" />
        <MetricCard label="Active units" value={formatNumber(currentList.filter((item: any) => item.is_active).length)} tone="gold" helper="Ready for reporting and portfolio updates" />
        <MetricCard label="Conferences in scope" value={formatNumber(new Set(currentList.map((item: any) => item.conference_name).filter(Boolean)).size)} tone="ink" helper="Conference coverage across visible campuses" />
      </div>

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Directory table</p>
            <h3 className="text-xl font-semibold text-slate-950">Profiles in the network</h3>
          </div>
          <TableSearchField
            value={search}
            onChange={setSearch}
            placeholder="Search campus, conference, union, location, or contact"
          />
        </div>

        {filteredUniversities.length === 0 ? (
          <EmptyState
            title={currentList.length ? "No universities or campuses match this search" : "No universities or campuses found"}
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>University / Campus</th>
                    <th>Conference / Union</th>
                    <th>Location</th>
                    <th>Programs</th>
                    <th>People</th>
                    <th>Contact</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {universitiesPagination.pageItems.map((university: any) => (
                    <tr key={university.id}>
                      <td>
                        <div className="table-primary">{university.name}</div>
                        <div className="table-secondary">{university.short_code || "No short code"}</div>
                        <div className="table-secondary">{university.mission_focus || "Mission focus not set."}</div>
                      </td>
                      <td>
                        <div className="table-primary">{university.conference_name || "Conference not set"}</div>
                        <div className="table-secondary">{university.union_name || "Union not set"}</div>
                      </td>
                      <td>
                        <div className="table-primary">{university.city || "City not set"}</div>
                        <div className="table-secondary">{university.country || "Country not set"} / {university.region || "Region not set"}</div>
                      </td>
                      <td>{formatNumber(university.program_count)}</td>
                      <td>{formatNumber(university.member_count)}</td>
                      <td>
                        <div className="table-primary">{university.contact_name || "Not assigned"}</div>
                        <div className="table-secondary">{university.contact_email || "No email"} / {university.contact_phone || "No phone"}</div>
                      </td>
                      <td>
                        <StatusBadge label={university.is_active ? "active" : "inactive"} tone={university.is_active ? "success" : "warning"} />
                      </td>
                      <td>
                        <div className="table-actions">
                          <TableActionButton label="Edit campus" tone="edit" onClick={() => hydrateForm(university)} />
                          {canCreate ? (
                            <TableActionButton
                              label="Delete campus"
                              tone="delete"
                              disabled={isDeletingId === university.id}
                              onClick={async () => {
                                if (!window.confirm(`Delete ${university.name}? This cannot be undone.`)) return;
                                setIsDeletingId(university.id);
                                try {
                                  await universitiesApi.delete(university.id);
                                  await client.invalidateQueries({ queryKey: ["universities"] });
                                } catch (error: any) {
                                  setDeleteError(error?.response?.data?.detail || "Unable to delete this university or campus right now.");
                                } finally {
                                  setIsDeletingId((current) => (current === university.id ? null : current));
                                }
                              }}
                            />
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={universitiesPagination}
              itemLabel="campuses"
              onExport={() => exportRowsAsCsv("universities-and-campuses", filteredUniversities.map((university: any) => ({
                university_or_campus: university.name,
                short_code: university.short_code || "",
                conference: university.conference_name || "",
                union: university.union_name || "",
                city: university.city || "",
                country: university.country || "",
                region: university.region || "",
                mission_focus: university.mission_focus || "",
                program_count: university.program_count || 0,
                member_count: university.member_count || 0,
                contact_name: university.contact_name || "",
                contact_email: university.contact_email || "",
                contact_phone: university.contact_phone || "",
                status: university.is_active ? "active" : "inactive"
              })))}
            />
          </>
        )}
      </Panel>

      <ModalDialog open={isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">{canCreate ? "Campus editor" : "Profile editor"}</p>
              <h3 className="text-xl font-semibold text-slate-950">
                {selectedId ? "Update campus profile" : canCreate ? "Enrol university or campus" : "View your campus profile"}
              </h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              const payload = {
                ...form,
                conference_id: form.conference_id ? Number(form.conference_id) : null
              };
              if (selectedId) {
                await universitiesApi.update(selectedId, payload);
              } else if (canCreate) {
                await universitiesApi.create(payload);
              } else {
                return;
              }
              await client.invalidateQueries({ queryKey: ["universities"] });
              closeForm();
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <label className="field-shell">
                <span className="field-label">University or campus name</span>
                <input className="field-input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Short code</span>
                <input className="field-input" value={form.short_code} onChange={(event) => setForm({ ...form, short_code: event.target.value })} />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {canCreate ? (
                <label className="field-shell">
                  <span className="field-label">Conference</span>
                  <select className="field-input" value={form.conference_id} onChange={(event) => setForm({ ...form, conference_id: event.target.value })} required>
                    <option value="">Select conference</option>
                    {conferences?.map((conference: any) => (
                      <option key={conference.id} value={conference.id}>
                        {conference.name} / {conference.union_name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="field-shell">
                  <span className="field-label">Conference</span>
                  <div className="field-input flex items-center text-slate-600">
                    {currentList.find((item: any) => item.id === (selectedId || user?.university_id))?.conference_name || "Conference not set"}
                  </div>
                </div>
              )}
              <div className="field-shell">
                <span className="field-label">Union</span>
                <div className="field-input flex items-center text-slate-600">
                  {conferences?.find((conference: any) => String(conference.id) === form.conference_id)?.union_name ||
                    currentList.find((item: any) => item.id === (selectedId || user?.university_id))?.union_name ||
                    "Union not set"}
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Country</span>
                <input className="field-input" value={form.country} onChange={(event) => setForm({ ...form, country: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">City</span>
                <input className="field-input" value={form.city} onChange={(event) => setForm({ ...form, city: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Region</span>
                <input className="field-input" value={form.region} onChange={(event) => setForm({ ...form, region: event.target.value })} />
              </label>
            </div>

            <label className="field-shell">
              <span className="field-label">Mission focus</span>
              <textarea className="field-input min-h-[120px]" value={form.mission_focus} onChange={(event) => setForm({ ...form, mission_focus: event.target.value })} />
            </label>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="field-shell">
                <span className="field-label">Primary contact</span>
                <input className="field-input" value={form.contact_name} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Contact email</span>
                <input className="field-input" value={form.contact_email} onChange={(event) => setForm({ ...form, contact_email: event.target.value })} />
              </label>
              <label className="field-shell">
                <span className="field-label">Contact phone</span>
                <input className="field-input" value={form.contact_phone} onChange={(event) => setForm({ ...form, contact_phone: event.target.value })} />
              </label>
            </div>

            <label className="field-shell field-checkbox">
              <span className="field-label">Active in network</span>
              <input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />
            </label>

            <div className="flex flex-wrap gap-3">
              <button className="primary-button" type="submit">
                {selectedId ? "Save campus profile" : canCreate ? "Enrol university or campus" : "Save profile"}
              </button>
              <button className="secondary-button" type="button" onClick={resetForm}>Reset</button>
            </div>
          </form>
        </div>
      </ModalDialog>

      <ModalDialog open={Boolean(deleteError)} onClose={closeDeleteError}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Delete blocked</p>
              <h3 className="text-xl font-semibold text-slate-950">University or campus could not be deleted</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeDeleteError}>Close</button>
          </div>

          <div className="rounded-[16px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {deleteError}
          </div>

          <div className="flex flex-wrap gap-3">
            <button className="primary-button" type="button" onClick={closeDeleteError}>OK</button>
          </div>
        </div>
      </ModalDialog>
    </div>
  );
}
