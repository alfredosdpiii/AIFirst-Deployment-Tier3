# Tier 3: Google Cloud Run Deployment Guide

This guide covers deploying ShopSage to Google Cloud Run, a fully managed serverless platform.

## 🎯 Overview

Cloud Run provides:
- Automatic scaling (including scale to zero)
- Pay-per-use pricing
- Built-in HTTPS
- Global deployment
- Container-based serverless

## 📋 Prerequisites

- UV installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Google Cloud account with billing enabled
- Google Cloud SDK (gcloud) installed
- Docker installed (optional, for local testing)
- API keys (Tavily, OpenAI/Anthropic)

## 🔧 Initial Setup

### 1. Install Google Cloud SDK

```bash
# macOS
brew install google-cloud-sdk

# Ubuntu/Debian
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update && sudo apt-get install google-cloud-sdk

# Windows
# Download installer from https://cloud.google.com/sdk/docs/install
```

### 2. Authenticate and Set Project

```bash
# Login to Google Cloud
gcloud auth login

# List your projects
gcloud projects list

# Set your project
export PROJECT_ID=aifirst-tier3
gcloud config set project $PROJECT_ID

# Set default region
export REGION=asia-southeast1
gcloud config set run/region $REGION

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com
```

## 🚀 Deployment Methods

### Method 1: Direct Source Deployment (Recommended for Teaching)

This method uses Cloud Build automatically:

```bash
# Navigate to Cloud Run directory
cd shopsage/tier3-gcp-cloud-run

# No need to copy core module - it's already in the directory

# Deploy directly from source
gcloud run deploy shopsage \
  --source . \
  --region=$REGION \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID"

# Follow the prompts:
# - Confirm source location
# - Allow Cloud Build API enablement
# - Wait for build and deployment
```

### Method 2: Build and Deploy Separately

```bash
# Configure Docker for Google Container Registry
gcloud auth configure-docker

# Build the container image
gcloud builds submit --tag gcr.io/$PROJECT_ID/shopsage:latest

# Deploy the image to Cloud Run
gcloud run deploy shopsage \
  --image gcr.io/$PROJECT_ID/shopsage:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60 \
  --concurrency=80 \
  --max-instances=10 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID"
```

## 🔐 Managing Secrets

### 1. Create Secrets in Secret Manager

```bash
# Create secrets for API keys
echo -n "your-tavily-api-key" | gcloud secrets create TAVILY_API_KEY --data-file=-
echo -n "your-openai-api-key" | gcloud secrets create OPENAI_API_KEY --data-file=-

# List secrets
gcloud secrets list

# View secret value (for verification)
gcloud secrets versions access latest --secret=TAVILY_API_KEY
```

### 2. Grant Cloud Run Access to Secrets

```bash
# Get the Cloud Run service account
export SERVICE_ACCOUNT=$(gcloud run services describe shopsage \
  --region=$REGION \
  --format="value(spec.template.spec.serviceAccountName)")

# Grant access to secrets
gcloud secrets add-iam-policy-binding TAVILY_API_KEY \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

## 📊 Testing the Deployment

### 1. Get Service URL

```bash
# Get the service URL
export SERVICE_URL=$(gcloud run services describe shopsage \
  --region=$REGION \
  --format="value(status.url)")

echo "Service URL: $SERVICE_URL"
```

### 2. Test Endpoints

```bash
# Health check
curl $SERVICE_URL/health

# API documentation
echo "API Docs: $SERVICE_URL/docs"

# Test recommendation endpoint
curl -X POST $SERVICE_URL/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "question": "best budget smartphone under $300"
  }'
```

## 🛠️ Advanced Configuration

### 1. Custom Domain

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service=shopsage \
  --domain=api.yourcompany.com \
  --region=$REGION

# Verify domain ownership and update DNS
gcloud run domain-mappings describe \
  --domain=api.yourcompany.com \
  --region=$REGION
```

### 2. Set Concurrency and Scaling

```bash
# Update service configuration
gcloud run services update shopsage \
  --region=$REGION \
  --min-instances=1 \
  --max-instances=100 \
  --concurrency=1000 \
  --cpu=2 \
  --memory=1Gi
```

### 3. Enable Cloud CDN

```bash
# Create backend service
gcloud compute backend-services create shopsage-backend \
  --global \
  --load-balancing-scheme=EXTERNAL \
  --protocol=HTTPS

# Add Cloud Run as backend
gcloud compute backend-services add-backend shopsage-backend \
  --global \
  --backend-bucket-name=shopsage-cdn
```

## 📈 Monitoring and Logging

### 1. View Logs

```bash
# Stream logs
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=shopsage" \
  --format="table(timestamp,jsonPayload.message)" \
  --limit=50

# Follow logs (tail -f equivalent)
gcloud alpha logging tail "resource.type=cloud_run_revision \
  AND resource.labels.service_name=shopsage"
```

### 2. View Metrics

```bash
# Open Cloud Console metrics
gcloud app browse --project=$PROJECT_ID \
  --service=shopsage \
  --version=$(gcloud run revisions list --service=shopsage --limit=1 --format="value(name)")

# Or use direct URL
echo "https://console.cloud.google.com/run/detail/$REGION/shopsage/metrics?project=$PROJECT_ID"
```

### 3. Set Up Alerts

```bash
# Create alert policy for high latency
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="ShopSage High Latency" \
  --condition="resource.type=\"cloud_run_revision\" 
    resource.labels.service_name=\"shopsage\"
    metric.type=\"run.googleapis.com/request_latencies\"
    threshold_value=1000"
```

## 🔍 Troubleshooting

### Common Issues and Solutions

1. **Build Fails**
```bash
# Check Cloud Build logs
gcloud builds list --limit=5
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")

# Common fix: Ensure Dockerfile paths are correct
```

2. **Service Won't Start**
```bash
# Check service logs
gcloud run services logs read shopsage --region=$REGION --limit=50

# Check service description
gcloud run services describe shopsage --region=$REGION
```

3. **Secret Access Errors**
```bash
# Verify secret exists
gcloud secrets list

# Check IAM permissions
gcloud secrets get-iam-policy TAVILY_API_KEY

# Re-grant permissions if needed
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

4. **Cold Start Issues**
```bash
# Set minimum instances to avoid cold starts
gcloud run services update shopsage \
  --region=$REGION \
  --min-instances=1
```

## 🎓 Teaching Notes

### Step-by-Step Workshop Flow

1. **Setup Phase** (15 mins)
   - Create GCP project
   - Enable billing
   - Install gcloud SDK
   - Authenticate

2. **First Deployment** (20 mins)
   - Deploy from source
   - Test endpoints
   - View logs

3. **Add Secrets** (15 mins)
   - Create secrets
   - Update service
   - Test with real APIs

4. **Monitoring** (10 mins)
   - View metrics
   - Check logs
   - Set up alerts

### Cost Optimization for Students

```bash
# Delete resources after class
gcloud run services delete shopsage --region=$REGION

# Delete secrets
gcloud secrets delete TAVILY_API_KEY
gcloud secrets delete OPENAI_API_KEY

# Remove container images
gcloud container images delete gcr.io/$PROJECT_ID/shopsage:latest
```

### Free Tier Limits
- 2 million requests per month
- 360,000 GB-seconds of memory
- 180,000 vCPU-seconds
- 1 GB egress

## 🚀 Production Best Practices

### 1. CI/CD Pipeline

Create `cloudbuild.yaml` for automatic deployments:
```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/shopsage:$COMMIT_SHA', '.']
  
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/shopsage:$COMMIT_SHA']
  
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'shopsage'
      - '--image=gcr.io/$PROJECT_ID/shopsage:$COMMIT_SHA'
      - '--region=asia-southeast1'
```

### 2. Multi-Region Deployment

```bash
# Deploy to multiple regions
for region in asia-southeast1 us-central1 europe-west1; do
  gcloud run deploy shopsage \
    --image gcr.io/$PROJECT_ID/shopsage:latest \
    --region=$region \
    --platform=managed \
    --allow-unauthenticated
done
```

### 3. Load Testing

```bash
# Install hey (HTTP load generator)
go install github.com/rakyll/hey@latest

# Run load test
hey -n 1000 -c 50 -m POST \
  -H "Content-Type: application/json" \
  -d '{"question":"test query","llm_provider":"openai"}' \
  $SERVICE_URL/recommend
```

## 🔗 Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Quickstart](https://cloud.google.com/run/docs/quickstarts)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Pricing Calculator](https://cloud.google.com/products/calculator)