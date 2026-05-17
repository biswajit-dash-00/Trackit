#!/bin/bash

# Check deployment status
# This script displays the current status of all TrackIt resources

NAMESPACE="nimbus-dev"

echo "======================================"
echo "TrackIt Deployment Status"
echo "======================================"
echo ""

echo "Namespace: $NAMESPACE"
echo ""

echo "--- Pods ---"
kubectl get pods -n $NAMESPACE -l app=trackit
echo ""

echo "--- Services ---"
kubectl get svc -n $NAMESPACE -l app=trackit
echo ""

echo "--- VirtualServices ---"
kubectl get vs -n $NAMESPACE -l app=trackit 2>/dev/null || echo "No VirtualServices found or Istio not installed"
echo ""

echo "--- DestinationRules ---"
kubectl get dr -n $NAMESPACE -l app=trackit 2>/dev/null || echo "No DestinationRules found or Istio not installed"
echo ""

echo "--- ConfigMaps ---"
kubectl get configmap -n $NAMESPACE -l app=trackit
echo ""

echo "--- Latest Events ---"
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10
echo ""

echo "--- Pod Details ---"
POD_NAME=$(kubectl get pods -n $NAMESPACE -l app=trackit -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD_NAME" ]; then
  echo "No running pod found"
else
  echo "Pod: $POD_NAME"
  echo ""
  echo "Status:"
  kubectl describe pod $POD_NAME -n $NAMESPACE | grep -A 20 "Status:"
  echo ""
  echo "Conditions:"
  kubectl describe pod $POD_NAME -n $NAMESPACE | grep -A 10 "Conditions:"
fi
