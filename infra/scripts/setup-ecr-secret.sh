#!/bin/bash

# Setup ECR Image Pull Secret
# This script creates the necessary credentials for pulling Docker images from AWS ECR

set -e

NAMESPACE="nimbus-dev"
REGION="ap-south-1"
ACCOUNT_ID="741448940918"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
SECRET_NAME="ecr-secret"
EMAIL="admin@example.com"

echo "Creating ECR image pull secret in namespace: $NAMESPACE"

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Get ECR login password
echo "Getting ECR login credentials..."
ECR_PASSWORD=$(aws ecr get-login-password --region $REGION)

# Create or update the image pull secret
echo "Creating/updating image pull secret..."
kubectl create secret docker-registry $SECRET_NAME \
  --docker-server=$ECR_REGISTRY \
  --docker-username=AWS \
  --docker-password=$ECR_PASSWORD \
  --docker-email=$EMAIL \
  --namespace=$NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

echo "ECR secret created successfully!"
echo "Secret name: $SECRET_NAME"
echo "Namespace: $NAMESPACE"
echo ""
echo "Verify with:"
echo "  kubectl get secrets -n $NAMESPACE"
echo "  kubectl describe secret $SECRET_NAME -n $NAMESPACE"
