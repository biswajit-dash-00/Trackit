#!/bin/bash

# Restart TrackIt deployment
# This script restarts the TrackIt pod by deleting and recreating it

set -e

NAMESPACE="nimbus-dev"

echo "======================================"
echo "TrackIt Restart Script"
echo "======================================"
echo ""
echo "Namespace: $NAMESPACE"
echo ""

read -p "Are you sure you want to restart TrackIt? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Restart cancelled"
  exit 0
fi

echo ""
echo "Restarting deployment..."
echo ""

echo "Rolling restart of TrackIt deployment..."
kubectl rollout restart deployment/trackit -n $NAMESPACE

echo "Waiting for deployment to be ready..."
kubectl rollout status deployment/trackit -n $NAMESPACE

echo ""
echo "======================================"
echo "Restart Complete!"
echo "======================================"
echo ""
echo "Check pod status with:"
echo "  kubectl get pods -n $NAMESPACE -l app=trackit"
echo "  kubectl logs -f deployment/trackit -n $NAMESPACE"
echo ""
