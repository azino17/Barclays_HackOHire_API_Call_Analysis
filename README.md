# Barclays_HackOHire_API_Call_Analysis
🚀 Alert Manager
A MongoDB-based alert management system that detects anomalies in API calls and generates alerts based on severity, environment, and API name.

It supports:
✅ Automatic alert creation & updates
✅ Filtering by API name, severity, and environment
✅ Alert acknowledgment & resolution
✅ Pagination for large alert datasets

📌 Features
Create Alerts: Automatically logs API anomalies into the system.

Update Alerts: Merges similar alerts within a timeframe to avoid duplicates.

Retrieve Alerts: Fetch alerts with filters like status, severity, api_name, environment.

Acknowledge Alerts: Mark alerts as acknowledged to track them.

Resolve Alerts: Mark alerts as resolved when fixed.

Pagination: Retrieve large alert datasets efficiently using limit and offset

How It Detects Anomalies
1️⃣ Baseline Initialization
When the system starts, it initializes baselines for each API by calculating:

Average response time

Standard deviation of response times

Error rate

Call volume

Percentiles (p50, p90, p95, p99)

If an API has no prior data, a default baseline with zero values is created.

2️⃣ Detecting Response Time Anomalies
Each incoming API log is compared to the baseline.

The Z-score is calculated using:

Z = \frac{\text{response_time} - \text{avg_response_time}}{\text{response_time_std}}
If any of these conditions hold:

Response time is greater than the 99th percentile (p99).

Z-score > 3 (which means it's more than 3 standard deviations away from the mean).

🔹 Example:

Baseline:

Avg Response Time: 100 ms

Std Dev: 20 ms

p99: 200 ms

New API Log:

Response Time: 250 ms

Z-score: (250 - 100) / 20 = 7.5 (which is >3)
✅ Anomaly Detected!

3️⃣ Detecting Error Rate Anomalies
Every hour, it calculates the error rate from logs:

Error Rate
=
(
Number of Errors
Total Calls
)
×
100
Error Rate=( 
Total Calls
Number of Errors
​
 )×100
If error rate is more than twice the baseline error rate or exceeds 5%, it's flagged as an anomaly.

🔹 Example:

Baseline:

Error Rate: 2%

Last Hour:

Current Error Rate: 10%
✅ Anomaly Detected!

4️⃣ Severity Classification
Anomalies are categorized based on severity:

Condition	Severity
Z-score > 3 or Response Time > p99	High
Error Rate > 20%	Critical
Error Rate > 10%	High
Error Rate > 5%	Medium

🔧 Installation
1️⃣ Clone the repository
git clone https://github.com/your-username/alert-manager.git
cd alert-manager

2️⃣ Set up a virtual environment (optional but recommended)
bash
Copy
Edit
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate  # On Windows
3️⃣ Install dependencies
bash
Copy
Edit
pip install -r requirements.txt
4️⃣ Set up MongoDB
Ensure MongoDB is running locally or use a MongoDB Atlas database.
Update .env or config.py with your MongoDB URI.

bash
Copy
Edit
MONGO_URI=mongodb://localhost:27017/api_monitoring
🚀 Running the Application
1️⃣ Start the Flask server
bash
Copy
Edit
python app.py
2️⃣ Server will start at
bash
Copy
Edit
http://127.0.0.1:5000/
📌 API Endpoints
1️⃣ Create an Alert
Endpoint: POST /alerts

Description: Creates a new alert if no similar alert exists within the last hour. Otherwise, updates the existing alert.

Request Body (JSON):

json
Copy
Edit
{
  "api_name": "payment_service",
  "environment": "production",
  "type": "latency_spike",
  "severity": "high"
}
Response:

json
Copy
Edit
{
  "alert_id": "65f8a7e2d8b4321a45de4e3c",
  "message": "Alert created successfully"
}
2️⃣ Get Active Alerts
Endpoint: GET /alerts

Description: Fetch active alerts with optional filters.

Query Parameters:

status: "new", "acknowledged", or "resolved" (default: "new", "acknowledged")

severity: "low", "medium", "high", "critical"

api_name: Filter by API name

environment: Filter by environment

limit: Number of alerts per page (default: 50)

offset: Pagination offset (default: 0)

Example Request:

bash
Copy
Edit
GET /alerts?status=new&severity=high&api_name=payment_service&environment=production&limit=10&offset=0
Response:

json
Copy
Edit
[
  {
    "api_name": "payment_service",
    "environment": "production",
    "type": "latency_spike",
    "severity": "high",
    "status": "new",
    "timestamp": "2025-04-02T10:15:30.123Z",
    "count": 1
  }
]
3️⃣ Acknowledge an Alert
Endpoint: PATCH /alerts/{alert_id}/acknowledge

Description: Marks an alert as acknowledged.

Example Request:

bash
Copy
Edit
PATCH /alerts/65f8a7e2d8b4321a45de4e3c/acknowledge
Response:

json
Copy
Edit
{
  "message": "Alert acknowledged successfully"
}
4️⃣ Resolve an Alert
Endpoint: PATCH /alerts/{alert_id}/resolve

Description: Marks an alert as resolved.

Example Request:

bash
Copy
Edit
PATCH /alerts/65f8a7e2d8b4321a45de4e3c/resolve
Response:

json
Copy
Edit
{
  "message": "Alert resolved successfully"
}
🛠 Configuration (config.py)
Modify MongoDB settings and logging preferences in config.py:

python
Copy
Edit
MONGO_URI = "mongodb://localhost:27017/api_monitoring"
LOG_LEVEL = "INFO"
🧪 Running Tests
Unit tests are located in the tests/ directory.
Run tests using:

bash
Copy
Edit
pytest tests/
