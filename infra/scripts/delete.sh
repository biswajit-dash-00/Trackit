#!/bin/bash

# Delete TrackIt deployment from Kubernetes
# This script removes all TrackIt resources from the nimbus-dev namespace

set -e

NAMESPACE="nimbus-dev"
K8S_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../k8s" && pwd)"

echo "======================================"
echo "TrackIt Kubernetes Deletion Script"
echo "======================================"
echo ""
echo "Namespace: $NAMESPACE"
echo ""

read -p "Are you sure you want to delete all TrackIt resources? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Deletion cancelled"
  exit 0
fi

echo ""
echo "Deleting resources..."
echo ""

echo "[1/4] Deleting VirtualService and DestinationRule..."
kubectl delete -f "$K8S_DIR/virtualservice.yaml" --ignore-not-found=true
kubectl delete -f "$K8S_DIR/destinationrule.yaml" --ignore-not-found=true
echo "✓ Deleted"
echo ""

echo "[2/4] Deleting Deployment..."
kubectl delete -f "$K8S_DIR/deployment.yaml" --ignore-not-found=true
echo "✓ Deleted"
echo ""

echo "[3/4] Deleting Service..."
kubectl delete -f "$K8S_DIR/service.yaml" --ignore-not-found=true
echo "✓ Deleted"
echo ""

echo "[4/4] Deleting ConfigMap..."
kubectl delete -f "$K8S_DIR/configmap.yaml" --ignore-not-found=true
echo "✓ Deleted"
echo ""

echo "======================================"
echo "Deletion Complete!"
echo "======================================"
echo ""
echo "Verify deletion with:"
echo "  kubectl get all -n $NAMESPACE"
echo ""
