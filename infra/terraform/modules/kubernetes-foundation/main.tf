locals {
  foundation_labels = merge(
    var.additional_labels,
    {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/part-of"    = "traceforge"
      "traceforge.dev/foundation"    = "local-kind"
    },
  )

  quota_hard = {
    "requests.cpu"           = var.resource_quota.requests_cpu
    "requests.memory"        = var.resource_quota.requests_memory
    "limits.cpu"             = var.resource_quota.limits_cpu
    "limits.memory"          = var.resource_quota.limits_memory
    "pods"                   = var.resource_quota.pods
    "services"               = var.resource_quota.services
    "configmaps"             = var.resource_quota.configmaps
    "persistentvolumeclaims" = var.resource_quota.persistent_volume_claims
    "requests.storage"       = var.resource_quota.requests_storage
  }

  limit_defaults = {
    default = {
      cpu    = var.limit_range_defaults.default_cpu_limit
      memory = var.limit_range_defaults.default_memory_limit
    }
    default_request = {
      cpu    = var.limit_range_defaults.default_cpu_request
      memory = var.limit_range_defaults.default_memory_request
    }
  }
}

resource "kubernetes_namespace_v1" "traceforge" {
  metadata {
    name   = var.namespace_name
    labels = local.foundation_labels
  }

  lifecycle {
    precondition {
      condition     = !contains(["default", "kube-node-lease", "kube-public", "kube-system"], var.namespace_name)
      error_message = "The foundation must never manage a Kubernetes system namespace."
    }
  }
}

resource "kubernetes_resource_quota_v1" "foundation" {
  metadata {
    name      = "traceforge-foundation"
    namespace = kubernetes_namespace_v1.traceforge.metadata[0].name
    labels    = local.foundation_labels
  }

  spec {
    hard = local.quota_hard
  }
}

resource "kubernetes_limit_range_v1" "foundation" {
  metadata {
    name      = "traceforge-container-defaults"
    namespace = kubernetes_namespace_v1.traceforge.metadata[0].name
    labels    = local.foundation_labels
  }

  spec {
    limit {
      type            = "Container"
      default         = local.limit_defaults.default
      default_request = local.limit_defaults.default_request
    }
  }
}

resource "kubernetes_service_account_v1" "workload" {
  for_each = var.service_account_names

  metadata {
    name      = each.value
    namespace = kubernetes_namespace_v1.traceforge.metadata[0].name
    labels    = merge(local.foundation_labels, { "app.kubernetes.io/name" = each.value })
  }

  automount_service_account_token = false
}
