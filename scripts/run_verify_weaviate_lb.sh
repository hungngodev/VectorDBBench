#!/usr/bin/env bash
# Run the Weaviate load balancing verification script in k8s

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}

echo "Creating verification pod in namespace $NS..."

# Delete existing job if present
kubectl -n "$NS" delete job verify-weaviate-lb --ignore-not-found

cat <<EOF | kubectl -n "$NS" apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: verify-weaviate-lb
spec:
  template:
    spec:
      containers:
      - name: verify
        image: ${IMG}
        command: ["python", "/opt/vdb/scripts/verify_weaviate_lb.py"]
        env:
        - name: WEAVIATE_URL
          value: "weaviate.marco.svc.cluster.local"
        - name: WEAVIATE_PORT
          value: "80"
        volumeMounts:
        - name: scripts
          mountPath: /opt/vdb/scripts
          readOnly: true
      volumes:
      - name: scripts
        configMap:
          name: verify-weaviate-lb-script
      restartPolicy: Never
  backoffLimit: 1
EOF

echo ""
echo "To view results:"
echo "  kubectl -n $NS logs job/verify-weaviate-lb"
echo ""
echo "Or run the script directly if you have the image locally:"
echo "  python scripts/verify_weaviate_lb.py"
