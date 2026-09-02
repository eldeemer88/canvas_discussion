"""Stand-in Canvas API that returns a 403, for capturing the SOP's failure figure."""
import os

from flask import Flask, jsonify, request

app = Flask(__name__)

COURSES = [
    {"id": 271234, "name": "BEHV 1750 Behavioral Economics", "workflow_state": "available",
     "term": {"name": "Spring 2026"}, "enrollments": [{"type": "TaEnrollment"}]},
    {"id": 288901, "name": "BEHV 1750 Behavioral Economics (Fall 2026)",
     "workflow_state": "unpublished", "term": {"name": "Fall 2026"},
     "enrollments": [{"type": "TaEnrollment"}]},
]

@app.get("/api/v1/courses/<cid>")
def course(cid):
    # The course the user typed: real, but not accessible to them yet.
    return jsonify({"status": "unauthorized",
                    "errors": [{"message": "user not authorized to perform that action"}]}), 403

@app.get("/api/v1/users/self")
def me():
    return jsonify({"id": 4242, "name": "Ethan Deemer"})

@app.get("/api/v1/courses")
def courses():
    state = request.args.get("enrollment_state")
    return jsonify(COURSES if state == "active" else [])

app.run(port=int(os.environ.get("MOCK_PORT", 5199)), debug=False)
