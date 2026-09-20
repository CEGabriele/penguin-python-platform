"""
Browser-based load test for the editor and Web Worker code execution.
Tests that students can run code concurrently without breaking the server/editor.

Install: pip install playwright
Setup browsers: playwright install
Run: python load_test_browser.py
"""

import asyncio
import time
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_URL = "https://portal.penguincodingschool.com"

# Test code samples to run
CODE_SAMPLES = [
    'print("Hello, World!")',
    'x = 42\nprint(f"Answer: {x}")',
    'for i in range(5):\n    print(i)',
    'result = sum([1, 2, 3, 4, 5])\nprint(result)',
    'name = "Student"\nprint(f"Hello {name}")',
]


async def load_editor_and_run_code(student_num, test_duration_seconds=60):
    """
    Simulates a single student:
    1. Login
    2. Open editor
    3. Wait for Pyodide to load
    4. Run code multiple times
    5. Close
    """
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        start_time = time.time()
        code_runs = 0
        errors = []

        try:
            logger.info(f"[Student {student_num}] Starting browser session")

            # Step 1: Login
            logger.info(f"[Student {student_num}] Logging in...")
            await page.goto(f"{BASE_URL}/accounts/login/")
            await page.fill('input[name="username"]', f'loadtest_student{student_num}')
            await page.fill('input[name="password"]', '<removed>')
            await page.click('button[type="submit"]')

            try:
                await page.wait_for_url("**/dashboard/**", timeout=30000)
            except PlaywrightTimeoutError:
                errors.append("Login timeout")
                return {
                    "student": student_num,
                    "duration": time.time() - start_time,
                    "code_runs": code_runs,
                    "errors": errors,
                    "success": False
                }

            logger.info(f"[Student {student_num}] Login successful")

            # Step 2: Get a valid project ID from dashboard
            logger.info(f"[Student {student_num}] Fetching project...")
            await page.goto(f"{BASE_URL}/dashboard/student-dashboard/")

            try:
                # Wait for dashboard to load
                await page.wait_for_selector('a', timeout=10000)

                # Extract project ID from any project link on the dashboard
                # Look for links like /dashboard/editor/?project_id=<ID> or /dashboard/editor/?assigned_id=<ID>
                result = await page.evaluate("""() => {
                    const links = document.querySelectorAll('a');
                    for (let link of links) {
                        const href = link.getAttribute('href') || '';

                        // Try project_id first
                        let match = href.match(/project_id=(\\d+)/);
                        if (match) return {type: 'project_id', id: match[1]};

                        // Try assigned_id
                        match = href.match(/assigned_id=(\\d+)/);
                        if (match) return {type: 'assigned_id', id: match[1]};
                    }

                    // Debug: log all links found
                    console.log('Links found:', Array.from(links).map(l => l.href));
                    return null;
                }""")

                if not result:
                    logger.error(f"[Student {student_num}] Could not find project or assignment ID")
                    # Get page HTML for debugging
                    page_content = await page.content()
                    logger.debug(f"Dashboard HTML snippet: {page_content[:500]}")
                    errors.append("No project/assignment found on dashboard")
                    return {
                        "student": student_num,
                        "duration": time.time() - start_time,
                        "code_runs": code_runs,
                        "errors": errors,
                        "success": False
                    }

                logger.info(f"[Student {student_num}] Using {result['type']}={result['id']}")
            except Exception as e:
                logger.error(f"[Student {student_num}] Error fetching project: {e}")
                errors.append(f"Project fetch error: {str(e)}")
                return {
                    "student": student_num,
                    "duration": time.time() - start_time,
                    "code_runs": code_runs,
                    "errors": errors,
                    "success": False
                }

            # Step 3: Open editor with the project/assignment
            logger.info(f"[Student {student_num}] Opening editor...")
            editor_url = f"{BASE_URL}/dashboard/editor/?{result['type']}={result['id']}"
            await page.goto(editor_url)

            # Step 4: Wait for editor to load (Monaco editor)
            try:
                # Wait for the editor div to be visible
                await page.wait_for_selector('#editor', timeout=15000)
                logger.info(f"[Student {student_num}] Editor loaded")
            except PlaywrightTimeoutError:
                errors.append("Editor load timeout")
                logger.warning(f"[Student {student_num}] Editor failed to load")
                return {
                    "student": student_num,
                    "duration": time.time() - start_time,
                    "code_runs": code_runs,
                    "errors": errors,
                    "success": False
                }

            # Step 5: Wait for Pyodide/Web Worker to initialize
            # Look for the Run button that indicates readiness
            logger.info(f"[Student {student_num}] Waiting for Pyodide to initialize...")
            try:
                await page.wait_for_selector('button.icon-btn', timeout=20000)
                logger.info(f"[Student {student_num}] Pyodide ready")
            except PlaywrightTimeoutError:
                errors.append("Pyodide initialization timeout")
                logger.warning(f"[Student {student_num}] Pyodide failed to initialize")
                return {
                    "student": student_num,
                    "duration": time.time() - start_time,
                    "code_runs": code_runs,
                    "errors": errors,
                    "success": False
                }

            # Step 6: Run code multiple times
            logger.info(f"[Student {student_num}] Running code...")
            code_index = 0

            while time.time() - start_time < test_duration_seconds:
                code = CODE_SAMPLES[code_index % len(CODE_SAMPLES)]
                code_index += 1

                try:
                    # Click inside Monaco editor to focus it
                    await page.click('#editor', timeout=5000)
                    await page.wait_for_timeout(500)  # Let it focus

                    # Clear existing code (Ctrl+A, Delete)
                    await page.keyboard.press('Control+A')
                    await page.keyboard.press('Delete')
                    await page.wait_for_timeout(200)

                    # Type new code
                    await page.keyboard.type(code, delay=5)
                    await page.wait_for_timeout(500)

                    # Click Run button (icon-btn with fa-solid fa-play)
                    await page.click('button.icon-btn', timeout=5000)

                    # Wait for output or just give time for code to run
                    # (might not have a dedicated output element, just wait a bit)
                    await page.wait_for_timeout(2000)

                    code_runs += 1
                    logger.info(f"[Student {student_num}] Code run #{code_runs} completed")

                    # Small delay between runs
                    await asyncio.sleep(1)

                except PlaywrightTimeoutError as e:
                    errors.append(f"Code run #{code_runs + 1} timeout")
                    logger.warning(f"[Student {student_num}] Code run timeout: {e}")
                except Exception as e:
                    errors.append(f"Code run error: {str(e)}")
                    logger.warning(f"[Student {student_num}] Error during code run: {e}")

            elapsed = time.time() - start_time
            logger.info(f"[Student {student_num}] Completed: {code_runs} code runs in {elapsed:.1f}s")

            return {
                "student": student_num,
                "duration": elapsed,
                "code_runs": code_runs,
                "errors": errors,
                "success": len(errors) == 0 or code_runs > 0
            }

        except Exception as e:
            logger.error(f"[Student {student_num}] Unexpected error: {e}")
            errors.append(f"Unexpected error: {str(e)}")
            return {
                "student": student_num,
                "duration": time.time() - start_time,
                "code_runs": code_runs,
                "errors": errors,
                "success": False
            }

        finally:
            await context.close()
            await browser.close()


async def run_concurrent_load_test(num_students=10, test_duration=60):
    """
    Run a concurrent load test with multiple students.
    """
    logger.info(f"Starting concurrent load test: {num_students} students, {test_duration}s each")

    # Launch all students concurrently
    tasks = [
        load_editor_and_run_code(i + 1, test_duration_seconds=test_duration)
        for i in range(num_students)
    ]

    results = await asyncio.gather(*tasks)

    # Print results
    logger.info("\n" + "=" * 70)
    logger.info("LOAD TEST RESULTS")
    logger.info("=" * 70)

    total_code_runs = 0
    successful_students = 0
    total_errors = 0

    for result in results:
        status = "✓" if result["success"] else "✗"
        logger.info(f"{status} Student {result['student']:2d}: {result['code_runs']:3d} runs in {result['duration']:6.1f}s", )
        if result["errors"]:
            for error in result["errors"]:
                logger.info(f"    Error: {error}")

        total_code_runs += result["code_runs"]
        if result["success"]:
            successful_students += 1
        total_errors += len(result["errors"])

    logger.info("=" * 70)
    logger.info(f"Summary:")
    logger.info(f"  Successful students: {successful_students}/{num_students}")
    logger.info(f"  Total code runs: {total_code_runs}")
    logger.info(f"  Total errors: {total_errors}")
    logger.info(f"  Avg runs per student: {total_code_runs / num_students:.1f}")
    logger.info("=" * 70)

    return {
        "successful": successful_students,
        "total": num_students,
        "code_runs": total_code_runs,
        "errors": total_errors,
        "results": results
    }


if __name__ == "__main__":
    # Run test: 10 concurrent students, each running code for 60 seconds
    summary = asyncio.run(run_concurrent_load_test(num_students=10, test_duration=60))

    # Exit with non-zero if there were failures
    exit(0 if summary["successful"] == summary["total"] else 1)
