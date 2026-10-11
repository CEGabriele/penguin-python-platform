"""
Comprehensive load test for the Penguin Coding School dashboard and editor.

Setup: First run:
  export DJANGO_SETTINGS_MODULE=mysite.settings.dev
  export LOAD_TEST_PASSWORD=<password for the test accounts>
  python manage.py setup_load_test --num-students 10 --num-classes 2

Then run the load test (LOAD_TEST_PASSWORD must be set in this shell too):
  locust -f locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 in your browser
"""
from locust import HttpUser, task, between, events
import os
import random
import logging
import re
import json

logger = logging.getLogger(__name__)

LOAD_TEST_PASSWORD = os.environ["LOAD_TEST_PASSWORD"]


class LoadTestUser(HttpUser):
    """Base class for load testing users with session management."""
    abstract = True

    def __init__(self, environment):
        super().__init__(environment)
        self.class_codes = []
        self.assignment_ids = []
        self.project_ids = []
        self.current_project_id = None

    def extract_csrf_token(self, response_text):
        """Extract CSRF token from HTML response."""
        csrf_match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', response_text)
        if not csrf_match:
            csrf_match = re.search(r'value="([^"]+)"\s+name="csrfmiddlewaretoken"', response_text)
        return csrf_match.group(1) if csrf_match else None

    def get_csrf_from_cookies(self):
        """Get CSRF token from cookies (post-login)."""
        return self.client.cookies.get("csrftoken")

    def login(self, username, password):
        """Authenticate user and maintain session."""
        try:
            # GET login page for CSRF token
            response = self.client.get("/accounts/login/", allow_redirects=False)
            if response.status_code != 200:
                logger.error(f"Failed to load login page (HTTP {response.status_code})")
                return False

            csrf_token = self.extract_csrf_token(response.text)
            if not csrf_token:
                logger.error("Could not extract CSRF token from login page")
                return False

            # POST login form
            headers = {
                "Referer": f"{self.client.base_url}/accounts/login/",
                "X-CSRFToken": csrf_token
            }

            login_data = {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": csrf_token
            }

            response = self.client.post(
                "/accounts/login/",
                data=login_data,
                headers=headers,
                allow_redirects=True,
                name="/accounts/login/"
            )

            # Check if login succeeded (should redirect to dashboard)
            success = (response.status_code == 200 and
                      ("dashboard" in response.url.lower() or "student" in response.url.lower()))

            if success:
                logger.info(f"✓ Login successful: {username}")
                return True
            else:
                logger.error(f"✗ Login failed for {username} (HTTP {response.status_code}, URL: {response.url})")
                return False

        except Exception as e:
            logger.error(f"Login exception for {username}: {e}")
            return False

    def get_assignment_id_from_class(self, class_code):
        """
        Navigate to a student class view and extract the first available assignment.
        Returns: (assigned_id, assignment_id) tuple or (None, None) if none found
        """
        try:
            response = self.client.get(
                f"/dashboard/student-class-view/{class_code}/",
                name="/dashboard/student-class-view/[class_code]/"
            )
            if response.status_code != 200:
                return None, None

            # Parse HTML to find assignment links
            # Look for patterns like: assigned_id=<num>
            assigned_id_match = re.search(r'assigned_id=(\d+)', response.text)
            if assigned_id_match:
                return int(assigned_id_match.group(1)), None

            return None, None
        except Exception as e:
            logger.error(f"Error getting assignment from class {class_code}: {e}")
            return None, None

    def create_project_from_assignment(self, assigned_id):
        """
        Open editor with an assignment to auto-create a project.
        Returns project_id if successful, None otherwise.
        """
        try:
            response = self.client.get(
                f"/dashboard/editor/?assigned_id={assigned_id}",
                allow_redirects=True,
                name="/dashboard/editor/?assigned_id=[id]"
            )

            if response.status_code != 200:
                logger.error(f"Failed to open editor for assigned_id={assigned_id}")
                return None

            # Extract project ID from HTML if present
            # Look for data-project-id or similar
            project_id_match = re.search(r'data-project-id="?(\d+)"?', response.text)
            if project_id_match:
                return int(project_id_match.group(1))

            # Alternative: look in JavaScript variables
            js_match = re.search(r'projectId\s*=\s*(\d+)', response.text)
            if js_match:
                return int(js_match.group(1))

            logger.debug(f"Could not extract project_id from editor response")
            return None

        except Exception as e:
            logger.error(f"Error creating project from assignment: {e}")
            return None

    def get_student_dashboard(self):
        """Fetch student dashboard and extract available class codes."""
        try:
            response = self.client.get(
                "/dashboard/student-dashboard/",
                name="/dashboard/student-dashboard/"
            )
            if response.status_code != 200:
                logger.error(f"Failed to get student dashboard (HTTP {response.status_code})")
                return []

            # Extract class codes from links
            # Pattern: /dashboard/student-class-view/<CODE>/
            class_codes = re.findall(r'/dashboard/student-class-view/([A-Z0-9]+)/', response.text)
            return list(set(class_codes))  # Remove duplicates

        except Exception as e:
            logger.error(f"Error getting student dashboard: {e}")
            return []

    def autosave_code(self, project_id, code, path="main.py"):
        """Autosave code to a project."""
        try:
            payload = {
                "code": code,
                "path": path,
                "project_id": project_id
            }

            csrf_token = self.get_csrf_from_cookies()
            headers = {}
            if csrf_token:
                headers["X-CSRFToken"] = csrf_token

            response = self.client.post(
                "/dashboard/editor/",
                json=payload,
                headers=headers,
                name="/dashboard/editor/ [autosave]"
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error autosaving code: {e}")
            return False

    def create_file(self, project_id, path, content=""):
        """Create a new file in a project."""
        try:
            payload = {
                "code": content,
                "path": path,
                "project_id": project_id
            }

            csrf_token = self.get_csrf_from_cookies()
            headers = {}
            if csrf_token:
                headers["X-CSRFToken"] = csrf_token

            response = self.client.post(
                "/dashboard/editor/",
                json=payload,
                headers=headers,
                name="/dashboard/editor/ [create_file]"
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error creating file: {e}")
            return False

    def list_files(self, project_id):
        """List files in a project."""
        try:
            response = self.client.get(
                f"/dashboard/editor/project/{project_id}/files/",
                name="/dashboard/editor/project/[id]/files/"
            )
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return False


class StudentLoadTestUser(LoadTestUser):
    """Simulates a student using the dashboard and editor."""
    wait_time = between(1, 3)

    def on_start(self):
        """Initialize student user."""
        # Randomly select a test student
        num_students = 10  # Must match setup_load_test default
        student_num = random.randint(1, num_students)
        username = f"loadtest_student{student_num}"
        password = LOAD_TEST_PASSWORD

        if not self.login(username, password):
            raise Exception(f"Failed to login as {username}")

        # Get available classes
        self.class_codes = self.get_student_dashboard()
        logger.info(f"✓ Student {username} has {len(self.class_codes)} class(es)")

        if not self.class_codes:
            logger.warning(f"Student {username} has no classes enrolled")

    @task(3)
    def view_dashboard(self):
        """View student dashboard (most common action)."""
        self.client.get("/dashboard/student-dashboard/", name="/dashboard/student-dashboard/")

    @task(2)
    def view_class(self):
        """View a class and its assignments."""
        if not self.class_codes:
            return

        class_code = random.choice(self.class_codes)
        response = self.client.get(
            f"/dashboard/student-class-view/{class_code}/",
            name="/dashboard/student-class-view/[class_code]/",
            allow_redirects=True
        )

        # Extract an assignment from this class
        if response.status_code == 200:
            assigned_id_match = re.search(r'assigned_id=(\d+)', response.text)
            if assigned_id_match:
                assigned_id = int(assigned_id_match.group(1))
                # Try to create/access a project for this assignment
                project_id = self.create_project_from_assignment(assigned_id)
                if project_id:
                    self.current_project_id = project_id
                    self.project_ids.append(project_id)

    @task(5)
    def open_editor_and_work(self):
        """Open editor, edit code, and autosave."""
        if not self.class_codes:
            return

        class_code = random.choice(self.class_codes)

        # Get an assignment for this class
        assigned_id, _ = self.get_assignment_id_from_class(class_code)
        if not assigned_id:
            return

        # Create/open project for this assignment
        project_id = self.create_project_from_assignment(assigned_id)
        if not project_id:
            return

        self.current_project_id = project_id

        # Simulate some code edits with different code samples
        code_samples = [
            'print("Hello from load test")',
            'x = 42\nprint(f"The answer is {x}")',
            'for i in range(10):\n    print(i)',
            'name = input("Enter your name: ")\nprint(f"Hello, {name}!")',
            'result = sum([1, 2, 3, 4, 5])\nprint(result)',
        ]

        code = random.choice(code_samples)
        self.autosave_code(project_id, code)

    @task(2)
    def create_new_file(self):
        """Create a new file in the current project."""
        if not self.current_project_id:
            return

        # Use one of the project IDs from recent activity
        if self.project_ids:
            project_id = random.choice(self.project_ids[-5:])  # Recent projects
            filename = f"module_{random.randint(1, 100)}.py"
            self.create_file(project_id, filename, 'def hello():\n    pass\n')

    @task(1)
    def list_project_files(self):
        """List files in the current project."""
        if self.project_ids:
            project_id = random.choice(self.project_ids)
            self.list_files(project_id)


class TeacherLoadTestUser(LoadTestUser):
    """Simulates a teacher viewing classes and student submissions."""
    wait_time = between(2, 5)

    def on_start(self):
        """Initialize teacher user."""
        username = "loadtest_teacher1"
        password = LOAD_TEST_PASSWORD

        if not self.login(username, password):
            raise Exception(f"Failed to login as {username}")

        logger.info("✓ Teacher user logged in")

        # Fetch the teacher's actual classes from the dashboard
        self.class_codes = self.get_teacher_classes()
        if not self.class_codes:
            logger.warning("Teacher has no classes")
        else:
            logger.info(f"✓ Teacher has {len(self.class_codes)} class(es): {self.class_codes}")

    def get_teacher_classes(self):
        """Extract teacher's actual class codes from dashboard."""
        try:
            response = self.client.get("/dashboard/teacher-dashboard/")
            if response.status_code != 200:
                return []

            # Extract class codes from links: /dashboard/teacher-class-view/<CODE>/
            class_codes = re.findall(r'/dashboard/teacher-class-view/([A-Z0-9]+)/', response.text)
            return list(set(class_codes))  # Remove duplicates
        except Exception as e:
            logger.error(f"Error fetching teacher classes: {e}")
            return []

    @task(2)
    def view_teacher_dashboard(self):
        """View teacher dashboard."""
        self.client.get("/dashboard/teacher-dashboard/", name="/dashboard/teacher-dashboard/")

    @task(3)
    def view_class(self):
        """View a teacher's class."""
        if not self.class_codes:
            return

        code = random.choice(self.class_codes)
        self.client.get(
            f"/dashboard/teacher-class-view/{code}/",
            name="/dashboard/teacher-class-view/[class_code]/",
            allow_redirects=True
        )

    @task(2)
    def view_submissions(self):
        """View student submissions (teacher view)."""
        if not self.class_codes:
            return

        # Get a random class and try to find assignments
        code = random.choice(self.class_codes)
        try:
            response = self.client.get(f"/dashboard/teacher-class-view/{code}/")
            if response.status_code == 200:
                # Extract assignment IDs from the class view
                assignment_ids = re.findall(r'/dashboard/assignment/(\d+)/submissions/', response.text)
                if assignment_ids:
                    assignment_id = random.choice(assignment_ids)
                    self.client.get(
                        f"/dashboard/assignment/{assignment_id}/submissions/",
                        name="/dashboard/assignment/[id]/submissions/ [teacher]",
                        allow_redirects=True
                    )
        except Exception as e:
            logger.error(f"Error viewing submissions: {e}")

    @task(1)
    def view_student_code(self):
        """View a student's project code."""
        # This would normally be accessed through submissions view
        # Using a sample project_id; in practice teachers discover these
        if self.project_ids:
            project_id = random.choice(self.project_ids)
            self.client.get(
                f"/dashboard/editor/?project_id={project_id}",
                name="/dashboard/editor/?project_id=[id] [teacher]",
                allow_redirects=True
            )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    logger.info("=" * 70)
    logger.info("LOAD TEST STARTED")
    logger.info(f"Host: {environment.host}")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Before starting, ensure test data is set up:")
    logger.info("  export DJANGO_SETTINGS_MODULE=mysite.settings.dev")
    logger.info("  python manage.py setup_load_test --num-students 10 --num-classes 2")
    logger.info("")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("LOAD TEST COMPLETED")
    logger.info("=" * 70)
