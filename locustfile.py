from locust import HttpUser, task, between, events
import random
import logging
import re

logger = logging.getLogger(__name__)

# Test accounts created in Django
STUDENT_CREDENTIALS = [
    {"username": "loadtest_student1", "password": "<removed>"},
    {"username": "loadtest_student2", "password": "<removed>"},
]

TEACHER_CREDENTIALS = {"username": "loadtest_teacher1", "password": "<removed>"}


def login(client, credentials, host):
    """Authenticate a user and maintain session."""
    # Step 1: GET the login page to extract CSRF token
    response = client.get("/accounts/login/")
    if response.status_code != 200:
        logger.error(f"Failed to load login page: {response.status_code}")
        return False

    # Extract CSRF token from HTML (try multiple patterns)
    csrf_token = None
    csrf_match = re.search(r'value="([a-zA-Z0-9]+)"[^>]*name="csrfmiddlewaretoken"', response.text)
    if not csrf_match:
        csrf_match = re.search(r'name="csrfmiddlewaretoken"[^>]*value="([a-zA-Z0-9]+)"', response.text)
    if not csrf_match:
        csrf_match = re.search(r'csrfmiddlewaretoken["\']?\s*[:=]\s*["\']([a-zA-Z0-9]+)', response.text)

    if csrf_match:
        csrf_token = csrf_match.group(1)
        logger.debug(f"Extracted CSRF token: {csrf_token[:20]}...")
    else:
        logger.warning("Could not find CSRF token in login page, trying without it")

    # Step 2: POST login form with CSRF token in headers (AJAX style)
    headers = {}
    if csrf_token:
        headers["X-CSRFToken"] = csrf_token

    login_payload = {
        "username": credentials["username"],
        "password": credentials["password"],
    }
    if csrf_token:
        login_payload["csrfmiddlewaretoken"] = csrf_token

    response = client.post(
        "/accounts/login/",
        data=login_payload,
        headers=headers,
        name="/accounts/login/",
        allow_redirects=True
    )

    # Check if login succeeded (200 OK or redirect to dashboard)
    if response.status_code == 200 and ("/dashboard/" in response.url or "student" in response.url.lower()):
        logger.info(f"Successfully logged in as {credentials['username']}")
        return True
    elif response.status_code in [301, 302]:
        # Successful redirect
        logger.info(f"Successfully logged in as {credentials['username']} (redirected)")
        return True
    else:
        logger.error(f"Login failed for {credentials['username']}: status={response.status_code}, url={response.url}")
        return False


class StudentUser(HttpUser):
    """Simulates a student using the dashboard and editor."""
    wait_time = between(2, 5)

    def on_start(self):
        """Called when a simulated user starts."""
        # Login with a random student account
        creds = random.choice(STUDENT_CREDENTIALS)
        if not login(self.client, creds, self.host):
            logger.error("Student login failed, tasks may not work")
        self.project_id = None
        self.assignment_id = None

    @task(1)
    def view_dashboard(self):
        """View the student dashboard."""
        self.client.get("/dashboard/student-dashboard/", name="/dashboard/student-dashboard/")

    @task(3)
    def view_class(self):
        """View a class and assignments."""
        self.client.get("/dashboard/student-class-view/4A67B3/", name="/dashboard/student-class-view/[class_code]/")

    @task(2)
    def open_editor(self):
        """Open the code editor for an assignment."""
        # In a real scenario, you'd assign real project/assignment IDs
        # This simulates navigating to the editor view
        self.client.get("/dashboard/editor/?assigned_id=1", name="/dashboard/editor/?assigned_id=[id]")

    @task(5)
    def autosave_code(self):
        """Autosave code to a project (the most frequent operation)."""
        payload = {
            "code": "print('Hello, World!')\nprint('Autosaved at ' + str(__import__('datetime').datetime.now()))",
            "path": "main.py",
            "project_id": 1
        }
        # Get CSRF token from cookies (set during login)
        headers = {}
        if "csrftoken" in self.client.cookies:
            headers["X-CSRFToken"] = self.client.cookies["csrftoken"]

        self.client.post(
            "/dashboard/editor/",
            json=payload,
            headers=headers,
            name="/dashboard/editor/ [autosave]"
        )

    @task(1)
    def list_project_files(self):
        """List files in a project."""
        self.client.get("/dashboard/editor/project/1/files/", name="/dashboard/editor/project/[id]/files/")

    @task(1)
    def view_submissions(self):
        """View submitted assignments."""
        self.client.get("/dashboard/assignment/1/submissions/", name="/dashboard/assignment/[id]/submissions/")


class TeacherUser(HttpUser):
    """Simulates a teacher managing classes and viewing submissions."""
    wait_time = between(3, 8)

    def on_start(self):
        """Called when a simulated user starts."""
        # Login with teacher account
        if not login(self.client, TEACHER_CREDENTIALS, self.host):
            logger.error("Teacher login failed, tasks may not work")
        self.class_id = 1
        self.assignment_id = 1

    @task(2)
    def view_dashboard(self):
        """View the teacher dashboard."""
        self.client.get("/dashboard/teacher-dashboard/", name="/dashboard/teacher-dashboard/")

    @task(3)
    def view_class(self):
        """View a specific class."""
        self.client.get(
            "/dashboard/teacher-class-view/4A67B3/",
            name="/dashboard/teacher-class-view/[class_code]/"
        )

    @task(2)
    def view_assignments(self):
        """View assignments for a class."""
        self.client.get(
            "/dashboard/teacher-assignment/1/",
            name="/dashboard/teacher-assignment/[id]/"
        )

    @task(3)
    def view_submissions(self):
        """View student submissions for an assignment."""
        self.client.get(
            f"/dashboard/assignment/{self.assignment_id}/submissions/",
            name="/dashboard/assignment/[id]/submissions/ [teacher]"
        )

    @task(1)
    def view_student_project(self):
        """View a student's project code."""
        # Teacher viewing student project
        self.client.get(
            "/dashboard/editor/?project_id=1",
            name="/dashboard/editor/?project_id=[id] [teacher]"
        )

    @task(1)
    def get_project_files(self):
        """Get list of files for a student project (teacher view)."""
        self.client.get(
            "/dashboard/editor/project/1/teacher-files/",
            name="/dashboard/editor/project/[id]/teacher-files/"
        )


class LightUser(HttpUser):
    """Simulates a user with minimal, infrequent interactions."""
    wait_time = between(5, 15)

    def on_start(self):
        """Called when a simulated user starts."""
        # Login with a random student account
        creds = random.choice(STUDENT_CREDENTIALS)
        if not login(self.client, creds, self.host):
            logger.error("Light user login failed, tasks may not work")

    @task(1)
    def view_dashboard(self):
        """Occasionally view student dashboard."""
        self.client.get("/dashboard/student-dashboard/", name="/dashboard/student-dashboard/ [light]")

    @task(1)
    def view_editor_projects(self):
        """Check list of projects."""
        self.client.get("/dashboard/editor/projects/", name="/dashboard/editor/projects/")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    logger.info("=" * 60)
    logger.info("Load Test Started")
    logger.info(f"Host: {environment.host}")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops."""
    logger.info("=" * 60)
    logger.info("Load Test Completed")
    logger.info("=" * 60)
