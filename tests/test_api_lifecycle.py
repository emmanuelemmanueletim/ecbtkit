"""HTTP lifecycle integration checks for the supported Starlette application."""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from starlette.testclient import TestClient
from starlette.responses import JSONResponse
from starlette.routing import Route

from ecbtkit.core.app import CBT
from ecbtkit.core.config import Settings, set_settings, get_settings
from ecbtkit.db.base import get_session_factory
from ecbtkit.models.attempt import Answer
from ecbtkit.models.attempt import Attempt, AttemptStatus
from ecbtkit.models.exam import Exam, ExamStatus
from ecbtkit.models.candidate import Candidate
from ecbtkit.models.question import Difficulty, Question, QuestionOption, QuestionStatus, QuestionType, Subject, Topic
from ecbtkit.engine.selection import QuestionSelector
from ecbtkit.core.exceptions import InsufficientQuestionsError
from ecbtkit.models.user import User, UserRole
from ecbtkit.security.passwords import hash_password
from ecbtkit.security.tokens import create_token_pair_for_user


class ExamLifecycleHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db_path = Path(self.temp_dir.name) / "test.db"
        settings = Settings(
            _env_file=None,
            database_url=f"sqlite:///{db_path.as_posix()}",
            database_auto_create=True,
            cors_origins=[],
        )
        set_settings(settings)
        get_settings.cache_clear()
        set_settings(settings)
        from ecbtkit.db import base as db_base
        db_base._engine = None
        db_base._SessionLocal = None
        self.cbt = CBT(settings)
        self.client = TestClient(self.cbt.app)
        self.db: Session = get_session_factory()()
        admin = User(
            email="admin@example.test",
            hashed_password=hash_password("AdminPass1!"),
            full_name="Admin",
            role=UserRole.ADMINISTRATOR,
            is_active=True,
            is_verified=True,
            refresh_token_jti="admin-jti",
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        self.admin_headers = {"Authorization": f"Bearer {create_token_pair_for_user(admin)['access_token']}"}

    def tearDown(self):
        self.db.close()
        from ecbtkit.db import base
        if base._engine:
            base._engine.dispose()
        from ecbtkit.db import base as db_base
        if db_base._engine:
            db_base._engine.dispose()
            db_base._engine = None
            db_base._SessionLocal = None
        set_settings(None)
        get_settings.cache_clear()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_candidate_can_take_exam_and_get_score_without_answer_key(self):
        signup = self.client.post("/api/v1/auth/signup", json={
            "email": "candidate@example.test",
            "password": "StrongPass1!",
            "full_name": "Candidate",
        })
        self.assertEqual(signup.status_code, 201, signup.text)
        candidate_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        question_response = self.client.post("/api/v1/questions", headers=self.admin_headers, json={
            "text": "2 + 2?",
            "marks": 3,
            "tags": "math,basic",
            "options": [
                {"text": "3", "is_correct": False},
                {"text": "4", "is_correct": True},
            ],
        })
        self.assertEqual(question_response.status_code, 201, question_response.text)
        question_id = question_response.json()["id"]
        correct_option = self.db.query(QuestionOption).filter_by(question_id=question_id, is_correct=True).one()

        exam_response = self.client.post("/api/v1/exams", headers=self.admin_headers, json={
            "title": "Basic arithmetic",
            "question_count": 1,
            "duration_minutes": 20,
            "marks_wrong": -0.5,
        })
        self.assertEqual(exam_response.status_code, 201, exam_response.text)
        exam_id = exam_response.json()["id"]
        publish = self.client.post(f"/api/v1/exams/{exam_id}/publish", headers=self.admin_headers)
        self.assertEqual(publish.status_code, 200, publish.text)

        started = self.client.post(f"/api/v1/exams/{exam_id}/start", headers=candidate_headers)
        self.assertEqual(started.status_code, 201, started.text)
        attempt = started.json()
        public_question = attempt["questions"][0]
        self.assertNotIn("is_correct", str(public_question))

        saved = self.client.post(
            f"/api/v1/attempts/{attempt['id']}/answers",
            headers=candidate_headers,
            json={"question_id": question_id, "selected_option_ids": [correct_option.id]},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        result = self.client.post(
            f"/api/v1/attempts/{attempt['id']}/submit", headers=candidate_headers
        )
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["score"], 3.0)
        self.assertEqual(result.json()["percentage"], 100.0)
        self.assertEqual(self.db.query(Answer).filter_by(attempt_id=attempt["id"]).count(), 1)

    def test_public_question_bank_and_exam_authoring_require_roles(self):
        candidate = self.client.post("/api/v1/auth/signup", json={
            "email": "candidate@example.test",
            "password": "StrongPass1!",
        })
        headers = {"Authorization": f"Bearer {candidate.json()['access_token']}"}
        subject_list = self.client.get("/api/v1/subjects", headers=headers)
        self.assertEqual(subject_list.status_code, 403, subject_list.text)
        create_exam = self.client.post("/api/v1/exams", headers=headers, json={"title": "No"})
        self.assertEqual(create_exam.status_code, 403, create_exam.text)

    def test_custom_routes_and_router_prefix_are_mounted_under_api_prefix(self):
        async def custom_endpoint(request):
            return JSONResponse({"route": "custom"})

        self.cbt.add_route("/custom/one", custom_endpoint)
        self.cbt.include_router([Route("/two", custom_endpoint)], prefix="custom")
        first = self.client.get("/api/v1/custom/one")
        second = self.client.get("/api/v1/custom/two")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json(), {"route": "custom"})

    def test_custom_routes_cannot_shadow_builtin_routes(self):
        async def shadow(request):
            return JSONResponse({"shadowed": True})

        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.cbt.add_route("/auth/signup", shadow, methods=["POST"])

    def test_signup_cannot_assign_staff_roles(self):
        for role in ("examiner", "administrator"):
            response = self.client.post("/api/v1/auth/signup", json={
                "email": f"{role}@example.test",
                "password": "StrongPass1!",
                "role": role,
            })
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.db.query(User).count(), 1)  # only the fixture administrator

    def test_refresh_is_single_use_and_logout_revokes_access(self):
        signup = self.client.post("/api/v1/auth/signup", json={
            "email": "tokens@example.test",
            "password": "StrongPass1!",
        })
        original = signup.json()
        refreshed = self.client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        replay = self.client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
        self.assertEqual(replay.status_code, 401, replay.text)
        headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
        revoked = self.client.post("/api/v1/auth/logout", headers=headers)
        self.assertEqual(revoked.status_code, 200, revoked.text)
        me = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me.status_code, 401, me.text)

    def test_quota_selection_applies_exact_tag_filter_and_requires_full_total(self):
        subject = Subject(name="Math")
        self.db.add(subject)
        self.db.flush()
        topic = Topic(name="Algebra", subject_id=subject.id)
        self.db.add(topic)
        self.db.flush()
        for index, tags in enumerate(("math,basic", "math,advanced", "science")):
            question = Question(
                subject_id=subject.id,
                topic_id=topic.id,
                text=f"Q{index}",
                question_type=QuestionType.SINGLE_CHOICE,
                difficulty=Difficulty.EASY,
                marks=1,
                tags=tags,
                status=QuestionStatus.ACTIVE,
            )
            self.db.add(question)
        self.db.commit()
        selected = QuestionSelector(self.db, seed="stable").select(
            total=1,
            topics={"Algebra": 1},
            tags=["basic"],
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].tags, "math,basic")
        with self.assertRaises(InsufficientQuestionsError):
            QuestionSelector(self.db, seed="stable").select(
                total=2,
                difficulty={"easy": 2},
                tags=["basic"],
            )

    def test_unique_active_attempt_constraint(self):
        user = User(
            email="constraint@example.test",
            hashed_password=hash_password("StrongPass1!"),
            role=UserRole.CANDIDATE,
            is_active=True,
            refresh_token_jti="constraint-jti",
        )
        self.db.add(user)
        self.db.flush()
        candidate = Candidate(user_id=user.id, full_name="Candidate")
        exam = Exam(title="Constraint", status=ExamStatus.PUBLISHED, question_count=1)
        self.db.add_all([candidate, exam])
        self.db.flush()
        self.db.add(Attempt(exam_id=exam.id, candidate_id=candidate.id, status=AttemptStatus.ACTIVE))
        self.db.commit()
        self.db.add(Attempt(exam_id=exam.id, candidate_id=candidate.id, status=AttemptStatus.ACTIVE))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
