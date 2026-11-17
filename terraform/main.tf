# Deploys the FinOps monitor to Kubernetes as code: namespace, config, deployment, service.

resource "kubernetes_namespace_v1" "finops" {
  metadata {
    name   = var.namespace
    labels = { "app.kubernetes.io/managed-by" = "terraform" }
  }
}

resource "kubernetes_config_map_v1" "config" {
  metadata {
    name      = "finops-monitor-config"
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
  }
  data = {
    MONTHLY_BUDGET_USD = tostring(var.monthly_budget_usd)
    AS_OF_DATE         = var.as_of_date
  }
}

resource "kubernetes_deployment_v1" "app" {
  metadata {
    name      = "finops-monitor"
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
    labels    = { app = "finops-monitor" }
  }

  spec {
    replicas = var.replicas
    selector {
      match_labels = { app = "finops-monitor" }
    }

    template {
      metadata {
        labels = { app = "finops-monitor" }
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "8080"
          "prometheus.io/path"   = "/metrics"
          "checksum/config"      = sha256(jsonencode(kubernetes_config_map_v1.config.data))
        }
      }

      spec {
        security_context {
          run_as_non_root = true
          run_as_user     = 10001
        }

        container {
          name              = "finops-monitor"
          image             = var.image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 8080
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.config.metadata[0].name
            }
          }

          resources {
            requests = { cpu = "50m", memory = "64Mi" }
            limits   = { cpu = "250m", memory = "128Mi" }
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            period_seconds = 5
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            period_seconds = 10
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
          }
        }
      }
    }
  }

  wait_for_rollout = true
}

resource "kubernetes_service_v1" "app" {
  metadata {
    name      = "finops-monitor"
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
  }
  spec {
    type     = "NodePort"
    selector = { app = "finops-monitor" }
    port {
      port        = 8080
      target_port = 8080
      node_port   = var.node_port
    }
  }
}
