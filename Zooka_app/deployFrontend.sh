CONFIG_FILE="config.env"

# Ensure config.env exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.env file not found at $CONFIG_FILE"
    exit 1
fi

# Load Config variables for this script to use
export $(grep -v '^#' "$CONFIG_FILE" | xargs)

export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")


echo "Creating APP's service account"
gcloud iam service-accounts create $APP_SERVICE_ACCOUNT \
    --display-name="Zooka APP Service Account" \
    --project=$PROJECT_ID

echo "Holding for 1 minute to make sure the service account is created"
duration=60
interval=10
while [ $duration -gt 0 ]; do
    echo "$duration seconds remaining..."
    sleep $interval
    duration=$((duration - interval))
done

echo "Time's up!"

echo "Granting IAM roles to the service account"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member serviceAccount:$APP_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member serviceAccount:$APP_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member serviceAccount:$APP_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
    --role="roles/spanner.databaseUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/artifactregistry.admin"

echo "Holding for 2 minutes to make sure the IAM policy is activated"
duration=120
interval=10
while [ $duration -gt 0 ]; do
    echo "$duration seconds remaining..."
    sleep $interval
    duration=$((duration - interval))
done

echo "Time's up!"


echo "Constructing agent's query URL"
AGENT_RESOURCE=$(gcloud asset search-all-resources \
  --scope=projects/$PROJECT_ID \
  --asset-types='aiplatform.googleapis.com/ReasoningEngine' \
  --format="value(name)" | head -n 1)

AGENT_ID=$(basename "$AGENT_RESOURCE")
AGENT_URL="projects/$PROJECT_ID/locations/$REGION_ID/reasoningEngines/$AGENT_ID"
sed -i "s|PHAR|$AGENT_URL|g" "$CONFIG_FILE"

echo "Deploying APP to cloud run"
export GOOGLE_CLOUD_PROJECT=$PROJECT_ID

gcloud artifacts repositories create zooka-repo \
    --repository-format=docker \
    --location=$REGION_ID \
    --description="Docker repository"

gcloud builds submit \
    --tag $REGION_ID-docker.pkg.dev/$PROJECT_ID/zooka-repo/zooka-app \
    --project=$PROJECT_ID \
    --region=$REGION_ID $BASE_DIR/zooka/Zooka_app

gcloud run deploy $SERVICE_NAME \
  --image $REGION_ID-docker.pkg.dev/$PROJECT_ID/zooka-repo/zooka-app \
  --project $PROJECT_ID \
  --platform managed \
  --region $REGION_ID \
  --service-account $APP_SERVICE_ACCOUNT \
  --allow-unauthenticated \
  --no-invoker-iam-check \
  --set-env-vars PROJECT_ID=$PROJECT_ID,REGION_ID=$REGION_ID,SPANNER_INSTANCE_NAME=$SPANNER_INSTANCE_NAME,SPANNER_DATABASE_NAME=$SPANNER_DATABASE_NAME,AGENT_RESOURCE_ID=$AGENT_URL
