import api from "./client";

function parseFilenameFromDisposition(value?: string | null) {
  if (!value) return null;
  const utfMatch = value.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1]);
  const basicMatch = value.match(/filename\s*=\s*"?(.*?)"?(?:;|$)/i);
  return basicMatch?.[1] || null;
}

function scopedParams(universityId?: number | null, extra?: Record<string, unknown>) {
  return {
    params: Object.fromEntries(
      Object.entries({
        university_id: universityId || undefined,
        ...extra
      }).filter(([, value]) => value !== undefined && value !== null && value !== "")
    )
  };
}

export const authApi = {
  login: (email: string, password: string) => api.post("/auth/login", { email, password }).then((res) => res.data),
  refresh: (refreshToken: string) => api.post("/auth/refresh", { refresh_token: refreshToken }).then((res) => res.data),
  lookupGeneralUser: (payload: any) => api.post("/auth/general-registration/search", payload).then((res) => res.data),
  registerGeneralUser: (payload: any) => api.post("/auth/general-registration/register", payload).then((res) => res.data)
};

export const usersMeApi = {
  me: () => api.get("/users/me").then((res) => res.data)
};

export const universitiesApi = {
  list: () => api.get("/universities").then((res) => res.data),
  listPublic: () => api.get("/universities/public").then((res) => res.data),
  create: (payload: any) => api.post("/universities", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/universities/${id}`, payload).then((res) => res.data)
};

export const conferencesApi = {
  list: (activeOnly = false) => api.get("/conferences", { params: activeOnly ? { active_only: true } : {} }).then((res) => res.data),
  create: (payload: any) => api.post("/conferences", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/conferences/${id}`, payload).then((res) => res.data)
};

export const programsApi = {
  list: (universityId?: number | null) => api.get("/programs", scopedParams(universityId)).then((res) => res.data),
  create: (payload: any) => api.post("/programs", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/programs/${id}`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/programs/${id}`).then((res) => res.data)
};

export const academicProgramsApi = {
  list: (universityId?: number | null) => api.get("/academic-programs", scopedParams(universityId)).then((res) => res.data)
};

export const usersApi = {
  list: () => api.get("/users").then((res) => res.data),
  create: (payload: any) => api.post("/users", payload).then((res) => res.data)
};

export const membersApi = {
  list: (universityId?: number | null) => api.get("/members", scopedParams(universityId)).then((res) => res.data),
  alumniConnect: (universityId?: number | null) => api.get("/members/alumni-connect", scopedParams(universityId)).then((res) => res.data),
  myProfile: () => api.get("/members/me-profile").then((res) => res.data),
  updateMyProfile: (payload: any) => api.patch("/members/me-profile", payload).then((res) => res.data),
  create: (payload: any) => api.post("/members", payload).then((res) => res.data),
  update: (id: string, payload: any) => api.patch(`/members/${id}`, payload).then((res) => res.data),
  delete: (id: string) => api.delete(`/members/${id}`).then((res) => res.data),
  bulkUpload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/members/bulk-upload", form, {
      headers: { "Content-Type": "multipart/form-data" }
    }).then((res) => res.data);
  }
};

export const eventsApi = {
  list: (options?: { universityId?: number | null; programId?: number | null; startFrom?: string | null; endTo?: string | null }) =>
    api.get(
      "/events",
      scopedParams(options?.universityId, {
        program_id: options?.programId,
        start_from: options?.startFrom,
        end_to: options?.endTo
      })
    ).then((res) => res.data),
  create: (payload: any) => api.post("/events", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/events/${id}`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/events/${id}`).then((res) => res.data)
};

export const broadcastsApi = {
  list: (options?: { universityId?: number | null; programId?: number | null }) =>
    api.get("/broadcasts", scopedParams(options?.universityId, { program_id: options?.programId })).then((res) => res.data),
  create: (payload: any) => api.post("/broadcasts", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/broadcasts/${id}`, payload).then((res) => res.data),
  respond: (id: number, payload: any) => api.post(`/broadcasts/${id}/respond`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/broadcasts/${id}`).then((res) => res.data)
};

export const programUpdatesApi = {
  list: (options?: { universityId?: number | null; programId?: number | null; reportingPeriod?: string | null }) =>
    api.get("/program-updates", scopedParams(options?.universityId, { program_id: options?.programId, reporting_period: options?.reportingPeriod })).then((res) => res.data),
  condensed: (options?: { universityId?: number | null; reportingPeriod?: string | null }) =>
    api.get("/program-updates/condensed", scopedParams(options?.universityId, { reporting_period: options?.reportingPeriod })).then((res) => res.data),
  create: (payload: any) =>
    api.post("/program-updates", payload, payload instanceof FormData ? {
      headers: { "Content-Type": "multipart/form-data" }
    } : undefined).then((res) => res.data),
  update: (id: number, payload: any) =>
    api.patch(`/program-updates/${id}`, payload, payload instanceof FormData ? {
      headers: { "Content-Type": "multipart/form-data" }
    } : undefined).then((res) => res.data),
  delete: (id: number) => api.delete(`/program-updates/${id}`).then((res) => res.data),
  downloadReport: (id: number) =>
    api.get(`/program-updates/${id}/report-pdf`, {
      responseType: "blob"
    }).then((res) => ({
      blob: res.data,
      filename: parseFilenameFromDisposition(res.headers["content-disposition"])
    })),
  downloadReportPack: (options?: { universityId?: number | null; programId?: number | null; reportingPeriod?: string | null }) =>
    api.get("/program-updates/report-pack", {
      params: Object.fromEntries(
        Object.entries({
          university_id: options?.universityId || undefined,
          program_id: options?.programId,
          reporting_period: options?.reportingPeriod || undefined,
        }).filter(([, value]) => value !== undefined && value !== null && value !== "")
      ),
      responseType: "blob"
    }).then((res) => ({
      blob: res.data,
      filename: parseFilenameFromDisposition(res.headers["content-disposition"])
    }))
};

export const mandatoryProgramsApi = {
  list: (options?: { programType?: string | null; includeInactive?: boolean }) =>
    api.get("/mandatory-programs", {
      params: Object.fromEntries(
        Object.entries({
          program_type: options?.programType,
          include_inactive: options?.includeInactive || undefined
        }).filter(([, value]) => value !== undefined && value !== null && value !== "")
      )
    }).then((res) => res.data),
  create: (payload: any) => api.post("/mandatory-programs", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/mandatory-programs/${id}`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/mandatory-programs/${id}`).then((res) => res.data)
};

export const reportingPeriodsApi = {
  list: (includeInactive = false) =>
    api.get("/reporting-periods", {
      params: includeInactive ? { include_inactive: true } : {}
    }).then((res) => res.data),
  create: (payload: any) => api.post("/reporting-periods", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/reporting-periods/${id}`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/reporting-periods/${id}`).then((res) => res.data)
};

export const fundingApi = {
  list: (universityId?: number | null) => api.get("/funding", scopedParams(universityId)).then((res) => res.data),
  create: (payload: any) => api.post("/funding", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/funding/${id}`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/funding/${id}`).then((res) => res.data)
};

export const reportsApi = {
  list: (universityId?: number | null) => api.get("/reports", scopedParams(universityId)).then((res) => res.data),
  submitForm: (form: FormData) =>
    api.post("/reports/submit-form", form, {
      headers: { "Content-Type": "multipart/form-data" }
    }).then((res) => res.data),
  rows: (id: number) => api.get(`/reports/${id}/rows`).then((res) => res.data)
};

export const messagesApi = {
  contacts: () => api.get("/messages/contacts").then((res) => res.data),
  conversations: () => api.get("/messages/conversations").then((res) => res.data),
  startDirectConversation: (payload: any) => api.post("/messages/conversations/direct", payload).then((res) => res.data),
  listMessages: (threadId: number) => api.get(`/messages/conversations/${threadId}`).then((res) => res.data),
  sendMessage: (threadId: number, payload: any) => api.post(`/messages/conversations/${threadId}/messages`, payload).then((res) => res.data),
  markRead: (threadId: number) => api.post(`/messages/conversations/${threadId}/read`).then((res) => res.data),
  getKeyBundle: () => api.get("/messages/e2ee-key-bundle").then((res) => res.data),
  setKeyBundle: (payload: any) => api.put("/messages/e2ee-key-bundle", payload).then((res) => res.data)
};

export const marketplaceApi = {
  list: (includeClosed = false) =>
    api.get("/marketplace", { params: includeClosed ? { include_closed: true } : {} }).then((res) => res.data),
  listInterests: (listingId: number) => api.get(`/marketplace/${listingId}/interests`).then((res) => res.data),
  registerInterest: (listingId: number, payload: any) => api.post(`/marketplace/${listingId}/interest`, payload).then((res) => res.data),
  withdrawInterest: (listingId: number) => api.delete(`/marketplace/${listingId}/interest`).then((res) => res.data),
  create: (payload: any) => api.post("/marketplace", payload).then((res) => res.data),
  update: (id: number, payload: any) => api.patch(`/marketplace/${id}`, payload).then((res) => res.data),
  delete: (id: number) => api.delete(`/marketplace/${id}`).then((res) => res.data)
};

export const analyticsApi = {
  overview: (universityId?: number | null) => api.get("/analytics/overview", scopedParams(universityId)).then((res) => res.data),
  people: (groupBy: string, universityId?: number | null) =>
    api.get("/analytics/people", scopedParams(universityId, { group_by: groupBy })).then((res) => res.data),
  universities: (universityId?: number | null) =>
    api.get("/analytics/universities", scopedParams(universityId)).then((res) => res.data),
  programs: (universityId?: number | null) =>
    api.get("/analytics/programs", scopedParams(universityId)).then((res) => res.data),
  funding: (universityId?: number | null) =>
    api.get("/analytics/funding", scopedParams(universityId)).then((res) => res.data)
};

export const adminApi = {
  runAlumni: () => api.post("/admin/alumni-transition").then((res) => res.data),
  auditLogs: () => api.get("/admin/audit-logs").then((res) => res.data)
};
