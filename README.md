**Zooka: AI Cardiologist Assistant**
Zooka is a stateful, reasoning-capable AI medical agent designed to assist in cardiac health analysis. 
Built on the Google Agent Development Kit (ADK) and deployed on Vertex AI Reasoning Engine,
Zooka simulates a diagnostic workflow to identify potential heart diseases from symptoms,
recommend diagnostic procedures, verify findings against medical reportsand suggest treatment paths. 

**Overview**
Zooka goes beyond simple Q&A. It acts as an intelligent medical partner that follows a strict reasoning chain:
Symptom Analysis: Extracts detailed conditions from user descriptions.
Differential Diagnosis: Maps symptoms to potential cardiac diseases with confidence levels.
Diagnostic Verification: Suggests specific tests (ECG, Echo, etc.) to confirm hypotheses.
Report Interpretation: Analyzes user-provided diagnostic results to confirm or refute a disease using logic and external validation.
Treatment Suggestions: Provides standard treatment protocols for confirmed conditions.

**Tech Stack**
- Agent Framework: Google ADK (Agent Development Kit)
- Runtime: Google Vertex AI Reasoning Engine
- Model: Freely select your desired Gemini model
- Frontend: Lightweight Flask + Vanilla HTML/JS (Session-based streaming).
- MCP: MCP toolbox for databases
- Database: Cloud Spanner

**Tools:**

- GoogleSearchTool: For real-time verification of diagnostic criteria.
- MemoryTool: For long-term user context and history.
- Custom Toolbox: Specialized medical data retrieval through semantic search (vector search) and knowledge graphs. 

**Key Features**
- Stateful Sessions: Maintains context across long medical interviews using the Reasoning Engine's session management.
- Persistent Long-Term Memory: Leverages Vertex AI to archive user preferences and critical diagnostic history. It intelligently retrieves relevant context across disjointed sessions, ensuring continuity without repetitive questioning.
- Active Reasoning: Does not guess; uses a "Confirm/Refute" logic flow based on diagnostic evidence.
- Safe Failovers: Strictly enforces medical disclaimers and refers users to real doctors for final validation.
- Tool Usage: Dynamically invokes Google Search only when necessary (e.g., to verify if a specific test result rules out a disease).

**Installation & Setup**
Tested and verified to work on Google Cloud Platform (GCP) in region us-central1 using cloud shell to create and deploy the required resources

1- Clone the Repository

git clone https://github.com/8amadel/zooka.git

2- Set your environment variables in zooka/config.env

3- Authenticate

gcloud auth application-default login

Accept all actions by always answering with "y", follow the prompt by opening the provided link in a browswer, tick all the checkboxes and copy the code back to the terminal.

4- Make the scripts executable and run the single deployment command

cd zooka/

find . -type f -name "*.sh" -exec chmod u+x {} +

nohup ./fullDeploy.sh &

5- Monitor the nohup.out file, you might get some warnings that could be safely ignored. The file should show a similar output when the script's work is done

Service [your service] revision [your revision] has been deployed and is serving 100 percent of traffic.

Service URL: [Your URL]

6- Access the web interface at [Your URL]

**Authentication Desclaimer:**
- Cloud Credentials: The gcloud auth command provided in the installation steps is intended strictly for local development.
- App Identity: The application enforces a simple username / password authentication mechanism to demonstrate session isolation and user-scoped long term memory. A proper authentication and access control mechanism should be used in production.

🛡️ **Disclaimer**
Zooka is a research prototype and AI assistant. It is not a replacement for a professional doctor or cardiologist. It is designed to demonstrate the capabilities of Generative AI in medical reasoning workflow support. Always consult a certified medical professional for health concerns.

📄 **License**
Distributed under the MIT License. See LICENSE for more information.
