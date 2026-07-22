mock_provider "kubernetes" {}

run "kind_defaults" {
  command = plan

  assert {
    condition     = output.namespace_name == "traceforge"
    error_message = "The kind environment must manage only the traceforge namespace."
  }

  assert {
    condition     = output.foundation_labels["traceforge.dev/environment"] == "kind-local"
    error_message = "The kind environment label is missing."
  }

  assert {
    condition = (
      output.foundation_resource_names.namespace == "traceforge" &&
      output.foundation_resource_names.resource_quota == "traceforge-foundation" &&
      output.foundation_resource_names.limit_range == "traceforge-container-defaults"
    )
    error_message = "The default foundation resource names changed unexpectedly."
  }

  assert {
    condition = (
      output.foundation_labels["app.kubernetes.io/managed-by"] == "terraform" &&
      output.foundation_labels["traceforge.dev/foundation"] == "local-kind" &&
      output.foundation_labels["app.kubernetes.io/part-of"] == "traceforge"
    )
    error_message = "The default foundation labels changed unexpectedly."
  }

  assert {
    condition     = length(output.service_account_names) == 5
    error_message = "The kind environment must expose five dedicated ServiceAccounts."
  }

  assert {
    condition = toset(output.service_account_names) == toset([
      "ingest-gateway",
      "kafka",
      "otel-collector",
      "traceforge-api",
      "traceforge-worker",
    ])
    error_message = "The dedicated ServiceAccount set changed."
  }

  assert {
    condition     = alltrue([for enabled in values(output.service_account_token_automount) : enabled == false])
    error_message = "ServiceAccount token automount must remain disabled."
  }

  assert {
    condition = output.resource_quota_hard == {
      "configmaps"             = "10"
      "limits.cpu"             = "4"
      "limits.memory"          = "4Gi"
      "persistentvolumeclaims" = "2"
      "pods"                   = "10"
      "requests.cpu"           = "1"
      "requests.memory"        = "2Gi"
      "requests.storage"       = "5Gi"
      "services"               = "6"
    }
    error_message = "The default ResourceQuota changed unexpectedly."
  }

  assert {
    condition     = output.limit_range_defaults.default_request == { cpu = "25m", memory = "64Mi" }
    error_message = "The default LimitRange requests changed unexpectedly."
  }

  assert {
    condition     = output.limit_range_defaults.default == { cpu = "500m", memory = "512Mi" }
    error_message = "The default LimitRange limits changed unexpectedly."
  }
}

run "reject_non_traceforge_context" {
  command = plan

  variables {
    kube_context = "default"
  }

  expect_failures = [var.kube_context]
}

run "reject_invalid_namespace" {
  command = plan

  variables {
    namespace_name = "default"
  }

  expect_failures = [var.namespace_name]
}

run "reject_invalid_resource_quota" {
  command = plan

  variables {
    resource_quota = {
      requests_cpu             = "invalid"
      requests_memory          = "2Gi"
      limits_cpu               = "4"
      limits_memory            = "4Gi"
      pods                     = "10"
      services                 = "6"
      configmaps               = "10"
      persistent_volume_claims = "2"
      requests_storage         = "5Gi"
    }
  }

  expect_failures = [var.resource_quota]
}

run "reject_invalid_limit_range" {
  command = plan

  variables {
    limit_range_defaults = {
      default_cpu_request    = "25m"
      default_memory_request = "zero"
      default_cpu_limit      = "500m"
      default_memory_limit   = "512Mi"
    }
  }

  expect_failures = [var.limit_range_defaults]
}
