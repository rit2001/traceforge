output "namespace_name" {
  description = "Terraform-managed TraceForge namespace."
  value       = module.foundation.namespace_name
}

output "foundation_labels" {
  description = "Labels applied to foundation resources."
  value       = module.foundation.foundation_labels
}

output "foundation_resource_names" {
  description = "Names of the fixed Terraform-managed foundation resources."
  value       = module.foundation.foundation_resource_names
}

output "service_account_names" {
  description = "Dedicated workload ServiceAccounts."
  value       = module.foundation.service_account_names
}

output "service_account_token_automount" {
  description = "Token automount setting for every dedicated ServiceAccount."
  value       = module.foundation.service_account_token_automount
}

output "resource_quota_hard" {
  description = "Effective local namespace quota."
  value       = module.foundation.resource_quota_hard
}

output "limit_range_defaults" {
  description = "Effective local container defaults."
  value       = module.foundation.limit_range_defaults
}
