"""
Minimal eCBTKit application (v0.1 — FastAPI-independent).

    pip install -e .
    python examples/basic_app.py

Open http://127.0.0.1:8000/docs
"""

from ecbtkit import CBT

app = CBT()

maths = app.exam(
    name="Engineering Mathematics",
    duration_minutes=60,
    question_count=20,
    randomize_questions=True,
    randomize_options=True,
    pass_mark=40.0,
    marks_correct=1.0,
    marks_wrong=-0.25,
)
maths.select_questions(
    subject="Mathematics",
    topics={"Algebra": 8, "Geometry": 6, "Calculus": 6},
)

if __name__ == "__main__":
    print("eCBTKit v0.1 — http://127.0.0.1:8000/docs")
    app.run(host="127.0.0.1", port=8000)
