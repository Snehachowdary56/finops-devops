# RBAC (least privilege): the app runs as its own service account that may only READ
# its own config map. It cannot list secrets, change deployments or touch other namespaces.

resource "kubernetes_service_account_v1" "app" {
  metadata {
    name      = "finops-monitor"
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
  }
  automount_service_account_token = false
}

resource "kubernetes_role_v1" "read_config" {
  metadata {
    name      = "finops-read-config"
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
  }
  rule {
    api_groups     = [""]
    resources      = ["configmaps"]
    resource_names = [kubernetes_config_map_v1.config.metadata[0].name]
    verbs          = ["get"]
  }
}

resource "kubernetes_role_binding_v1" "read_config" {
  metadata {
    name      = "finops-read-config"
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role_v1.read_config.metadata[0].name
  }
  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account_v1.app.metadata[0].name
    namespace = kubernetes_namespace_v1.finops.metadata[0].name
  }
}
