// Jenkins BUILD & quality gate for ACEest Fitness & Gym.
// Pulls the latest code from GitHub into a clean workspace, rebuilds the Python
// environment from scratch, then compiles, lints and unit-tests the application.
// Works on Linux and Windows agents; the Docker stage runs only where Docker exists.

def run(String command) {
    if (isUnix()) {
        sh command
    } else {
        bat command
    }
}

def dockerAvailable() {
    def status = isUnix()
        ? sh(script: 'docker info > /dev/null 2>&1', returnStatus: true)
        : bat(script: '@docker info > NUL 2>&1', returnStatus: true)
    return status == 0
}

pipeline {
    agent any

    options {
        skipDefaultCheckout()
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    triggers {
        // GitHub webhooks cannot reach a local Jenkins, so poll the repository for new commits
        pollSCM('H/5 * * * *')
    }

    environment {
        IMAGE_NAME = 'aceest-fitness'
    }

    stages {
        stage('Checkout') {
            steps {
                cleanWs()
                checkout scm
                script {
                    env.PYTHON = isUnix() ? 'python3' : 'python'
                    env.VENV_PYTHON = isUnix() ? '.venv/bin/python' : '.venv\\Scripts\\python.exe'
                    env.DOCKER_AVAILABLE = dockerAvailable() ? 'true' : 'false'
                }
                run 'git log -1 --oneline'
            }
        }

        stage('Install dependencies') {
            steps {
                run "${env.PYTHON} --version"
                run "${env.PYTHON} -m venv .venv"
                run "${env.VENV_PYTHON} -m pip install -r requirements-dev.txt"
            }
        }

        stage('Build (compile)') {
            steps {
                run "${env.VENV_PYTHON} -m compileall -q app.py fitness.py tests"
            }
        }

        stage('Lint') {
            steps {
                run "${env.VENV_PYTHON} -m flake8 . --count --show-source --statistics"
            }
        }

        stage('Unit tests') {
            steps {
                run "${env.VENV_PYTHON} -m pytest -v --junitxml=reports/junit.xml " +
                    '--cov=app --cov=fitness --cov-report=term-missing ' +
                    '--cov-report=xml:reports/coverage.xml --cov-fail-under=90'
            }
            post {
                always {
                    junit 'reports/junit.xml'
                }
            }
        }

        stage('Docker build') {
            when {
                environment name: 'DOCKER_AVAILABLE', value: 'true'
            }
            steps {
                run "docker build --target test -t ${env.IMAGE_NAME}:test ."
                run "docker run --rm ${env.IMAGE_NAME}:test"
                run "docker build --target production -t ${env.IMAGE_NAME}:${env.BUILD_NUMBER} ."
            }
        }
    }

    post {
        success {
            archiveArtifacts artifacts: 'reports/*.xml', fingerprint: true
        }
        always {
            echo "Docker available on this agent: ${env.DOCKER_AVAILABLE}"
            echo "Result: ${currentBuild.currentResult} - ${env.JOB_NAME} #${env.BUILD_NUMBER}"
        }
    }
}
