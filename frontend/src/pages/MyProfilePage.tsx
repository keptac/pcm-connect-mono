import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { membersApi } from "../api/endpoints";
import { PageHeader, Panel, StatusBadge } from "../components/ui";
import { useAuthStore } from "../store/auth";

const employmentOptions = [
  "Employed",
  "Not employed",
  "Entrepreneur",
  "Job seeking",
  "Further studies",
  "Volunteer service",
  "Other"
];

function buildInitialForm(profile?: any) {
  return {
    employment_status: profile?.employment_status || "",
    employer_name: profile?.employer_name || "",
    current_city: profile?.current_city || "",
    services_offered: profile?.services_offered || "",
    products_supplied: profile?.products_supplied || ""
  };
}

export default function MyProfilePage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const { user } = useAuthStore();
  const canView = Boolean(user?.member_id);

  const [form, setForm] = useState(() => buildInitialForm());
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const profileQuery = useQuery({
    queryKey: ["member-self-profile"],
    queryFn: membersApi.myProfile,
    enabled: canView
  });

  const profile = profileQuery.data;

  useEffect(() => {
    if (profile) {
      setForm(buildInitialForm(profile));
    }
  }, [profile]);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">No member-linked profile is available for this account.</p></Panel>;
  }

  const currentForm = form;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Member profile"
        title="My profile"
        description="Keep your PCM profile current so alumni networking and the marketplace can surface your employment status, services, and products accurately."
      />

      {profile ? (
        <div className="grid gap-6 xl:grid-cols-[1.1fr_1.4fr]">
          <Panel className="space-y-4">
            <div>
              <p className="eyebrow">Profile snapshot</p>
              <h3 className="text-xl font-semibold text-slate-950">{profile.first_name} {profile.last_name}</h3>
            </div>

            <div className="space-y-2 text-sm text-slate-600">
              <p><span className="font-medium text-slate-800">Member ID:</span> {profile.member_id || "Not assigned"}</p>
              <p><span className="font-medium text-slate-800">University / campus:</span> {user?.member_university_name || `University #${profile.university_id}`}</p>
              <p><span className="font-medium text-slate-800">Joined:</span> {profile.start_year || "Not captured"}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <StatusBadge label={profile.status} tone={profile.status === "Student" ? "warning" : "info"} />
              <StatusBadge label={profile.employment_status || "Employment not set"} tone={profile.employment_status ? "success" : "neutral"} />
            </div>

            <div className="rounded-[16px] border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <p className="font-medium text-slate-900">Marketplace readiness</p>
              <p className="mt-2">Your services and products help other PCM members find you faster when posting needs or browsing offers.</p>
              <button className="secondary-button mt-4" type="button" onClick={() => navigate("/marketplace")}>
                Open marketplace
              </button>
            </div>
          </Panel>

          <Panel className="space-y-5">
            <div>
              <p className="eyebrow">Editable details</p>
              <h3 className="text-xl font-semibold text-slate-950">Update marketplace-facing information</h3>
            </div>

            <form
              className="grid gap-4"
              onSubmit={async (event) => {
                event.preventDefault();
                setIsSaving(true);
                setMessage("");
                setError("");
                try {
                  const saved = await membersApi.updateMyProfile(currentForm);
                  setForm(buildInitialForm(saved));
                  setMessage("Your profile has been updated.");
                  await client.invalidateQueries({ queryKey: ["member-self-profile"] });
                  await client.invalidateQueries({ queryKey: ["marketplace"] });
                } catch (err: any) {
                  setError(err?.response?.data?.detail || "Unable to save your profile.");
                } finally {
                  setIsSaving(false);
                }
              }}
            >
              <label className="field-shell">
                <span className="field-label">Employment status</span>
                <select
                  className="field-input"
                  value={currentForm.employment_status}
                  onChange={(event) => setForm((value) => ({ ...value, employment_status: event.target.value }))}
                >
                  <option value="">Select employment status</option>
                  {employmentOptions.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </label>

              <div className="grid gap-4 md:grid-cols-2">
                <label className="field-shell">
                  <span className="field-label">Employer / organisation</span>
                  <input
                    className="field-input"
                    value={currentForm.employer_name}
                    onChange={(event) => setForm((value) => ({ ...value, employer_name: event.target.value }))}
                    placeholder="Company, ministry, or organisation"
                  />
                </label>

                <label className="field-shell">
                  <span className="field-label">Current city</span>
                  <input
                    className="field-input"
                    value={currentForm.current_city}
                    onChange={(event) => setForm((value) => ({ ...value, current_city: event.target.value }))}
                    placeholder="City"
                  />
                </label>
              </div>

              <label className="field-shell">
                <span className="field-label">Services I can offer</span>
                <textarea
                  className="field-input min-h-[140px]"
                  value={currentForm.services_offered}
                  onChange={(event) => setForm((value) => ({ ...value, services_offered: event.target.value }))}
                  placeholder="Mentorship, design, transport, consulting, catering, technical support"
                />
              </label>

              <label className="field-shell">
                <span className="field-label">Products I can supply</span>
                <textarea
                  className="field-input min-h-[140px]"
                  value={currentForm.products_supplied}
                  onChange={(event) => setForm((value) => ({ ...value, products_supplied: event.target.value }))}
                  placeholder="Printed materials, food packs, stationery, apparel, electronics, farm produce"
                />
              </label>

              {message ? <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</p> : null}
              {error ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p> : null}

              <button className="primary-button" type="submit" disabled={isSaving}>
                {isSaving ? "Saving..." : "Save profile"}
              </button>
            </form>
          </Panel>
        </div>
      ) : (
        <Panel><p className="text-sm text-slate-600">{profileQuery.isLoading ? "Loading your profile..." : "Profile unavailable."}</p></Panel>
      )}
    </div>
  );
}
