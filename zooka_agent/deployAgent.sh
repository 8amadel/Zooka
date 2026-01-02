CONFIG_FILE="config.env"

# Ensure config.env exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.env file not found at $CONFIG_FILE"
    exit 1
fi

# Load Config variables for this script to use
export $(grep -v '^#' "$CONFIG_FILE" | xargs)

echo "Granting IAM roles"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$COMPUTE_SA" \
    --role="roles/aiplatform.user"

echo "enabling required APIs"
gcloud services enable \
  telemetry.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  cloudtrace.googleapis.com \
  clouderrorreporting.googleapis.com \
  cloudasset.googleapis.com \
  --project=$PROJECT_ID

echo "installing packages"
python3 -m pip install google-adk
python3 -m pip install toolbox-core

echo "setting toolbox URL and Gemini Model in agent definition"
export TOOLBOX_URL=$(gcloud run services describe toolbox --region us-central1 --format 'value(status.url)')
sed -i "s|PHTB|$TOOLBOX_URL|g" "$BASE_DIR/zooka/zooka_agent/agent.py"
sed -i "s|PHGM|$GEMINI_MODEL|g" "$BASE_DIR/zooka/zooka_agent/agent.py"

echo "setting PROJECT_ID and region in .env"
sed -i "s|PHPI|$PROJECT_ID|g" "$BASE_DIR/zooka/zooka_agent/.env"
sed -i "s|PHRI|$REGION_ID|g" "$BASE_DIR/zooka/zooka_agent/.env"

(
    cd "${BASE_DIR}/zooka"
    echo "Enhancing project for deployment"
    uvx agent-starter-pack enhance --adk -d agent_engine -n zooka -dir zooka_agent --cicd-runner google_cloud_build --region $REGION_ID -y
    uv add toolbox_core
    echo "Deploying agent to Vertex AI Agent Engine"
    make backend
)
