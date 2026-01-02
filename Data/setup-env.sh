CONFIG_FILE="config.env"
# Ensure config.env exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.env file not found at $CONFIG_FILE"
    exit 1
fi

# Load Config variables for this script to use
export $(grep -v '^#' "$CONFIG_FILE" | xargs)
# Get the Project Number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Construct the Default Compute Engine Service Account Email
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "enabling required APIs"
gcloud services enable \
    spanner.googleapis.com \
    aiplatform.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    compute.googleapis.com \
    --project=$PROJECT_ID

gcloud beta services identity create --service=spanner.googleapis.com --project=$PROJECT_ID
gcloud beta services identity create --service=compute.googleapis.com --project=$PROJECT_ID


echo "Holding for 1 minute to make sure the default service accounts are created"
duration=60
interval=10
while [ $duration -gt 0 ]; do
    echo "$duration seconds remaining..."
    sleep $interval
    duration=$((duration - interval))
done

echo "Time's up!"

echo "Granting roles to: $COMPUTE_SA"

# 1. Grant Spanner Admin (Required to create Instances and Databases)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$COMPUTE_SA" \
    --role="roles/spanner.admin"

# 2. Grant Vertex AI User (Required for using GenAI/Embeddings features)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$COMPUTE_SA" \
    --role="roles/aiplatform.user"
# Grant Vertex AI User to the Spanner Service Agent
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-spanner.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

echo "Holding for 2 minutes to make sure the IAM policy is activated"
duration=120
interval=10
while [ $duration -gt 0 ]; do
    echo "$duration seconds remaining..."
    sleep $interval
    duration=$((duration - interval))
done

echo "Time's up!"

python $BASE_DIR/zooka/Data/setup-env.py