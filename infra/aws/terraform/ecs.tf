data "aws_caller_identity" "current" {}

locals {
  scheme           = local.https_enabled ? "https" : "http"
  dashboard_url    = "${local.scheme}://${var.dashboard_hostname}"
  api_url          = "${local.scheme}://${var.api_hostname}"
  redis_url        = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379/0"
  metric_namespace = "AIReceptionist/Agent"
  metric_service   = "${var.project}-agent"

  api_secrets = concat(
    [
      for key in keys(local.app_secret_values) : {
        name      = key
        valueFrom = "${aws_secretsmanager_secret.app.arn}:${key}::"
      }
      if !startswith(key, "S3_")
    ],
    [
      { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
    ],
  )

  egress_secrets = [
    for key in ["S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"] : {
      name      = key
      valueFrom = "${aws_secretsmanager_secret.app.arn}:${key}::"
    }
  ]

  agent_secrets = concat(local.api_secrets, local.egress_secrets)

  common_environment = [
    { name = "ENV", value = var.environment },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "DATABASE_URL_SECRET_ARN", value = aws_secretsmanager_secret.database_url.arn },
    { name = "REDIS_URL", value = local.redis_url },
    { name = "S3_REGION", value = var.aws_region },
    { name = "S3_BUCKET", value = aws_s3_bucket.recordings.id },
    { name = "S3_FORCE_PATH_STYLE", value = "false" },
    { name = "RECORDING_ENABLED", value = "true" },
    { name = "RECORDING_PREFIX", value = "recordings" },
    { name = "RECORDING_URL_TTL_SECONDS", value = "900" },
    { name = "EMBEDDING_MODEL", value = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" },
    { name = "EMBEDDING_DIMENSIONS", value = "384" },
    { name = "FASTEMBED_CACHE_PATH", value = "/app/.cache/fastembed" },
    { name = "EMBEDDING_WARMUP", value = "true" },
    { name = "FAQ_MAX_DISTANCE", value = "0.55" },
    { name = "FAQ_HIGH_CONFIDENCE_SIMILARITY", value = "0.55" },
    { name = "FAQ_ANSWER_MAX_CHARS", value = "320" },
    { name = "COST_CURRENCY", value = "INR" },
  ]

  api_environment = concat(local.common_environment, [
    { name = "API_BASE_URL", value = local.api_url },
    { name = "DASHBOARD_URL", value = local.dashboard_url },
    { name = "LLM_MODEL", value = var.llm_model },
    { name = "LLM_BASE_URL", value = var.llm_base_url },
    { name = "LLM_TIMEOUT_SECONDS", value = "30" },
    { name = "WHATSAPP_PROVIDER", value = var.whatsapp_provider },
    { name = "WHATSAPP_PHONE_NUMBER_ID", value = var.whatsapp_phone_number_id },
    { name = "SMS_PROVIDER", value = var.sms_provider },
    { name = "EXOTEL_SID", value = var.exotel_sid },
    { name = "EXOTEL_API_KEY", value = var.exotel_api_key },
    { name = "EXOTEL_CALLER_ID", value = var.exotel_caller_id },
    { name = "PLIVO_AUTH_ID", value = var.plivo_auth_id },
    { name = "PLIVO_NUMBER", value = var.plivo_number },
    { name = "LANGFUSE_HOST", value = var.langfuse_host },
    { name = "LANGFUSE_PUBLIC_KEY", value = var.langfuse_public_key },
    { name = "REMINDER_JOBS_ENABLED", value = "true" },
    { name = "POST_CALL_JOBS_ENABLED", value = "true" },
    { name = "DEMO_STAFF_EMAIL", value = var.demo_staff_email },
  ])

  agent_environment = concat(local.common_environment, [
    { name = "LIVEKIT_URL", value = var.livekit_url },
    { name = "LIVEKIT_AGENT_NAME", value = var.livekit_agent_name },
    { name = "LIVEKIT_SIP_NUMBER", value = var.livekit_sip_number },
    { name = "LIVEKIT_SIP_OUTBOUND_TRUNK", value = var.livekit_sip_outbound_trunk },
    { name = "AGENT_API_URL", value = "http://api.${var.project}.local:8000" },
    { name = "AGENT_API_TIMEOUT_SECONDS", value = "8" },
    { name = "AGENT_HTTP_PORT", value = "8081" },
    { name = "AGENT_MAX_ACTIVE_CALLS", value = "8" },
    { name = "AGENT_NUM_IDLE_PROCESSES", value = "2" },
    { name = "AGENT_JOB_MEMORY_LIMIT_MB", value = "768" },
    { name = "DEFAULT_LANGUAGE", value = "hi-IN" },
    { name = "SARVAM_STT_LANGUAGE", value = "unknown" },
    { name = "SARVAM_STT_MODEL", value = var.sarvam_stt_model },
    { name = "SARVAM_TTS_MODEL", value = var.sarvam_tts_model },
    { name = "SARVAM_TTS_SPEAKER", value = var.sarvam_tts_speaker },
    { name = "SARVAM_LANGUAGE", value = var.sarvam_language },
    { name = "LLM_MODEL", value = var.llm_model },
    { name = "LLM_BASE_URL", value = var.llm_base_url },
    { name = "LLM_TIMEOUT_SECONDS", value = "15" },
    { name = "TRANSFER_RING_TIMEOUT_SECONDS", value = "20" },
    { name = "RECORDING_CONSENT_REQUIRED", value = "true" },
    { name = "LANGFUSE_HOST", value = var.langfuse_host },
    { name = "LANGFUSE_PUBLIC_KEY", value = var.langfuse_public_key },
  ])

  api_container = {
    name      = "api"
    image     = "${aws_ecr_repository.app["api"].repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    environment = local.api_environment
    secrets     = local.api_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs["api"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 90
    }
  }

  agent_container = {
    name      = "agent"
    image     = "${aws_ecr_repository.app["agent"].repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 8081
      hostPort      = 8081
      protocol      = "tcp"
    }]
    environment = local.agent_environment
    secrets     = local.agent_secrets
    stopTimeout = 120
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs["agent"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "agent"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/', timeout=3)\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }
}

resource "aws_cloudwatch_log_group" "ecs" {
  for_each = toset(["api", "worker", "dashboard", "agent", "agent-metrics"])

  name              = "/ecs/${local.name_prefix}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([local.api_container])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      for key, value in merge(local.api_container, {
        name         = "worker"
        command      = ["arq", "app.workers.main.WorkerSettings"]
        healthCheck  = null
        portMappings = []
        logConfiguration = {
          logDriver = "awslogs"
          options = {
            awslogs-group         = aws_cloudwatch_log_group.ecs["worker"].name
            awslogs-region        = var.aws_region
            awslogs-stream-prefix = "worker"
          }
        }
      }) : key => value if value != null
    }
  ])
}

resource "aws_ecs_task_definition" "dashboard" {
  family                   = "${local.name_prefix}-dashboard"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.dashboard_cpu
  memory                   = var.dashboard_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "dashboard"
    image     = "${aws_ecr_repository.app["dashboard"].repository_url}:${var.image_tag}"
    essential = true
    portMappings = [{
      containerPort = 3000
      hostPort      = 3000
      protocol      = "tcp"
    }]
    environment = [
      { name = "NEXT_PUBLIC_API_URL", value = local.api_url },
      { name = "API_BASE_URL", value = local.api_url },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.ecs["dashboard"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "dashboard"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "node -e \"fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\""]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
}

resource "aws_ecs_task_definition" "agent" {
  family                   = "${local.name_prefix}-agent"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.agent_cpu
  memory                   = var.agent_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    local.agent_container,
    {
      name              = "metrics"
      image             = "${aws_ecr_repository.app["metrics"].repository_url}:${var.image_tag}"
      essential         = false
      memoryReservation = 64
      environment = [
        { name = "AGENT_WORKER_URL", value = "http://127.0.0.1:8081/worker" },
        { name = "METRICS_INTERVAL_SECONDS", value = "15" },
        { name = "METRICS_NAMESPACE", value = local.metric_namespace },
        { name = "METRICS_SERVICE", value = local.metric_service },
        { name = "METRICS_ENVIRONMENT", value = var.environment },
      ]
      dependsOn = [{
        containerName = "agent"
        condition     = "START"
      }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs["agent-metrics"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "metrics"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 60

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.api.arn
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener.https,
    aws_lb_listener_rule.api_http,
    aws_lb_listener_rule.api_https,
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy_attachment.execution_secrets,
    aws_iam_role_policy_attachment.recordings,
    aws_secretsmanager_secret_version.app,
    aws_secretsmanager_secret_version.database_url,
  ]
}

resource "aws_ecs_service" "dashboard" {
  name            = "${local.name_prefix}-dashboard"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = var.dashboard_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 30

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.dashboard.arn
    container_name   = "dashboard"
    container_port   = 3000
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener.https,
    aws_lb_listener_rule.dashboard_http,
    aws_lb_listener_rule.dashboard_https,
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy_attachment.execution_secrets,
    aws_iam_role_policy_attachment.recordings,
    aws_secretsmanager_secret_version.app,
    aws_secretsmanager_secret_version.database_url,
  ]
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy_attachment.execution_secrets,
    aws_iam_role_policy_attachment.recordings,
    aws_secretsmanager_secret_version.app,
    aws_secretsmanager_secret_version.database_url,
  ]
}

resource "aws_ecs_service" "agent" {
  name            = "${local.name_prefix}-agent"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.agent.arn
  desired_count   = var.agent_min_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy_attachment.execution_secrets,
    aws_iam_role_policy_attachment.recordings,
    aws_secretsmanager_secret_version.app,
    aws_secretsmanager_secret_version.database_url,
  ]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

resource "aws_appautoscaling_target" "agent" {
  max_capacity       = var.agent_max_count
  min_capacity       = var.agent_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.agent.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  depends_on = [aws_ecs_service.agent]
}

resource "aws_appautoscaling_policy" "agent_active_calls" {
  name               = "${local.name_prefix}-agent-active-calls"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.agent.resource_id
  scalable_dimension = aws_appautoscaling_target.agent.scalable_dimension
  service_namespace  = aws_appautoscaling_target.agent.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = var.agent_target_calls_per_task
    scale_in_cooldown  = 120
    scale_out_cooldown = 60

    customized_metric_specification {
      namespace   = local.metric_namespace
      metric_name = "ActiveCalls"
      statistic   = "Average"

      dimensions {
        name  = "Service"
        value = local.metric_service
      }

      dimensions {
        name  = "Environment"
        value = var.environment
      }
    }
  }
}
