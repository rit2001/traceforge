variable "kubeconfig_path" {
  description = "Explicit kubeconfig path; use a portable path such as ~/.kube/config."
  type        = string
  default     = "~/.kube/config"

  validation {
    condition     = trimspace(var.kubeconfig_path) != ""
    error_message = "kubeconfig_path must not be empty."
  }
}

variable "kube_context" {
  description = "Dedicated kind context used by this local environment."
  type        = string
  default     = "kind-traceforge"

  validation {
    condition     = var.kube_context == "kind-traceforge"
    error_message = "The local environment is restricted to context kind-traceforge."
  }
}

variable "namespace_name" {
  description = "Dedicated namespace managed by this local environment."
  type        = string
  default     = "traceforge"

  validation {
    condition     = var.namespace_name == "traceforge"
    error_message = "The local environment is restricted to namespace traceforge."
  }
}

variable "resource_quota" {
  description = "Local namespace quota passed to the reusable foundation module."
  type = object({
    requests_cpu             = string
    requests_memory          = string
    limits_cpu               = string
    limits_memory            = string
    pods                     = string
    services                 = string
    configmaps               = string
    persistent_volume_claims = string
    requests_storage         = string
  })
  default = {
    requests_cpu             = "1"
    requests_memory          = "2Gi"
    limits_cpu               = "4"
    limits_memory            = "4Gi"
    pods                     = "10"
    services                 = "6"
    configmaps               = "10"
    persistent_volume_claims = "2"
    requests_storage         = "5Gi"
  }

  validation {
    condition = alltrue([
      can(regex("^([1-9][0-9]*|[1-9][0-9]*m)$", var.resource_quota.requests_cpu)),
      can(regex("^[1-9][0-9]*(Mi|Gi)$", var.resource_quota.requests_memory)),
      can(regex("^([1-9][0-9]*|[1-9][0-9]*m)$", var.resource_quota.limits_cpu)),
      can(regex("^[1-9][0-9]*(Mi|Gi)$", var.resource_quota.limits_memory)),
      can(regex("^[1-9][0-9]*$", var.resource_quota.pods)),
      can(regex("^[1-9][0-9]*$", var.resource_quota.services)),
      can(regex("^[1-9][0-9]*$", var.resource_quota.configmaps)),
      can(regex("^[1-9][0-9]*$", var.resource_quota.persistent_volume_claims)),
      can(regex("^[1-9][0-9]*(Mi|Gi)$", var.resource_quota.requests_storage)),
    ])
    error_message = "resource_quota values must be positive Kubernetes quantities."
  }
}

variable "limit_range_defaults" {
  description = "Local container defaults passed to the reusable foundation module."
  type = object({
    default_cpu_request    = string
    default_memory_request = string
    default_cpu_limit      = string
    default_memory_limit   = string
  })
  default = {
    default_cpu_request    = "25m"
    default_memory_request = "64Mi"
    default_cpu_limit      = "500m"
    default_memory_limit   = "512Mi"
  }

  validation {
    condition = alltrue([
      can(regex("^([1-9][0-9]*|[1-9][0-9]*m)$", var.limit_range_defaults.default_cpu_request)),
      can(regex("^[1-9][0-9]*(Mi|Gi)$", var.limit_range_defaults.default_memory_request)),
      can(regex("^([1-9][0-9]*|[1-9][0-9]*m)$", var.limit_range_defaults.default_cpu_limit)),
      can(regex("^[1-9][0-9]*(Mi|Gi)$", var.limit_range_defaults.default_memory_limit)),
    ])
    error_message = "limit_range_defaults values must be positive Kubernetes CPU or memory quantities."
  }
}
