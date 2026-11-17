output "namespace" {
  value = kubernetes_namespace_v1.finops.metadata[0].name
}

output "app_url" {
  description = "URL of the service on your computer (kind maps the NodePort to localhost)"
  value       = "http://localhost:${var.node_port}"
}

output "replicas" {
  value = var.replicas
}

output "service_account" {
  value = kubernetes_service_account_v1.app.metadata[0].name
}
