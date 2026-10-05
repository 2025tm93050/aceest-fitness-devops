# ACEest Fitness & Gym – DevOps CI/CD

[![CI/CD Pipeline](https://github.com/2025tm93050/aceest-fitness-devops/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/2025tm93050/aceest-fitness-devops/actions/workflows/main.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Flask 3.1](https://img.shields.io/badge/flask-3.1-000000?logo=flask)
![Docker](https://img.shields.io/badge/docker-multi--stage-2496ED?logo=docker&logoColor=white)

A Flask REST API that ACEest Fitness & Gym uses to manage clients, training programs, workouts, weekly progress and body metrics. It ships with a complete automated delivery workflow:

**Git & GitHub** (version control) → **Pytest** (unit tests) → **Docker** (portable image) → **Jenkins** (BUILD & quality gate) → **GitHub Actions** (CI/CD on every push and pull request)

The business rules come from the original ACEest desktop (Tkinter) application, versions 1.0 to 3.2.4. That code is kept in [`legacy/`](legacy/), with each version tagged `legacy-v*`, and the rules were rebuilt as a tested web service.

## Contents

- [Project structure](#project-structure)
- [Run locally](#run-locally)
- [API reference](#api-reference)
- [Run the tests](#run-the-tests)
- [Docker](#docker)
- [CI/CD: Jenkins and GitHub Actions](#cicd-jenkins-and-github-actions)
- [Git workflow](#git-workflow)
- [Screenshots](#screenshots)

## Project structure

```text
aceest-fitness-devops/
├── app.py                      # Flask application: REST API + SQLite storage
├── fitness.py                  # Business rules: programs, calories, BMI, membership (pure functions)
├── requirements.txt            # Runtime dependencies (pinned)
├── requirements-dev.txt        # Runtime + test/lint tools (pytest, pytest-cov, flake8)
├── tests/
│   ├── conftest.py             # Fixtures: fresh app with a temporary database for every test
│   ├── test_app.py             # API tests for every endpoint (success, validation, not-found)
│   └── test_fitness.py         # Unit tests for the business rules
├── Dockerfile                  # Multi-stage build: "test" image and slim "production" image
├── .dockerignore               # Keeps the build context small and secret-free
├── Jenkinsfile                 # Jenkins BUILD & quality gate pipeline
├── .github/workflows/main.yml  # GitHub Actions CI/CD pipeline
├── pytest.ini, .flake8         # Test and lint settings
├── docs/screenshots/           # Evidence screenshots (see "Screenshots" below)
└── legacy/aceest_desktop.py    # Original desktop app (history only, not deployed)
```

## Run locally

**Prerequisites:** Python 3.12 and Git.

```bash
git clone https://github.com/2025tm93050/aceest-fitness-devops.git
cd aceest-fitness-devops

python -m venv .venv
# Windows (PowerShell):   .venv\Scripts\Activate.ps1   (if blocked: Set-ExecutionPolicy -Scope Process Bypass)
# Linux / macOS:          source .venv/bin/activate

pip install -r requirements-dev.txt
python app.py
```

The API now runs at <http://localhost:5000>. Check it:

```bash
curl http://localhost:5000/health
# {"status":"ok","version":"1.0.0"}
```

> On Windows PowerShell 5.1, `curl` is an alias for `Invoke-WebRequest`. Use `curl.exe` or `Invoke-RestMethod http://localhost:5000/health` instead.

### Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `ACEEST_DB` | `aceest_fitness.db` | Path of the SQLite database file (created automatically) |
| `ACEEST_ADMIN_PASSWORD` | `admin` | Password of the built-in `admin` user, set when the database is first created |
| `PORT` | `5000` | Port used by `python app.py` |

## API reference

All requests and responses are JSON. Invalid input returns `400` with `{"error": "..."}`. A missing client returns `404`, a duplicate client name returns `409`, and a failed login returns `401`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | App name, version and list of endpoints |
| `GET` | `/health` | Health check (also checks the database connection) |
| `POST` | `/login` | Verify `username` / `password`, returns the user's role |
| `GET` | `/programs` | All programs: `FL` Fat Loss, `MG` Muscle Gain, `BG` Beginner |
| `GET` | `/programs/<code>` | Program details: weekly workout plan, diet plan, calorie factor |
| `GET` `POST` | `/clients` | List clients / create a client (daily calories = weight × program factor) |
| `GET` `PUT` `DELETE` | `/clients/<id>` | Get, partially update or delete a client |
| `GET` | `/clients/<id>/bmi` | BMI, category (Underweight / Normal / Overweight / Obese) and risk note |
| `POST` | `/clients/<id>/program` | Generate a training template for the client's (or a given) program |
| `GET` | `/clients/<id>/membership` | Membership status (`Active` / `Expired` / `None`) and renewal date |
| `GET` `POST` | `/clients/<id>/progress` | Weekly adherence entries (0–100 %) and the average |
| `GET` `POST` | `/clients/<id>/workouts` | Workouts (`Strength`, `Hypertrophy`, `Cardio`, `Mobility`) with exercises |
| `GET` `POST` | `/clients/<id>/metrics` | Body metrics: weight, waist, body fat |

**Example session** (bash or Git Bash):

```bash
curl -s -X POST http://localhost:5000/clients -H "Content-Type: application/json" \
     -d '{"name": "Arun", "age": 28, "height": 175, "weight": 80, "program": "FL", "membership_end": "2026-12-31"}'
# 201 Created: {"calories": 1760, "id": 1, "membership_status": "Active", "name": "Arun", ...}

curl -s http://localhost:5000/clients/1/bmi
# {"bmi": 26.1, "category": "Overweight", "client_id": 1, "risk": "Moderate risk; ..."}

curl -s -X POST http://localhost:5000/clients/1/workouts -H "Content-Type: application/json" \
     -d '{"workout_type": "Strength", "duration_min": 60, "exercises": [{"name": "Squat", "sets": 5, "reps": 5, "weight": 100}]}'

curl -s -X POST http://localhost:5000/clients/1/progress -H "Content-Type: application/json" \
     -d '{"week": "Week 1", "adherence": 85}'
```

## Run the tests

With the virtual environment active:

```bash
pytest                                                     # run all 108 tests
pytest -v --cov=app --cov=fitness --cov-report=term-missing  # with a coverage report (~99 %)
flake8 .                                                   # lint / style check
```

- Every test gets its own temporary SQLite database (see `tests/conftest.py`), so tests never touch real data and can run in any order.
- `tests/test_fitness.py` covers the business rules: calorie factors, BMI values and category boundaries, the program generator and membership status.
- `tests/test_app.py` calls every endpoint through Flask's test client and checks the success path, input validation (wrong types, out-of-range values, bad dates, missing fields), not-found cases and error codes.

## Docker

Build and run the production image:

```bash
docker build --target production -t aceest-fitness .
docker run -d --name aceest -p 5000:5000 -v aceest-data:/app/data aceest-fitness

curl http://localhost:5000/health
docker ps            # STATUS shows "(healthy)" once the health check passes
```

Run the test suite inside a container:

```bash
docker build --target test -t aceest-fitness:test .
docker run --rm aceest-fitness:test
```

How the Dockerfile is optimised for **size and security**:

| Technique | Why |
|---|---|
| `python:3.12-slim` base | Small image (~200 MB) with only what Python needs |
| Multi-stage build (`base` → `test` / `production`) | Test tools and test code never reach the production image |
| `requirements.txt` copied before the code | Dependency layer stays cached until the requirements change |
| `PIP_NO_CACHE_DIR`, `PYTHONDONTWRITEBYTECODE` | No pip cache or `.pyc` files left in the image |
| Non-root user `app` | The app cannot modify system files if compromised |
| `.dockerignore` | Keeps `.git`, virtualenvs, local databases and docs out of the build context |
| `HEALTHCHECK` on `/health` | Docker (and orchestrators) can tell when the app is really ready |
| `gunicorn` with 2 workers | Production WSGI server instead of Flask's development server |

## CI/CD: Jenkins and GitHub Actions

```mermaid
flowchart LR
    dev([Developer]) -->|git push / pull request| repo[(GitHub repository)]

    repo -->|every push and pull request| ga
    repo -->|polled every 5 minutes| jk

    subgraph ga ["GitHub Actions: .github/workflows/main.yml"]
        direction LR
        g1["Build & Lint"] --> g2["Docker Image Assembly"] --> g3["Pytest inside the container"]
    end

    subgraph jk ["Jenkins: Jenkinsfile"]
        direction LR
        j1["Clean checkout"] --> j2["Fresh virtualenv + install"] --> j3["Compile"] --> j4["Lint"] --> j5["Unit tests + coverage gate"] --> j6["Docker build *"]
    end

    ga -->|status check + badge| merge{{Merge to main}}
    jk -->|build result + JUnit report| merge
```

<sub>* The Jenkins Docker stage runs only when the build agent has Docker installed; otherwise it is skipped.</sub>

### How the two pipelines work together

Both pipelines run against the same GitHub repository and apply the same quality rules: the code must compile, pass `flake8`, and pass all Pytest tests with at least **90 % coverage**. A change is ready for `main` only when both are green.

- **GitHub Actions** is the automated CI/CD pipeline. It runs on GitHub's cloud runners for **every push to any branch and every pull request**, and its result appears as a status check on the pull request and as the badge above. The jobs are chained with `needs`, so each stage runs only if the previous one passed:
  1. **Build & Lint**: installs the pinned dependencies, compiles every Python file (syntax check) and runs `flake8`.
  2. **Docker Image Assembly**: builds the production image, starts it, waits for `/health`, and checks that it runs as the non-root user.
  3. **Automated Testing**: builds the `test` image and runs the Pytest suite **inside the container**, with the coverage gate.

  Docker layers are cached between runs (GitHub Actions cache), and a newer push to the same branch cancels the older run.

- **Jenkins** is the **BUILD environment and secondary quality gate**, running on infrastructure the team controls. The job pulls the latest `main` from GitHub, wipes its workspace and builds a **fresh virtual environment** every time. This proves the project builds from scratch using only what is in the repository, and catches "works on my machine" problems early. It publishes the test results through the JUnit plugin and archives `junit.xml` and `coverage.xml` with every build. A local Jenkins cannot receive GitHub webhooks, so the `Jenkinsfile` sets up **SCM polling** (`H/5 * * * *`), and new commits start a build automatically.

| Stage | GitHub Actions | Jenkins |
|---|---|---|
| Trigger | Every `push` and `pull_request` | SCM polling every 5 min (or "Build Now") |
| Environment | Fresh Ubuntu 24.04 cloud runner | Clean workspace + fresh virtualenv on the Jenkins agent |
| Compile / syntax check | `py_compile` | `compileall` |
| Lint | `flake8` | `flake8` |
| Docker image | Built and smoke-tested | Built when the agent has Docker |
| Tests | Pytest **inside the container**, coverage ≥ 90 % | Pytest + JUnit report, coverage ≥ 90 % |

### Set up the Jenkins job

1. **Plugins:** Pipeline (`workflow-aggregator`), Git, GitHub, JUnit, Pipeline Stage View, Timestamper and Workspace Cleanup.
2. **Agent requirements:** Python 3.12 and Git on the `PATH` (Docker is optional). The `Jenkinsfile` works on both Linux (`sh`) and Windows (`bat`) agents.
3. **New Item** → **Pipeline** → under *Pipeline* choose **Pipeline script from SCM**:
   - SCM: **Git**, Repository URL: `https://github.com/2025tm93050/aceest-fitness-devops.git` (public, no credentials needed)
   - Branch: `*/main`, Script Path: `Jenkinsfile`
4. **Save** → **Build Now**. After the first build, Jenkins registers the polling trigger from the `Jenkinsfile`, and every new commit on `main` then starts a build automatically.

## Git workflow

- `main` always holds working code. All work happens on short-lived branches named by purpose: `feature/*`, `infra/*`, `docs/*`, `fix/*`. Each branch is merged through a **pull request** after the pipeline passes.
- Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/) style, for example `feat:`, `fix:`, `test:`, `build:`, `ci:`, `docs:`, `chore:`.
- The history starts with the original desktop app versions committed in order and tagged `legacy-v1.0` … `legacy-v3.2.4`. The Flask service, tests, Docker image and pipelines were then added through pull requests, and the first web release is tagged `v1.0.0`.

## Screenshots

Evidence that every stage works. All images are in [`docs/screenshots/`](docs/screenshots/).

### Git and GitHub

![Public GitHub repository](docs/screenshots/01_github_repo.png)
*Public repository with all required files, a green check on the latest commit and the passing CI/CD badge.*

![Git history](docs/screenshots/02_git_history.png)
*Git history: legacy versions with tags, feature branches merged through pull requests, and the `v1.0.0` release tag.*

![Pull requests](docs/screenshots/03_pull_requests.png)
*Six pull requests, one per feature or infrastructure branch, all merged into `main`.*

### Tests, build and lint

![Pytest local run](docs/screenshots/04_pytest_local.png)
*Local Pytest run: 108 tests passed with a 99 % coverage report (the middle of the list is shortened).*

![Compile and lint](docs/screenshots/05_build_lint_local.png)
*Compile (syntax) check and `flake8` lint: no problems.*

### Docker

![Docker build](docs/screenshots/06_docker_build.png)
*Production image built from scratch (`--no-cache`) and the test image; final sizes 199 MB and 223 MB.*

![Pytest inside the container](docs/screenshots/07_docker_tests_in_container.png)
*The full Pytest suite running inside the Docker container: 108 passed, 99 % coverage.*

![Docker run](docs/screenshots/08_docker_run.png)
*Production container is `healthy`, runs as the non-root user `app` and answers API requests.*

### Jenkins

![Jenkins login](docs/screenshots/09_jenkins_login.png)
*Jenkins (2.580.1 LTS) with login security enabled.*

![Jenkins dashboard](docs/screenshots/10_jenkins_dashboard.png)
*Dashboard with the pipeline job `aceest-fitness-build`.*

![Jenkins job page](docs/screenshots/11_jenkins_job_page.png)
*Job page: archived `coverage.xml` and `junit.xml`, test result trend (108 passing tests per build) and the stage view.*

![Jenkins stage view](docs/screenshots/12_jenkins_stage_view.png)
*Stage view: Checkout → Install dependencies → Build (compile) → Lint → Unit tests all green for builds #2 to #5. The Docker build stage is skipped because the build agent has no Docker. Build #1 failed on a Jenkinsfile error that was then fixed.*

![Jenkins changes](docs/screenshots/13_jenkins_changes.png)
*Changes page: the commits pulled from GitHub by each build. Build #4 was started automatically by SCM polling.*

![Jenkins build running](docs/screenshots/14_jenkins_build_running.png)
*A new build (#6) running on `main`, with the stages filling in live.*

![Jenkins console output](docs/screenshots/15_jenkins_console.png)
*Console output of build #5 on `main`: clean checkout, fresh install, compile, lint, 108 tests passed, `Finished: SUCCESS` (lines marked `...` are omitted).*

![Jenkins build history](docs/screenshots/16_jenkins_build_history.png)
*Build history and JUnit test report from the Jenkins REST API.*

### GitHub Actions

![GitHub Actions runs](docs/screenshots/17_github_actions_runs.png)
*The pipeline runs on every push and pull request, including the `v1.0.0` tag. The one cancelled run was replaced by a newer push to the same branch (`concurrency`).*

![GitHub Actions run on main](docs/screenshots/18_github_actions_main_run.png)
*Run on `main`: Build & Lint → Docker Image Assembly → Automated Testing, all successful.*

![Pytest inside the container on GitHub Actions](docs/screenshots/19_github_actions_pytest_in_container.png)
*Automated Testing job log: Pytest runs inside the Docker container on the GitHub runner, 108 passed.*
