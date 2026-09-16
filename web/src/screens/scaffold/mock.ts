/** Mock data for the Phase 6 scaffold screens.
 *
 *  Shapes match the API's Read types where an endpoint already exists, so wiring a
 *  screen is a matter of replacing one constant with the matching hook in `@/data`.
 *  Each screen names the endpoints it needs in a TODO at the top of its file. */

import type { Schemas } from "@/lib/api";

const NOW = new Date();
function at(days: number, hour = 12): string {
  const d = new Date(NOW);
  d.setDate(d.getDate() + days);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}
const stamp = { created_at: at(-30), updated_at: at(-1) };

// ---- Academics (GET /api/courses, /api/assessments, /api/fyp-milestones, /api/documents?scope=course:<id>)

export const COURSES: Schemas["CourseRead"][] = [
  { id: 1, ...stamp, code: "CS3006", name: "Parallel and Distributed Computing", instructor: "Dr. Naveed Ahmed · Mon/Wed 09:00", schedule: "Mon/Wed 09:00", room: "CS block, room 204", term: "Fall 2026", is_fyp: false, fyp_title: "", fyp_note: "", document_count: 14, assessment_count: 3, next_due_at: at(1), next_due_label: "asgn Wed" },
  { id: 2, ...stamp, code: "CS4053", name: "Machine Learning", instructor: "Dr. Sadia Malik · Tue/Thu 11:00", schedule: "Tue/Thu 11:00", room: "B-14", term: "Fall 2026", is_fyp: false, fyp_title: "", fyp_note: "", document_count: 22, assessment_count: 2, next_due_at: at(0, 11), next_due_label: "quiz today" },
  { id: 3, ...stamp, code: "SE4012", name: "Software Architecture", instructor: "Mr. Faraz Hussain · Fri 14:00", schedule: "Fri 14:00", room: "E-3", term: "Fall 2026", is_fyp: false, fyp_title: "", fyp_note: "", document_count: 9, assessment_count: 1, next_due_at: null, next_due_label: "—" },
  { id: 4, ...stamp, code: "CS3001", name: "Computer Networks", instructor: "Dr. Imran Shafi · Mon/Thu 13:00", schedule: "Mon/Thu 13:00", room: "Lab 2", term: "Fall 2026", is_fyp: false, fyp_title: "", fyp_note: "", document_count: 11, assessment_count: 2, next_due_at: at(3), next_due_label: "lab Sat" },
  { id: 5, ...stamp, code: "SS3013", name: "Technical and Business Writing", instructor: "Ms. Rabia Noor · Wed 15:30", schedule: "Wed 15:30", room: "A-9", term: "Fall 2026", is_fyp: false, fyp_title: "", fyp_note: "", document_count: 5, assessment_count: 1, next_due_at: at(9), next_due_label: "report 26 Sep" },
];

export const COURSE_DEADLINES: Array<{ kind: string; title: string; when: string; tone: "held" | "soft" | "muted" }> = [
  { kind: "Assignment", title: "Assignment 3 — Raft leader election", when: "Wed 17 Sep", tone: "held" },
  { kind: "Quiz", title: "Quiz 3 — consensus and failure detectors", when: "24 Sep", tone: "soft" },
  { kind: "Exam", title: "Midterm", when: "8 Oct", tone: "muted" },
];

export const COURSE_FILES = [
  { name: "lecture-07-consensus.pdf", ext: "PDF" },
  { name: "lecture-06-replication.pdf", ext: "PDF" },
  { name: "raft-extended.pdf", ext: "PDF" },
  { name: "asgn3-spec.docx", ext: "DOC" },
  { name: "week5-notes.md", ext: "MD" },
  { name: "lecture-05-time.pdf", ext: "PDF" },
];

export const COURSE_CHAT = [
  { who: "you", text: "What exactly does assignment 3 want for leader election?", cite: null },
  { who: "enola", text: "A working election with randomised timeouts, plus a short argument for why your timeout range avoids split votes. The spec asks for a log, not a proof.", cite: "asgn3-spec.docx · §2, §4 · lecture-07-consensus.pdf · slides 18–24" },
  { who: "you", text: "Is this on the quiz too?", cite: null },
  { who: "enola", text: "Quiz 3 covers consensus and failure detectors, so yes; only the election, not log compaction. I can only see this course's 14 documents from here.", cite: "syllabus.pdf · week 8" },
];

export const FYP = {
  code: "CS4001",
  title: "Context-aware personal agents: scheduling under human approval",
  note: "Advisor: Dr. Naveed Ahmed · co-supervised with the Systems group. Two-person project with Hamza Sheikh.",
};

export const FYP_MILESTONES: Schemas["FypMilestoneRead"][] = [
  { id: 1, ...stamp, course_id: 6, title: "Proposal accepted", note: "Scope narrowed to approval-gated scheduling", due_at: at(-25), state: "done", sort_order: 1 },
  { id: 2, ...stamp, course_id: 6, title: "Milestone 1 — literature review", note: "12 papers, 3 on human-in-the-loop planners", due_at: at(-11), state: "done", sort_order: 2 },
  { id: 3, ...stamp, course_id: 6, title: "Milestone 2 — working prototype", note: "Review with Dr. Naveed. Report still unwritten.", due_at: at(2), state: "current", sort_order: 3 },
  { id: 4, ...stamp, course_id: 6, title: "Milestone 3 — evaluation study", note: "Needs 8 participants", due_at: at(59), state: "upcoming", sort_order: 4 },
  { id: 5, ...stamp, course_id: 6, title: "Final defence", note: "", due_at: at(120), state: "upcoming", sort_order: 5 },
];

export const FYP_NOTES = [
  { title: "Approval gates are not confirmation dialogs", body: "Three of the papers treat human approval as a modal interrupt. In practice the task has already been suspended; the interesting design question is how the paused task stays legible for hours, not how the dialog looks.", meta: "12 Sep · cited in milestone 2" },
  { title: "Timeout choice for stale approvals", body: "If nothing is approved within a window, the agent should expire the draft rather than send it. Open question for the report: is expiry a failure or a normal outcome?", meta: "8 Sep" },
  { title: "Related work gap", body: "Nobody measures how often a user rejects versus edits. That is the metric the evaluation study should collect.", meta: "2 Sep" },
];

// ---- Finance (GET /api/accounts, /api/transactions?month=, /api/finance/summary, POST /api/transactions, POST /api/splits/{id}/settle)

export const ACCOUNTS: Schemas["AccountRead"][] = [
  { id: 1, ...stamp, name: "Meezan · current", kind: "bank", currency: "PKR", opening_balance: "90500", balance: "84320", month_delta: "-6180" },
  { id: 2, ...stamp, name: "SadaPay", kind: "wallet", currency: "PKR", opening_balance: "18140", balance: "21140", month_delta: "3000" },
  { id: 3, ...stamp, name: "Cash", kind: "cash", currency: "PKR", opening_balance: "8900", balance: "6500", month_delta: "-2400" },
];

export const TRANSACTIONS: Schemas["TransactionRead"][] = [
  { id: 1, ...stamp, account_id: 3, category_id: 1, kind: "expense", amount: "2400", title: "Carpool fuel — Shell Gulshan", notes: "", occurred_at: at(-2, 20), paid_by_me: true, category_name: "carpool", account_name: "Cash", splits: [{ id: 1, person_id: 6, person_name: "Usman Raza", share_amount: "800", settled_at: null }, { id: 2, person_id: 3, person_name: "Hamza Sheikh", share_amount: "800", settled_at: null }] },
  { id: 2, ...stamp, account_id: 2, category_id: 3, kind: "expense", amount: "1250", title: "Foodpanda — Kolachi", notes: "", occurred_at: at(-3, 21), paid_by_me: true, category_name: "food", account_name: "SadaPay", splits: [] },
  { id: 3, ...stamp, account_id: 1, category_id: 4, kind: "expense", amount: "5680", title: "ChatGPT Plus", notes: "", occurred_at: at(-4, 9), paid_by_me: true, category_name: "subscriptions", account_name: "Meezan · current", splits: [] },
  { id: 4, ...stamp, account_id: 1, category_id: 6, kind: "expense", amount: "8990", title: "Daraz — mechanical keyboard", notes: "", occurred_at: at(-5, 15), paid_by_me: true, category_name: "one-off", account_name: "Meezan · current", splits: [] },
  { id: 5, ...stamp, account_id: 3, category_id: 2, kind: "expense", amount: "4000", title: "Fuel — top up", notes: "", occurred_at: at(-7, 18), paid_by_me: true, category_name: "fuel", account_name: "Cash", splits: [] },
  { id: 6, ...stamp, account_id: 2, category_id: 3, kind: "settlement", amount: "1150", title: "Hamza — settled dinner", notes: "", occurred_at: at(-9, 13), paid_by_me: false, category_name: "food", account_name: "SadaPay", splits: [] },
  { id: 7, ...stamp, account_id: 1, category_id: 5, kind: "expense", amount: "3500", title: "Internet bill", notes: "", occurred_at: at(-13, 10), paid_by_me: true, category_name: "bills", account_name: "Meezan · current", splits: [] },
];

export const FINANCE_SUMMARY: Schemas["FinanceSummary"] = {
  month: NOW.toISOString().slice(0, 7),
  total_spend: "31420",
  spend: [
    { category_name: "subscriptions", color_token: "cy", amount: "9180", pct: 29 },
    { category_name: "food", color_token: "gr", amount: "7640", pct: 24 },
    { category_name: "carpool & fuel", color_token: "oc", amount: "6400", pct: 20 },
    { category_name: "one-off", color_token: "tx3", amount: "8990", pct: 21 },
    { category_name: "bills", color_token: "line2", amount: "3500", pct: 6 },
  ],
  owed: [
    { person_id: 6, person_name: "Usman Raza", amount: "800", detail: "carpool fuel · 14 Sep" },
    { person_id: 3, person_name: "Hamza Sheikh", amount: "800", detail: "carpool fuel · 14 Sep" },
    { person_id: 8, person_name: "Areeba Fatima", amount: "-450", detail: "FYP printing · 2 Sep" },
  ],
  net_owed: "1150",
};

export const SPLIT_PEOPLE = [
  { id: 6, name: "Usman Raza" },
  { id: 3, name: "Hamza Sheikh" },
  { id: 8, name: "Areeba Fatima" },
  { id: 2, name: "Bilal Qureshi" },
];

// ---- Projects (GET /api/projects, PATCH /api/projects/{id}, GET /api/tasks?entity_type=project&entity_id=)

export const PROJECTS: Schemas["ProjectRead"][] = [
  { id: 1, ...stamp, name: "faizan/enola", repo_url: "", local_path: "", status: "active", summary: "This app. FastAPI backend, LangGraph agent with an approval gate, APScheduler worker; every gated tool suspends into approval_request and resumes from a Postgres checkpoint.", stack: ["python", "fastapi", "langgraph", "postgres", "react"], structure_summary: "", last_touched_at: at(0), linked_task_count: 4 },
  { id: 2, ...stamp, name: "faizan/raft-lite", repo_url: "", local_path: "", status: "coursework", summary: "Leader election and log replication for CS3006 assignment 3. Election works, log compaction is a stub.", stack: ["go", "grpc"], structure_summary: "", last_touched_at: at(-2), linked_task_count: 1 },
  { id: 3, ...stamp, name: "faizan/carpool-splitter", repo_url: "", local_path: "", status: "shelved", summary: "Weekend script that split carpool fuel over WhatsApp. Replaced by Finance in this app, kept because the parsing was fiddly.", stack: ["python", "twilio"], structure_summary: "", last_touched_at: at(-120), linked_task_count: 0 },
  { id: 4, ...stamp, name: "faizan/portfolio", repo_url: "", local_path: "", status: "active", summary: "Static site, four project write-ups. Linked from every resume version.", stack: ["astro", "tailwind"], structure_summary: "", last_touched_at: at(-9), linked_task_count: 2 },
];

// ---- Self-learning (GET /api/learning-goals, PATCH /api/learning-goals/{id}, GET /api/postings?status=saved for skill gaps)

export const GOALS: Schemas["LearningGoalRead"][] = [
  { id: 1, ...stamp, title: "Design systems in React — component libraries", gap_note: "Surfaced from 4 saved postings, including Marrow. Most asked for two years of it.", progress_pct: 35, state: "active", seeded_from_postings: true, resources: [{ id: 1, label: "storybook docs", url: "", done: false }, { id: 2, label: "Marrow posting", url: "", done: false }, { id: 3, label: "notes/ds-primitives.md", url: "", done: true }] },
  { id: 2, ...stamp, title: "System design for backend interviews", gap_note: "Kestrel and Northwind both have a design round. CS3006 covers half of it.", progress_pct: 60, state: "active", seeded_from_postings: true, resources: [{ id: 4, label: "DDIA ch. 5–9", url: "", done: true }, { id: 5, label: "CS3006 lectures", url: "", done: false }, { id: 6, label: "mock with Bilal", url: "", done: false }] },
  { id: 3, ...stamp, title: "Go, enough to be useful", gap_note: "Not in any saved posting. You started it for raft-lite.", progress_pct: 20, state: "active", seeded_from_postings: false, resources: [{ id: 7, label: "tour of go", url: "", done: false }, { id: 8, label: "faizan/raft-lite", url: "", done: false }] },
  { id: 4, ...stamp, title: "Writing — technical posts", gap_note: "Two posts drafted, none published. SS3013 assignments can double up.", progress_pct: 45, state: "active", seeded_from_postings: false, resources: [{ id: 9, label: "drafts/caching.md", url: "", done: false }, { id: 10, label: "SS3013", url: "", done: false }] },
];

export const SKILL_GAPS = [
  { skill: "component libraries", postings: 4 },
  { skill: "system design", postings: 3 },
  { skill: "kubernetes", postings: 2 },
  { skill: "spark", postings: 1 },
];

// ---- Email (no backend yet: GET /api/email/threads?bucket=, GET /api/email/threads/{id}, POST /api/email/threads/{id}/draft → Held)

export interface MailItem {
  id: string;
  from: string;
  subject: string;
  when: string;
  thread: string | null;
  tie: string | null;
  unread: boolean;
}

export interface MailGroup {
  label: string;
  tone: "held" | "accent" | "muted";
  items: MailItem[];
}

export const MAIL_GROUPS: MailGroup[] = [
  {
    label: "Needs you",
    tone: "held",
    items: [
      { id: "m1", from: "Ayesha Tariq", subject: "Re: Backend Engineer (Python) — take-home", when: "11:04", thread: "4 messages", tie: "kestrel · screening", unread: true },
      { id: "m2", from: "Dr. Naveed Ahmed", subject: "Thursday 15:30 for milestone 2?", when: "09:12", thread: "2 messages", tie: "FYP · clashes with quiz", unread: true },
      { id: "m3", from: "Northwind Systems", subject: "Take-home assignment — due Thursday 18:00", when: "yest", thread: null, tie: "northwind · deadline", unread: true },
    ],
  },
  {
    label: "Ongoing threads",
    tone: "accent",
    items: [
      { id: "m4", from: "Bilal Qureshi", subject: "Re: quick question about Turing", when: "2d", thread: "6 messages", tie: "you replied last", unread: false },
      { id: "m5", from: "Ali Hassan (TA)", subject: "Assignment 3 clarification — leader election", when: "3d", thread: "3 messages", tie: "CS3006", unread: false },
      { id: "m6", from: "Orbit HQ Recruiting", subject: "Application received", when: "6d", thread: "2 messages", tie: "no reply in 6 days", unread: false },
    ],
  },
  {
    label: "Worth knowing",
    tone: "muted",
    items: [
      { id: "m7", from: "FAST Registrar", subject: "Final semester fee deadline — 30 Sep", when: "yest", thread: null, tie: "added to tasks", unread: false },
      { id: "m8", from: "Kestrel Labs", subject: "Engineering blog: how we shard ingestion", when: "4d", thread: null, tie: "before your call", unread: false },
    ],
  },
];

export interface MailDetail {
  state: string;
  stateTone: "held" | "soft";
  thread: string;
  subject: string;
  parties: string;
  summary: string;
  ask: string;
  replyNote: string;
  messages: Array<{ who: string; when: string; body: string }>;
}

export const MAIL_DETAILS: Record<string, MailDetail> = {
  m1: {
    state: "Needs you · 2 days of silence",
    stateTone: "held",
    thread: "4 messages · since 10 Sep",
    subject: "Re: Backend Engineer (Python) — take-home",
    parties: "Ayesha Tariq (Kestrel Labs) · you",
    summary: "She confirmed receipt of the take-home on Saturday and said the team would review it early this week. Nothing since. Your screening call is tomorrow at 13:00, which she has not re-confirmed.",
    ask: "The open question from her side is still the new-grad band. From yours: whether tomorrow's call is going ahead.",
    replyNote: "A follow-up is already drafted and Held in Approvals from this morning. Drafting again would duplicate it.",
    messages: [
      { who: "Ayesha Tariq", when: "Sat 13 Sep · 17:40", body: "Got it, thanks Faizan. The team will look at this early next week and I'll come back to you. Still waiting on a decision about the new-grad band internally." },
      { who: "You", when: "Sat 13 Sep · 16:02", body: "Submitted; I added a short write-up of the caching decisions alongside the code. Happy to walk through the trade-offs on the call." },
      { who: "Ayesha Tariq", when: "Thu 11 Sep · 10:15", body: "Application received. Take-home attached, take a week if you need it. Aiming to keep the whole process inside two weeks." },
    ],
  },
  m2: {
    state: "Needs you · conflict detected",
    stateTone: "held",
    thread: "2 messages · today",
    subject: "Thursday 15:30 for milestone 2?",
    parties: "Dr. Naveed Ahmed · you · Hamza Sheikh",
    summary: "He proposed Thursday 15:30 for the milestone 2 review. That collides with your ML quiz, which is on your calendar at 15:00–16:30.",
    ask: "He needs a yes or an alternative today. Two slots are free for you and for him: Friday 11:00 and Monday 14:30.",
    replyNote: "Nothing drafted yet. Ask Enola to propose the two alternates; the reply will be Held before it goes out.",
    messages: [
      { who: "Dr. Naveed Ahmed", when: "today · 09:12", body: "Faizan, Hamza — can we do Thursday 15:30 for the milestone 2 review? Bring the working prototype and whatever you have of the report." },
      { who: "You", when: "Fri 12 Sep · 14:20", body: "Prototype is running end to end. Report is behind; I'll have a draft before the review." },
    ],
  },
  m3: {
    state: "Needs you · deadline Thursday",
    stateTone: "held",
    thread: "1 message",
    subject: "Take-home assignment — due Thursday 18:00",
    parties: "Northwind Systems Recruiting · you",
    summary: "Data platform take-home, roughly four hours of work, due Thursday 18:00. It arrived yesterday evening.",
    ask: "Nothing is drafted. This one is work, not a reply; it is on your task list for Thursday.",
    replyNote: "Enola added “Northwind take-home” to Tasks. No reply is needed until you submit.",
    messages: [{ who: "Northwind Systems Recruiting", when: "yest · 19:30", body: "Hi Faizan — attached is the data platform take-home. Roughly four hours. Submit through the link by Thursday 18:00 and we'll schedule round two from there." }],
  },
  m4: {
    state: "Ongoing · you replied last",
    stateTone: "soft",
    thread: "6 messages · since Aug",
    subject: "Re: quick question about Turing",
    parties: "Bilal Qureshi · you",
    summary: "You asked whether he could vouch for you at Kestrel through his open-source work with two of their engineers. He said yes in principle but wanted to know which role first. You answered two days ago.",
    ask: "Ball is in his court. Last contact 41 days before this thread; worth not letting it go cold again.",
    replyNote: "Nothing drafted. Enola will flag this if he has not replied by Friday.",
    messages: [
      { who: "You", when: "2d ago", body: "Backend Engineer (Python), the platform team. Ayesha Tariq is the recruiter. A note from you about the scheduler work would help more than anything I can say about myself." },
      { who: "Bilal Qureshi", when: "3d ago", body: "Happy to. Which role and who is the recruiter? I only really know the two engineers I worked with on the scheduler." },
    ],
  },
};

export const MAIL_FILED = 41;
