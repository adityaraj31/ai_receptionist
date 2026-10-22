resource "random_password" "secret_key" {
  length  = 48
  special = false
}

locals {
  app_secret_values = {
    SECRET_KEY            = random_password.secret_key.result
    LIVEKIT_API_KEY       = var.livekit_api_key
    LIVEKIT_API_SECRET    = var.livekit_api_secret
    SARVAM_API_KEY        = var.sarvam_api_key
    LLM_API_KEY           = var.llm_api_key
    AGENT_API_KEY         = var.agent_api_key
    DEMO_AGENT_KEY        = var.agent_api_key
    DEMO_STAFF_PASSWORD   = var.demo_staff_password
    WHATSAPP_ACCESS_TOKEN = var.whatsapp_access_token
    WHATSAPP_VERIFY_TOKEN = var.whatsapp_verify_token
    WHATSAPP_APP_SECRET   = var.whatsapp_app_secret
    EXOTEL_API_TOKEN      = var.exotel_api_token
    PLIVO_AUTH_TOKEN      = var.plivo_auth_token
    SENTRY_DSN            = var.sentry_dsn
    LANGFUSE_SECRET_KEY   = var.langfuse_secret_key
    S3_ACCESS_KEY_ID      = aws_iam_access_key.egress.id
    S3_SECRET_ACCESS_KEY  = aws_iam_access_key.egress.secret
  }
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.project}/${var.environment}/app"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id     = aws_secretsmanager_secret.app.id
  secret_string = jsonencode(local.app_secret_values)
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.project}/${var.environment}/database-url"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+asyncpg://%s:%s@%s:5432/%s?sslmode=require",
    var.db_username,
    urlencode(random_password.db.result),
    aws_db_instance.main.address,
    var.db_name,
  )
}

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!*_-"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid = "ReadDeploymentSecrets"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      aws_secretsmanager_secret.app.arn,
      aws_secretsmanager_secret.database_url.arn,
    ]
  }
}

resource "aws_iam_policy" "execution_secrets" {
  name   = "${var.project}-${var.environment}-execution-secrets"
  policy = data.aws_iam_policy_document.execution_secrets.json
}

resource "aws_iam_role_policy_attachment" "execution_secrets" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.execution_secrets.arn
}
