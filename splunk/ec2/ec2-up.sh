#!/usr/bin/env bash
# Our own Splunk Enterprise 10.6.1.1 on EC2 (Elastic Compute Cloud), next to the EKS (Amazon Elastic
# Kubernetes Service) cluster, for the control-tower app while Splunk Cloud cannot take it.
#   - m7i.xlarge (x86, 4 vCPU (virtual CPU), 16 GiB), Amazon Linux 2023, 100 GiB gp3, in a public subnet of
#     the tuktukpay-eks VPC (Virtual Private Cloud) with an Elastic IP
#   - security group: 22 (SSH (Secure Shell)), 8000 (Splunk Web, HTTPS), 8089 (management), 8088 (HEC
#     (HTTP Event Collector)) from your current public IP; 8088 also from the EKS node security group,
#     so pods reach HEC on the private IP
#   - Splunk: admin user, license, index tuktukpay, HEC token, control-tower app, lookups
#   - terminates itself on Fri 30 Oct 2026 22:00 (+07) with EKS; k8s/eks-down.sh also calls ec2-down.sh
# Safe to re-run (also re-opens the security group for a new network).
#   splunk/ec2/ec2-up.sh      # or: make splunk-ec2-up
# Writes splunk/ec2/ec2_creds.txt (git-ignored): line 1 user, 2 password, 3 HEC token, 4 Splunk Web URL,
# 5 password of o11y_connect (the Log Observer Connect service account).
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$DIR/../.." && pwd)
export AWS_PROFILE=${EKS_AWS_PROFILE:-default}
export AWS_REGION=ap-southeast-1
ACCOUNT=${EKS_AWS_ACCOUNT:?set EKS_AWS_ACCOUNT (your AWS account ID) in .env}
CLUSTER=tuktukpay-eks
NAME=tuktukpay-splunk
TYPE=${SPLUNK_EC2_TYPE:-m7i.xlarge}
KEY=$HOME/.ssh/$NAME.pem
CREDS=$DIR/ec2_creds.txt
LICENSE=${SPLUNK_LICENSE_FILE:-$HOME/Downloads/Splunk Enterprise NFR CY2026.License}
APP_TGZ=$(ls -t "$ROOT"/splunk/control-tower/dist/tuktukpay_control_tower-*.tgz 2>/dev/null | head -1 || true)
TAGS="{Key=Name,Value=$NAME},{Key=Project,Value=tuktukpay}"

who=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || { echo "AWS profile $AWS_PROFILE has no working credentials." >&2; exit 1; }
[ "$who" = "$ACCOUNT" ] || { echo "AWS profile $AWS_PROFILE is account $who, expected $ACCOUNT. Stopping." >&2; exit 1; }
[ -f "$LICENSE" ] || { echo "License file not found: $LICENSE (set SPLUNK_LICENSE_FILE)" >&2; exit 1; }

# Network: the EKS cluster's VPC, a public subnet, and the security group its nodes use
read -r VPC NODE_SG < <(aws eks describe-cluster --name $CLUSTER --query 'cluster.resourcesVpcConfig.[vpcId,clusterSecurityGroupId]' --output text) \
  || { echo "EKS cluster $CLUSTER not found: run make eks-up first." >&2; exit 1; }
SUBNET=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=map-public-ip-on-launch,Values=true Name=availability-zone,Values=${AWS_REGION}a \
  --query 'Subnets[0].SubnetId' --output text)
VPC_CIDR=$(aws ec2 describe-vpcs --vpc-ids $VPC --query 'Vpcs[0].CidrBlock' --output text)
MYIP=$(curl -fsS https://checkip.amazonaws.com)
echo "== VPC $VPC ($VPC_CIDR), subnet $SUBNET, EKS node security group $NODE_SG, your IP $MYIP"

# Key pair (private key stays in ~/.ssh)
if ! aws ec2 describe-key-pairs --key-names $NAME >/dev/null 2>&1; then
  echo "== creating key pair $NAME -> $KEY"
  ( umask 077; aws ec2 create-key-pair --key-name $NAME --key-type ed25519 --tag-specifications "ResourceType=key-pair,Tags=[$TAGS]" \
      --query KeyMaterial --output text > "$KEY" )
fi
[ -s "$KEY" ] || { echo "Key pair $NAME exists in AWS but $KEY is missing: run splunk/ec2/ec2-down.sh, then this again." >&2; exit 1; }

# Security group
SG=$(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC Name=group-name,Values=$NAME --query 'SecurityGroups[0].GroupId' --output text)
if [ "$SG" = None ]; then
  echo "== creating security group $NAME"
  SG=$(aws ec2 create-security-group --group-name $NAME --description "TukTukPay Splunk Enterprise" --vpc-id $VPC \
        --tag-specifications "ResourceType=security-group,Tags=[$TAGS]" --query GroupId --output text)
fi
allow() {  # port, then --cidr x or --source-group y; "already exists" is fine
  local out
  out=$(aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port "$@" 2>&1) || grep -q Duplicate <<<"$out" || { echo "$out" >&2; exit 1; }
}
for p in 22 8000 8089 8088; do allow $p --cidr "$MYIP/32"; done
allow 8088 --source-group "$NODE_SG"     # pods on the EKS nodes -> HEC on the private IP
allow 8088 --cidr "$VPC_CIDR"            # anything else in the VPC (e.g. a future node group)
# Log Observer Connect: Observability Cloud realm us1 queries the management port from these IPs (docs/logs-setup.md 1.3, fact [M20])
for ip in 44.230.152.35 44.231.27.66 44.225.234.52 44.230.82.104; do allow 8089 --cidr "$ip/32"; done

# Instance
ID=$(aws ec2 describe-instances --filters Name=tag:Name,Values=$NAME Name=instance-state-name,Values=pending,running,stopping,stopped \
      --query 'Reservations[0].Instances[0].InstanceId' --output text)
if [ "$ID" = None ]; then
  AMI=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 --query Parameter.Value --output text)
  echo "== launching $TYPE ($AMI)"
  ID=$(aws ec2 run-instances --image-id $AMI --instance-type $TYPE --key-name $NAME --subnet-id $SUBNET --security-group-ids $SG \
        --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=100,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}' \
        --metadata-options HttpTokens=required,HttpEndpoint=enabled \
        --instance-initiated-shutdown-behavior terminate \
        --user-data "file://$DIR/user-data.sh" \
        --tag-specifications "ResourceType=instance,Tags=[$TAGS]" "ResourceType=volume,Tags=[$TAGS]" \
        --query 'Instances[0].InstanceId' --output text)
fi
aws ec2 start-instances --instance-ids $ID >/dev/null 2>&1 || true
aws ec2 wait instance-running --instance-ids $ID

# Elastic IP, so the address survives a stop/start
EIP=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[0].[AllocationId,PublicIp]' --output text)
if [ "$EIP" = "None	None" ] || [ "$EIP" = None ]; then
  aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[$TAGS]" >/dev/null
  EIP=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query 'Addresses[0].[AllocationId,PublicIp]' --output text)
fi
read -r ALLOC PUBIP <<<"$EIP"
aws ec2 associate-address --allocation-id $ALLOC --instance-id $ID --allow-reassociation >/dev/null
PRIVIP=$(aws ec2 describe-instances --instance-ids $ID --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)
echo "== instance $ID  public $PUBIP  private $PRIVIP"

SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME -o ConnectTimeout=10 ec2-user@$PUBIP"
echo "== waiting for SSH and for cloud-init to download Splunk (a few minutes on first launch)"
for i in $(seq 60); do $SSH true 2>/dev/null && break; sleep 10; done
$SSH 'sudo cloud-init status --wait >/dev/null; test -f /var/tmp/tuktukpay-splunk-unpacked' \
  || { echo "cloud-init did not finish cleanly: $SSH sudo tail -50 /var/log/cloud-init-output.log" >&2; exit 1; }

# Admin password: generated once, kept only in the git-ignored creds file
if [ ! -s "$CREDS" ]; then
  ( umask 077; printf 'admin\n%s\n' "$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)Aa1" > "$CREDS" )
fi
# Log Observer Connect service account o11y_connect: password on line 5
LOCPW=$(sed -n 5p "$CREDS"); [ -n "$LOCPW" ] || LOCPW="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)Aa1"
echo "== staging files and configuring Splunk"
$SSH 'rm -rf /tmp/stage && mkdir -m 700 /tmp/stage /tmp/stage/lookups'
sed -n 2p "$CREDS" | $SSH 'umask 077; cat > /tmp/stage/admin.pw'
printf '%s' "$LOCPW" | $SSH 'umask 077; cat > /tmp/stage/o11y_connect.pw'
scp -q -i "$KEY" -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME "$LICENSE" ec2-user@$PUBIP:/tmp/stage/license.lic
scp -q -i "$KEY" -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME "$DIR/setup-splunk.sh" ec2-user@$PUBIP:/tmp/stage/
scp -q -i "$KEY" -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME "$ROOT"/splunk/control-tower/lookups/*.csv ec2-user@$PUBIP:/tmp/stage/lookups/
[ -n "$APP_TGZ" ] && scp -q -i "$KEY" -o UserKnownHostsFile=$HOME/.ssh/known_hosts.$NAME "$APP_TGZ" ec2-user@$PUBIP:/tmp/stage/app.tgz \
  || echo "   no control-tower app in splunk/control-tower/dist (run build-app.sh); skipping the app"
$SSH 'sudo bash /tmp/stage/setup-splunk.sh'
HEC=$($SSH 'cat /tmp/stage/hec.token; rm -f /tmp/stage/hec.token')
( umask 077; { sed -n 1,2p "$CREDS"; echo "$HEC"; echo "https://$PUBIP:8000"; echo "$LOCPW"; } > "$CREDS.new" && mv "$CREDS.new" "$CREDS" )

cat <<EOF

Splunk Enterprise is up (self-signed certificates; accept the browser warning).
  Splunk Web       https://$PUBIP:8000   user admin, password: line 2 of splunk/ec2/ec2_creds.txt
  Control tower    https://$PUBIP:8000/en-US/app/tuktukpay_control_tower/control_tower
  REST (REpresentational State Transfer) API  https://$PUBIP:8089
  Log Observer Connect  https://$PUBIP:8089   user o11y_connect, password: line 5 of splunk/ec2/ec2_creds.txt
  HEC from pods    https://$PRIVIP:8088/services/collector   token: line 3 of splunk/ec2/ec2_creds.txt
  SSH              $SSH
  Scripts          TUKTUK_STACK=ec2 python3 -I splunk/control-tower/preview.py 8765   (stack.py against this host)
Terminates Fri 30 Oct 2026 22:00 (+07); earlier: splunk/ec2/ec2-down.sh
EOF
