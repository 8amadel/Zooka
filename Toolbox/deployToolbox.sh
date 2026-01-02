CONFIG_FILE="config.env"

# Ensure config.env exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.env file not found at $CONFIG_FILE"
    exit 1
fi

# Load Config variables for this script to use
export $(grep -v '^#' "$CONFIG_FILE" | xargs)
export IMAGE="$REGION_ID-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest"

echo "enabling required APIs"
gcloud services enable run.googleapis.com \
                       cloudbuild.googleapis.com \
                       artifactregistry.googleapis.com \
                       iam.googleapis.com \
                       secretmanager.googleapis.com

echo "Creating service account and granting roles"
gcloud iam service-accounts create $TOOLBOX_SERVICE_ACCOUNT

echo "Holding for 1 minute to make sure the service account is created"
duration=60
interval=10
while [ $duration -gt 0 ]; do
    echo "$duration seconds remaining..."
    sleep $interval
    duration=$((duration - interval))
done

echo "Time's up!"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member serviceAccount:$TOOLBOX_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
    --role roles/secretmanager.secretAccessor
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member serviceAccount:$TOOLBOX_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com \
    --role roles/spanner.databaseUser

echo "Holding for 2 minutes to make sure the IAM policy is activated"
duration=120
interval=10
while [ $duration -gt 0 ]; do
    echo "$duration seconds remaining..."
    sleep $interval
    duration=$((duration - interval))
done

echo "Time's up!"

echo "setting variables in yaml file"
sed -i "s|PHPI|$PROJECT_ID|g" "$BASE_DIR/zooka/Toolbox/tools.yaml"
sed -i "s|PHSI|$SPANNER_INSTANCE_NAME|g" "$BASE_DIR/zooka/Toolbox/tools.yaml"
sed -i "s|PHSD|$SPANNER_DATABASE_NAME|g" "$BASE_DIR/zooka/Toolbox/tools.yaml"

echo "Uploading tools to secret manager"
gcloud secrets create tools --data-file=$BASE_DIR/zooka/Toolbox/tools.yaml

echo "Deploying toolbox"
gcloud run deploy toolbox \
    --image $IMAGE \
    --service-account $TOOLBOX_SERVICE_ACCOUNT \
    --region $REGION_ID \
    --set-secrets "/app/tools.yaml=tools:latest" \
    --args="--tools-file=/app/tools.yaml","--address=0.0.0.0","--port=8080" \
    --allow-unauthenticated \
    --no-invoker-iam-check




