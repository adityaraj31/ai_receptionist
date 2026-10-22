locals {
  ecr_repositories = {
    api       = "api"
    agent     = "agent"
    dashboard = "dashboard"
    metrics   = "agent-metrics"
  }
}

resource "aws_ecr_repository" "app" {
  for_each = local.ecr_repositories

  name                 = "${var.project}/${each.value}"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}
