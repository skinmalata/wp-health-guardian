#!/bin/bash
# ============================================================
# WordPress Health Guardian — Deploy to Google Cloud Run
# ============================================================
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. A GCP project with billing enabled
#   3. Firestore API enabled (for history storage)
#   4. Vertex AI API enabled (for Gemini via Vertex AI)
#   5. Required secrets in Secret Manager or pass as env vars
#
# Usage:
#   ./deploy/deploy.sh <project-id> [region]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:?Usage: $0 <project-id> [region]}"
REGION="${2:-us-central1}"
SERVICE_NAME="wordpress-health-guardian"

echo "=== Deploying $SERVICE_NAME to $REGION in project $PROJECT_ID ==="

# 1. Ensure required APIs are enabled
echo "[1/6] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    aiplatform.googleapis.com \
    secretmanager.googleapis.com \
    logging.googleapis.com \
    cloudscheduler.googleapis.com \
    --project="$PROJECT_ID"

# 2. Ensure Firestore is in Native mode (create default database if needed)
echo "[2/6] Checking Firestore..."
gcloud firestore databases create \
    --location="$REGION" \
    --project="$PROJECT_ID" 2>/dev/null || echo "  Firestore database already exists"

# 3. Ensure required secrets exist in Secret Manager
echo "[3/6] Ensuring secrets in Secret Manager..."

# Create scheduler secret if it doesn't exist
SCHEDULER_SECRET_VALUE=$(openssl rand -hex 16)
if ! gcloud secrets describe scheduler-check-secret --project="$PROJECT_ID" >/dev/null 2>&1; then
    printf '%s' "$SCHEDULER_SECRET_VALUE" | gcloud secrets create scheduler-check-secret \
        --replication-policy=automatic \
        --data-file=- \
        --project="$PROJECT_ID"
    echo "  Created scheduler-check-secret"
else
    SCHEDULER_SECRET_VALUE=$(gcloud secrets versions access latest \
        --secret=scheduler-check-secret --project="$PROJECT_ID")
    echo "  Using existing scheduler-check-secret"
fi

# Create DT secrets if they don't exist
for SECRET in dt-environment dt-platform-token; do
    if ! gcloud secrets describe "$SECRET" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo "  WARNING: Secret $SECRET does not exist. Create it with:"
        echo "    echo -n 'your-value' | gcloud secrets create $SECRET --data-file=- --project=$PROJECT_ID"
    fi
done

# Grant compute SA access to secrets
COMPUTE_SA="${PROJECT_ID}-compute@developer.gserviceaccount.com"
for SECRET in dt-environment dt-platform-token scheduler-check-secret; do
    if gcloud secrets describe "$SECRET" --project="$PROJECT_ID" >/dev/null 2>&1; then
        gcloud secrets add-iam-policy-binding "$SECRET" \
            --member="serviceAccount:$COMPUTE_SA" \
            --role="roles/secretmanager.secretAccessor" \
            --project="$PROJECT_ID" 2>/dev/null || true
    fi
done

# 4. Build and submit to Cloud Build
echo "[4/6] Building container image..."
gcloud builds submit \
    --config=deploy/cloudbuild.yaml \
    --project="$PROJECT_ID" \
    --substitutions=_REGION="$REGION"

# 5. Deploy to Cloud Run with secrets
echo "[5/6] Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --image="$REGION-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/app" \
    --region="$REGION" \
    --platform=managed \
    --allow-unauthenticated \
    --timeout=300 \
    --memory=1Gi \
    --cpu=1 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --set-env-vars="GOOGLE_CLOUD_LOCATION=$REGION" \
    --set-env-vars="FIRESTORE_COLLECTION=health-checks" \
    --set-secrets="SCHEDULED_CHECK_SECRET=scheduler-check-secret:latest" \
    --set-secrets="DT_ENVIRONMENT=dt-environment:latest" \
    --set-secrets="DT_PLATFORM_TOKEN=dt-platform-token:latest" \
    --project="$PROJECT_ID"

# 6. Set up Cloud Scheduler for periodic checks
echo "[6/6] Setting up Cloud Scheduler..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --format="value(status.url)")

echo "  Service URL: $SERVICE_URL"

# Create a weekly check for wordpress.org (customize as needed)
gcloud scheduler jobs create http "weekly-health-check-wordpress-org" \
    --schedule="0 8 * * 1" \
    --uri="$SERVICE_URL/api/scheduled-check?url=https://wordpress.org&secret=$SCHEDULER_SECRET_VALUE" \
    --http-method=GET \
    --location="$REGION" \
    --project="$PROJECT_ID" 2>/dev/null || gcloud scheduler jobs update http "weekly-health-check-wordpress-org" \
    --uri="$SERVICE_URL/api/scheduled-check?url=https://wordpress.org&secret=$SCHEDULER_SECRET_VALUE" \
    --http-method=GET \
    --location="$REGION" \
    --project="$PROJECT_ID"

echo ""
echo "=== Deployment complete! ==="
echo "Service URL: $SERVICE_URL"
echo ""
echo "To verify: curl $SERVICE_URL/api/health"
echo ""
echo "Scheduled check runs every Monday at 8:00 AM UTC for wordpress.org"
