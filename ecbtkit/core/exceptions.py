"""
Structured error system for eCBTKit.

Every application error has:
  - code       (machine-readable, stable)
  - message    (human-readable)
  - details    (optional context)
  - status_code (HTTP)
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ECBTError(Exception):
    """Base exception for all eCBTKit errors."""

    def __init__(
        self,
        message: str,
        code: str = "ECBT_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 400,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


# ---- Auth -----------------------------------------------------------------

class AuthenticationError(ECBTError):
    def __init__(self, message: str = "Authentication required", details: Optional[Dict] = None):
        super().__init__(message, "AUTHENTICATION_REQUIRED", details, 401)


class InvalidCredentialsError(AuthenticationError):
    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message)
        self.code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    def __init__(self, message: str = "Token has expired"):
        super().__init__(message)
        self.code = "TOKEN_EXPIRED"


class TokenInvalidError(AuthenticationError):
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)
        self.code = "TOKEN_INVALID"


class AccountLockedError(AuthenticationError):
    def __init__(self, minutes: int = 15):
        super().__init__(
            f"Account temporarily locked. Try again in {minutes} minutes.",
            details={"lockout_minutes": minutes},
        )
        self.code = "ACCOUNT_LOCKED"
        self.status_code = 423


class AccountDisabledError(AuthenticationError):
    def __init__(self, message: str = "Account is disabled"):
        super().__init__(message)
        self.code = "ACCOUNT_DISABLED"


class EmailNotVerifiedError(AuthenticationError):
    def __init__(self, message: str = "Email address is not verified"):
        super().__init__(message)
        self.code = "EMAIL_NOT_VERIFIED"


class AuthorizationError(ECBTError):
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict] = None):
        super().__init__(message, "FORBIDDEN", details, 403)


class PasswordPolicyError(ECBTError):
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "PASSWORD_POLICY_VIOLATION", details, 422)


class RateLimitError(ECBTError):
    def __init__(self, message: str = "Too many requests. Please slow down.", retry_after: int = 60):
        super().__init__(message, "RATE_LIMIT_EXCEEDED", {"retry_after": retry_after}, 429)


# ---- Resources ------------------------------------------------------------

class NotFoundError(ECBTError):
    def __init__(self, resource: str = "Resource", resource_id: Any = None):
        details: Dict[str, Any] = {"resource": resource}
        if resource_id is not None:
            details["id"] = str(resource_id)
        super().__init__(f"{resource} not found", "NOT_FOUND", details, 404)


class ExamNotFoundError(NotFoundError):
    def __init__(self, exam_id: Any = None):
        super().__init__("Examination", exam_id)
        self.code = "EXAM_NOT_FOUND"


class QuestionNotFoundError(NotFoundError):
    def __init__(self, question_id: Any = None):
        super().__init__("Question", question_id)
        self.code = "QUESTION_NOT_FOUND"


class AttemptNotFoundError(NotFoundError):
    def __init__(self, attempt_id: Any = None):
        super().__init__("Attempt", attempt_id)
        self.code = "ATTEMPT_NOT_FOUND"


class CandidateNotFoundError(NotFoundError):
    def __init__(self, candidate_id: Any = None):
        super().__init__("Candidate", candidate_id)
        self.code = "CANDIDATE_NOT_FOUND"


class ResultNotFoundError(NotFoundError):
    def __init__(self, result_id: Any = None):
        super().__init__("Result", result_id)
        self.code = "RESULT_NOT_FOUND"


class ConflictError(ECBTError):
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "CONFLICT", details, 409)


class ValidationError(ECBTError):
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message, "VALIDATION_ERROR", details, 422)


# ---- Exam lifecycle -------------------------------------------------------

class ExamNotPublishedError(ECBTError):
    def __init__(self, message: str = "Examination is not published"):
        super().__init__(message, "EXAM_NOT_PUBLISHED", status_code=400)


class ExamNotAvailableError(ECBTError):
    def __init__(self, message: str = "Examination is not currently available"):
        super().__init__(message, "EXAM_NOT_AVAILABLE", status_code=400)


class AttemptLimitExceededError(ECBTError):
    def __init__(self, message: str = "Maximum number of attempts reached"):
        super().__init__(message, "ATTEMPT_LIMIT_EXCEEDED", status_code=400)


class InvalidAttemptStateError(ECBTError):
    def __init__(self, current: str, expected: str):
        super().__init__(
            f"Invalid attempt state. Current: {current}, expected: {expected}",
            "INVALID_ATTEMPT_STATE",
            {"current": current, "expected": expected},
            400,
        )


class ExamExpiredError(ECBTError):
    def __init__(self, message: str = "This examination attempt has expired"):
        super().__init__(message, "EXAM_EXPIRED", status_code=400)


class AttemptAlreadySubmittedError(ECBTError):
    def __init__(self, message: str = "This attempt has already been submitted"):
        super().__init__(message, "ATTEMPT_ALREADY_SUBMITTED", status_code=400)


class AttemptNotActiveError(ECBTError):
    def __init__(self, message: str = "Attempt is not active"):
        super().__init__(message, "ATTEMPT_NOT_ACTIVE", status_code=400)


class InsufficientQuestionsError(ECBTError):
    def __init__(self, required: int, available: int, criteria: Optional[Dict] = None):
        super().__init__(
            f"Insufficient questions. Required: {required}, available: {available}",
            "INSUFFICIENT_QUESTIONS",
            {"required": required, "available": available, "criteria": criteria or {}},
            400,
        )


class QuestionNotInAttemptError(ECBTError):
    def __init__(self, question_id: Any = None):
        super().__init__(
            "Question was not assigned to this attempt",
            "QUESTION_NOT_IN_ATTEMPT",
            {"question_id": str(question_id) if question_id else None},
            400,
        )


class InvalidScoringRuleError(ValidationError):
    def __init__(self, message: str = "Invalid scoring rule configuration"):
        super().__init__(message)
        self.code = "INVALID_SCORING_RULE"


class InvalidGradingScaleError(ValidationError):
    def __init__(self, message: str = "Invalid grading scale configuration"):
        super().__init__(message)
        self.code = "INVALID_GRADING_SCALE"


class ConcurrentModificationError(ECBTError):
    def __init__(self, message: str = "Resource was modified concurrently"):
        super().__init__(message, "CONCURRENT_MODIFICATION", status_code=409)


class IntegrityError(ECBTError):
    def __init__(self, message: str = "Data integrity violation"):
        super().__init__(message, "INTEGRITY_ERROR", status_code=409)
