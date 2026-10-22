resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "recordings" {
  bucket        = "${var.project}-${var.environment}-recordings-${random_id.bucket_suffix.hex}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "recordings" {
  bucket                  = aws_s3_bucket.recordings.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  rule {
    id     = "expire-call-recordings"
    status = "Enabled"

    filter {
      prefix = "recordings/"
    }

    expiration {
      days = var.recording_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project}-${var.environment}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name = "${var.project}-${var.environment}-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

data "aws_iam_policy_document" "recordings" {
  statement {
    sid = "ListRecordingsBucket"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [aws_s3_bucket.recordings.arn]
  }

  statement {
    sid = "ReadWriteRecordings"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = ["${aws_s3_bucket.recordings.arn}/*"]
  }
}

resource "aws_iam_policy" "recordings" {
  name   = "${var.project}-${var.environment}-recordings"
  policy = data.aws_iam_policy_document.recordings.json
}

resource "aws_iam_role_policy_attachment" "recordings" {
  role       = aws_iam_role.task.name
  policy_arn = aws_iam_policy.recordings.arn
}

resource "aws_iam_user" "egress" {
  name = "${var.project}-${var.environment}-egress"
  path = "/service/"
}

data "aws_iam_policy_document" "egress_recordings" {
  statement {
    sid = "PutRecordingObjects"
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = ["${aws_s3_bucket.recordings.arn}/recordings/*"]
  }
}

resource "aws_iam_user_policy" "egress_recordings" {
  name   = "${var.project}-${var.environment}-egress-recordings"
  user   = aws_iam_user.egress.name
  policy = data.aws_iam_policy_document.egress_recordings.json
}

resource "aws_iam_access_key" "egress" {
  user = aws_iam_user.egress.name
}
