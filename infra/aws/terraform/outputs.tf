output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "api_url" {
  value = local.api_url
}

output "dashboard_url" {
  value = local.dashboard_url
}

output "ecr_repository_urls" {
  value = { for key, repo in aws_ecr_repository.app : key => repo.repository_url }
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_names" {
  value = {
    api       = aws_ecs_service.api.name
    dashboard = aws_ecs_service.dashboard.name
    worker    = aws_ecs_service.worker.name
    agent     = aws_ecs_service.agent.name
  }
}

output "agent_task_definition_arn" {
  value = aws_ecs_task_definition.agent.arn
}

output "api_task_definition_arn" {
  value = aws_ecs_task_definition.api.arn
}

output "database_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = aws_elasticache_replication_group.main.primary_endpoint_address
  sensitive = true
}

output "recordings_bucket" {
  value = aws_s3_bucket.recordings.id
}

output "app_secret_arn" {
  value     = aws_secretsmanager_secret.app.arn
  sensitive = true
}

output "database_url_secret_arn" {
  value     = aws_secretsmanager_secret.database_url.arn
  sensitive = true
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "app_security_group_id" {
  value = aws_security_group.app.id
}

output "cloudwatch_agent_metric_namespace" {
  value = local.metric_namespace
}
