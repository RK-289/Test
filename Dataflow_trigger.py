from datetime import datetime
from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.providers.google.cloud.operators.dataflow import DataflowTemplatedJobStartOperator
from airflow.providers.google.cloud.transfers.gcs_to_gcs import GCSToGCSOperator
from airflow.utils.trigger_rule import TriggerRule

RESOURCE_ORDER = ['observation', 'encounter', 'patient']
BUCKET = 'your-fhir-bucket'
PROJECT = 'your-gcp-project'
REGION = 'us-central1'
DATAFLOW_TEMPLATE_GCS_PATH = 'gs://your-bucket/path/to/classic-template.json'

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2023, 1, 1),
    'retries': 2,
    'retry_delay': 300  # 5 minutes
}

with DAG(
    'ordered_fhir_processing',
    default_args=default_args,
    schedule_interval=None,
    catchup=False
) as dag:

    start = DummyOperator(task_id='start')
    end = DummyOperator(task_id='end')

    previous_resource_task = start

    for resource in RESOURCE_ORDER:
        # 1. Move files from stage to process directory
        stage_to_process = GCSToGCSOperator(
            task_id=f'stage_to_process_{resource}',
            source_bucket=BUCKET,
            source_object=f'stage/{resource}/*',
            destination_bucket=BUCKET,
            destination_object=f'{resource}/process/',
            move_object=True,
            trigger_rule=TriggerRule.ALL_SUCCESS
        )

        # 2. Trigger Dataflow job using a classic template
        dataflow_job = DataflowTemplatedJobStartOperator(
            task_id=f'process_{resource}',
            template=DATAFLOW_TEMPLATE_GCS_PATH,
            parameters={
                'input': f'gs://{BUCKET}/{resource}/process/*',
                'resource_type': resource
            },
            project_id=PROJECT,
            location=REGION,
            wait_until_finished=True  # Ensures sequential execution
        )

        # Set up dependencies
        previous_resource_task >> stage_to_process >> dataflow_job
        previous_resource_task = dataflow_job

    previous_resource_task >> end
