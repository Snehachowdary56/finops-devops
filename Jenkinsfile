// Jenkins pipeline: test -> build image -> load into kind -> deploy with Terraform -> smoke test with Ansible.
// Needs an agent with python3, docker, kind, kubectl, terraform and ansible-playbook on PATH.
pipeline {
  agent any
  options { timestamps(); timeout(time: 30, unit: 'MINUTES') }
  parameters {
    choice(name: 'TARGET_ENV', choices: ['dev', 'test', 'prod'], description: 'Environment settings to deploy')
  }
  environment {
    IMAGE = "finops-monitor:${env.BUILD_NUMBER}"
    CLUSTER = 'finops'
  }
  stages {
    stage('Test') {
      steps {
        sh 'python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements.txt -r requirements-dev.txt && pytest -q'
        sh '. .venv/bin/activate && ansible-playbook ansible/site.yml --syntax-check'
      }
    }
    stage('Build image') {
      steps { sh 'docker build -t "$IMAGE" .' }
    }
    stage('Cluster') {
      steps {
        sh 'kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --config kind-config.yaml'
        sh 'kind load docker-image "$IMAGE" --name "$CLUSTER"'
      }
    }
    stage('Configure') {
      steps { sh '. .venv/bin/activate && ansible-playbook ansible/site.yml --tags config,preflight -e target_env=$TARGET_ENV' }
    }
    stage('Deploy (Terraform)') {
      steps {
        dir('terraform') {
          sh 'terraform init -input=false'
          sh 'terraform apply -input=false -auto-approve -var "image=$IMAGE"'
        }
      }
    }
    stage('Smoke test') {
      steps { sh '. .venv/bin/activate && ansible-playbook ansible/site.yml --tags smoke' }
    }
  }
  post {
    always { sh 'kubectl -n finops get pods -o wide || true' }
  }
}
