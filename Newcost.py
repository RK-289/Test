from google.cloud import monitoring_v3
import datetime
import smtplib
from email.mime.text import MIMEText

# Configuration
THRESHOLD = 100  # USD
PROJECT_ID = "your-project-id"
BUCKET_NAME = "your-bucket-name"  # <--- Added bucket name
EMAIL_SENDER = "alerts@example.com"
EMAIL_RECEIVER = "devops@example.com"

# Pricing Rates (same as before)
PRICING = {
    "storage": {
        "STANDARD": 0.02,
        "NEARLINE": 0.01,
        "COLDLINE": 0.004,
        "ARCHIVE": 0.0012,
    },
    "operations": {
        "CLASS_A": 0.05 / 10000,
        "CLASS_B": 0.004 / 10000,
    },
    "egress": 0.12
}

def get_storage_cost(client, bucket_name, interval):
    storage_metric = "storage.googleapis.com/storage/total_bytes"
    results = client.list_time_series(
        name=f"projects/{PROJECT_ID}",
        filter=(
            f'metric.type="{storage_metric}" '
            f'AND resource.labels.bucket_name="{bucket_name}"'  # <--- Bucket filter
        ),
        interval=interval,
        view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
    )

    storage_cost = 0.0
    for ts in results:
        storage_class = ts.metric.labels["storage_class"]
        bytes_used = float(ts.points[0].value.double_value)
        gb_used = bytes_used / (1024 ** 3)
        hourly_rate = PRICING["storage"][storage_class] / (30 * 24)
        storage_cost += gb_used * hourly_rate * 4
    return storage_cost

def get_operations_cost(client, bucket_name, interval):
    class_a_metric = "storage.googleapis.com/api/request_count"
    results = client.list_time_series(
        name=f"projects/{PROJECT_ID}",
        filter=(
            f'metric.type="{class_a_metric}" '
            f'AND metric.labels.method="storage.buckets.list" '
            f'AND resource.labels.bucket_name="{bucket_name}"'  # <--- Bucket filter
        ),
        interval=interval,
    )
    class_a_ops = sum(point.value.int64_value for ts in results for point in ts.points)

    class_b_metric = "storage.googleapis.com/api/request_count"
    results = client.list_time_series(
        name=f"projects/{PROJECT_ID}",
        filter=(
            f'metric.type="{class_b_metric}" '
            f'AND metric.labels.method="storage.objects.get" '
            f'AND resource.labels.bucket_name="{bucket_name}"'  # <--- Bucket filter
        ),
        interval=interval,
    )
    class_b_ops = sum(point.value.int64_value for ts in results for point in ts.points)

    return (class_a_ops * PRICING["operations"]["CLASS_A"]) + \
           (class_b_ops * PRICING["operations"]["CLASS_B"])

def get_egress_cost(client, bucket_name, interval):
    egress_metric = "storage.googleapis.com/network/sent_bytes_count"
    results = client.list_time_series(
        name=f"projects/{PROJECT_ID}",
        filter=(
            f'metric.type="{egress_metric}" '
            f'AND resource.labels.bucket_name="{bucket_name}"'  # <--- Bucket filter
        ),
        interval=interval,
    )
    bytes_sent = sum(point.value.int64_value for ts in results for point in ts.points)
    return (bytes_sent / (1024 ** 3)) * PRICING["egress"]

def send_alert(bucket_name, total_cost):
    msg = MIMEText(f"GCS bucket {bucket_name} cost alert: ${total_cost:.2f} (Threshold: ${THRESHOLD})")
    msg["Subject"] = f"Cost Alert for GCS Bucket {bucket_name}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    with smtplib.SMTP("smtp.example.com", 587) as server:
        server.starttls()
        server.login("user", "password")
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

def main():
    client = monitoring_v3.MetricServiceClient()
    now = datetime.datetime.utcnow()
    interval = monitoring_v3.TimeInterval({
        "end_time": {"seconds": int(now.timestamp())},
        "start_time": {"seconds": int((now - datetime.timedelta(hours=4)).timestamp())},
    })

    total_cost = 0.0
    total_cost += get_storage_cost(client, BUCKET_NAME, interval)
    total_cost += get_operations_cost(client, BUCKET_NAME, interval)
    total_cost += get_egress_cost(client, BUCKET_NAME, interval)

    if total_cost > THRESHOLD:
        send_alert(BUCKET_NAME, total_cost)

if __name__ == "__main__":
    main()
