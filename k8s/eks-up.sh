#!/usr/bin/env bash
# The workshop on EKS (Amazon Elastic Kubernetes Service), the counterpart of kind-up.sh:
# cluster (k8s/eks-cluster.yaml) + ECR (Elastic Container Registry) images + Splunk OTel Collector chart
# + the TukTukPay stack, with the war-room panel and the agent console behind load balancers that only
# accept your current public IP. Safe to re-run: it creates what is missing and rolls out changed images.
#
# Requirements: docker, eksctl, kubectl, helm, aws CLI (EKS_AWS_ACCOUNT, EKS_AWS_PROFILE in .env). Reads SPLUNK_* and
# DEPLOYMENT_ENVIRONMENT from ../.env (same as kind). Stop the kind cluster first if both would
# report the same environment (docker stop tuktukpay-control-plane).
#   k8s/eks-up.sh            # or: make eks-up
#   k8s/eks-down.sh          # deletes everything again
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$DIR/.." && pwd)
[ -f "$ROOT/.env" ] && set -a && . "$ROOT/.env" && set +a
export AWS_PROFILE=${EKS_AWS_PROFILE:-default}
export AWS_REGION=ap-southeast-1      # also used below; the apps' AWS_REGION in .env is the same region
CLUSTER=tuktukpay-eks
ACCOUNT=${EKS_AWS_ACCOUNT:?set EKS_AWS_ACCOUNT (your AWS account ID) in .env}
CONTEXT=$CLUSTER
: "${NAMESPACE:=tuktukpay}"
: "${DEPLOYMENT_ENVIRONMENT:=tuktukpay-k8s}"
: "${SPLUNK_REALM:?set SPLUNK_REALM in .env}"
: "${SPLUNK_ACCESS_TOKEN:?set SPLUNK_ACCESS_TOKEN in .env}"
SERVICES="chaos-controller checkout-api risk-engine payment-router acquirer-sim ledger webhook-dispatcher merchant-copilot wallet-sim loadgen"
REGISTRY=$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
K="kubectl --context $CONTEXT"

docker info >/dev/null 2>&1 || { echo "Docker is not running: start Docker Desktop (open -a Docker), then run this again." >&2; exit 1; }
who=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "AWS profile $AWS_PROFILE has no working credentials." >&2; exit 1; }
[ "$who" = "$ACCOUNT" ] || { echo "AWS profile $AWS_PROFILE is account $who, expected $ACCOUNT (Cisco). Stopping." >&2; exit 1; }

if ! eksctl get cluster --name "$CLUSTER" >/dev/null 2>&1; then
  echo "== creating EKS cluster $CLUSTER (15-20 min; billing starts now, about USD 0.60/hour)"
  eksctl create cluster -f "$DIR/eks-cluster.yaml" --kubeconfig "$HOME/.kube/config" --set-kubeconfig-context=false
fi
aws eks update-kubeconfig --name "$CLUSTER" --alias "$CONTEXT" >/dev/null
echo "== kube-context $CONTEXT (kind stays the current context; use --context $CONTEXT)"

NAT_IP=$(aws ec2 describe-nat-gateways --filter "Name=tag:alpha.eksctl.io/cluster-name,Values=$CLUSTER" "Name=state,Values=available" \
  --query 'NatGateways[0].NatGatewayAddresses[0].PublicIp' --output text)
echo "== cluster egress IP: $NAT_IP — must be on Splunk Cloud: Settings > Server settings > IP allow list > HEC access for ingestion"

echo "== ECR repositories + image push"
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
( cd "$ROOT" && docker compose build $SERVICES )
CHANGED=""
for s in $SERVICES; do
  repo=tuktukpay/tuktukpay-$s
  aws ecr describe-repositories --repository-names "$repo" >/dev/null 2>&1 ||
    aws ecr create-repository --repository-name "$repo" --tags Key=Project,Value=tuktukpay >/dev/null
  before=$(aws ecr describe-images --repository-name "$repo" --image-ids imageTag=latest --query 'imageDetails[0].imageDigest' --output text 2>/dev/null || true)
  docker tag "tuktukpay-workshop-$s:latest" "$REGISTRY/$repo:latest"
  docker push -q "$REGISTRY/$repo:latest" >/dev/null
  after=$(aws ecr describe-images --repository-name "$repo" --image-ids imageTag=latest --query 'imageDetails[0].imageDigest' --output text)
  if [ -n "$before" ] && [ "$before" != "None" ] && [ "$before" != "$after" ]; then CHANGED="$CHANGED $s"; fi
  echo "   $s ${after:7:12}"
done

echo "== Splunk OTel Collector chart + OpenTelemetry Operator"
helm repo add splunk-otel-collector-chart https://signalfx.github.io/splunk-otel-collector-chart >/dev/null 2>&1 || true
helm repo update >/dev/null
HEC_ARGS=()
if [ -n "${SPLUNK_HEC_URL:-}" ] && [ -n "${SPLUNK_HEC_TOKEN:-}" ]; then
  HEC_ARGS=(--set "splunkPlatform.endpoint=$SPLUNK_HEC_URL" --set "splunkPlatform.token=$SPLUNK_HEC_TOKEN" --set "splunkPlatform.index=${SPLUNK_HEC_INDEX:-tuktukpay}")
fi
EC2_VALUES=""; KUBECONFIG_EKS=""
trap 'rm -f "$EC2_VALUES" "$KUBECONFIG_EKS"' EXIT
# Second log destination: our Splunk Enterprise on EC2 (splunk/ec2/ec2-up.sh), next to Splunk Cloud, when it
# exists. Pods reach its HEC on the private IP (self-signed certificate). The token stays out of the command
# line: it goes into a private values file that is deleted on exit.
EXTRA_VALUES=()
EC2_CREDS=$ROOT/splunk/ec2/ec2_creds.txt
EC2_IP=$(aws ec2 describe-instances --filters Name=tag:Name,Values=tuktukpay-splunk Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text 2>/dev/null || true)
if [ -s "$EC2_CREDS" ] && [ -n "$(sed -n 3p "$EC2_CREDS")" ] && [ -n "$EC2_IP" ] && [ "$EC2_IP" != None ]; then
  EC2_VALUES=$(mktemp)   # mktemp creates it 0600
  python3 -I - "$EC2_IP" "$EC2_CREDS" "${SPLUNK_HEC_INDEX:-tuktukpay}" > "$EC2_VALUES" <<'PY'
import json, sys
ip, creds, index = sys.argv[1:]
token = open(creds).read().splitlines()[2].strip()   # line 3 of ec2_creds.txt
# Same settings as the chart's splunk_hec/platform_logs on each side: the agent leaves profiling data
# out, the cluster receiver labels Kubernetes events kube:events.
def exp(**extra):
    return {"splunk_hec/ec2": {"endpoint": f"https://{ip}:8088/services/collector", "token": token, "index": index,
            "source": "kubernetes", "tls": {"insecure_skip_verify": True}, "timeout": "10s",
            "retry_on_failure": {"enabled": True, "max_elapsed_time": "120s"},
            "sending_queue": {"enabled": True, "num_consumers": 10, "queue_size": 1000}, **extra}}
both = ["splunk_hec/platform_logs", "splunk_hec/ec2"]
print(json.dumps({  # JSON is valid YAML; lists replace the chart's, so name every exporter
  "agent": {"config": {"exporters": exp(profiling_data_enabled=False),
                       "service": {"pipelines": {"logs": {"exporters": ["splunk_hec/o11y"] + both}}}}},
  "clusterReceiver": {"config": {"exporters": exp(sourcetype="kube:events"), "service": {"pipelines": {
      "logs": {"exporters": both}, "logs/objects": {"exporters": both}}}}}}))
PY
  EXTRA_VALUES=(-f "$EC2_VALUES")
  echo "   logs also -> Splunk Enterprise on EC2 https://$EC2_IP:8088 (index ${SPLUNK_HEC_INDEX:-tuktukpay})"
fi
helm upgrade --install splunk-otel-collector splunk-otel-collector-chart/splunk-otel-collector \
  --kube-context "$CONTEXT" --namespace splunk-otel --create-namespace \
  --set splunkObservability.accessToken="$SPLUNK_ACCESS_TOKEN" \
  --set splunkObservability.realm="$SPLUNK_REALM" \
  --set clusterName="$CLUSTER" \
  --set environment="$DEPLOYMENT_ENVIRONMENT" \
  --set cloudProvider=aws --set distribution=eks \
  ${HEC_ARGS[@]+"${HEC_ARGS[@]}"} \
  -f "$DIR/values-splunk-otel-collector.yaml" ${EXTRA_VALUES[@]+"${EXTRA_VALUES[@]}"} --wait --timeout 8m
$K -n splunk-otel wait --for=condition=available deployment -l app.kubernetes.io/name=opentelemetry-operator --timeout=180s 2>/dev/null || true

echo "== deploying TukTukPay ($NAMESPACE / $DEPLOYMENT_ENVIRONMENT)"
# apply.sh uses the current context; point it at EKS for this call only.
KUBECONFIG_EKS=$(mktemp)
kubectl config view --raw --minify --context "$CONTEXT" > "$KUBECONFIG_EKS"
KUBECONFIG=$KUBECONFIG_EKS IMAGE_REGISTRY="$REGISTRY/tuktukpay" NAMESPACE="$NAMESPACE" DEPLOYMENT_ENVIRONMENT="$DEPLOYMENT_ENVIRONMENT" "$DIR/apply.sh"
if [ -n "$CHANGED" ]; then
  echo "== restarting deployments whose image changed:$CHANGED"
  for s in $CHANGED; do
    case $s in loadgen) deps=merchant-storefront ;; wallet-sim) deps="wallet-sim shopping-agent" ;; *) deps=$s ;; esac
    for d in $deps; do $K -n "$NAMESPACE" rollout restart "deployment/$d" >/dev/null 2>&1 || true; done
  done
fi

echo "== load balancers for the two UIs (only your IP)"
MY_IP=$(curl -4 -s -m 5 https://api.ipify.org)
# Separate Services so apply.sh (NodePort, as on kind) never fights over the type.
for pair in chaos-controller:8090 shopping-agent:8087; do
  app=${pair%:*}; port=${pair#*:}
  $K apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Service
metadata:
  name: $app-lb
  namespace: $NAMESPACE
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  loadBalancerSourceRanges: ["$MY_IP/32"]
  selector: {app: $app}
  ports: [{port: 80, targetPort: $port, name: http}]
EOF
done
$K -n "$NAMESPACE" rollout status deployment --timeout=300s 2>/dev/null || $K -n "$NAMESPACE" get pods
for app in chaos-controller shopping-agent; do
  for _ in $(seq 1 30); do
    host=$($K -n "$NAMESPACE" get svc "$app-lb" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    [ -n "$host" ] && break; sleep 5
  done
  eval "URL_${app//-/_}=http://${host:-pending}"
done
echo
echo "war room:      $URL_chaos_controller   (load balancer DNS takes 2-3 min to answer the first time)"
echo "agent console: $URL_shopping_agent"
echo "allowed IP:    $MY_IP/32 — on a new network re-run this script to update it"
echo "HEC egress IP: $NAT_IP"
echo "kubectl:       kubectl --context $CONTEXT -n $NAMESPACE get pods"
echo "tear down:     k8s/eks-down.sh"
