# Lowest-Cost AWS Setup

This is the cheapest practical AWS setup for this repo.

- Frontend: `S3 + CloudFront`
- Backend: one small `Lightsail` Linux instance
- Database: `PostgreSQL on the same Lightsail instance`
- Region: `us-east-1` (US East, N. Virginia)

This is the low-cost path because:

- Lightsail uses fixed monthly pricing and bundles disk and transfer
- S3 + CloudFront is usually the cheapest clean way to host a static Vite frontend
- running PostgreSQL on the same instance avoids the extra monthly cost of RDS

## Cheapest region

Use `us-east-1`.

Why:

- AWS Fargate public pricing is tied across `us-east-1`, `us-east-2`, and `us-west-2` for the Linux task rates this app would use, so there is no advantage there to moving away from `us-east-1`
- Lightsail pricing is presented as fixed plan pricing, and `us-east-1` is the safest low-cost default with the broadest AWS service support
- Lightsail object storage overage is also at the low end in `us-east-1`

If your users are mostly in Zimbabwe or southern Africa, `af-south-1` is closer, but it is not the cheapest.

## What to create in AWS

Create these resources in `us-east-1`:

1. One `Lightsail` Linux instance
2. One `Lightsail` static IP attached to that instance
3. One `S3` bucket for the frontend
4. One `ACM` certificate in `us-east-1` for the frontend domain
5. One `CloudFront` distribution in front of the S3 bucket
6. Optional `Route 53` DNS records for:
   - `pcmconnect.advent-events.info` -> CloudFront
   - `api.pcmconnect.advent-events.info` -> Lightsail static IP

## Recommended Lightsail plan

Choose one of these:

- Lowest workable option: `Linux/Unix $7/month` with `1 GB RAM`, `2 vCPUs`, `40 GB SSD`
- Safer option: `Linux/Unix $12/month` with `2 GB RAM`, `2 vCPUs`, `60 GB SSD`

For this app, the `$7` plan is the lowest-cost starting point. If you expect more than light traffic, or if you see memory pressure, move to the `$12` plan.

## DNS shape

Use two hostnames:

- `pcmconnect.advent-events.info` for the frontend
- `api.pcmconnect.advent-events.info` for the backend

That matters because:

- the frontend will be served over HTTPS from CloudFront
- the backend should also be served over HTTPS to avoid browser mixed-content problems

This repo includes:

- [docker-compose.low-cost.yml](/Users/kelvinchelenje/Desktop/Auxiliary/Church/pcm-system/deploy/aws/docker-compose.low-cost.yml)
- [Caddyfile](/Users/kelvinchelenje/Desktop/Auxiliary/Church/pcm-system/deploy/aws/Caddyfile)
- [lightsail.env.example](/Users/kelvinchelenje/Desktop/Auxiliary/Church/pcm-system/deploy/aws/lightsail.env.example)

The compose stack runs:

- `postgres`
- the FastAPI backend
- `Caddy` as the HTTPS reverse proxy

Caddy automatically handles TLS certificates for `api.pcmconnect.advent-events.info` once DNS points to the instance.

## Step-by-step

### 1. Create the S3 bucket for the frontend

In AWS Console:

1. Open `S3`
2. Create a bucket in `us-east-1`
3. Use a unique bucket name, for example `pcm-frontend-prod-yourname`
4. Keep `Block all public access` enabled
5. Create the bucket

### 2. Create the ACM certificate for the frontend domain

In AWS Console:

1. Open `Certificate Manager`
2. Switch to region `us-east-1`
3. Request a public certificate
4. Add the name `pcmconnect.advent-events.info`
5. Choose `DNS validation`
6. Create the certificate
7. Add the suggested DNS validation record in `GoDaddy DNS`
8. Wait until the certificate status becomes `Issued`

CloudFront custom domains need the certificate to exist in `us-east-1`.

### 3. Create the CloudFront distribution

In AWS Console:

1. Open `CloudFront`
2. Create a distribution
3. Choose the S3 bucket as the origin
4. Use `Origin access control (OAC)`
5. Add alternate domain name `pcmconnect.advent-events.info`
6. Select the ACM certificate you created in `us-east-1`
7. Set default root object to `index.html`
8. Add custom error responses:
   - `403` -> `/index.html` -> `200`
   - `404` -> `/index.html` -> `200`

Save:

- CloudFront distribution ID
- CloudFront domain name

### 4. Create the Lightsail instance

In AWS Console:

1. Open `Lightsail`
2. Create instance
3. Region: `US East (N. Virginia) / us-east-1`
4. Platform: `Linux/Unix`
5. Blueprint: `Ubuntu 22.04 LTS` or the current Ubuntu LTS
6. Instance plan:
   - cheapest usable start: `$7/month`
7. Name it something like `pcm-backend`
8. Create the instance

### 5. Attach a static IP to the Lightsail instance

In Lightsail:

1. Open `Networking`
2. Choose `Create static IP`
3. Attach it to `pcm-backend`

Save the static IP address. Your API DNS record will point here.

### 6. Open the right firewall ports in Lightsail

In the Lightsail instance networking settings:

1. Allow `22` for SSH
2. Allow `80` for HTTP
3. Allow `443` for HTTPS

Do not open `5432`. PostgreSQL should stay private on the same machine.

### 7. Point your backend domain to the Lightsail static IP

Create a DNS record with your DNS provider or Route 53:

- `A` record for `api.pcmconnect.advent-events.info` -> your Lightsail static IP

If you keep DNS in `GoDaddy`, create:

- type `A`
- name `api.pcmconnect`
- value `YOUR_LIGHTSAIL_STATIC_IP`


### 8. Point your frontend domain to CloudFront

Create a DNS record:

- `CNAME` or alias for `pcmconnect.advent-events.info` -> your CloudFront domain

If you keep DNS in `GoDaddy`, create:

- type `CNAME`
- name `pcmconnect`
- value `YOUR_DISTRIBUTION.cloudfront.net`



### 9. Build and upload the frontend

On your local machine:

1. Set the frontend API URL:

```bash
cd frontend
VITE_API_URL=https://api.pcmconnect.advent-events.info npm run build
```

2. Upload the `frontend/dist` files to the S3 bucket

If you use AWS CLI:

```bash
aws s3 sync dist s3://YOUR_BUCKET_NAME --delete
```

3. Invalidate CloudFront:

```bash
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```



### 10. SSH into the Lightsail instance

From your machine:

```bash
ssh ubuntu@YOUR_LIGHTSAIL_STATIC_IP
```

### 11. Install Docker, Compose, and Git on the Lightsail instance

On the instance:

```bash
sudo apt update
sudo apt install -y docker.io git curl
sudo usermod -aG docker $USER
```

Log out and back in so your user gets Docker access.

Then install the Docker Compose plugin:

```bash
mkdir -p "$HOME/.docker/cli-plugins"
curl -fSL "https://github.com/docker/compose/releases/download/v2.39.1/docker-compose-linux-x86_64" --output "$HOME/.docker/cli-plugins/docker-compose"
chmod +x "$HOME/.docker/cli-plugins/docker-compose"
docker compose version
```

### 12. Clone the repo on the Lightsail instance

On the instance:

```bash
git clone YOUR_GITHUB_REPO_URL
cd pcm-system
```

If this repo is private, configure GitHub access on the instance now. The automated backend deploy uses `git pull` over SSH, so the server must be able to fetch the repo without an interactive password prompt.

### 13. Create the runtime env file

On the instance:

```bash
cp deploy/aws/lightsail.env.example deploy/aws/lightsail.env
```

Edit `deploy/aws/lightsail.env` and set:

- `APP_DOMAIN=api.pcmconnect.advent-events.info`
- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `CORS_ORIGINS=https://pcmconnect.advent-events.info`

Generate a strong secret, for example:

```bash
openssl rand -hex 32
```

### 14. Start the backend stack

From the repo root on the instance:

```bash
docker compose \
  -f deploy/aws/docker-compose.low-cost.yml \
  --env-file deploy/aws/lightsail.env \
  up -d --build
```

This starts:

- Postgres
- the backend
- Caddy

### 15. Verify the backend

Check the containers:

```bash
docker compose -f deploy/aws/docker-compose.low-cost.yml --env-file deploy/aws/lightsail.env ps
```

Check logs:

```bash
docker compose -f deploy/aws/docker-compose.low-cost.yml --env-file deploy/aws/lightsail.env logs -f backend
```

Then open:

- `https://api.pcmconnect.advent-events.info/`
- `https://api.pcmconnect.advent-events.info/docs`

### 16. Add swap if you use the $7 instance

If you choose the `$7` plan, add swap immediately.

On the instance:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 17. Basic update flow later

When you push new code:

1. SSH to the instance
2. Pull latest code
3. Rebuild and restart the stack

```bash
cd ~/pcm-system
git pull
docker compose -f deploy/aws/docker-compose.low-cost.yml --env-file deploy/aws/lightsail.env up -d --build
```

For frontend updates:

```bash
cd frontend
VITE_API_URL=https://api.pcmconnect.advent-events.info npm run build
aws s3 sync dist s3://YOUR_BUCKET_NAME --delete
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```

## GitHub Actions deployment

The deploy workflow in [deploy-aws.yml](/Users/kelvinchelenje/Desktop/Auxiliary/Church/pcm-system/.github/workflows/deploy-aws.yml) now matches this low-cost setup:

- backend deploy: SSH to Lightsail, `git pull`, then `docker compose ... up -d --build`
- frontend deploy: build the Vite app, upload to `S3`, then invalidate `CloudFront`

Before you rely on the workflow, finish the manual setup through step 14 at least once.

### GitHub production variables

Set these in your GitHub `production` environment:

- `AWS_REGION=us-east-1`
- `AWS_FRONTEND_BUCKET=YOUR_BUCKET_NAME`
- `AWS_CLOUDFRONT_DISTRIBUTION_ID=YOUR_DISTRIBUTION_ID`
- `VITE_API_URL=https://api.pcmconnect.advent-events.info`
- `LIGHTSAIL_HOST=YOUR_LIGHTSAIL_STATIC_IP_OR_DNS_NAME`
- `LIGHTSAIL_USER=ubuntu`
- `LIGHTSAIL_APP_DIR=/home/ubuntu/pcm-system`
- optional `LIGHTSAIL_SSH_PORT=22`

### GitHub production secrets

Set these in the same GitHub `production` environment:

- `AWS_ROLE_TO_ASSUME`
  - used by the frontend deploy job for `S3` and `CloudFront`
- `LIGHTSAIL_SSH_PRIVATE_KEY`
  - use a dedicated SSH private key that can log in to the Lightsail instance

On every push to `main`, the backend job connects to the instance, checks out the pushed branch, pulls the latest code, and runs:

```bash
docker compose -f deploy/aws/docker-compose.low-cost.yml --env-file deploy/aws/lightsail.env up -d --build
```

## Expected monthly cost

Very rough baseline:

- Lightsail instance: `$7/month` or `$12/month`
- S3: usually very low for a small frontend
- CloudFront: usually low at small traffic
- Total for a small app: often much lower than `ECS + ALB + RDS`

The main savings come from avoiding:

- ECS/Fargate runtime costs
- ALB fixed monthly cost
- RDS fixed monthly cost

## When to upgrade from this setup

Move away from this setup when:

- you need highly available production infrastructure
- you want managed database backups and failover
- your traffic grows enough that one small VM becomes a bottleneck
- you need zero-downtime deploys

At that point, move to:

- backend on ECS or App Runner
- database on RDS

## Sources

- Amazon Lightsail pricing: https://aws.amazon.com/lightsail/pricing/
- AWS Fargate pricing: https://aws.amazon.com/fargate/pricing/
- Create and attach a Lightsail static IP: https://docs.aws.amazon.com/lightsail/latest/userguide/lightsail-create-static-ip.html
- Lightsail static IP behavior: https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-static-ip-addresses-in-amazon-lightsail.html
- Create Lightsail DNS zone: https://docs.aws.amazon.com/lightsail/latest/userguide/lightsail-how-to-create-dns-entry.html
- Point domain to Lightsail using Route 53: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-using-route-53-to-point-a-domain-to-an-instance.html
- S3 static hosting overview: https://docs.aws.amazon.com/AmazonS3/latest/dev/WebsiteHosting.html
- CloudFront origin settings: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html
- Restrict access to S3 origin with CloudFront OAC: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
