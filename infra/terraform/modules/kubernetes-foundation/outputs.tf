output "namespace_name" {
  description = "Terraform-managed TraceForge namespace."
  value       = kubernetes_namespace_v1.traceforge.metadata[0].name
}

output "foundation_labels" {
  description = "Labels applied to every Terraform-managed foundation resource."
  value       = local.foundation_labels
}

output "foundation_resource_names" {
  description = "Names of the fixed namespace-scoped foundation resources."
  value = {
    namespace      = kubernetes_namespace_v1.traceforge.metadata[0].name
    resource_quota = kubernetes_resource_quota_v1.foundation.metadata[0].name
    limit_range    = kubernetes_limit_range_v1.foundation.metadata[0].name
  }
}

output "service_account_names" {
  description = "Dedicated ServiceAccounts with token automount disabled."
  value       = sort(keys(kubernetes_service_account_v1.workload))
}

output "service_account_token_automount" {
  description = "Token automount setting for every dedicated ServiceAccount."
  value = {
    for name, account in kubernetes_service_account_v1.workload :
    name => account.automount_service_account_token
  }
}

output "resource_quota_hard" {
  description = "Effective ResourceQuota hard values."
  value       = local.quota_hard
}

output "limit_range_defaults" {
  description = "Effective container defaults supplied by the LimitRange."
  value       = local.limit_defaults
}
