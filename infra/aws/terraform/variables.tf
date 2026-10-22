variable "aws_region" {
  description = "AWS region. Keep all health data in India."
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Short resource prefix."
  type        = string
  default     = "ai-receptionist"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "prod"
}

variable "image_tag" {
  description = "Image tag pushed by infra/aws/deploy.sh."
  type        = string
  default     = "latest"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.1.0/24", "10.42.2.0/24"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.42.11.0/24", "10.42.12.0/24"]
}

variable "api_hostname" {
  description = "Public API hostname, e.g. api.clinic.example.com."
  type        = string
}

variable "dashboard_hostname" {
  description = "Public dashboard hostname, e.g. app.clinic.example.com."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ACM certificate covering both hostnames. Leave empty for HTTP-only smoke testing."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Optional Route53 hosted zone id for api/dashboard alias records."
  type        = string
  default     = ""
}

variable "agent_api_key" {
  description = "Clinic-scoped service key. Must equal DEMO_AGENT_KEY when seeding the database."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.agent_api_key) >= 24
    error_message = "agent_api_key must be at least 24 characters."
  }
}

variable "demo_staff_email" {
  type    = string
  default = "admin@demo-clinic.example.com"
}

variable "demo_staff_password" {
  type      = string
  sensitive = true

  validation {
    condition     = length(var.demo_staff_password) >= 12
    error_message = "demo_staff_password must be at least 12 characters."
  }
}

variable "livekit_url" {
  type = string
}

variable "livekit_api_key" {
  type      = string
  sensitive = true
}

variable "livekit_api_secret" {
  type      = string
  sensitive = true
}

variable "livekit_agent_name" {
  type    = string
  default = "ai-receptionist"
}

variable "livekit_sip_number" {
  type    = string
  default = ""
}

variable "livekit_sip_outbound_trunk" {
  type    = string
  default = ""
}

variable "sarvam_api_key" {
  type      = string
  sensitive = true
}

variable "sarvam_stt_model" {
  type    = string
  default = "saaras:v4"
}

variable "sarvam_tts_model" {
  type    = string
  default = "bulbul:v3"
}

variable "sarvam_tts_speaker" {
  type    = string
  default = "shubh"
}

variable "sarvam_language" {
  type    = string
  default = "hi-IN"
}

variable "llm_api_key" {
  type      = string
  sensitive = true
}

variable "llm_model" {
  type    = string
  default = "gpt-4.1-mini"
}

variable "llm_base_url" {
  type    = string
  default = ""
}

variable "whatsapp_provider" {
  type    = string
  default = "none"
}

variable "whatsapp_access_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "whatsapp_phone_number_id" {
  type    = string
  default = ""
}

variable "whatsapp_verify_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "whatsapp_app_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "sms_provider" {
  type    = string
  default = "none"
}

variable "exotel_sid" {
  type    = string
  default = ""
}

variable "exotel_api_key" {
  type    = string
  default = ""
}

variable "exotel_api_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "exotel_caller_id" {
  type    = string
  default = ""
}

variable "plivo_auth_id" {
  type    = string
  default = ""
}

variable "plivo_auth_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "plivo_number" {
  type    = string
  default = ""
}

variable "sentry_dsn" {
  type      = string
  default   = ""
  sensitive = true
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}

variable "langfuse_public_key" {
  type    = string
  default = ""
}

variable "langfuse_secret_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "api_cpu" {
  type    = number
  default = 1024
}

variable "api_memory" {
  type    = number
  default = 2048
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "dashboard_cpu" {
  type    = number
  default = 512
}

variable "dashboard_memory" {
  type    = number
  default = 1024
}

variable "dashboard_desired_count" {
  type    = number
  default = 1
}

variable "worker_cpu" {
  type    = number
  default = 512
}

variable "worker_memory" {
  type    = number
  default = 1024
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

variable "agent_cpu" {
  type    = number
  default = 2048
}

variable "agent_memory" {
  type    = number
  default = 4096
}

variable "agent_min_count" {
  type    = number
  default = 1
}

variable "agent_max_count" {
  type    = number
  default = 20
}

variable "agent_target_calls_per_task" {
  description = "Target average active calls per agent task for ECS target tracking."
  type        = number
  default     = 6
}

variable "rds_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "rds_allocated_storage" {
  type    = number
  default = 100
}

variable "rds_max_allocated_storage" {
  type    = number
  default = 500
}

variable "rds_multi_az" {
  type    = bool
  default = false
}

variable "db_name" {
  type    = string
  default = "receptionist"
}

variable "db_username" {
  type    = string
  default = "receptionist"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "recording_retention_days" {
  type    = number
  default = 90
}

variable "log_retention_days" {
  type    = number
  default = 30
}
