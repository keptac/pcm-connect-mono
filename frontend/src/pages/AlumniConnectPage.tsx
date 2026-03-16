import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { membersApi, messagesApi, universitiesApi } from "../api/endpoints";
import { EmptyState, PageHeader, Panel, StatusBadge, TablePagination, usePagination } from "../components/ui";
import { exportRowsAsCsv } from "../lib/export";
import { canAccessAlumniConnect } from "../lib/alumniConnectAccess";
import { useUniversityScope } from "../lib/universityScope";

function graduationYear(value?: string | null, fallbackYear?: number | null) {
  if (value) {
    const parsed = new Date(`${value}T00:00:00`);
    if (!Number.isNaN(parsed.getTime())) return String(parsed.getFullYear());
  }
  if (fallbackYear) return String(fallbackYear);
  return "Not captured";
}

function employmentTone(status?: string | null): "success" | "warning" | "info" | "neutral" {
  const normalized = (status || "").toLowerCase();
  if (normalized === "employed") return "success";
  if (normalized === "entrepreneur") return "info";
  if (normalized === "job seeking" || normalized === "not employed") return "warning";
  return "neutral";
}

export default function AlumniConnectPage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const { user, roles, scopeKey, scopeParams } = useUniversityScope();
  const canView = canAccessAlumniConnect(user, roles);

  const [search, setSearch] = useState("");
  const [employmentFilter, setEmploymentFilter] = useState("all");
  const [actionError, setActionError] = useState("");

  const { data: members } = useQuery({
    queryKey: ["alumni-connect", scopeKey],
    queryFn: () => membersApi.alumniConnect(scopeParams),
    enabled: canView
  });
  const { data: contacts } = useQuery({
    queryKey: ["message-contacts"],
    queryFn: messagesApi.contacts,
    enabled: canView,
    refetchInterval: 60_000
  });
  const { data: universities } = useQuery({
    queryKey: ["universities", scopeKey],
    queryFn: () => universitiesApi.list(scopeParams),
    enabled: canView
  });

  const universityLookup = useMemo(
    () => Object.fromEntries((universities || []).map((university: any) => [university.id, university.name])),
    [universities]
  );

  const contactLookup = useMemo(
    () =>
      new Map(
        (contacts || []).flatMap((contact: any) => {
          const entries: [string, any][] = [];
          if (contact.member_id) entries.push([`member:${String(contact.member_id)}`, contact]);
          if (contact.member_number) entries.push([`number:${String(contact.member_number).trim().toLowerCase()}`, contact]);
          if (contact.email) entries.push([`email:${String(contact.email).trim().toLowerCase()}`, contact]);
          return entries;
        })
      ),
    [contacts]
  );

  function marketplaceProfileSummary(member: any) {
    const details = [member.services_offered, member.products_supplied].filter(Boolean);
    if (details.length > 0) return details.join(" | ");
    return member.email ? "Chat can be matched by account email" : "No account email on profile";
  }

  const alumniRows = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return (members || [])
      .map((member: any) => {
        const chatContact =
          contactLookup.get(`member:${member.id}`) ||
          (member.member_id ? contactLookup.get(`number:${String(member.member_id).trim().toLowerCase()}`) : null) ||
          (member.email ? contactLookup.get(`email:${String(member.email).trim().toLowerCase()}`) : null) ||
          null;

        return {
          ...member,
          chatContact,
          graduation_year: graduationYear(member.expected_graduation_date, member.start_year),
          university_name: universityLookup[member.university_id] || "University not set"
        };
      })
      .filter((member: any) => {
        const matchesEmployment =
          employmentFilter === "all" ||
          (member.employment_status || "Not captured").toLowerCase() === employmentFilter.toLowerCase();

        const haystack = [
          member.first_name,
          member.last_name,
          member.program_of_study_name,
          member.university_name,
          member.graduation_year,
          member.employment_status,
          member.employer_name,
          member.current_city,
          member.services_offered,
          member.products_supplied
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        return matchesEmployment && haystack.includes(normalizedSearch);
      })
      .sort((left: any, right: any) => {
        const leftYear = Number(left.graduation_year) || 0;
        const rightYear = Number(right.graduation_year) || 0;
        if (rightYear !== leftYear) return rightYear - leftYear;
        return String(left.first_name || "").localeCompare(String(right.first_name || ""));
      });
  }, [contactLookup, employmentFilter, members, search, universityLookup]);

  const alumniPagination = usePagination(alumniRows);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Access denied.</p></Panel>;
  }

  const employmentOptions = Array.from(
    new Set(
      (members || []).map((member: any) => member.employment_status || "Not captured")
    )
  ).sort((left, right) => left.localeCompare(right));

  async function reachOut(member: any) {
    setActionError("");

    if (!member.chatContact) {
      setActionError(`${member.first_name} does not have a PCM chat account yet.`);
      return;
    }

    if (!member.chatContact.chat_public_key) {
      setActionError(`${member.first_name} has not activated secure chat yet.`);
      return;
    }

    try {
      const conversation = await messagesApi.startDirectConversation({ recipient_user_id: member.chatContact.id });
      await client.invalidateQueries({ queryKey: ["message-conversations"] });
      navigate(`/messages?thread=${conversation.id}`);
    } catch (error: any) {
      setActionError(error?.response?.data?.detail || "Unable to open the alumni conversation.");
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Alumni network"
        title="Alumni connect"
        description="Browse alumni by name, graduation year, employment status, program of study, services offered, and products supplied, then reach out through secure system chat. Phone numbers stay hidden on this page."
      />

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Directory</p>
            <h3 className="text-xl font-semibold text-slate-950">Alumni directory</h3>
            <p className="mt-2 text-sm text-slate-600">Use the secure chat button to reach out where an alumni chat account is available. Personal phone numbers are not shown here.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(220px,1fr)] md:items-end">
            <label className="field-shell">
              <span className="field-label">Search alumni</span>
              <input
                className="field-input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by name, programme, university, year, service, or product"
              />
            </label>
            <label className="field-shell">
              <span className="field-label">Employment status</span>
              <select className="field-input" value={employmentFilter} onChange={(event) => setEmploymentFilter(event.target.value)}>
                <option value="all">All alumni</option>
                {employmentOptions.map((status) => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {alumniRows.length === 0 ? (
          <EmptyState
            title="No alumni profiles found"
            description="Alumni records will appear here once their profiles are captured in the people registry for this scope."
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>First name</th>
                    <th>Surname</th>
                    <th>University / Campus</th>
                    <th>Program of study</th>
                    <th>Graduation year</th>
                    <th>Employment status</th>
                    <th>Reach out</th>
                  </tr>
                </thead>
                <tbody>
                  {alumniPagination.pageItems.map((member: any) => (
                    <tr key={member.id}>
                      <td>
                        <div className="table-primary">{member.first_name || "Unnamed"}</div>
                        <div className="table-secondary">Alumni profile</div>
                      </td>
                      <td>{member.last_name || "Not captured"}</td>
                      <td>
                        <div className="table-primary">{member.university_name}</div>
                        <div className="table-secondary">{member.current_city || "Location not captured"}</div>
                      </td>
                      <td>
                        <div className="table-primary">{member.program_of_study_name || "Not captured"}</div>
                        <div className="table-secondary">{marketplaceProfileSummary(member)}</div>
                      </td>
                      <td>{member.graduation_year}</td>
                      <td>
                        <StatusBadge
                          label={member.employment_status || "Not captured"}
                          tone={employmentTone(member.employment_status)}
                        />
                      </td>
                      <td>
                        <div className="table-actions">
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => void reachOut(member)}
                            disabled={!member.chatContact?.chat_public_key}
                          >
                            Reach out
                          </button>
                          <StatusBadge
                            label={
                              member.chatContact?.chat_public_key
                                ? "Chat ready"
                                : member.chatContact
                                  ? "Chat pending"
                                  : "No chat account"
                            }
                            tone={
                              member.chatContact?.chat_public_key
                                ? "success"
                                : member.chatContact
                                  ? "warning"
                                  : "neutral"
                            }
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePagination
              pagination={alumniPagination}
              itemLabel="alumni profiles"
              onExport={() => exportRowsAsCsv("alumni-connect", alumniRows.map((member: any) => ({
                first_name: member.first_name || "",
                surname: member.last_name || "",
                university_or_campus: member.university_name,
                program_of_study: member.program_of_study_name || "",
                graduation_year: member.graduation_year,
                employment_status: member.employment_status || "Not captured",
                employer_name: member.employer_name || "",
                location: member.current_city || "Not captured",
                services_offered: member.services_offered || "",
                products_supplied: member.products_supplied || "",
                chat_status: member.chatContact?.chat_public_key ? "Chat ready" : member.chatContact ? "Chat pending" : "No chat account"
              })))}
            />
          </>
        )}

        {actionError ? <p className="rounded-[14px] bg-rose-50 px-4 py-3 text-sm text-rose-700">{actionError}</p> : null}
      </Panel>
    </div>
  );
}
