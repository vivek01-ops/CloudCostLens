# CloudCostLens — AWS Permissions

CloudCostLens separates **discovery** (read-only) from **execution** (mutation) identities.
The MVP supports **EC2 stop/start only**; **`ec2:TerminateInstances` is intentionally
absent from every policy and from the application allowlist**.

## 1. Connection models

### Local development
Uses the standard AWS credential chain (environment variables or a named profile) in the
user's shell. No customer keys are ever entered into the application.

### Customer accounts (recommended)
Cross-account IAM role assumption:

- Customer creates a role in their account with a trust policy allowing the CloudCostLens
  platform account (or user) and requiring a **unique external ID**.
- CloudCostLens stores the customer's `role_arn` and an **encrypted** external ID, then
  calls `sts:AssumeRole` to obtain temporary credentials (1 hour, auto-refreshed).
- No long-lived customer access keys are stored anywhere.

Example trust policy (discovery role):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::<PLATFORM_ACCOUNT_ID>:root" },
    "Action": "sts:AssumeRole",
    "Condition": { "StringEquals": { "sts:ExternalId": "<UNIQUE_EXTERNAL_ID>" } }
  }]
}
```

## 2. Discovery role policy (read-only)

Attached to the role assumed by the discovery/scan workers.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IdentityAndRegion",
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    },
    {
      "Sid": "ComputeDescribe",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeRegions",
        "ec2:DescribeAvailabilityZones",
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeSnapshots",
        "ec2:DescribeAddresses",
        "ec2:DescribeTags",
        "ec2:DescribeNetworkInterfaces"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DatabaseDescribe",
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "rds:DescribeDBClusters",
        "rds:ListTagsForResource"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LoadBalancerDescribe",
      "Effect": "Allow",
      "Action": [
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTags",
        "elasticloadbalancing:DescribeTargetGroups"
      ],
      "Resource": "*"
    },
    {
      "Sid": "MetricsRead",
      "Effect": "Allow",
      "Action": ["cloudwatch:GetMetricData", "cloudwatch:GetMetricStatistics", "cloudwatch:ListMetrics"],
      "Resource": "*"
    },
    {
      "Sid": "BillingRead",
      "Effect": "Allow",
      "Action": ["ce:GetCostAndUsage", "ce:GetCostForecast", "ce:GetDimensionValues", "ce:GetTags"],
      "Resource": "*"
    },
    {
      "Sid": "PriceListRead",
      "Effect": "Allow",
      "Action": ["pricing:GetProducts", "pricing:DescribeServices"],
      "Resource": "*"
    }
  ]
}
```

Notes:
- Cost Explorer and the Price List API are **global/account-level**; Cost Explorer must be
  enabled in the management (or linked) account, and the Price List API is queried in
  `us-east-1`.
- `DescribeSnapshots` may be restricted to `OwnerIds=self` via condition if desired.

## 3. Execution role policy (mutation, restricted)

Separate role, separate credentials, used **only** by the executor worker after an approval
has been validated. It can start/stop only and is further scoped by tags.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StartStopOnly",
      "Effect": "Allow",
      "Action": ["ec2:StopInstances", "ec2:StartInstances"],
      "Resource": "arn:aws:ec2:*:*:instance/*",
      "Condition": {
        "StringEquals": { "ec2:ResourceTag/cloudcostlens:manageable": "true" }
      }
    },
    {
      "Sid": "VerifyState",
      "Effect": "Allow",
      "Action": ["ec2:DescribeInstances"],
      "Resource": "*"
    }
  ]
}
```

There is **no** `ec2:TerminateInstances`, no `ec2:ModifyInstanceAttribute`, and no wildcard
`ec2:*` anywhere. The executor validates the exact ARN/region/action/params against the
stored approval payload before calling AWS, and verifies the resulting instance state with
`DescribeInstances` afterward.

## 4. Permissions matrix (per capability)

| Capability | Identity | Key actions |
|---|---|---|
| Verify connection | discovery | `sts:GetCallerIdentity` |
| Enumerate regions | discovery | `ec2:DescribeRegions` |
| Discover EC2/EBS/EIP | discovery | `ec2:Describe*` |
| Discover RDS | discovery | `rds:Describe*` |
| Discover ELB | discovery | `elasticloadbalancing:Describe*` |
| Utilization | discovery | `cloudwatch:GetMetricData` |
| Billing | discovery | `ce:GetCostAndUsage` |
| Pricing | discovery | `pricing:GetProducts` |
| Stop/start EC2 | execution | `ec2:StopInstances`, `ec2:StartInstances` |
| Verify action | execution | `ec2:DescribeInstances` |
| Terminate EC2 | — | **not granted** |

## 5. Handling rules

- Never log credentials, authorization headers, or external IDs.
- Classify throttling/retryable errors and apply bounded exponential backoff with jitter.
- Record `scan_runs` errors; never delete inventory because a scan failed.
- The execution identity is never used for discovery, and vice-versa.
