/** Server-state hooks. Every screen reads and writes through these; none of them
 *  hand-roll fetch or their own loading booleans. Keys come from lib/query. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Schemas } from "@/lib/api";
import { keys } from "@/lib/query";

export type Dashboard = Schemas["DashboardRead"];
export type Task = Schemas["TaskRead"];
export type TaskCreate = Schemas["TaskCreate"];
export type Person = Schemas["PersonRead"];
export type PersonCreate = Schemas["PersonCreate"];
export type Interaction = Schemas["InteractionRead"];
export type SharedMoney = Schemas["SharedMoneyRow"];
export type Application = Schemas["ApplicationRead"];
export type ApplicationEvent = Schemas["ApplicationEventRead"];
export type Posting = Schemas["JobPostingRead"];
export type Company = Schemas["CompanyRead"];
export type Approval = Schemas["ApprovalRead"];
export type Activity = Schemas["ActivityRead"];
export type LogEntry = Schemas["LogEntryRead"];
export type LogCandidate = Schemas["LogCandidate"];
export type MemoryFact = Schemas["MemoryFactRead"];
export type ChatMessage = Schemas["ChatMessageRead"];
export type RunRead = Schemas["RunRead"];
export type SearchHit = Schemas["SearchHit"];

async function unwrap<T>(promise: Promise<{ data?: T }>): Promise<T> {
  const { data } = await promise;
  if (data === undefined) throw new Error("Empty response");
  return data;
}

// ---- dashboard -----------------------------------------------------------------

export function useDashboard() {
  return useQuery({ queryKey: keys.dashboard, queryFn: () => unwrap(api.GET("/api/dashboard")), refetchInterval: 60_000 });
}

export function useSearch(q: string) {
  return useQuery({
    queryKey: keys.search(q),
    queryFn: () => unwrap(api.GET("/api/search", { params: { query: { q } } })),
    enabled: q.trim().length > 1,
    staleTime: 10_000,
  });
}

// ---- notifications -------------------------------------------------------------

export type Notification = Schemas["NotificationRead"];

export function useNotificationBadge() {
  return useQuery({ queryKey: keys.notifications, queryFn: () => unwrap(api.GET("/api/notifications/badge")), refetchInterval: 60_000 });
}

export function useNotificationMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: keys.notifications });
    void qc.invalidateQueries({ queryKey: keys.dashboard });
  };
  const markRead = useMutation({ mutationFn: (id: number) => unwrap(api.POST("/api/notifications/{notification_id}/read", { params: { path: { notification_id: id } } })), onSettled: invalidate });
  const markAllRead = useMutation({ mutationFn: () => unwrap(api.POST("/api/notifications/read-all")), onSettled: invalidate });
  return { markRead, markAllRead };
}

// ---- approvals -----------------------------------------------------------------

export function useHeldCountQuery() {
  return useQuery({ queryKey: [...keys.approvals, "count"], queryFn: () => unwrap(api.GET("/api/approvals/count")), refetchInterval: 30_000 });
}

export function useApprovals(state?: Schemas["ApprovalState"]) {
  return useQuery({
    queryKey: [...keys.approvals, state ?? "all"],
    queryFn: () => unwrap(api.GET("/api/approvals", { params: { query: state ? { state } : {} } })),
    refetchInterval: 30_000,
  });
}

function useInvalidateAgentState() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: keys.approvals });
    void qc.invalidateQueries({ queryKey: keys.dashboard });
    void qc.invalidateQueries({ queryKey: ["chat"] });
    void qc.invalidateQueries({ queryKey: ["activity"] });
    void qc.invalidateQueries({ queryKey: ["people"] });
    void qc.invalidateQueries({ queryKey: ["tasks"] });
    void qc.invalidateQueries({ queryKey: keys.memory });
  };
}

export function useDecideApproval() {
  const invalidate = useInvalidateAgentState();
  return useMutation({
    mutationFn: ({ id, approve, args, note }: { id: number; approve: boolean; args?: Record<string, unknown> | undefined; note?: string | undefined }) =>
      unwrap(api.POST(approve ? "/api/approvals/{approval_id}/approve" : "/api/approvals/{approval_id}/reject", { params: { path: { approval_id: id } }, body: { args: args ?? null, note: note ?? "" } })),
    onSettled: invalidate,
  });
}

// ---- chat ---------------------------------------------------------------------------

export function useChatHistory(threadId: string) {
  return useQuery({ queryKey: keys.chat(threadId), queryFn: () => unwrap(api.GET("/api/chat/{thread_id}", { params: { path: { thread_id: threadId } } })) });
}

export function useClearChat(threadId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.DELETE("/api/chat/{thread_id}", { params: { path: { thread_id: threadId } } }),
    onSuccess: () => {
      qc.setQueryData(keys.chat(threadId), []);
      void qc.invalidateQueries({ queryKey: ["chat"] });
    },
  });
}

export function useSendChat(threadId: string) {
  const invalidate = useInvalidateAgentState();
  return useMutation({
    mutationFn: ({ text, scope, source }: { text: string; scope: string; source: Schemas["ChatSource"] }) => unwrap(api.POST("/api/chat", { body: { text, thread_id: threadId, scope, source } })),
    onSettled: invalidate,
  });
}

// ---- tasks ---------------------------------------------------------------------------

export function useTasks(state?: Schemas["TaskState"], extra?: { entity_type?: Schemas["EntityType"]; entity_id?: number }) {
  const query = { ...(state ? { state } : {}), ...(extra ?? {}) };
  return useQuery({ queryKey: keys.tasks(JSON.stringify(query)), queryFn: () => unwrap(api.GET("/api/tasks", { params: { query } })) });
}

export function useTaskMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["tasks"] });
    void qc.invalidateQueries({ queryKey: keys.dashboard });
    void qc.invalidateQueries({ queryKey: ["log"] });
  };
  const create = useMutation({ mutationFn: (body: TaskCreate) => unwrap(api.POST("/api/tasks", { body })), onSettled: invalidate });
  const setState = useMutation({
    mutationFn: ({ id, state }: { id: number; state: Schemas["TaskState"] }) => unwrap(api.POST("/api/tasks/{task_id}/state/{state}", { params: { path: { task_id: id, state } } })),
    onSettled: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Schemas["TaskUpdate"] }) => unwrap(api.PATCH("/api/tasks/{item_id}", { params: { path: { item_id: id } }, body })),
    onSettled: invalidate,
  });
  const remove = useMutation({ mutationFn: (id: number) => api.DELETE("/api/tasks/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { create, setState, update, remove };
}

// ---- people ---------------------------------------------------------------------------

export function usePeople(params: { tag?: string; q?: string; going_cold?: boolean; can_refer?: boolean }) {
  return useQuery({ queryKey: keys.people(JSON.stringify(params)), queryFn: () => unwrap(api.GET("/api/people", { params: { query: params } })) });
}

export function usePerson(id: number) {
  return useQuery({ queryKey: keys.person(id), queryFn: () => unwrap(api.GET("/api/people/{item_id}", { params: { path: { item_id: id } } })), enabled: Number.isFinite(id) });
}

export function usePersonInteractions(id: number) {
  return useQuery({ queryKey: [...keys.person(id), "interactions"], queryFn: () => unwrap(api.GET("/api/interactions", { params: { query: { person_id: id } } })), enabled: Number.isFinite(id) });
}

export function usePersonMoney(id: number) {
  return useQuery({ queryKey: [...keys.person(id), "money"], queryFn: () => unwrap(api.GET("/api/people/{person_id}/money", { params: { path: { person_id: id } } })), enabled: Number.isFinite(id) });
}

export function usePeopleMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["people"] });
    void qc.invalidateQueries({ queryKey: keys.dashboard });
  };
  const create = useMutation({ mutationFn: (body: PersonCreate) => unwrap(api.POST("/api/people", { body })), onSettled: invalidate });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Schemas["PersonUpdate"] }) => unwrap(api.PATCH("/api/people/{item_id}", { params: { path: { item_id: id } }, body })),
    onSettled: invalidate,
  });
  const addInteraction = useMutation({ mutationFn: (body: Schemas["InteractionCreate"]) => unwrap(api.POST("/api/interactions", { body })), onSettled: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.DELETE("/api/people/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { create, update, addInteraction, remove };
}

// ---- jobs ---------------------------------------------------------------------------------

export function useApplications() {
  return useQuery({ queryKey: keys.applications, queryFn: () => unwrap(api.GET("/api/applications", { params: { query: { limit: 500 } } })) });
}

export function useApplication(id: number) {
  return useQuery({ queryKey: keys.application(id), queryFn: () => unwrap(api.GET("/api/applications/{item_id}", { params: { path: { item_id: id } } })), enabled: Number.isFinite(id) });
}

export function useApplicationEvents(id: number) {
  return useQuery({ queryKey: [...keys.application(id), "events"], queryFn: () => unwrap(api.GET("/api/application-events", { params: { query: { application_id: id } } })), enabled: Number.isFinite(id) });
}

export function usePostings(status: Schemas["PostingStatus"] = "discovered") {
  return useQuery({ queryKey: [...keys.postings, status], queryFn: () => unwrap(api.GET("/api/postings", { params: { query: { status } } })) });
}

export function useCompanies() {
  return useQuery({ queryKey: keys.companies, queryFn: () => unwrap(api.GET("/api/companies")) });
}

export function useJobMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["applications"] });
    void qc.invalidateQueries({ queryKey: keys.postings });
    void qc.invalidateQueries({ queryKey: keys.companies });
    void qc.invalidateQueries({ queryKey: keys.dashboard });
  };
  const createCompany = useMutation({ mutationFn: (body: Schemas["CompanyCreate"]) => unwrap(api.POST("/api/companies", { body })), onSettled: invalidate });
  const createApplication = useMutation({ mutationFn: (body: Schemas["ApplicationCreate"]) => unwrap(api.POST("/api/applications", { body })), onSettled: invalidate });
  const updateApplication = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Schemas["ApplicationUpdate"] }) => unwrap(api.PATCH("/api/applications/{item_id}", { params: { path: { item_id: id } }, body })),
    onSettled: invalidate,
  });
  const addEvent = useMutation({ mutationFn: (body: Schemas["ApplicationEventCreate"]) => unwrap(api.POST("/api/application-events", { body })), onSettled: invalidate });
  const createPosting = useMutation({ mutationFn: (body: Schemas["JobPostingCreate"]) => unwrap(api.POST("/api/postings", { body })), onSettled: invalidate });
  const updatePosting = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Schemas["JobPostingUpdate"] }) => unwrap(api.PATCH("/api/postings/{item_id}", { params: { path: { item_id: id } }, body })),
    onSettled: invalidate,
  });
  const pullPosting = useMutation({ mutationFn: (id: number) => unwrap(api.POST("/api/postings/{posting_id}/pull", { params: { path: { posting_id: id } } })), onSettled: invalidate });
  return { createCompany, createApplication, updateApplication, addEvent, createPosting, updatePosting, pullPosting };
}

// ---- log ---------------------------------------------------------------------------------

export function useLogEntries(params: { tag?: string; q?: string }) {
  return useQuery({ queryKey: keys.log(JSON.stringify(params)), queryFn: () => unwrap(api.GET("/api/log", { params: { query: params } })) });
}

export function useLogCandidates() {
  return useQuery({ queryKey: [...keys.log("candidates")], queryFn: () => unwrap(api.GET("/api/log-candidates")) });
}

export function useActivity(sinceHours?: number) {
  return useQuery({ queryKey: ["activity", sinceHours ?? "all"], queryFn: () => unwrap(api.GET("/api/activity", { params: { query: sinceHours ? { since_hours: sinceHours } : {} } })) });
}

export function useLogMutations() {
  const qc = useQueryClient();
  const invalidate = () => void qc.invalidateQueries({ queryKey: ["log"] });
  const create = useMutation({ mutationFn: (body: Schemas["LogEntryCreate"]) => unwrap(api.POST("/api/log", { body })), onSettled: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.DELETE("/api/log/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { create, remove };
}

// ---- memory ---------------------------------------------------------------------------------

export function useMemory() {
  return useQuery({ queryKey: keys.memory, queryFn: () => unwrap(api.GET("/api/memory", { params: { query: { limit: 500 } } })) });
}

export function useMemoryMutations() {
  const qc = useQueryClient();
  const invalidate = () => void qc.invalidateQueries({ queryKey: keys.memory });
  const create = useMutation({ mutationFn: (body: Schemas["MemoryFactCreate"]) => unwrap(api.POST("/api/memory", { body })), onSettled: invalidate });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Schemas["MemoryFactUpdate"] }) => unwrap(api.PATCH("/api/memory/{item_id}", { params: { path: { item_id: id } }, body })),
    onSettled: invalidate,
  });
  const forget = useMutation({ mutationFn: (id: number) => unwrap(api.POST("/api/memory/{fact_id}/forget", { params: { path: { fact_id: id } } })), onSettled: invalidate });
  const restore = useMutation({ mutationFn: (id: number) => unwrap(api.POST("/api/memory/{fact_id}/restore", { params: { path: { fact_id: id } } })), onSettled: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.DELETE("/api/memory/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { create, update, forget, restore, remove };
}

// ---- projects (a registry, not a code browser) ---------------------------------

export type Project = Schemas["ProjectRead"];
export type ProjectCreate = Schemas["ProjectCreate"];
export type ProjectUpdate = Schemas["ProjectUpdate"];

export function useProjects(status?: Schemas["ProjectStatus"]) {
  return useQuery({ queryKey: keys.projects(status), queryFn: () => unwrap(api.GET("/api/projects", { params: { query: status ? { status } : {} } })) });
}

export function useProjectMutations() {
  const qc = useQueryClient();
  const invalidate = () => void qc.invalidateQueries({ queryKey: ["projects"] });
  const create = useMutation({ mutationFn: (body: ProjectCreate) => unwrap(api.POST("/api/projects", { body })), onSettled: invalidate });
  const update = useMutation({ mutationFn: ({ id, body }: { id: number; body: ProjectUpdate }) => unwrap(api.PATCH("/api/projects/{item_id}", { params: { path: { item_id: id } }, body })), onSettled: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.DELETE("/api/projects/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { create, update, remove };
}

// ---- self-learning -------------------------------------------------------------

export type LearningGoal = Schemas["LearningGoalRead"];
export type LearningGoalCreate = Schemas["LearningGoalCreate"];
export type LearningGoalUpdate = Schemas["LearningGoalUpdate"];
export type LearningResource = Schemas["LearningResourceRead"];

export function useLearningGoals(state?: Schemas["LearningGoalState"]) {
  return useQuery({ queryKey: keys.learning(state), queryFn: () => unwrap(api.GET("/api/learning-goals", { params: { query: state ? { state } : {} } })) });
}

export function useLearningMutations() {
  const qc = useQueryClient();
  const invalidate = () => void qc.invalidateQueries({ queryKey: ["learning"] });
  const create = useMutation({ mutationFn: (body: LearningGoalCreate) => unwrap(api.POST("/api/learning-goals", { body })), onSettled: invalidate });
  const update = useMutation({ mutationFn: ({ id, body }: { id: number; body: LearningGoalUpdate }) => unwrap(api.PATCH("/api/learning-goals/{item_id}", { params: { path: { item_id: id } }, body })), onSettled: invalidate });
  const remove = useMutation({ mutationFn: (id: number) => api.DELETE("/api/learning-goals/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { create, update, remove };
}

// ---- academics -----------------------------------------------------------------

export type Course = Schemas["CourseRead"];
export type CourseCreate = Schemas["CourseCreate"];
export type CourseUpdate = Schemas["CourseUpdate"];
export type Assessment = Schemas["AssessmentRead"];
export type AssessmentCreate = Schemas["AssessmentCreate"];
export type AssessmentUpdate = Schemas["AssessmentUpdate"];
export type FypMilestone = Schemas["FypMilestoneRead"];
export type FypMilestoneCreate = Schemas["FypMilestoneCreate"];
export type FypMilestoneUpdate = Schemas["FypMilestoneUpdate"];
export type EnolaDocument = Schemas["DocumentRead"];

/** A course's documents and its scoped chat share one scope string. One definition,
 *  so the chat thread and the material list can never drift apart. */
export function courseScope(courseId: number): string {
  return `course:${courseId}`;
}

export function useCourses(term?: string) {
  return useQuery({
    queryKey: keys.courses(term),
    queryFn: () => unwrap(api.GET("/api/courses", { params: { query: term ? { term } : {} } })),
  });
}

export function useAssessments(courseId?: number) {
  return useQuery({
    queryKey: keys.assessments(courseId ? String(courseId) : undefined),
    queryFn: () => unwrap(api.GET("/api/assessments", { params: { query: courseId ? { course_id: courseId } : {} } })),
  });
}

export function useFypMilestones(courseId?: number) {
  return useQuery({
    queryKey: keys.fyp(courseId ? String(courseId) : undefined),
    queryFn: () => unwrap(api.GET("/api/fyp-milestones", { params: { query: courseId ? { course_id: courseId } : {} } })),
  });
}

export function useDocuments(scope?: string) {
  return useQuery({
    queryKey: keys.documents(scope),
    queryFn: () => unwrap(api.GET("/api/documents", { params: { query: scope ? { scope } : {} } })),
    enabled: scope !== undefined,
  });
}

export function useAcademicsMutations() {
  const qc = useQueryClient();
  // Assessments write through to tasks server-side, so the dashboard moves too.
  const invalidate = () => {
    for (const key of [["courses"], ["assessments"], ["fyp"], ["tasks"], keys.dashboard]) {
      void qc.invalidateQueries({ queryKey: key });
    }
  };
  const createCourse = useMutation({ mutationFn: (body: CourseCreate) => unwrap(api.POST("/api/courses", { body })), onSettled: invalidate });
  const updateCourse = useMutation({ mutationFn: ({ id, body }: { id: number; body: CourseUpdate }) => unwrap(api.PATCH("/api/courses/{item_id}", { params: { path: { item_id: id } }, body })), onSettled: invalidate });
  const removeCourse = useMutation({ mutationFn: (id: number) => api.DELETE("/api/courses/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  const createAssessment = useMutation({ mutationFn: (body: AssessmentCreate) => unwrap(api.POST("/api/assessments", { body })), onSettled: invalidate });
  const updateAssessment = useMutation({ mutationFn: ({ id, body }: { id: number; body: AssessmentUpdate }) => unwrap(api.PATCH("/api/assessments/{item_id}", { params: { path: { item_id: id } }, body })), onSettled: invalidate });
  const removeAssessment = useMutation({ mutationFn: (id: number) => api.DELETE("/api/assessments/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  const createMilestone = useMutation({ mutationFn: (body: FypMilestoneCreate) => unwrap(api.POST("/api/fyp-milestones", { body })), onSettled: invalidate });
  const updateMilestone = useMutation({ mutationFn: ({ id, body }: { id: number; body: FypMilestoneUpdate }) => unwrap(api.PATCH("/api/fyp-milestones/{item_id}", { params: { path: { item_id: id } }, body })), onSettled: invalidate });
  const removeMilestone = useMutation({ mutationFn: (id: number) => api.DELETE("/api/fyp-milestones/{item_id}", { params: { path: { item_id: id } } }), onSettled: invalidate });
  return { createCourse, updateCourse, removeCourse, createAssessment, updateAssessment, removeAssessment, createMilestone, updateMilestone, removeMilestone };
}

export function useDocumentMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["documents"] });
    void qc.invalidateQueries({ queryKey: ["courses"] });
  };
  /** Multipart: the generated client would JSON-encode the body, so hand the FormData
   *  through untouched and let the browser set the boundary. */
  const upload = useMutation({
    mutationFn: ({ file, entityId }: { file: File; entityId: number }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("entity_type", "course");
      form.append("entity_id", String(entityId));
      return unwrap(api.POST("/api/documents", { body: form as never, bodySerializer: (b: unknown) => b as FormData }));
    },
    onSettled: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.DELETE("/api/documents/{document_id}", { params: { path: { document_id: id } } }),
    onSettled: invalidate,
  });
  return { upload, remove };
}

// ---- email ---------------------------------------------------------------------

export type MailInbox = Schemas["MailInboxRead"];
export type MailGroup = Schemas["MailGroupRead"];
export type MailThread = Schemas["MailThreadRead"];
export type MailThreadDetail = Schemas["MailThreadDetail"];

/** Reading the inbox is an IMAP round trip, so the server caches it. Refetching on
 *  window focus would spend that round trip for nothing. */
export function useInbox() {
  return useQuery({
    queryKey: keys.email,
    queryFn: () => unwrap(api.GET("/api/email/threads", { params: { query: {} } })),
    refetchOnWindowFocus: false,
    staleTime: 120_000,
  });
}

export function useRefreshInbox() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.GET("/api/email/threads", { params: { query: { refresh: true } } })),
    onSuccess: (data) => {
      qc.setQueryData(keys.email, data);
      void qc.invalidateQueries({ queryKey: ["email"] });
    },
  });
}

export function useEmailThread(id: string | null) {
  return useQuery({
    queryKey: keys.emailThread(id ?? ""),
    queryFn: () => unwrap(api.GET("/api/email/threads/{item_id}", { params: { path: { item_id: id ?? "" } } })),
    enabled: Boolean(id),
    refetchOnWindowFocus: false,
    staleTime: 120_000,
  });
}
