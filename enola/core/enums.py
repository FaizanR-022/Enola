"""Every closed vocabulary in the system, in one place.

These are exported to the web app (`python -m enola.scripts.export_enums`) so both
sides share one definition. No string literals for these anywhere else.
"""

from __future__ import annotations

from enum import StrEnum


class Risk(StrEnum):
    """Risk classification of an agent tool. Lives in the registry, never in tool bodies."""

    SAFE = "safe"
    WRITE_LOCAL = "write_local"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"
    # Assigned when a tool is registered without a risk level. Always gated: this is
    # what keeps the gate from eroding when someone forgets the argument.
    UNCLASSIFIED = "unclassified"


GATED_RISKS: frozenset[Risk] = frozenset({Risk.EXTERNAL, Risk.DESTRUCTIVE, Risk.UNCLASSIFIED})


class ApprovalState(StrEnum):
    HELD = "held"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaskState(StrEnum):
    OPEN = "open"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskSource(StrEnum):
    YOU = "you"
    ENOLA = "enola"
    ASSESSMENT = "assessment"
    EMAIL = "email"


class EntityType(StrEnum):
    """Targets for polymorphic links (task_link, document, notification)."""

    PERSON = "person"
    TASK = "task"
    COMPANY = "company"
    APPLICATION = "application"
    JOB_POSTING = "job_posting"
    COURSE = "course"
    ASSESSMENT = "assessment"
    FYP_MILESTONE = "fyp_milestone"
    PROJECT = "project"
    LEARNING_GOAL = "learning_goal"
    TRANSACTION = "transaction"
    APPROVAL_REQUEST = "approval_request"
    DOCUMENT = "document"


class InteractionKind(StrEnum):
    CALL = "call"
    EMAIL = "email"
    MESSAGE = "message"
    MEETING = "meeting"
    NOTE = "note"


class ActorSource(StrEnum):
    """Who produced a record: the owner, Enola, or an ingested source."""

    YOU = "you"
    ENOLA = "enola"
    EMAIL = "email"
    CALENDAR = "calendar"
    IMPORT = "import"


class ApplicationStage(StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    CLOSED = "closed"


class ApplicationEventKind(StrEnum):
    NOTE = "note"
    APPLIED = "applied"
    EMAIL = "email"
    CALL = "call"
    TAKE_HOME = "take_home"
    INTERVIEW = "interview"
    STAGE_CHANGE = "stage_change"
    OFFER = "offer"
    REJECTED = "rejected"
    HELD = "held"


class LocationKind(StrEnum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"


class PostingStatus(StrEnum):
    DISCOVERED = "discovered"
    SAVED = "saved"
    DISMISSED = "dismissed"


class AssessmentKind(StrEnum):
    ASSIGNMENT = "assignment"
    QUIZ = "quiz"
    EXAM = "exam"
    LAB = "lab"
    PROJECT = "project"
    REPORT = "report"


class MilestoneState(StrEnum):
    DONE = "done"
    CURRENT = "current"
    UPCOMING = "upcoming"


class AccountKind(StrEnum):
    BANK = "bank"
    WALLET = "wallet"
    CASH = "cash"


class TransactionKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    SETTLEMENT = "settlement"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    COURSEWORK = "coursework"
    SHELVED = "shelved"
    ARCHIVED = "archived"


class LearningGoalState(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    INGESTED = "ingested"
    FAILED = "failed"


class MemorySource(StrEnum):
    TOLD = "told"  # you said so
    INFERRED = "inferred"  # Enola worked it out
    RULE = "rule"  # a standing rule, locked


class MemoryState(StrEnum):
    ACTIVE = "active"
    FORGOTTEN = "forgotten"


class NotificationKind(StrEnum):
    TASK_DUE = "task_due"
    ACADEMIC_DEADLINE = "academic_deadline"
    FOLLOWUP_NUDGE = "followup_nudge"
    DAILY_BRIEF = "daily_brief"
    HELD = "held"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"


class NotificationState(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class ActivityKind(StrEnum):
    TOOL_CALL = "tool_call"
    HELD = "held"
    APPROVED = "approved"
    REJECTED = "rejected"
    JOB_RUN = "job_run"
    MEMORY = "memory"
    NOTE = "note"


ALL_ENUMS: tuple[type[StrEnum], ...] = (
    Risk,
    ApprovalState,
    TaskState,
    TaskPriority,
    TaskSource,
    EntityType,
    InteractionKind,
    ActorSource,
    ApplicationStage,
    ApplicationEventKind,
    LocationKind,
    PostingStatus,
    AssessmentKind,
    MilestoneState,
    AccountKind,
    TransactionKind,
    ProjectStatus,
    LearningGoalState,
    DocumentStatus,
    MemorySource,
    MemoryState,
    NotificationKind,
    NotificationChannel,
    NotificationState,
    ActivityKind,
)
