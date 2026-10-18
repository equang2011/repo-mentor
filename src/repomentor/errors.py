"""Exception types. Every message should tell the user what to do next."""


class RepoMentorError(Exception):
    """Base class for expected, user-facing errors."""

    exit_code = 2


class ChallengeError(RepoMentorError):
    """A challenge is unknown, unvalidated, or otherwise unusable."""


class ManifestError(ChallengeError):
    """A manifest.json is missing, malformed, or inconsistent."""


class ValidationError(RepoMentorError):
    """A `validate` check failed."""


class WorkspaceError(RepoMentorError):
    """Creating or using a workspace failed."""


class SessionError(RepoMentorError):
    """A session id is unknown or its metadata is unreadable."""


class GraderError(RepoMentorError):
    """The grader itself failed (as opposed to the candidate's fix failing)."""

    exit_code = 3


class ToolError(RepoMentorError):
    """An external tool (git, python, pip) is missing or failed."""
