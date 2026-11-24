#!/usr/bin/env bash
# Delete everything k8s/eks-up.sh created: the UI load balancers, the EKS cluster with its VPC,
# NAT gateway, Elastic IP and node group (one eksctl call), the ECR repositories and the kube-context.
# Then list anything still tagged Project=tuktukpay so nothing keeps billing.
#   k8s/eks-down.sh          # or: make eks-down
set -uo pipefail
export AWS_PROFILE=${EKS_AWS_PROFILE:-default}
export AWS_REGION=ap-southeast-1
CLUSTER=tuktukpay-eks
ACCOUNT=${EKS_AWS_ACCOUNT:?set EKS_AWS_ACCOUNT (your AWS account ID) in .env}
NAMESPACE=${NAMESPACE:-tuktukpay}
SERVICES="chaos-controller checkout-api risk-engine payment-router acquirer-sim ledger webhook-dispatcher merchant-copilot wallet-sim loadgen"

who=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "AWS profile $AWS_PROFILE has no working credentials." >&2; exit 1; }
[ "$who" = "$ACCOUNT" ] || { echo "AWS profile $AWS_PROFILE is account $who, expected $ACCOUNT. Stopping." >&2; exit 1; }

# Our Splunk Enterprise instance lives in the cluster VPC; it must go first or the VPC cannot be deleted
"$(dirname "$0")/../splunk/ec2/ec2-down.sh"

if eksctl get cluster --name "$CLUSTER" >/dev/null 2>&1; then
  # Load balancers belong to Kubernetes Services, not to the CloudFormation stacks: delete them first
  # or the VPC cannot be deleted.
  echo "== deleting the UI load balancers"
  kubectl --context "$CLUSTER" -n "$NAMESPACE" delete svc chaos-controller-lb shopping-agent-lb --ignore-not-found --wait=true --timeout=180s || true
  sleep 30
  echo "== deleting EKS cluster $CLUSTER (10-15 min)"
  eksctl delete cluster --name "$CLUSTER" --wait --disable-nodegroup-eviction
else
  echo "== no cluster $CLUSTER"
fi

echo "== deleting ECR repositories"
for s in $SERVICES; do
  aws ecr delete-repository --repository-name "tuktukpay/tuktukpay-$s" --force >/dev/null 2>&1 && echo "   tuktukpay/tuktukpay-$s"
done
kubectl config delete-context "$CLUSTER" >/dev/null 2>&1 || true

echo "== leftovers (should all be empty)"
echo "   clusters:      $(aws eks list-clusters --query 'clusters' --output text)"
echo "   NAT gateways:  $(aws ec2 describe-nat-gateways --filter "Name=tag:alpha.eksctl.io/cluster-name,Values=$CLUSTER" Name=state,Values=pending,available,deleting --query 'NatGateways[].NatGatewayId' --output text)"
echo "   Elastic IPs:   $(aws ec2 describe-addresses --filters "Name=tag:alpha.eksctl.io/cluster-name,Values=$CLUSTER" --query 'Addresses[].PublicIp' --output text)"
echo "   VPCs:          $(aws ec2 describe-vpcs --filters "Name=tag:alpha.eksctl.io/cluster-name,Values=$CLUSTER" --query 'Vpcs[].VpcId' --output text)"
echo "   load balancers:$(aws elbv2 describe-load-balancers --query "LoadBalancers[?contains(LoadBalancerName, 'k8s') || contains(DNSName, 'tuktukpay')].LoadBalancerName" --output text)"
echo "   instances:     $(aws ec2 describe-instances --filters Name=tag:Project,Values=tuktukpay Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text)"
echo "   ECR repos:     $(aws ecr describe-repositories --query "repositories[?starts_with(repositoryName, 'tuktukpay/')].repositoryName" --output text)"
echo "   CloudFormation:$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE DELETE_FAILED --query "StackSummaries[?starts_with(StackName, 'eksctl-$CLUSTER')].StackName" --output text)"
