variable "namespace_name" {
  description = "Kubernetes namespace dedicated to the TraceForge local stack."
  type        = string
  default     = "traceforge"

  validation {
    condition = (
      can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.namespace_name)) &&
      length(var.namespace_name) <= 63 &&
      !contains(["default", "kube-node-lease", "kube-public", "kube-system"], var.namespace_name)
    )
    error_message = "namespace_name must be a non-system Kubernetes DNS label of at most 63 characters."
  }
}

variable "additional_labels" {
  description = "Additional non-sensitive labels applied to all foundation resources."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for key, value in var.additional_labels : trimspace(key) != "" && trimspace(value) != ""])
    error_message = "additional_labels keys and values must not be empty."
  }
}

variable "service_account_names" {
  description = "Dedicated workload ServiceAccounts that do not automount Kubernetes API tokens."
  type        = set(string)
  default = [
    "ingest-gateway",
    "kafka",
    "otel-collector",
    "traceforge-api",
    "traceforge-worker",
  ]

  validation {
    condition = (
      var.service_account_names == toset([
        "ingest-gateway",
        "kafka",
        "otel-collector",
        "traceforge-api",
        "traceforge-worker",
      ]) &&
      alltrue([
        for name in var.service_account_names :
        can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", name)) && length(name) <= 63
      ])
    )
    error_message = "service_account_names must contain exactly the five TraceForge workload ServiceAccounts."
  }
}

variable "resource_quota" {
  description = "Local namespace quota with headroom above the five explicit workload resource declarations."
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
    error_message = "resource_quota values must be positive Kubernetes CPU, memory, storage, or integer quantities."
  }
}

variable "limit_range_defaults" {
  description = "Safe defaults for containers that omit resources; explicit workload values remain unchanged."
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
