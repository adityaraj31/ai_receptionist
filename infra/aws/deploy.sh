#!/usr/bin/env bash
# Build and push the API, agent, dashboard, and metrics images to ECR.
# Run `terraform apply` in infra/aws/terraform once first so the repositories exist.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/aws/terraform"
AWS_REGION="${AWS_REGION:-ap-south-1}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
APPLY=0

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -h|--help)
      echo "Usage: AWS_REGION=ap-south-1 IMAGE_TAG=$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo latest) $0 [--apply]"
      exit 0
      ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

AWS_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_BASE="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

API_URL="${NEXT_PUBLIC_API_URL:-}"
if [[ -z "$API_URL" ]]; then
  API_URL="$(terraform -chdir="$TF_DIR" output -raw api_url 2>/dev/null || true)"
fi
if [[ -z "$API_URL" ]]; then
  echo "Set NEXT_PUBLIC_API_URL or apply Terraform first so api_url is available." >&2
  exit 1
fi

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_BASE" >/dev/null

build_and_push() {
  local name="$1" context="$2" dockerfile="$3"
  shift 3
  local image="${ECR_BASE}/ai-receptionist/${name}:${IMAGE_TAG}"

  echo "==> Building $name ($image)"
  if docker buildx version >/dev/null 2>&1; then
    docker buildx build \
      --platform linux/amd64 \
      --file "$dockerfile" \
      --tag "$image" \
      --push \
      "$@" \
      "$context"
  else
    docker build --platform linux/amd64 --file "$dockerfile" --tag "$image" "$@" "$context"
    docker push "$image"
  fi
}

build_and_push api "$ROOT_DIR/api" "$ROOT_DIR/infra/docker/api.Dockerfile"
build_and_push agent "$ROOT_DIR/agent" "$ROOT_DIR/infra/docker/agent.Dockerfile"
build_and_push dashboard "$ROOT_DIR/dashboard" "$ROOT_DIR/infra/docker/dashboard.Dockerfile" \
  --build-arg "NEXT_PUBLIC_API_URL=${API_URL}"
build_and_push agent-metrics "$ROOT_DIR/infra/aws/agent-metrics" \
  "$ROOT_DIR/infra/aws/agent-metrics/Dockerfile"

echo
echo "Pushed images with tag: $IMAGE_TAG"
echo "Apply with: terraform -chdir=\"$TF_DIR\" apply -var=\"image_tag=$IMAGE_TAG\""

if [[ "$APPLY" == "1" ]]; then
  terraform -chdir="$TF_DIR" apply -var="image_tag=$IMAGE_TAG"
fi
