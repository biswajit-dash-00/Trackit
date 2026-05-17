#!/bin/bash

# Deploy TrackIt to Kubernetes
# This script deploys all K8s resources to the nimbus-dev namespace

set -e

NAMESPACE="nimbus-dev"
K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../k8s" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================"
echo "TrackIt Kubernetes Deployment Script"
echo "======================================"
echo ""
echo "Namespace: $NAMESPACE"
echo "K8s manifests directory: $K8S_DIR"
echo ""

# Step 1: Create namespace
echo "[1/6] Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✓ Namespace created/updated"
echo ""

# Step 2: Setup ECR secret
echo "[2/6] Setting up ECR credentials..."
bash "$SCRIPT_DIR/setup-ecr-secret.sh"
echo ""

# Step 3: Apply ConfigMap
echo "[3/6] Applying ConfigMap..."
kubectl apply -f "$K8S_DIR/configmap.yaml"
echo "✓ ConfigMap applied"
echo ""

# Step 4: Apply Service
echo "[4/6] Applying Service..."
kubectl apply -f "$K8S_DIR/service.yaml"
echo "✓ Service applied"
echo ""

# Step 5: Apply Deployment
echo "[5/6] Applying Deployment..."
kubectl apply -f "$K8S_DIR/deployment.yaml"
echo "✓ Deployment applied"
echo ""

# Step 6: Apply VirtualService and DestinationRule
echo "[6/6] Applying VirtualService and DestinationRule..."
kubectl apply -f "$K8S_DIR/virtualservice.yaml"
kubectl apply -f "$K8S_DIR/destinationrule.yaml"
echo "✓ VirtualService and DestinationRule applied"
echo ""

echo "======================================"
echo "Deployment Complete!"
echo "======================================"
echo ""
echo "Verify deployment with:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -f deployment/trackit -n $NAMESPACE"
echo "  kubectl describe pod -l app=trackit -n $NAMESPACE"
echo ""
