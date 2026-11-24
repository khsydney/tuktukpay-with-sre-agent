#!/usr/bin/env bash
# Delete everything splunk/ec2/ec2-up.sh created: the instance (and its disk), the Elastic IP, the security
# group and the key pair. Must run before the EKS VPC (Virtual Private Cloud) is deleted, so
# k8s/eks-down.sh calls it first.
#   splunk/ec2/ec2-down.sh    # or: make splunk-ec2-down
set -uo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
export AWS_PROFILE=${EKS_AWS_PROFILE:-default}
export AWS_REGION=ap-southeast-1
ACCOUNT=${EKS_AWS_ACCOUNT:?set EKS_AWS_ACCOUNT (your AWS account ID) in .env}
NAME=tuktukpay-splunk

who=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "AWS profile $AWS_PROFILE has no working credentials." >&2; exit 1; }
[ "$who" = "$ACCOUNT" ] || { echo "AWS profile $AWS_PROFILE is account $who, expected $ACCOUNT. Stopping." >&2; exit 1; }

IDS=$(aws ec2 describe-instances --filters Name=tag:Name,Values=$NAME Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down \
       --query 'Reservations[].Instances[].InstanceId' --output text)
if [ -n "$IDS" ]; then
  echo "== terminating $IDS"
  aws ec2 terminate-instances --instance-ids $IDS >/dev/null
  aws ec2 wait instance-terminated --instance-ids $IDS
fi
for a in $(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[].AllocationId' --output text); do
  echo "== releasing Elastic IP $a"; aws ec2 release-address --allocation-id $a
done
for sg in $(aws ec2 describe-security-groups --filters Name=group-name,Values=$NAME --query 'SecurityGroups[].GroupId' --output text); do
  echo "== deleting security group $sg"
  for i in 1 2 3 4 5 6; do aws ec2 delete-security-group --group-id $sg 2>/dev/null && break; sleep 10; done   # ENI (network interface) release lags termination
done
aws ec2 delete-key-pair --key-name $NAME >/dev/null 2>&1 && echo "== deleted key pair $NAME"
rm -f "$HOME/.ssh/$NAME.pem" "$HOME/.ssh/known_hosts.$NAME" "$DIR/ec2_creds.txt"

echo "== leftovers (should all be empty)"
echo "   instances:       $(aws ec2 describe-instances --filters Name=tag:Name,Values=$NAME Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text)"
echo "   Elastic IPs:     $(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[].PublicIp' --output text)"
echo "   security groups: $(aws ec2 describe-security-groups --filters Name=group-name,Values=$NAME --query 'SecurityGroups[].GroupId' --output text)"
