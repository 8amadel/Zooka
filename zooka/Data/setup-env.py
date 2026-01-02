import os
import uuid
import json
import time
import traceback
from google.cloud import spanner
from google.cloud.spanner_admin_instance_v1.types import spanner_instance_admin

# --- Configuration Loading ---
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION_ID = os.environ.get("REGION_ID")
INSTANCE_NAME = os.environ.get("SPANNER_INSTANCE_NAME")
DATABASE_NAME = os.environ.get("SPANNER_DATABASE_NAME")
BASE_DIR = os.environ.get("BASE_DIR")

JSON_FILE_NAME = f"{BASE_DIR}/zooka/Data/data.json"

def validate_env():
    try:
        if not all([PROJECT_ID, REGION_ID, INSTANCE_NAME, DATABASE_NAME]):
            raise ValueError("Missing required environment variables. Please source config.env first.")
        print("Environment validation passed.")
    except Exception as e:
        print(f"Error validating environment: {e}")
        traceback.print_exc()
        exit(1)

def create_instance(instance_id):
    """Creates a Cloud Spanner instance."""
    try:
        spanner_client = spanner.Client(project=PROJECT_ID)
        instance_admin_api = spanner_client.instance_admin_api

        config_name = f"{spanner_client.project_name}/instanceConfigs/regional-{REGION_ID}"
        
        print(f"Checking/Creating Instance: {instance_id} in {config_name}...")

        try:
            instance = instance_admin_api.get_instance(name=f"{spanner_client.project_name}/instances/{instance_id}")
            print(f"Instance {instance_id} already exists.")
            return
        except Exception:
            pass # Instance doesn't exist, proceed to create

        instance = spanner_instance_admin.Instance(
            config=config_name,
            display_name=instance_id,
            node_count=1,
            edition=spanner_instance_admin.Instance.Edition.ENTERPRISE,
        )

        operation = instance_admin_api.create_instance(
            parent=spanner_client.project_name,
            instance_id=instance_id,
            instance=instance
        )

        print("Waiting for instance creation to complete...")
        operation.result(timeout=240)
        print(f"Instance {instance_id} created successfully.")
    except Exception as e:
        print(f"Error in create_instance: {e}")
        traceback.print_exc()
        raise

def create_database(instance_id, database_id):
    """Creates a database, tables, and the ML Model within the instance."""
    try:
        spanner_client = spanner.Client(project=PROJECT_ID)
        instance = spanner_client.instance(instance_id)
        
        print(f"Creating Database: {database_id}...")
        
        # DDL Statements
        ddl_statements = [
            """CREATE TABLE disease (
                ID STRING(36) NOT NULL,
                Name STRING(MAX),
                Description STRING(MAX)
            ) PRIMARY KEY (ID)""",
            
            # Embedding column
            """CREATE TABLE symptom (
                ID STRING(36) NOT NULL,
                Name STRING(MAX),
                Details STRING(MAX),
                Embedding ARRAY<FLOAT32>
            ) PRIMARY KEY (ID)""",

            """CREATE TABLE diagnostic (
                ID STRING(36) NOT NULL,
                Name STRING(MAX),
                Purpose STRING(MAX)
            ) PRIMARY KEY (ID)""",

            """CREATE TABLE treatment (
                ID STRING(36) NOT NULL,
                Name STRING(MAX),
                Details STRING(MAX)
            ) PRIMARY KEY (ID)""",

            """CREATE TABLE indicate (
                DiseaseID STRING(36) NOT NULL,
                SymptomID STRING(36) NOT NULL,
                Confidence STRING(MAX),
                FOREIGN KEY (DiseaseID) REFERENCES disease (ID),
                FOREIGN KEY (SymptomID) REFERENCES symptom (ID)
            ) PRIMARY KEY (DiseaseID, SymptomID)""",

            """CREATE TABLE verify (
                DiseaseID STRING(36) NOT NULL,
                DiagnosticID STRING(36) NOT NULL,
                IsGoldStandard BOOL,
                FOREIGN KEY (DiseaseID) REFERENCES disease (ID),
                FOREIGN KEY (DiagnosticID) REFERENCES diagnostic (ID)
            ) PRIMARY KEY (DiseaseID, DiagnosticID)""",

            """CREATE TABLE cure (
                DiseaseID STRING(36) NOT NULL,
                TreatmentID STRING(36) NOT NULL,
                TreatmentType STRING(MAX),
                Confidence STRING(MAX),
                FOREIGN KEY (DiseaseID) REFERENCES disease (ID),
                FOREIGN KEY (TreatmentID) REFERENCES treatment (ID)
            ) PRIMARY KEY (DiseaseID, TreatmentID)""",

            """CREATE TABLE users (
                username STRING(128) NOT NULL,
                password_hash STRING(256) NOT NULL,
                ) PRIMARY KEY (username)""",
                
                f"""CREATE MODEL TextEmbeddingModel
                INPUT(content STRING(MAX))
                OUTPUT(
                    embeddings STRUCT<
                        values ARRAY<FLOAT32>,
                        statistics STRUCT<truncated BOOL, token_count FLOAT64>
                    >
                )
                REMOTE OPTIONS (
                    endpoint = '//aiplatform.googleapis.com/projects/{PROJECT_ID}/locations/{REGION_ID}/publishers/google/models/text-embedding-004'
                )"""
        ]
        database = instance.database(database_id, ddl_statements)
        operation = database.create()
        print("Waiting for database and table creation...")
        operation.result(timeout=240)
        print("Database created successfully.")
        return database
    except Exception as e:
        print(f"Error in create_database: {e}")
        traceback.print_exc()
        raise

def read_json_local():
    """Reads the JSON file from the local directory."""
    try:
        print(f"Reading {JSON_FILE_NAME} from local directory...")
        if not os.path.exists(JSON_FILE_NAME):
            raise FileNotFoundError(f"File {JSON_FILE_NAME} not found in current directory.")
        
        with open(JSON_FILE_NAME, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        traceback.print_exc()
        raise

def insert_data(database, data):
    """Parses JSON and inserts data into Spanner with deduplication."""
    try:
        print("Parsing data and preparing for insertion...")
        
        #symptom_lookup = {} 
        #diagnostic_lookup = {}
        #treatment_lookup = {}

        rows_disease = []
        rows_symptom = []
        rows_diagnostic = []
        rows_treatment = []
        
        rows_indicate = []
        rows_verify = []
        rows_cure = []

        for entry in data:
            disease_id = str(uuid.uuid4())
            rows_disease.append((
                disease_id, 
                entry.get('disease_name'), 
                entry.get('description')
            ))

            for sym in entry.get('symptoms', []):
                s_name = sym.get('symptom')
                #if s_name not in symptom_lookup:
                s_uuid = str(uuid.uuid4())
                #symptom_lookup[s_name] = s_uuid
                # Note: Embedding is None initially
                rows_symptom.append((s_uuid, s_name, sym.get('details'), None))
               # else:
                   # s_uuid = symptom_lookup[s_name]
                
                rows_indicate.append((
                    disease_id, 
                    s_uuid, 
                    sym.get('confidence_indicator')
                ))

            for diag in entry.get('diagnostic_procedures', []):
                d_name = diag.get('procedure')
                #if d_name not in diagnostic_lookup:
                d_uuid = str(uuid.uuid4())
                #diagnostic_lookup[d_name] = d_uuid
                rows_diagnostic.append((d_uuid, d_name, diag.get('purpose')))
                #else:
                 #   d_uuid = diagnostic_lookup[d_name]
                
                rows_verify.append((
                    disease_id, 
                    d_uuid, 
                    diag.get('is_gold_standard')
                ))

            for treat in entry.get('treatments_and_cures', []):
                t_name = treat.get('treatment')
                #if t_name not in treatment_lookup:
                t_uuid = str(uuid.uuid4())
                #treatment_lookup[t_name] = t_uuid
                rows_treatment.append((t_uuid, t_name, treat.get('details')))
                #else:
                #    t_uuid = treatment_lookup[t_name]
                
                rows_cure.append((
                    disease_id, 
                    t_uuid, 
                    treat.get('treatment_type'),
                    treat.get('confidence_efficacy')
                ))

        def insert_batch(txn):
            if rows_disease:
                txn.insert(table='disease', columns=('ID', 'Name', 'Description'), values=rows_disease)
            if rows_symptom:
                txn.insert(table='symptom', columns=('ID', 'Name', 'Details', 'Embedding'), values=rows_symptom)
            if rows_diagnostic:
                txn.insert(table='diagnostic', columns=('ID', 'Name', 'Purpose'), values=rows_diagnostic)
            if rows_treatment:
                txn.insert(table='treatment', columns=('ID', 'Name', 'Details'), values=rows_treatment)
            
            if rows_indicate:
                txn.insert(table='indicate', columns=('DiseaseID', 'SymptomID', 'Confidence'), values=rows_indicate)
            if rows_verify:
                txn.insert(table='verify', columns=('DiseaseID', 'DiagnosticID', 'IsGoldStandard'), values=rows_verify)
            if rows_cure:
                txn.insert(table='cure', columns=('DiseaseID', 'TreatmentID', 'TreatmentType', 'Confidence'), values=rows_cure)

        print("Writing data to Spanner...")
        database.run_in_transaction(insert_batch)
        print("Data insertion complete.")
    except Exception as e:
        print(f"Error in insert_data: {e}")
        traceback.print_exc()
        raise

def update_embeddings(database):
    """Uses the Spanner ML Model to generate and store embeddings."""
    try:
        print("Generating Embeddings using Database Model (TextEmbeddingModel)...")
        
        sql_query = """
            SELECT ID, embeddings.values 
            FROM ML.PREDICT(
                MODEL TextEmbeddingModel, 
                (SELECT ID, Name || ' ' || Details AS content FROM symptom)
            )
        """
        
        updates = []
        
        with database.snapshot() as snapshot:
            results = snapshot.execute_sql(sql_query)
            for row in results:
                updates.append((row[0], row[1]))
        
        if not updates:
            print("No symptoms found to embed.")
            return

        print(f"Fetched {len(updates)} embeddings. Updating table...")

        def write_embeddings(txn):
            txn.update(
                table='symptom',
                columns=['ID', 'Embedding'],
                values=updates
            )
            
        database.run_in_transaction(write_embeddings)
        print("Embeddings generated and updated successfully.")
        
    except Exception as e:
        print(f"\nError generating embeddings: {e}")
        print("NOTE: Ensure the Spanner Service Agent has 'Vertex AI User' role.")
        traceback.print_exc()

def create_spanner_graph(instance_id, database_id):
    """Creates the Spanner Graph (Knowledge Graph) schema."""
    try:
        print("Creating Spanner Graph Schema...")
        spanner_client = spanner.Client(project=PROJECT_ID)
        instance = spanner_client.instance(instance_id)
        database = instance.database(database_id)

        # Graph DDL
        # We define nodes for entities and edges for the relationship tables
        # connecting them.
        graph_ddl = ["""
            CREATE PROPERTY GRAPH HeartDiseaseGraph
            NODE TABLES (
                disease,
                symptom,
                diagnostic,
                treatment
            )
            EDGE TABLES (
                indicate
                    SOURCE KEY (SymptomID) REFERENCES symptom (ID)
                    DESTINATION KEY (DiseaseID) REFERENCES disease (ID)
                    LABEL Indicates,
                verify
                    SOURCE KEY (DiseaseID) REFERENCES disease (ID)
                    DESTINATION KEY (DiagnosticID) REFERENCES diagnostic (ID)
                    LABEL VerifiedBy,
                cure
                    SOURCE KEY (DiseaseID) REFERENCES disease (ID)
                    DESTINATION KEY (TreatmentID) REFERENCES treatment (ID)
                    LABEL CuredBy
            )
        """]

        operation = database.update_ddl(graph_ddl)
        print("Waiting for Graph creation...")
        operation.result(timeout=240)
        print("Spanner Graph 'HeartDiseaseGraph' created successfully.")

    except Exception as e:
        print(f"Error creating Spanner Graph: {e}")
        traceback.print_exc()

def main():
    try:
        validate_env()
        create_instance(INSTANCE_NAME)
        database = create_database(INSTANCE_NAME, DATABASE_NAME)
        json_data = read_json_local()
        insert_data(database, json_data)
        update_embeddings(database)
        create_spanner_graph(INSTANCE_NAME, DATABASE_NAME)
    except Exception as e:
        print("Script failed due to an unhandled exception.")

if __name__ == "__main__":
    main()