from google.cloud import storage
from google.cloud import monitoring_v3
import datetime

# Replace with your Google Cloud Project ID
PROJECT_ID = "your-project-id"

# Define pricing for various resources
STORAGE_CLASS_PRICING = {
    "STANDARD": 0.026,  # Price per GB/month
    "NEARLINE": 0.01,   # Price per GB/month
    "COLDLINE": 0.004,  # Price per GB/month
    "ARCHIVE": 0.001,   # Price per GB/month
}

EGRESS_COST_PER_GB = 0.12  # Price per GB for data egress
CLASS_A_OPERATION_COST = 0.005  # Price per 1,000 Class A operations


def get_storage_usage(project_id, bucket_name):
    """
    Fetches the storage usage for a given bucket.

    Args:
        project_id: Google Cloud Project ID.
        bucket_name: Name of the bucket.

    Returns:
        A dictionary with storage usage (in GB) by storage class.
    """
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.get_bucket(bucket_name)

    # Placeholder for storage usage data
    storage_usage = {
        "STANDARD": 0,
        "NEARLINE": 0,
        "COLDLINE": 0,
        "ARCHIVE": 0,
    }

    # Iterate through blob metadata to calculate storage usage by class
    blobs = bucket.list_blobs()
    for blob in blobs:
        storage_class = blob.storage_class
        if storage_class in storage_usage:
            storage_usage[storage_class] += blob.size / (1024 ** 3)  # Convert bytes to GB

    return storage_usage


def get_monitoring_data(project_id, start_time, end_time, metrics):
    """
    Retrieves monitoring data for specified metrics.

    Args:
        project_id: Google Cloud Project ID.
        start_time: Start time for the query.
        end_time: End time for the query.
        metrics: List of metrics to query.

    Returns:
        A dictionary containing metric values.
    """
    client = monitoring_v3.MetricServiceClient()
    filter_ = " OR ".join([f'metric.type = "{metric}"' for metric in metrics])
    results = client.list_time_series(
        request={
            "name": f"projects/{project_id}",
            "filter": filter_,
            "interval": {"end_time": end_time, "start_time": start_time},
        }
    )

    data = {}
    for time_series in results:
        metric_type = time_series.metric.type
        for point in time_series.points:
            value = point.value.double_value
            data[metric_type] = value
    return data


def calculate_storage_cost(storage_usage):
    """
    Calculates storage cost based on usage.

    Args:
        storage_usage: Dictionary with storage usage by class (in GB).

    Returns:
        Total storage cost in dollars.
    """
    return sum(usage * STORAGE_CLASS_PRICING.get(storage_class, 0) 
               for storage_class, usage in storage_usage.items())


def calculate_data_transfer_cost(egress_bytes):
    """
    Calculates the data transfer cost based on egress bytes.

    Args:
        egress_bytes: Total egress bytes.

    Returns:
        Data transfer cost in dollars.
    """
    return (egress_bytes / (1024 ** 3)) * EGRESS_COST_PER_GB  # Convert bytes to GB


def calculate_operation_cost(operation_count):
    """
    Calculates the cost of Class A operations.

    Args:
        operation_count: Total number of operations.

    Returns:
        Class A operation cost in dollars.
    """
    return (operation_count / 1000) * CLASS_A_OPERATION_COST


def main():
    """
    Main function to calculate and display storage costs.
    """
    # Define the time interval for monitoring data
    end_time = datetime.datetime.now(tz=datetime.timezone.utc)
    start_time = end_time - datetime.timedelta(hours=24)

    # Specify bucket name
    BUCKET_NAME = "your-bucket-name"

    # Get storage usage data
    storage_usage = get_storage_usage(PROJECT_ID, BUCKET_NAME)

    # Fetch monitoring data
    metrics = [
        "storage.googleapis.com/bytes_written",
        "storage.googleapis.com/bytes_read",
        "storage.googleapis.com/request_count",
    ]
    monitoring_data = get_monitoring_data(PROJECT_ID, start_time, end_time, metrics)

    # Calculate individual costs
    storage_cost = calculate_storage_cost(storage_usage)
    egress_cost = calculate_data_transfer_cost(monitoring_data.get("storage.googleapis.com/bytes_written", 0))
    operation_cost = calculate_operation_cost(monitoring_data.get("storage.googleapis.com/request_count", 0))

    # Calculate total cost
    total_cost = storage_cost + egress_cost + operation_cost

    # Print the cost breakdown
    print(f"Storage Cost: ${storage_cost:.2f}")
    print(f"Egress Cost: ${egress_cost:.2f}")
    print(f"Operation Cost: ${operation_cost:.2f}")
    print(f"Total Cost: ${total_cost:.2f}")


if __name__ == "__main__":
    main()
