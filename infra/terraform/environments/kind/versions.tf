terraform {
  required_version = ">= 1.11.0, < 2.0.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.38.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}
