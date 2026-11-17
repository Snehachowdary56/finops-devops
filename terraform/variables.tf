variable "kubeconfig_path" {
  description = "Path to the kubeconfig file for the target cluster"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Kubeconfig context (kind clusters are named kind-<name>)"
  type        = string
  default     = "kind-finops"
}

variable "namespace" {
  description = "Namespace for the FinOps monitor"
  type        = string
  default     = "finops"
}

variable "image" {
  description = "Container image to deploy"
  type        = string
  default     = "finops-monitor:local"
}

variable "replicas" {
  description = "Number of pods"
  type        = number
  default     = 2
  validation {
    condition     = var.replicas >= 1 && var.replicas <= 5
    error_message = "replicas must be between 1 and 5."
  }
}

variable "monthly_budget_usd" {
  description = "Monthly cloud budget used for budget status alerts"
  type        = number
  default     = 25000
}

variable "as_of_date" {
  description = "Date the report is calculated for (YYYY-MM-DD)"
  type        = string
  default     = "2026-10-30"
}

variable "node_port" {
  description = "NodePort exposed on the cluster node"
  type        = number
  default     = 30080
}
