module "foundation" {
  source = "../../modules/kubernetes-foundation"

  namespace_name       = var.namespace_name
  resource_quota       = var.resource_quota
  limit_range_defaults = var.limit_range_defaults
  additional_labels = {
    "traceforge.dev/environment" = "kind-local"
  }
}
