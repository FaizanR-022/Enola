"""Seed the database with realistic content.

    python -m enola.scripts.seed            # adds seed rows (fails if already seeded)
    python -m enola.scripts.seed --reset    # wipes every table first

Dates are relative to now so the dashboard always has something due, something
overdue and someone going cold. Domain rules run through the services, so seeded
assessments create their task rows exactly as real ones would.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from enola.core.config import get_settings
from enola.core.db import Base, session_scope
from enola.core.enums import (
    AccountKind,
    ActivityKind,
    ActorSource,
    ApplicationEventKind,
    ApplicationStage,
    AssessmentKind,
    EntityType,
    InteractionKind,
    LearningGoalState,
    LocationKind,
    MemorySource,
    MilestoneState,
    PostingStatus,
    ProjectStatus,
    Risk,
    SettlementDirection,
    TaskPriority,
    TaskSource,
    TaskState,
    TransactionKind,
)
from enola.core.models import Company, MemoryFact, Person
from enola.core.schemas.academics import AssessmentCreate, CourseCreate, FypMilestoneCreate
from enola.core.schemas.finance import (
    AccountCreate,
    CategoryCreate,
    SettlementCreate,
    SplitIn,
    TransactionCreate,
)
from enola.core.schemas.jobs import ApplicationCreate, JobPostingCreate
from enola.core.schemas.journal import LogEntryCreate
from enola.core.schemas.learning import LearningGoalCreate, LearningResourceIn
from enola.core.schemas.people import InteractionCreate, PersonCreate
from enola.core.schemas.projects import ProjectCreate
from enola.core.schemas.tasks import TaskCreate, TaskLinkIn
from enola.core.services.academics import AssessmentService, CourseService, FypMilestoneService
from enola.core.services.activity import record_activity
from enola.core.services.finance import (
    AccountService,
    CategoryService,
    SettlementService,
    TransactionService,
)
from enola.core.services.jobs import ApplicationService, JobPostingService
from enola.core.services.journal import LogEntryService
from enola.core.services.learning import LearningGoalService
from enola.core.services.people import InteractionService, PersonService
from enola.core.services.projects import ProjectService
from enola.core.services.tasks import TaskService

KEEP_ON_RESET = {"alembic_version", "user_session"}


LANGGRAPH_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")


def reset(db: Session) -> None:
    tables = [t.name for t in reversed(Base.metadata.sorted_tables) if t.name not in KEEP_ON_RESET]
    db.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
    # Conversation state lives in LangGraph's own tables; a reset wipes it too.
    for name in LANGGRAPH_TABLES:
        db.execute(text(f"DELETE FROM {name}")) if db.execute(text("SELECT to_regclass(:n)"), {"n": name}).scalar() else None


def _at(days: float, hour: int = 10, minute: int = 0) -> datetime:
    """A local-time instant relative to today, so "today" agrees with the dashboard."""
    local = datetime.now(ZoneInfo(get_settings().timezone))
    base = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return (base + timedelta(days=days)).astimezone(UTC)


def seed(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}

    # --- companies ------------------------------------------------------------------
    companies = {}
    for name, website, location in [
        ("Kestrel Labs", "https://kestrellabs.io", "Remote · global"),
        ("Northwind Systems", "https://northwind.systems", "Remote · US"),
        ("Orbit HQ", "https://orbithq.com", "Remote · EU"),
        ("Marrow", "https://marrow.dev", "Remote · APAC"),
        ("Sable", "https://sable.sh", "Remote · global"),
        ("Truffle", "https://truffle.co.uk", "Remote · UK"),
        ("Systems Limited", "https://systemsltd.com", "Karachi"),
        ("Bazaar Technologies", "https://bazaartech.com", "Karachi"),
        ("Careem", "https://careem.com", "Karachi · hybrid"),
        ("Turing", "https://turing.com", "Remote"),
    ]:
        company = Company(name=name, website=website, location=location)
        db.add(company)
        companies[name] = company
    db.flush()
    counts["company"] = len(companies)

    # --- people -----------------------------------------------------------------------
    people_service = PersonService(db)
    interactions = InteractionService(db)
    people: dict[str, Person] = {}

    def person(name: str, role: str, tags: list[str], **kw: object) -> Person:
        p = people_service.create(PersonCreate(name=name, role=role, tags=tags, **kw))
        people[name] = p
        return p

    person("Ayesha Tariq", "Technical recruiter · Kestrel Labs", ["recruiter", "kestrel", "can refer"], company_id=companies["Kestrel Labs"].id, email="ayesha.tariq@kestrellabs.io", how_we_met="FAST careers fair, March 2026", can_refer=True, cadence_days=14, notes="Handles all new-grad backend hiring at Kestrel.\n\nPrefers short emails and replies within two days normally. Told you on the call to apply directly and mention her name.")
    person("Bilal Qureshi", "Senior engineer · Turing", ["alumni", "FAST '23", "distributed systems", "can refer"], company_id=companies["Turing"].id, email="bilal.q@turing.com", how_we_met="FAST senior, same society", can_refer=True, cadence_days=30, notes="Worked with two Kestrel engineers on an open-source scheduler. Warm but indirect path. Happy to vouch technically; not on the hiring side.")
    person("Hamza Sheikh", "Final year · FYP partner", ["friend", "FYP", "carpool"], how_we_met="Same batch since first semester", cadence_days=7, notes="FYP partner. Owns the evaluation study. Drives on Mondays.")
    person("Sana Iqbal", "Engineering manager · Systems Limited", ["senior", "karachi", "can refer"], company_id=companies["Systems Limited"].id, how_we_met="Guest lecture in Software Engineering", can_refer=True, cadence_days=45, notes="Runs a platform team at Systems. Said to ping her when the FYP has a demo.")
    person("Zainab Farooq", "Product manager · Careem", ["alumni", "product"], company_id=companies["Careem"].id, how_we_met="Alumni meetup, Jan 2026", cadence_days=60, notes="Offered to review the portfolio. Never followed up.")
    person("Usman Raza", "Final year · same batch", ["friend", "carpool", "university"], cadence_days=7, notes="Drives the Wednesday–Friday carpool. Splits fuel at the end of each week.\n\nGood at algorithms, wants to do a masters rather than work. Proof-reads well; caught two mistakes in the FYP proposal.")
    person("Ali Hassan", "TA · Parallel & Distributed Computing", ["university", "CS3006"], cadence_days=None, notes="Answers assignment questions on the course forum within a day.")
    person("Areeba Fatima", "Final year · FYP group B", ["friend", "university"], cadence_days=21, notes="Printed the FYP posters for both groups; you owe her for yours.")
    person("Dr. Naveed Ahmed", "FYP advisor · FAST-NUCES", ["faculty", "FYP"], email="naveed.ahmed@nu.edu.pk", cadence_days=14, notes="Advisor. Wants the working prototype before the report. Prefers Thursday afternoons.")
    person("Faraz Hussain", "Recruiter · Bazaar Technologies", ["recruiter", "karachi"], company_id=companies["Bazaar Technologies"].id, how_we_met="LinkedIn, replied to a post", can_refer=True, cadence_days=21, notes="Onsite roles only. Said to reach out after finals.")
    person("Maryam Siddiqui", "Backend engineer · Marrow", ["alumni", "FAST '22", "backend"], company_id=companies["Marrow"].id, how_we_met="Alumni Discord", can_refer=True, cadence_days=30, notes="Joined Marrow remote from Lahore. Happy to explain their interview loop.")
    person("Taha Malik", "Product engineer · Orbit HQ", ["referral", "react"], company_id=companies["Orbit HQ"].id, how_we_met="Replied to a cold DM", cadence_days=30, notes="Said Orbit hires slowly. Follow up in October if nothing moves.")
    counts["person"] = len(people)

    def touch(name: str, days_ago: float, kind: InteractionKind, summary: str, source: ActorSource = ActorSource.YOU) -> None:
        interactions.create(InteractionCreate(person_id=people[name].id, kind=kind, summary=summary, occurred_at=_at(-days_ago, 15), source=source))

    touch("Ayesha Tariq", 6, InteractionKind.CALL, "Call, 22 min — team structure, new-grad band undecided")
    touch("Ayesha Tariq", 3, InteractionKind.EMAIL, "Take-home submitted through her")
    touch("Bilal Qureshi", 41, InteractionKind.MESSAGE, "Asked whether he could vouch at Kestrel; he asked which role first")
    touch("Hamza Sheikh", 1, InteractionKind.MEETING, "FYP sync — evaluation study needs 8 participants")
    touch("Sana Iqbal", 63, InteractionKind.MEETING, "Coffee after her guest lecture")
    touch("Zainab Farooq", 88, InteractionKind.MESSAGE, "Sent portfolio link for review")
    touch("Usman Raza", 1, InteractionKind.MESSAGE, "Split carpool fuel three ways")
    touch("Usman Raza", 5, InteractionKind.MESSAGE, "Sent him the Kestrel posting")
    touch("Ali Hassan", 8, InteractionKind.EMAIL, "Clarified leader election spec for assignment 3")
    touch("Areeba Fatima", 13, InteractionKind.MEETING, "Picked up the printed posters")
    touch("Dr. Naveed Ahmed", 4, InteractionKind.EMAIL, "Confirmed milestone 2 review slot")
    touch("Faraz Hussain", 30, InteractionKind.MESSAGE, "He said reach out after finals")
    touch("Maryam Siddiqui", 20, InteractionKind.MESSAGE, "Explained Marrow's design-round format")
    touch("Taha Malik", 12, InteractionKind.EMAIL, "Orbit hiring slowly; October")
    counts["interaction"] = 14

    # --- applications -----------------------------------------------------------------
    apps = ApplicationService(db)

    def application(company: str, role: str, stage: ApplicationStage, **kw: object) -> int:
        a = apps.create(ApplicationCreate(company_id=companies[company].id, role_title=role, stage=stage, **kw))
        return a.id

    kestrel = application(
        "Kestrel Labs", "Backend Engineer (Python)", ApplicationStage.SCREENING,
        location_kind=LocationKind.REMOTE, location_label="Remote · global", pay_label="$52–68k",
        posting_url="https://kestrellabs.io/careers/backend-python",
        posting_summary="Small platform team, five engineers, async-first with a two-hour overlap requirement. You would own ingestion services in FastAPI and share on-call after three months. They explicitly accept final-year students who can commit 30 hours a week until graduation.",
        tags=["python", "fastapi", "postgres", "async-first", "no sponsorship", "30h/week ok"],
        referral_person_id=people["Ayesha Tariq"].id, resume_version="faizan-backend-v4.pdf",
        resume_note="Reordered to lead with the FastAPI scheduler project",
        next_action="Screening call with Ayesha Tariq", next_action_at=_at(1, 13), applied_at=_at(-5, 11),
    )
    kestrel_app = apps.get(kestrel)
    apps.add_event(kestrel_app, ApplicationEventKind.CALL, "Call with Ayesha Tariq · she suggested applying", _at(-6, 15))
    apps.add_event(kestrel_app, ApplicationEventKind.TAKE_HOME, "Take-home submitted with caching write-up", _at(-3, 16))
    apps.add_event(kestrel_app, ApplicationEventKind.INTERVIEW, "Screening call scheduled", _at(-2, 9), ActorSource.EMAIL)

    northwind_data = application(
        "Northwind Systems", "SWE I, Data Platform", ApplicationStage.SCREENING,
        location_label="Remote · US", pay_label="$60–72k", tags=["python", "spark", "data"],
        next_action="Take-home due", next_action_at=_at(2, 13), applied_at=_at(-9, 10),
    )
    apps.add_event(apps.get(northwind_data), ApplicationEventKind.TAKE_HOME, "Data platform take-home arrived, roughly four hours", _at(-1, 14), ActorSource.EMAIL)

    northwind_fs = application(
        "Northwind Systems", "Full-Stack Engineer, New Grad", ApplicationStage.INTERVIEW,
        location_label="Remote · US", pay_label="$65–75k", tags=["react", "node", "postgres"],
        referral_person_id=people["Bilal Qureshi"].id, next_action="Round 2 · system design", next_action_at=_at(3, 14), applied_at=_at(-14, 10),
    )
    apps.add_event(apps.get(northwind_fs), ApplicationEventKind.INTERVIEW, "Round 1 passed — recruiter screen", _at(-4, 12))

    orbit = application("Orbit HQ", "Frontend Engineer (React)", ApplicationStage.APPLIED, location_label="Remote · EU", pay_label="€40–48k", tags=["react", "typescript"], applied_at=_at(-6, 10))
    _ = orbit
    marrow = application("Marrow", "Junior Backend Engineer", ApplicationStage.APPLIED, location_label="Remote · APAC", pay_label="$45–55k", tags=["python", "django"], applied_at=_at(-7, 10))
    _ = marrow
    application("Sable", "Platform Engineer", ApplicationStage.SAVED, location_label="Remote · global", pay_label="not stated", tags=["go", "kubernetes"], next_action="Posting closes", next_action_at=_at(6, 18))
    application("Systems Limited", "Associate Software Engineer", ApplicationStage.SAVED, location_kind=LocationKind.ONSITE, location_label="Karachi · onsite", pay_label="PKR 150–200k", tags=["java", "spring"], next_action="Ask Sana whether to apply now or after finals")
    application("Bazaar Technologies", "Software Engineer I", ApplicationStage.APPLIED, location_kind=LocationKind.ONSITE, location_label="Karachi · onsite", pay_label="PKR 180–250k", tags=["python", "django", "postgres"], applied_at=_at(-12, 10))
    truffle = application("Truffle", "Software Engineer I", ApplicationStage.CLOSED, location_label="Remote · UK", pay_label="£35–42k", tags=["ruby", "rails"], applied_at=_at(-30, 10), closed_reason="Rejected 4 Sep · no reason given")
    apps.add_event(apps.get(truffle), ApplicationEventKind.REJECTED, "Rejected, no reason given", _at(-12, 9), ActorSource.EMAIL)
    counts["application"] = 9

    postings = JobPostingService(db)
    for company_name, role, loc, pay, score, reason, tags in [
        ("Palegate", "Junior Backend Engineer (FastAPI)", "Remote · EU friendly", "€38–46k", 87, "Python, FastAPI and Postgres all match. They hire final-year students and sponsor nothing, which you said is fine.", ["python", "fastapi", "postgres"]),
        ("Marrow", "React Engineer, Design Systems", "Remote · APAC", "$45–60k", 74, "Strong React match but they want two years of component-library work. That is one of your saved skill gaps.", ["react", "design systems"]),
        ("Kestrel Labs", "New Grad SWE, Infrastructure", "Remote · global", "not stated", 61, "Same company as your live application. Applying twice usually reads badly; I would leave it.", ["go", "infra"]),
        ("Retailo", "Backend Engineer", "Karachi · hybrid", "PKR 200–280k", 69, "Django and Postgres match. Hybrid in Karachi, which you said is acceptable.", ["python", "django"]),
    ]:
        postings.upsert(JobPostingCreate(company_name=company_name, role_title=role, location_label=loc, pay_label=pay, match_score=score, match_reason=reason, tags=tags, status=PostingStatus.DISCOVERED, url=f"https://jobs.example/{company_name.lower()}"))
    counts["job_posting"] = 4

    # --- academics --------------------------------------------------------------------
    courses = CourseService(db)
    assessments = AssessmentService(db)
    milestones = FypMilestoneService(db)
    course_ids: dict[str, int] = {}
    for code, name, instructor, schedule, room in [
        ("CS3006", "Parallel and Distributed Computing", "Dr. Naveed Ahmed", "Mon/Wed 09:00", "CS block, room 204"),
        ("CS4053", "Machine Learning", "Dr. Sadia Malik", "Tue/Thu 11:00", "B-14"),
        ("SE4012", "Software Architecture", "Mr. Faraz Hussain", "Fri 14:00", "E-3"),
        ("CS3001", "Computer Networks", "Dr. Imran Shafi", "Mon/Thu 13:00", "Lab 2"),
        ("SS3013", "Technical and Business Writing", "Ms. Rabia Noor", "Wed 15:30", "A-9"),
    ]:
        course_ids[code] = courses.create(CourseCreate(code=code, name=name, instructor=instructor, schedule=schedule, room=room, term="Fall 2026")).id
    fyp = courses.create(CourseCreate(code="CS4001", name="Final Year Project I", instructor="Dr. Naveed Ahmed", term="Fall 2026", is_fyp=True, fyp_title="Context-aware personal agents: scheduling under human approval", fyp_note="Advisor: Dr. Naveed Ahmed · co-supervised with the Systems group. Two-person project with Hamza Sheikh."))
    course_ids["CS4001"] = fyp.id
    counts["course"] = 6

    for code, kind, title, days, weight in [
        ("CS3006", AssessmentKind.ASSIGNMENT, "Assignment 3 — Raft leader election", 1, 10),
        ("CS3006", AssessmentKind.QUIZ, "Quiz 3 — consensus and failure detectors", 8, 5),
        ("CS3006", AssessmentKind.EXAM, "Midterm", 22, 25),
        ("CS4053", AssessmentKind.QUIZ, "Quiz 2 — trees, bagging, boosting", 0, 5),
        ("CS4053", AssessmentKind.ASSIGNMENT, "Assignment 2 — gradient boosting from scratch", 12, 10),
        ("SE4012", AssessmentKind.PROJECT, "Architecture decision record — group project", 16, 15),
        ("CS3001", AssessmentKind.LAB, "Lab 4 — socket programming", 3, 5),
        ("CS3001", AssessmentKind.QUIZ, "Quiz 2 — transport layer", 10, 5),
        ("SS3013", AssessmentKind.REPORT, "Technical report draft", 9, 20),
        ("CS4001", AssessmentKind.REPORT, "Milestone 2 report", 2, 20),
        ("CS3006", AssessmentKind.ASSIGNMENT, "Assignment 2 — MPI matrix multiply", -9, 10),
    ]:
        assessments.create(AssessmentCreate(course_id=course_ids[code], kind=kind, title=title, due_at=_at(days, 23, 59) if kind != AssessmentKind.QUIZ else _at(days, 11), weight_pct=Decimal(weight), source_note="from the course outline"))
    counts["assessment"] = 11

    for title, note, days, milestone_state, order in [
        ("Proposal accepted", "Scope narrowed to approval-gated scheduling", -25, MilestoneState.DONE, 1),
        ("Milestone 1 — literature review", "12 papers, 3 on human-in-the-loop planners", -11, MilestoneState.DONE, 2),
        ("Milestone 2 — working prototype", "Review with Dr. Naveed. Report still unwritten.", 2, MilestoneState.CURRENT, 3),
        ("Milestone 3 — evaluation study", "Needs 8 participants", 59, MilestoneState.UPCOMING, 4),
        ("Final defence", "", 120, MilestoneState.UPCOMING, 5),
    ]:
        milestones.create(FypMilestoneCreate(course_id=fyp.id, title=title, note=note, due_at=_at(days, 15), state=milestone_state, sort_order=order))
    counts["fyp_milestone"] = 5

    # --- tasks (hand-written; assessment tasks already exist) ----------------------------
    tasks = TaskService(db)
    for title, days, priority, links, state in [
        ("Tailor resume for Kestrel Labs", 0, TaskPriority.URGENT, [TaskLinkIn(entity_type=EntityType.APPLICATION, entity_id=kestrel, label="kestrel")], TaskState.OPEN),
        ("Email Bilal re: Turing referral", 0, TaskPriority.HIGH, [TaskLinkIn(entity_type=EntityType.PERSON, entity_id=people["Bilal Qureshi"].id, label="people")], TaskState.OPEN),
        ("Revise trees & ensembles before the quiz", 0, TaskPriority.HIGH, [TaskLinkIn(entity_type=EntityType.COURSE, entity_id=course_ids["CS4053"], label="CS4053")], TaskState.OPEN),
        ("Northwind take-home", 2, TaskPriority.HIGH, [TaskLinkIn(entity_type=EntityType.APPLICATION, entity_id=northwind_data, label="northwind")], TaskState.OPEN),
        ("Networks lab 4 prep", 3, TaskPriority.NORMAL, [TaskLinkIn(entity_type=EntityType.COURSE, entity_id=course_ids["CS3001"], label="CS3001")], TaskState.OPEN),
        ("Book mock system-design round with Bilal", 5, TaskPriority.NORMAL, [], TaskState.OPEN),
        ("Pay internet bill", -13, TaskPriority.NORMAL, [], TaskState.DONE),
        ("Apply to Kestrel Labs", -5, TaskPriority.HIGH, [TaskLinkIn(entity_type=EntityType.APPLICATION, entity_id=kestrel, label="kestrel")], TaskState.DONE),
        ("Send Areeba the poster money", -2, TaskPriority.LOW, [TaskLinkIn(entity_type=EntityType.PERSON, entity_id=people["Areeba Fatima"].id, label="people")], TaskState.OPEN),
    ]:
        tasks.create(TaskCreate(title=title, due_at=_at(days, 18), priority=priority, links=links, state=state, source=TaskSource.YOU))
    counts["task"] = 9 + counts["assessment"]

    # --- finance ------------------------------------------------------------------------
    accounts = AccountService(db)
    categories = CategoryService(db)
    txs = TransactionService(db)
    meezan = accounts.create(AccountCreate(name="Meezan · current", kind=AccountKind.BANK, opening_balance=Decimal("90500"))).id
    sadapay = accounts.create(AccountCreate(name="SadaPay", kind=AccountKind.WALLET, opening_balance=Decimal("18140"))).id
    cash = accounts.create(AccountCreate(name="Cash", kind=AccountKind.CASH, opening_balance=Decimal("8900"))).id
    cat: dict[str, int] = {}
    for name, token in [("carpool", "oc"), ("fuel", "oc"), ("food", "gr"), ("subscriptions", "cy"), ("bills", "line2"), ("one-off", "tx3"), ("university", "paper-ink")]:
        cat[name] = categories.create(CategoryCreate(name=name, color_token=token)).id
    counts["account"], counts["category"] = 3, len(cat)

    def tx(account: int, category: str | None, kind: TransactionKind, amount: int, title: str, days_ago: float, splits: list[SplitIn] | None = None, paid_by_me: bool = True) -> None:
        txs.create(TransactionCreate(account_id=account, category_id=cat[category] if category else None, kind=kind, amount=Decimal(amount), title=title, occurred_at=_at(-days_ago, 20), paid_by_me=paid_by_me, splits=splits or []))

    tx(cash, "carpool", TransactionKind.EXPENSE, 2400, "Carpool fuel — Shell Gulshan", 2, [SplitIn(person_id=people["Usman Raza"].id), SplitIn(person_id=people["Hamza Sheikh"].id)])
    tx(sadapay, "food", TransactionKind.EXPENSE, 1250, "Foodpanda — Kolachi", 3)
    tx(meezan, "subscriptions", TransactionKind.EXPENSE, 5680, "ChatGPT Plus", 4)
    tx(meezan, "one-off", TransactionKind.EXPENSE, 8990, "Daraz — mechanical keyboard", 5)
    tx(cash, "fuel", TransactionKind.EXPENSE, 4000, "Fuel — top up", 7)
    tx(meezan, "bills", TransactionKind.EXPENSE, 3500, "Internet bill", 13)
    tx(meezan, "subscriptions", TransactionKind.EXPENSE, 3500, "GitHub Copilot", 14)
    tx(cash, "university", TransactionKind.EXPENSE, 900, "FYP poster printing — Areeba paid", 14, [SplitIn(person_id=people["Areeba Fatima"].id, share_amount=Decimal("450"))], paid_by_me=False)
    # Hamza paid back part of the dinner from last week: a partial settlement, the real shape.
    tx(sadapay, "food", TransactionKind.EXPENSE, 2300, "Dinner at Kolachi — you paid", 9, [SplitIn(person_id=people["Hamza Sheikh"].id, share_amount=Decimal("1150"))])
    SettlementService(db).create(SettlementCreate(person_id=people["Hamza Sheikh"].id, amount=Decimal("700"), direction=SettlementDirection.THEY_PAID_ME, occurred_at=_at(-7, 12), note="SadaPay transfer", account_id=sadapay))
    tx(meezan, None, TransactionKind.INCOME, 25000, "Freelance — landing page for a cousin's shop", 10)
    tx(meezan, "food", TransactionKind.EXPENSE, 2100, "Groceries — Imtiaz", 1)
    counts["transaction"] = 11
    counts["settlement"] = 1

    # --- projects -----------------------------------------------------------------------
    projects = ProjectService(db)
    for name, status, summary, stack, touched in [
        ("faizan/enola", ProjectStatus.ACTIVE, "This app. FastAPI backend, LangGraph agent with an approval gate, APScheduler worker; every gated tool suspends into approval_request and resumes from a Postgres checkpoint.", ["python", "fastapi", "langgraph", "postgres", "react"], 0),
        ("faizan/raft-lite", ProjectStatus.COURSEWORK, "Leader election and log replication for CS3006 assignment 3. Election works, log compaction is a stub.", ["go", "grpc"], 2),
        ("faizan/carpool-splitter", ProjectStatus.SHELVED, "Weekend script that split carpool fuel over WhatsApp. Replaced by Finance in this app, kept because the parsing was fiddly.", ["python", "twilio"], 120),
        ("faizan/portfolio", ProjectStatus.ACTIVE, "Static site, four project write-ups. Linked from every resume version.", ["astro", "tailwind"], 9),
        ("faizan/fyp-agent-eval", ProjectStatus.ACTIVE, "Evaluation harness for the FYP: replays approval decisions and measures reject-vs-edit rates.", ["python", "pandas"], 1),
    ]:
        projects.create(ProjectCreate(name=name, repo_url=f"https://github.com/{name}", status=status, summary=summary, stack=stack, last_touched_at=_at(-touched, 21)))
    counts["project"] = 5

    # --- learning ------------------------------------------------------------------------
    goals = LearningGoalService(db)
    for title, gap, pct, seeded, resources in [
        ("Design systems in React — component libraries", "Surfaced from 4 saved postings, including Marrow. Most asked for two years of it.", 35, True, ["storybook docs", "Marrow posting", "notes/ds-primitives.md"]),
        ("System design for backend interviews", "Kestrel and Northwind both have a design round. CS3006 covers half of it.", 60, True, ["DDIA ch. 5–9", "CS3006 lectures", "mock with Bilal"]),
        ("Go, enough to be useful", "Not in any saved posting. You started it for raft-lite.", 20, False, ["tour of go", "faizan/raft-lite"]),
        ("Writing — technical posts", "Two posts drafted, none published. SS3013 assignments can double up.", 45, False, ["drafts/caching.md", "SS3013"]),
    ]:
        goals.create(LearningGoalCreate(title=title, gap_note=gap, progress_pct=pct, seeded_from_postings=seeded, state=LearningGoalState.ACTIVE, resources=[LearningResourceIn(label=r) for r in resources]))
    counts["learning_goal"] = 4

    # --- memory ---------------------------------------------------------------------------
    for group, statement, source, evidence, confidence, locked in [
        ("About the job hunt", "Targeting backend roles over frontend", MemorySource.INFERRED, "inferred · 9 applications, 6 backend", 78, False),
        ("About the job hunt", "Will not need visa sponsorship for remote roles", MemorySource.TOLD, "you told me · 2 Sep", 100, False),
        ("About the job hunt", "Prefers async-first teams with small overlap windows", MemorySource.INFERRED, "inferred · your notes on 3 postings", 92, False),
        ("About the job hunt", "Available 30 hours a week until graduation in January", MemorySource.TOLD, "you told me · 2 Sep", 100, False),
        ("About the job hunt", "Remote preferred; onsite in Karachi is acceptable", MemorySource.TOLD, "you told me · 28 Aug", 100, False),
        ("Habits and rules", "Nudge a recruiter after 48h of silence past take-home stage", MemorySource.TOLD, "you told me · 6 Sep", 100, False),
        ("Habits and rules", "Never send anything outbound without approval", MemorySource.RULE, "standing rule · locked", 100, True),
        ("Habits and rules", "Studies best between 21:00 and 01:00", MemorySource.INFERRED, "inferred · task completion times", 64, False),
        ("Life", "Carpool runs Wednesday to Friday with Usman and Hamza", MemorySource.INFERRED, "inferred · 6 carpool splits", 85, False),
    ]:
        db.add(MemoryFact(group=group, statement=statement, source=source, evidence=evidence, confidence=confidence, locked=locked))
    db.flush()
    counts["memory_fact"] = 9

    # --- journal + activity -------------------------------------------------------------------
    log = LogEntryService(db)
    for title, body, tags, days_ago, hour in [
        ("Raft election finally stable", "Rewrote the timeout range to 150–300ms with jitter. Split votes down to about 1 in 40 runs, from 1 in 4. Log compaction is still a stub and assignment 3 does not ask for it.", ["#code", "#study"], 0, 14),
        ("Sat the ML quiz", "The bagging question came up almost verbatim from lecture 6.", ["#study"], 0, 11),
        ("Read back the Kestrel take-home before the follow-up went out", "", ["#jobs"], 0, 9),
        ("Milestone 1 review went fine", "Dr. Naveed wants the prototype before the report. Hamza owns the evaluation design.", ["#fyp"], 1, 16),
        ("Fixed the carpool split rounding", "PKR 2,400 three ways is 800 each; the old script gave 799.", ["#code"], 3, 22),
    ]:
        log.create(LogEntryCreate(title=title, body=body, tags=tags, occurred_at=_at(-days_ago, hour), source=ActorSource.YOU, source_label="you"))
    counts["log_entry"] = 5

    for activity_kind, summary, tool, risk, hours_ago in [
        (ActivityKind.TOOL_CALL, "Structured 3 new remote postings into Jobs · discovery", "discover_postings", Risk.WRITE_LOCAL, 3),
        (ActivityKind.TOOL_CALL, "Extracted 6 deadlines from CS4053 slide deck 07", "extract_deadlines", Risk.WRITE_LOCAL, 4),
        (ActivityKind.TOOL_CALL, "Logged PKR 2,400 carpool fuel, split with Usman and Hamza", "log_transaction", Risk.WRITE_LOCAL, 13),
        (ActivityKind.MEMORY, "Updated belief: “targeting backend over frontend” → 78%", "", None, 14),
    ]:
        row = record_activity(db, kind=activity_kind, summary=summary, tool_name=tool, risk=risk, run_id="seed")
        row.created_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    db.flush()
    counts["activity_log"] = 4
    return counts


def main() -> None:
    """--reset wipes and reseeds. --wipe empties it and stops, for starting from nothing."""
    do_wipe = "--wipe" in sys.argv
    do_reset = "--reset" in sys.argv
    with session_scope() as db:
        if do_wipe or do_reset:
            reset(db)
        elif db.query(Person).count() > 0:
            print("Database already has people. Use --reset to wipe and reseed, or --wipe to just empty it.", file=sys.stderr)
            sys.exit(1)
        if do_wipe:
            print("Wiped. Every record is gone; the owner login and migration history remain.")
            return
        counts = seed(db)
    for table, n in counts.items():
        print(f"{table:16} {n}")


if __name__ == "__main__":
    main()
