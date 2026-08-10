from locust import HttpUser, task, between, events
import logging

logger = logging.getLogger(__name__)


class HealthCheckUser(HttpUser):
    """Tests the public health check endpoint."""
    wait_time = between(1, 3)

    @task(5)
    def health_check(self):
        """Check system health (DB, S3, etc)."""
        self.client.get("/healthz/", name="/healthz/")

    @task(2)
    def health_check_no_slash(self):
        """Health check without trailing slash."""
        self.client.get("/healthz", name="/healthz")

    @task(1)
    def unauthenticated_dashboard_redirect(self):
        """Try to access dashboard (will redirect to login)."""
        self.client.get("/dashboard/student-dashboard/",
                       allow_redirects=False,
                       name="/dashboard/student-dashboard/ [no-redirect]")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("Load Test Started (Health Check Focus)")
    logger.info(f"Host: {environment.host}")
    logger.info("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logger.info("=" * 60)
    logger.info("Load Test Completed")
    logger.info("=" * 60)
