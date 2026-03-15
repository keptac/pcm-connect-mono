const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getToken() {
  return localStorage.getItem("pcm_token");
}

export function setToken(token) {
  localStorage.setItem("pcm_token", token);
}

export function clearToken() {
  localStorage.removeItem("pcm_token");
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Request failed");
  }
  return res.json();
}

export async function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

export async function fetchUniversities() {
  return request("/universities");
}

export async function fetchMe() {
  return request("/users/me");
}

export async function fetchDepartments() {
  return request("/departments");
}

export async function createUniversity(payload) {
  return request("/universities", { method: "POST", body: JSON.stringify(payload) });
}

export async function createDepartment(payload) {
  return request("/departments", { method: "POST", body: JSON.stringify(payload) });
}

export async function listUsers() {
  return request("/users");
}

export async function createUser(payload) {
  return request("/users", { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchStudents() {
  return request("/students");
}

export async function createStudent(payload) {
  return request("/students", { method: "POST", body: JSON.stringify(payload) });
}

export async function updateStudent(id, payload) {
  return request(`/students/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function importStudents(file) {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/students/import`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Import failed");
  }
  return res.json();
}

export async function reconcileStudents() {
  return request("/students/reconcile", { method: "POST" });
}

export async function fetchReports() {
  return request("/reports");
}

export async function uploadReport(file, reportPeriod, universityId) {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  if (reportPeriod) form.append("report_period", reportPeriod);
  if (universityId) form.append("university_id", universityId);
  const res = await fetch(`${API_URL}/reports/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || "Upload failed");
  }
  return res.json();
}

export async function fetchReportRows(reportId) {
  return request(`/reports/${reportId}/rows`);
}

export async function fetchReportAnalysis(reportId) {
  return request(`/reports/${reportId}/analysis`);
}

export async function fetchStudentAnalytics() {
  return request("/analytics/students");
}

export function reportTemplateUrl() {
  return `${API_URL}/reports/template`;
}
