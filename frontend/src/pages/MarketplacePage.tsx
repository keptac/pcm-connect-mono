import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { marketplaceApi, membersApi, messagesApi, universitiesApi } from "../api/endpoints";
import { UniversitySelectOptions } from "../components/UniversitySelectOptions";
import { EmptyState, ModalDialog, PageHeader, Panel, StatusBadge, TableActionButton, TablePagination, usePagination } from "../components/ui";
import { formatDate } from "../lib/format";
import { useAuthStore } from "../store/auth";

function typeTone(value: string) {
  return value === "offer" ? "success" : "warning";
}

function buildInitialForm() {
  return {
    posting_scope: "self",
    university_id: "",
    listing_type: "offer",
    title: "",
    category: "",
    price_text: "",
    description: ""
  };
}

function interestActionLabel(listing: any) {
  if (listing.interest_registered) return "Update response";
  return listing.listing_type === "need" ? "I can provide this" : "Register interest";
}

function buildInterestDialogCopy(listing: any) {
  if (listing.listing_type === "need") {
    return {
      title: listing.interest_registered ? "Update what you can provide" : "Tell them what you can provide",
      description: "Explain the service, supply, pricing, timing, or support you can offer for this need.",
      placeholder: "I can supply the printed shirts within 7 days, minimum order 80 units, and can share samples.",
      submitLabel: listing.interest_registered ? "Update response" : "Send response"
    };
  }

  return {
    title: listing.interest_registered ? "Update your interest" : "Register your interest",
    description: "Tell the poster why this offer is relevant to you and how you would like to proceed.",
    placeholder: "I am interested in this offering for our upcoming PCM workshop and would like pricing details.",
    submitLabel: listing.interest_registered ? "Update interest" : "Register interest"
  };
}

export default function MarketplacePage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const { user } = useAuthStore();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [includeClosed, setIncludeClosed] = useState(false);
  const [actionError, setActionError] = useState("");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [selectedListingId, setSelectedListingId] = useState<number | null>(null);
  const [selectedInterestListing, setSelectedInterestListing] = useState<any | null>(null);
  const [selectedResponsesListing, setSelectedResponsesListing] = useState<any | null>(null);
  const [interestNote, setInterestNote] = useState("");
  const [form, setForm] = useState(buildInitialForm);

  const canView = Boolean(user && user.member_status !== "Student");
  const globalRoles = new Set(["super_admin", "executive", "director"]);
  const canManageAny = (user?.roles || []).some((role) => globalRoles.has(role));
  const canPostForUniversity = canManageAny;
  const selectedResponsesListingId = selectedResponsesListing?.id ?? null;
  const interestDialogCopy = selectedInterestListing ? buildInterestDialogCopy(selectedInterestListing) : null;

  const { data: listings } = useQuery({
    queryKey: ["marketplace", includeClosed],
    queryFn: () => marketplaceApi.list(includeClosed),
    enabled: canView
  });
  const { data: profile } = useQuery({
    queryKey: ["member-self-profile"],
    queryFn: membersApi.myProfile,
    enabled: canView && Boolean(user?.member_id)
  });
  const { data: universities } = useQuery({
    queryKey: ["marketplace-universities"],
    queryFn: universitiesApi.list,
    enabled: canView && canPostForUniversity
  });
  const { data: listingResponses, isLoading: listingResponsesLoading } = useQuery({
    queryKey: ["marketplace-interests", selectedResponsesListingId],
    queryFn: () => marketplaceApi.listInterests(selectedResponsesListingId as number),
    enabled: canView && Boolean(selectedResponsesListingId)
  });

  const filteredListings = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return (listings || [])
      .filter((item: any) => typeFilter === "all" || item.listing_type === typeFilter)
      .filter((item: any) => {
        if (!normalizedSearch) return true;
        return [
          item.title,
          item.description,
          item.category,
          item.owner_name,
          item.university_name
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalizedSearch));
      });
  }, [listings, search, typeFilter]);
  const pagination = usePagination(filteredListings);

  if (!canView) {
    return <Panel><p className="text-sm text-slate-600">Marketplace access is only available to non-student profiles.</p></Panel>;
  }

  function resetForm() {
    setSelectedListingId(null);
    setForm(buildInitialForm());
  }

  function closeForm() {
    setIsFormOpen(false);
    resetForm();
  }

  function closeInterestForm() {
    setSelectedInterestListing(null);
    setInterestNote("");
  }

  function closeResponsesModal() {
    setSelectedResponsesListing(null);
  }

  function openCreateForm() {
    resetForm();
    setIsFormOpen(true);
  }

  function openEditForm(listing: any) {
    setSelectedListingId(listing.id);
    setForm({
      posting_scope: listing.university_id ? "campus" : "self",
      university_id: listing.university_id ? String(listing.university_id) : "",
      listing_type: listing.listing_type,
      title: listing.title || "",
      category: listing.category || "",
      price_text: listing.price_text || "",
      description: listing.description || ""
    });
    setIsFormOpen(true);
  }

  function openInterestForm(listing: any) {
    setActionError("");
    setSelectedInterestListing(listing);
    setInterestNote(listing.interest_note || "");
  }

  function openResponsesModal(listing: any) {
    setActionError("");
    setSelectedResponsesListing(listing);
  }

  async function startDirectConversation(recipientUserId: number, recipientName: string | undefined, chatReady: boolean) {
    setActionError("");
    if (!chatReady) {
      setActionError(`${recipientName || "This member"} has not activated secure chat yet.`);
      return;
    }
    try {
      const conversation = await messagesApi.startDirectConversation({ recipient_user_id: recipientUserId });
      await client.invalidateQueries({ queryKey: ["message-conversations"] });
      navigate(`/messages?thread=${conversation.id}`);
    } catch (error: any) {
      setActionError(error?.response?.data?.detail || "Unable to open the conversation.");
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="PCM marketplace"
        title="Needs and offers"
        description="Post what you need, list what you can offer, and let the PCM network meet real marketplace needs through trusted member connections."
        actions={(
          <button className="primary-button" type="button" onClick={openCreateForm}>
            New listing
          </button>
        )}
      />

      {profile ? (
        <Panel className="space-y-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="eyebrow">Your profile inventory</p>
              <h3 className="text-xl font-semibold text-slate-950">What the network can already identify about you</h3>
              <p className="mt-2 text-sm text-slate-600">Keep these current so marketplace follow-up starts from accurate information.</p>
            </div>
            <button className="secondary-button" type="button" onClick={() => navigate("/my-profile")}>
              Edit my profile
            </button>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-[16px] border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Employment</p>
              <p className="mt-2 text-sm text-slate-900">{profile.employment_status || "Not captured"}</p>
              <p className="mt-1 text-sm text-slate-600">{profile.employer_name || "Employer not captured"}</p>
            </div>
            <div className="rounded-[16px] border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Services offered</p>
              <p className="mt-2 text-sm text-slate-700">{profile.services_offered || "No services listed yet."}</p>
            </div>
            <div className="rounded-[16px] border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Products supplied</p>
              <p className="mt-2 text-sm text-slate-700">{profile.products_supplied || "No products listed yet."}</p>
            </div>
          </div>
        </Panel>
      ) : null}

      <Panel className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="eyebrow">Directory</p>
            <h3 className="text-xl font-semibold text-slate-950">Network exchange board</h3>
            <p className="mt-2 text-sm text-slate-600">Register interest on listings and review the people who responded to your own listings.</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <label className="field-shell min-w-[240px]">
              <span className="field-label">Search</span>
              <input
                className="field-input"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search titles, categories, or campuses"
              />
            </label>
            <label className="field-shell min-w-[160px]">
              <span className="field-label">Type</span>
              <select className="field-input" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
                <option value="all">All</option>
                <option value="offer">Services im offerring</option>
                <option value="need">Service Needed</option>
              </select>
            </label>
            <label className="flex items-center gap-3 rounded-[14px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
              <input type="checkbox" checked={includeClosed} onChange={(event) => setIncludeClosed(event.target.checked)} />
              <span>Show closed listings</span>
            </label>
          </div>
        </div>

        {actionError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{actionError}</p> : null}

        {filteredListings.length === 0 ? (
          <EmptyState
            title="No marketplace listings found"
            description="Once members begin sharing needs and offers, the exchange board will appear here."
          />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Listing</th>
                    <th>Owner</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pagination.pageItems.map((listing: any) => {
                    const canManageListing = listing.user_id === user?.id || canManageAny;
                    return (
                      <tr key={listing.id}>
                        <td>
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="table-primary">{listing.title}</div>
                            <StatusBadge label={listing.listing_type === "offer" ? "On offer" : "Needed"} tone={typeTone(listing.listing_type)} />
                            {listing.response_count ? <StatusBadge label={`${listing.response_count} responses`} tone="info" /> : null}
                          </div>
                          <div className="table-secondary">{listing.description}</div>
                          <div className="table-secondary">{listing.price_text || "Price by discussion"} | Posted {formatDate(listing.created_at)}</div>
                        </td>
                        <td>
                          <div className="table-primary">{listing.owner_name || listing.owner_email}</div>
                          <div className="table-secondary">{listing.university_name || "PCM network"}</div>
                        </td>
                        <td>{listing.category || "General"}</td>
                        <td>
                          <StatusBadge label={listing.status} tone={listing.status === "active" ? "success" : "neutral"} />
                        </td>
                        <td>
                          <div className="table-actions">
                            {listing.user_id !== user?.id ? (
                              <>
                                <button
                                  className="secondary-button"
                                  type="button"
                                  onClick={() => void startDirectConversation(listing.user_id, listing.owner_name || listing.owner_email, listing.owner_chat_ready)}
                                  disabled={!listing.owner_chat_ready}
                                >
                                  Chat
                                </button>
                                <button
                                  className="secondary-button"
                                  type="button"
                                  onClick={() => openInterestForm(listing)}
                                >
                                  {interestActionLabel(listing)}
                                </button>
                              </>
                            ) : null}
                            {canManageListing ? (
                              <>
                                <button className="secondary-button" type="button" onClick={() => openResponsesModal(listing)}>
                                  Responses ({listing.response_count || 0})
                                </button>
                                <TableActionButton label="Edit listing" tone="edit" onClick={() => openEditForm(listing)} />
                                <TableActionButton
                                  label={listing.status === "active" ? "Close listing" : "Reopen listing"}
                                  tone="download"
                                  onClick={async () => {
                                    await marketplaceApi.update(listing.id, { status: listing.status === "active" ? "closed" : "active" });
                                    await client.invalidateQueries({ queryKey: ["marketplace"] });
                                  }}
                                />
                                <TableActionButton
                                  label="Delete listing"
                                  tone="delete"
                                  onClick={async () => {
                                    await marketplaceApi.delete(listing.id);
                                    await client.invalidateQueries({ queryKey: ["marketplace"] });
                                  }}
                                />
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <TablePagination pagination={pagination} itemLabel="listings" />
          </>
        )}
      </Panel>

      <ModalDialog open={Boolean(selectedInterestListing)} onClose={closeInterestForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Marketplace response</p>
              <h3 className="text-xl font-semibold text-slate-950">{interestDialogCopy?.title || "Register interest"}</h3>
              <p className="mt-2 text-sm text-slate-600">{selectedInterestListing?.title || ""}</p>
            </div>
            <button className="secondary-button" type="button" onClick={closeInterestForm}>Close</button>
          </div>

          {interestDialogCopy ? <p className="text-sm text-slate-600">{interestDialogCopy.description}</p> : null}
          {selectedInterestListing?.status !== "active" ? (
            <p className="rounded-2xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
              This listing is closed. You can withdraw an earlier response, but you cannot submit a new one.
            </p>
          ) : null}

          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              if (!selectedInterestListing) return;
              try {
                await marketplaceApi.registerInterest(selectedInterestListing.id, { note: interestNote });
                await client.invalidateQueries({ queryKey: ["marketplace"] });
                closeInterestForm();
              } catch (error: any) {
                setActionError(error?.response?.data?.detail || "Unable to register your response right now.");
              }
            }}
          >
            <label className="field-shell">
              <span className="field-label">Your note</span>
              <textarea
                className="field-input min-h-[160px]"
                value={interestNote}
                onChange={(event) => setInterestNote(event.target.value)}
                placeholder={interestDialogCopy?.placeholder}
              />
            </label>

            <div className="flex flex-wrap gap-3">
              {selectedInterestListing?.interest_registered ? (
                <button
                  className="secondary-button text-rose-700"
                  type="button"
                  onClick={async () => {
                    if (!selectedInterestListing) return;
                    try {
                      await marketplaceApi.withdrawInterest(selectedInterestListing.id);
                      await client.invalidateQueries({ queryKey: ["marketplace"] });
                      closeInterestForm();
                    } catch (error: any) {
                      setActionError(error?.response?.data?.detail || "Unable to withdraw your response right now.");
                    }
                  }}
                >
                  Withdraw response
                </button>
              ) : null}
              <button
                className="primary-button"
                type="submit"
                disabled={selectedInterestListing?.status !== "active"}
              >
                {interestDialogCopy?.submitLabel || "Submit"}
              </button>
            </div>
          </form>
        </div>
      </ModalDialog>

      <ModalDialog open={Boolean(selectedResponsesListing)} onClose={closeResponsesModal}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Listing responses</p>
              <h3 className="text-xl font-semibold text-slate-950">{selectedResponsesListing?.title || "Responses"}</h3>
              <p className="mt-2 text-sm text-slate-600">Review who has shown interest or who says they can provide what this listing needs.</p>
            </div>
            <button className="secondary-button" type="button" onClick={closeResponsesModal}>Close</button>
          </div>

          {listingResponsesLoading ? (
            <p className="text-sm text-slate-600">Loading responses...</p>
          ) : (listingResponses || []).length === 0 ? (
            <EmptyState
              title="No responses yet"
              description="Interested members and suppliers will appear here once they respond to this listing."
            />
          ) : (
            <div className="space-y-4">
              {(listingResponses || []).map((response: any) => (
                <div key={response.id} className="rounded-[20px] border border-slate-200 bg-slate-50 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div>
                        <p className="text-base font-semibold text-slate-950">{response.responder_name || response.responder_email}</p>
                        <p className="text-sm text-slate-600">
                          {response.responder_university_name || "PCM network"} | {response.responder_member_status || "Member"}
                        </p>
                      </div>
                      <p className="text-sm text-slate-500">Responded {formatDate(response.created_at)}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => void startDirectConversation(response.user_id, response.responder_name || response.responder_email, response.responder_chat_ready)}
                        disabled={!response.responder_chat_ready}
                      >
                        Chat
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-[16px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Response note</p>
                      <p className="mt-2 text-sm text-slate-700">{response.note || "No note was added."}</p>
                    </div>
                    <div className="rounded-[16px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Marketplace profile</p>
                      <p className="mt-2 text-sm text-slate-700"><span className="font-medium text-slate-900">Employment:</span> {response.employment_status || "Not captured"}</p>
                      <p className="mt-2 text-sm text-slate-700"><span className="font-medium text-slate-900">Services:</span> {response.services_offered || "No services listed"}</p>
                      <p className="mt-2 text-sm text-slate-700"><span className="font-medium text-slate-900">Products:</span> {response.products_supplied || "No products listed"}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ModalDialog>

      <ModalDialog open={isFormOpen} onClose={closeForm}>
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Marketplace posting</p>
              <h3 className="text-xl font-semibold text-slate-950">{selectedListingId ? "Edit listing" : "Create listing"}</h3>
            </div>
            <button className="secondary-button" type="button" onClick={closeForm}>Close</button>
          </div>

          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              const payload = {
                listing_type: form.listing_type,
                title: form.title,
                category: form.category,
                price_text: form.price_text,
                description: form.description,
                ...(canPostForUniversity
                  ? {
                      university_id: form.posting_scope === "campus" && form.university_id
                        ? Number(form.university_id)
                        : null
                    }
                  : {})
              };
              if (selectedListingId) {
                await marketplaceApi.update(selectedListingId, payload);
              } else {
                await marketplaceApi.create(payload);
              }
              await client.invalidateQueries({ queryKey: ["marketplace"] });
              closeForm();
            }}
          >
            {canPostForUniversity ? (
              <>
                <label className="field-shell">
                  <span className="field-label">Post on behalf of</span>
                  <select
                    className="field-input"
                    value={form.posting_scope}
                    onChange={(event) => setForm((current) => ({
                      ...current,
                      posting_scope: event.target.value,
                      university_id: event.target.value === "campus" ? current.university_id : ""
                    }))}
                  >
                    <option value="self">Myself</option>
                    <option value="campus">University / campus</option>
                  </select>
                </label>

                {form.posting_scope === "campus" ? (
                  <label className="field-shell">
                    <span className="field-label">University / campus</span>
                    <select
                      className="field-input"
                      value={form.university_id}
                      onChange={(event) => setForm((current) => ({ ...current, university_id: event.target.value }))}
                      required
                    >
                      <UniversitySelectOptions universities={universities} emptyOptionLabel="Select university or campus" />
                    </select>
                  </label>
                ) : null}
              </>
            ) : (
              <div className="rounded-[16px] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                This listing will be published as your personal marketplace post.
              </div>
            )}

            <label className="field-shell">
              <span className="field-label">Listing type</span>
              <select className="field-input" value={form.listing_type} onChange={(event) => setForm((current) => ({ ...current, listing_type: event.target.value }))}>
                <option value="offer">Service/Product i'm offering</option>
                <option value="need">Service/Product Needed</option>
              </select>
            </label>

            <label className="field-shell">
              <span className="field-label">Title</span>
              <input className="field-input" value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} />
            </label>

            <label className="field-shell">
              <span className="field-label">Category</span>
              <input className="field-input" value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))} placeholder="Consulting, transport, housing, supplies" />
            </label>

            <label className="field-shell">
              <span className="field-label">Price or terms</span>
              <input className="field-input" value={form.price_text} onChange={(event) => setForm((current) => ({ ...current, price_text: event.target.value }))} placeholder="USD 150 / negotiable / service swap" />
            </label>

            <label className="field-shell">
              <span className="field-label">Description</span>
              <textarea className="field-input min-h-[140px]" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
            </label>

            <button className="primary-button" type="submit">{selectedListingId ? "Save changes" : "Publish listing"}</button>
          </form>
        </div>
      </ModalDialog>
    </div>
  );
}
