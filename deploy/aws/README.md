# Managed AWS Setup

This is the higher-cost managed AWS path for this repo: `ECS Fargate + RDS + S3 + CloudFront`.

The current GitHub Actions deploy workflow in [deploy-aws.yml](/Users/kelvinchelenje/Desktop/Auxiliary/Church/pcm-system/.github/workflows/deploy-aws.yml) now follows the lower-cost Lightsail backend path described in [README-low-cost.md](/Users/kelvinchelenje/Desktop/Auxiliary/Church/pcm-system/deploy/aws/README-low-cost.md).

## What this guide deploys

- Frontend: Vite app assets in `S3` with optional `CloudFront`.
- Backend: FastAPI Docker image in `ECR` deployed to `ECS Fargate`.
- Database: PostgreSQL in `Amazon RDS`.

## Important before you start

1. This managed path expects these resources to already exist:
   - ECR repository
   - ECS cluster
   - ECS service
   - ECS task execution role
   - ECS task role
   - CloudWatch log group
   - S3 bucket
   - optional CloudFront distribution
2. The backend currently stores uploads in `/data/uploads` inside the container.
   - On ECS, that storage is ephemeral.
   - If uploads must survive deploys and task restarts, add EFS or move uploads to S3 before you rely on file uploads in production.
3. The deploy jobs use the GitHub `production` environment.
   - Your AWS OIDC trust policy should allow `repo:YOUR_ORG/YOUR_REPO:environment:production`.

## What you need to create in AWS

Create these once:

1. One ECR private repository for the backend image
2. One S3 bucket for the frontend files
3. One optional CloudFront distribution in front of that S3 bucket
4. One ECS cluster
5. One ECS service running on Fargate
6. One CloudWatch log group for the backend container logs
7. One ECS task execution IAM role
8. One ECS task IAM role
9. One IAM OIDC provider for GitHub Actions
10. One IAM role that GitHub Actions can assume
11. One Application Load Balancer for the backend
12. Security groups for ALB, ECS, and RDS
13. One PostgreSQL RDS instance
14. Optional Route 53 DNS records
15. Optional ACM certificates if you want custom HTTPS domains

## Suggested names

Use any names you want, but keep them consistent with the GitHub variables:

- Region: `YOUR_AWS_REGION`
- ECR repository: `pcm-backend`
- ECS cluster: `pcm-cluster`
- ECS service: `pcm-backend-service`
- ECS task family: `pcm-backend`
- ECS container name: `pcm-backend`
- CloudWatch log group: `/ecs/pcm-backend`
- S3 bucket: `pcm-frontend-prod-YOUR_ACCOUNT_ID`
- GitHub deploy role: `GitHubActionsPcmDeployRole`

## Step-by-step

### 1. Choose your region and public URLs

Write these down first:

- `AWS_REGION`
- frontend URL
  - simplest first deploy: use the CloudFront domain name
  - custom domain later: `https://app.example.com`
- backend URL
  - simplest first deploy: use the ALB DNS name
  - custom domain later: `https://api.example.com`

You will use the backend URL as `VITE_API_URL`.

### 2. Create the ECR repository

In AWS Console:

1. Open `Amazon ECR`
2. Choose `Create repository`
3. Choose `Private`
4. Set repository name to your backend image repo, for example `pcm-backend`
5. Create it

Save:

- repository name
- repository URI

This value becomes GitHub variable `AWS_ECR_REPOSITORY`.

### 3. Create the S3 bucket for the frontend

In AWS Console:

1. Open `Amazon S3`
2. Create a bucket
3. Use a globally unique bucket name
4. Keep `Block all public access` enabled if you will use CloudFront with OAC
5. Create the bucket

Save:

- bucket name

This becomes GitHub variable `AWS_FRONTEND_BUCKET`.

### 4. Create the CloudFront distribution for the frontend

This is optional, but recommended. It gives you CDN caching and a clean public URL.

In AWS Console:

1. Open `CloudFront`
2. Create a distribution
3. Origin domain: your S3 bucket
4. Origin access: use `Origin access control (OAC)`
5. Default root object: `index.html`
6. Viewer protocol policy: `Redirect HTTP to HTTPS`
7. Add custom error responses:
   - `403` -> `/index.html` -> response code `200`
   - `404` -> `/index.html` -> response code `200`

Save:

- distribution ID
- distribution domain name

Use the distribution domain as the frontend URL if you are not setting up a custom domain yet.

GitHub variable:

- `AWS_CLOUDFRONT_DISTRIBUTION_ID`

If you do not want CloudFront yet, you can leave `AWS_CLOUDFRONT_DISTRIBUTION_ID` empty and use the S3 website endpoint or bucket-hosting approach later. The workflow already handles an empty CloudFront ID.

### 5. Create the ECS task execution role

In AWS Console:

1. Open `IAM`
2. Create role
3. Trusted entity type: `AWS service`
4. Use case: `Elastic Container Service Task`
5. Attach the AWS managed policy `AmazonECSTaskExecutionRolePolicy`
6. Name it something like `ecsTaskExecutionRole`

Save the role ARN.

This becomes GitHub variable `AWS_ECS_EXECUTION_ROLE_ARN`.

### 6. Create the ECS task role

This is the role your backend container itself runs as.

In AWS Console:

1. Open `IAM`
2. Create role
3. Trusted entity type: `AWS service`
4. Use case: `Elastic Container Service Task`
5. Do not attach broad permissions unless the app actually needs them
6. Name it something like `pcmEcsTaskRole`

Save the role ARN.

This becomes GitHub variable `AWS_ECS_TASK_ROLE_ARN`.

### 7. Create the CloudWatch log group

In AWS Console:

1. Open `CloudWatch`
2. Go to `Log groups`
3. Create log group
4. Name it, for example, `/ecs/pcm-backend`

Save:

- log group name

This becomes GitHub variable `AWS_LOG_GROUP`.

### 8. Create the ECS cluster

In AWS Console:

1. Open `Amazon ECS`
2. Choose `Clusters`
3. Create cluster
4. Use an ECS Fargate-compatible cluster
5. Name it, for example, `pcm-cluster`

Save:

- cluster name

This becomes GitHub variable `AWS_ECS_CLUSTER`.

### 9. Create security groups

Create these security groups in the same VPC:

1. `pcm-alb-sg`
   - inbound `80` from `0.0.0.0/0`
   - inbound `443` from `0.0.0.0/0` if you will use HTTPS
   - outbound all
2. `pcm-ecs-sg`
   - inbound `8000` from `pcm-alb-sg`
   - outbound all
3. `pcm-rds-sg`
   - inbound `5432` from `pcm-ecs-sg`
   - outbound as needed

### 10. Create the Application Load Balancer

In AWS Console:

1. Open `EC2`
2. Go to `Load Balancers`
3. Create `Application Load Balancer`
4. Scheme: `internet-facing`
5. IP type: `ipv4`
6. Select at least two subnets
7. Attach `pcm-alb-sg`
8. Create a target group:
   - target type: `IP`
   - protocol: `HTTP`
   - port: `8000`
   - health check path: `/`
9. Attach that target group to the listener

Save:

- ALB DNS name
- target group ARN

You can use the ALB DNS name as your temporary backend URL.

### 11. Create the PostgreSQL RDS instance

In AWS Console:

1. Open `RDS`
2. Create database
3. Engine: `PostgreSQL`
4. Choose a small instance size that fits your budget
5. Set:
   - DB instance identifier
   - master username
   - master password
6. Put it in the same VPC as ECS
7. Attach `pcm-rds-sg`
8. Prefer `Public access = No` if your VPC layout supports it
9. Create the database

After it is ready, save:

- endpoint
- port
- database name
- username
- password

Build your GitHub secret `DATABASE_URL` like this:

```text
postgresql+psycopg2://USERNAME:PASSWORD@RDS_ENDPOINT:5432/DATABASE_NAME
```

### 12. Create the first ECS task definition

The GitHub workflow updates an existing ECS service. That means you need one initial task definition and one initial service before the first automated deploy.

Create the first task definition in ECS:

1. Launch type: `Fargate`
2. Task family: match your planned GitHub variable, for example `pcm-backend`
3. Task execution role: the role from step 5
4. Task role: the role from step 6
5. CPU and memory: start with `512` CPU and `1024` MiB memory
6. Add one container:
   - container name: `pcm-backend`
   - image: use a temporary image that can listen on port `8000`
   - container port: `8000`

The easiest placeholder container is:

- image: `public.ecr.aws/docker/library/python:3.11-slim`
- command: `python -m http.server 8000`

The container name and container port must match the GitHub workflow values later.

### 13. Create the first ECS service

Still in ECS:

1. Create service in your cluster
2. Launch type: `Fargate`
3. Service name: for example `pcm-backend-service`
4. Task definition family: `pcm-backend`
5. Desired tasks: `1`
6. Networking:
   - same VPC as the ALB
   - choose subnets
   - attach `pcm-ecs-sg`
7. Load balancing:
   - attach the ALB target group from step 10
   - container name: `pcm-backend`
   - container port: `8000`

Save:

- service name

This becomes GitHub variable `AWS_ECS_SERVICE`.

### 14. Create the IAM OIDC provider for GitHub Actions

In AWS Console:

1. Open `IAM`
2. Go to `Identity providers`
3. Add provider
4. Provider type: `OpenID Connect`
5. Provider URL: `https://token.actions.githubusercontent.com`
6. Audience: `sts.amazonaws.com`
7. Create

### 15. Create the GitHub Actions deploy role

Create one IAM role that GitHub Actions can assume.

Trusted entity:

- `Web identity`
- provider: `token.actions.githubusercontent.com`

Use a trust policy like this. Replace `YOUR_GITHUB_ORG` and `YOUR_GITHUB_REPO`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/YOUR_GITHUB_REPO:environment:production"
        }
      }
    }
  ]
}
```

Attach permissions that let this role:

- push images to ECR
- register ECS task definitions
- update ECS services
- pass the ECS execution role and ECS task role
- write to the frontend S3 bucket
- create CloudFront invalidations if you use CloudFront

Save:

- role ARN

This becomes GitHub secret `AWS_ROLE_TO_ASSUME`.

### 16. Create the GitHub `production` environment

In GitHub:

1. Open your repository
2. Go to `Settings`
3. Go to `Environments`
4. Create environment `production`
5. Add branch protection so only `main` can deploy to it

This matches the workflow that already exists in this repo.

### 17. Add GitHub Actions variables

In GitHub:

1. Open repository `Settings`
2. Open `Secrets and variables`
3. Open `Actions`
4. Add these repository variables

Required:

- `AWS_REGION`
- `AWS_ECR_REPOSITORY`
- `AWS_ECS_CLUSTER`
- `AWS_ECS_SERVICE`
- `AWS_ECS_TASK_FAMILY`
- `AWS_ECS_EXECUTION_ROLE_ARN`
- `AWS_ECS_TASK_ROLE_ARN`
- `AWS_LOG_GROUP`
- `AWS_FRONTEND_BUCKET`
- `VITE_API_URL`
- `CORS_ORIGINS`

Optional:

- `AWS_CLOUDFRONT_DISTRIBUTION_ID`
- `AWS_ECS_CONTAINER_NAME` default `pcm-backend`
- `AWS_APP_NAME` default `PCM System`
- `AWS_APP_PORT` default `8000`
- `AWS_ECS_CPU` default `512`
- `AWS_ECS_MEMORY` default `1024`
- `ACCESS_TOKEN_EXPIRE_MINUTES` default `30`
- `REFRESH_TOKEN_EXPIRE_DAYS` default `7`
- `UPLOAD_DIR` default `/data/uploads`
- `ALLOWED_UPLOAD_EXTENSIONS` default `csv,xlsx,jpg,jpeg,png,pdf,doc,docx`
- `MAX_UPLOAD_MB` default `10`

Recommended values:

- `AWS_ECS_TASK_FAMILY=pcm-backend`
- `AWS_ECS_CONTAINER_NAME=pcm-backend`
- `AWS_APP_PORT=8000`
- `VITE_API_URL=http://YOUR_ALB_DNS_NAME`
- `CORS_ORIGINS=https://YOUR_CLOUDFRONT_DOMAIN` or your real frontend domain

### 18. Add GitHub Actions secrets

Add these repository secrets:

- `AWS_ROLE_TO_ASSUME`
- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

Generate a strong random `SECRET_KEY`.

### 19. Run the first deploy

In GitHub:

1. Open `Actions`
2. Open `Deploy AWS`
3. Choose `Run workflow`

What should happen:

1. Backend image builds and pushes to ECR
2. ECS task definition is rendered from `deploy/aws/ecs-task-definition.json.template`
3. ECS service updates to the new task definition
4. Frontend builds and uploads to S3
5. CloudFront cache is invalidated if configured

### 20. Verify everything

Check these in order:

1. `GitHub Actions` deploy workflow is green
2. `ECR` contains a new image tag for the commit SHA
3. `ECS` service has a healthy running task
4. `CloudWatch Logs` shows backend startup logs
5. ALB URL returns the backend root response
6. Frontend URL loads
7. Frontend can call the backend without CORS errors

## Common values you will need

### `DATABASE_URL`

```text
postgresql+psycopg2://pcm_user:YOUR_PASSWORD@YOUR_RDS_ENDPOINT:5432/pcm_db
```

### `VITE_API_URL`

Fastest first deploy:

```text
http://YOUR_ALB_DNS_NAME
```

Custom API domain later:

```text
https://api.example.com
```

### `CORS_ORIGINS`

Single frontend URL:

```text
https://app.example.com
```

Multiple frontend URLs:

```text
https://app.example.com,https://www.example.com
```

## Optional custom domains

If you want custom domains:

1. Create or use a hosted zone in Route 53
2. Create an ACM certificate for the frontend domain
   - for CloudFront, the certificate must be in `us-east-1`
3. Add the alternate domain name to the CloudFront distribution
4. Create a Route 53 alias record pointing your frontend domain to CloudFront
5. For the backend, either:
   - keep using the ALB DNS name, or
   - create an ACM certificate and HTTPS listener on the ALB, then point `api.example.com` to the ALB

## Straight answer: fastest working setup

If you want the minimum path with the least decisions:

1. Create ECR
2. Create S3
3. Create CloudFront
4. Create ECS execution role
5. Create ECS task role
6. Create CloudWatch log group
7. Create ECS cluster
8. Create ALB, target group, and security groups
9. Create RDS PostgreSQL
10. Create one placeholder ECS task definition on port `8000`
11. Create one ECS service attached to the ALB
12. Create IAM OIDC provider
13. Create GitHub deploy role
14. Add GitHub variables and secrets
15. Run `Deploy AWS`

## Official references

- AWS IAM OIDC provider setup: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html
- AWS role for OIDC federation: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html
- GitHub OIDC with AWS: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- GitHub OIDC subject claim reference: https://docs.github.com/actions/reference/security/oidc
- Amazon ECR repository creation: https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html
- Amazon ECS Fargate getting started: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html
- Amazon ECS task execution role: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html
- RDS PostgreSQL creation: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.CreatingConnecting.PostgreSQL.html
- S3 static hosting: https://docs.aws.amazon.com/AmazonS3/latest/userguide/HostingWebsiteOnS3Setup.html
- CloudFront with S3 origin and OAC: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/GettingStarted.SimpleDistribution.html
- CloudFront custom error responses: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/custom-error-pages-procedure.html
- CloudFront custom domain setup: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/add-domain-existing-distribution.html
- Route 53 alias to CloudFront: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-to-cloudfront-distribution.html
