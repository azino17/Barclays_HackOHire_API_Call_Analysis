import logging
import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self, db):
        """Initialize the AlertManager with a MongoDB connection"""
        self.db = db
        self.alerts_collection = db['alerts']
        
        # Create indexes for optimized queries
        self.alerts_collection.create_index([("timestamp", DESCENDING)])
        self.alerts_collection.create_index([("api_name", ASCENDING)])
        self.alerts_collection.create_index([("environment", ASCENDING)])
        self.alerts_collection.create_index([("severity", ASCENDING)])
        self.alerts_collection.create_index([("status", ASCENDING)])

    def _severity_rank(self, severity):
        """Helper function to rank severity levels"""
        severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return severity_levels.get(severity, 1)  # Default to low if not found

    def create_alert(self, anomaly):
        """Create an alert from an anomaly"""
        try:
            existing_alert = self.alerts_collection.find_one({
                'api_name': anomaly.get('api_name'),
                'environment': anomaly.get('environment'),
                'type': anomaly.get('type'),
                'status': {'$in': ['new', 'acknowledged']},
                'timestamp': {'$gte': datetime.datetime.utcnow() - datetime.timedelta(hours=1)}
            })

            if existing_alert:
                self.alerts_collection.update_one(
                    {'_id': existing_alert['_id']},
                    {
                        '$set': {
                            'updated_at': datetime.datetime.utcnow(),
                            'severity': max(existing_alert['severity'], anomaly.get('severity', 'low'), 
                                           key=self._severity_rank),
                        },
                        '$inc': {'count': 1}  # Increment occurrence count
                    }
                )
                logger.info(f"Updated existing alert: {existing_alert['_id']}")
                return str(existing_alert['_id'])

            new_alert = {
                '_id': ObjectId(),
                'api_name': anomaly.get('api_name'),
                'environment': anomaly.get('environment'),
                'type': anomaly.get('type'),
                'severity': anomaly.get('severity', 'low'),
                'status': 'new',
                'timestamp': datetime.datetime.utcnow(),
                'updated_at': datetime.datetime.utcnow(),
                'count': 1
            }
            self.alerts_collection.insert_one(new_alert)
            logger.info(f"Created new alert: {new_alert['_id']}")
            return str(new_alert['_id'])

        except Exception as e:
            logger.exception("Error creating alert", exc_info=True)
            return None

    def acknowledge_alert(self, alert_id):
        """Acknowledge an alert"""
        try:
            result = self.alerts_collection.update_one(
                {'_id': ObjectId(alert_id)},  
                {'$set': {'status': 'acknowledged', 'updated_at': datetime.datetime.utcnow()}}
            )
            if result.modified_count:
                logger.info(f"Alert {alert_id} acknowledged")
                return True
            else:
                logger.warning(f"Alert {alert_id} not found or already acknowledged")
                return False
        except Exception as e:
            logger.exception("Error acknowledging alert", exc_info=True)
            return False

    def resolve_alert(self, alert_id):
        """Resolve an alert"""
        try:
            result = self.alerts_collection.update_one(
                {'_id': ObjectId(alert_id)},
                {'$set': {'status': 'resolved', 'updated_at': datetime.datetime.utcnow()}}
            )
            if result.modified_count:
                logger.info(f"Alert {alert_id} resolved")
                return True
            else:
                logger.warning(f"Alert {alert_id} not found or already resolved")
                return False
        except Exception as e:
            logger.exception("Error resolving alert", exc_info=True)
            return False

    def get_active_alerts(self, status=None, severity=None, api_name=None, environment=None, limit=50, offset=0):
        """Retrieve active alerts with optional filtering and pagination."""
        try:
            query = {}

            if status is None:
                query["status"] = {"$in": ["new", "acknowledged"]}
            else:
                query["status"] = status

            if severity:
                query["severity"] = severity
            if api_name:
                query["api_name"] = api_name
            if environment:
                query["environment"] = environment

            active_alerts = list(
                self.alerts_collection.find(query)
                .sort("timestamp", DESCENDING)
                .skip(offset)
                .limit(limit)
            )

            return active_alerts

        except Exception as e:
            logger.exception("Error retrieving active alerts", exc_info=True)
            return []

# Example Usage
if __name__ == "__main__":
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["api_monitoring"]

        alert_manager = AlertManager(db)

        # Create a test alert
        anomaly = {
            "api_name": "payment_service",
            "environment": "production",
            "type": "latency_spike",
            "severity": "high"
        }

        alert_id = alert_manager.create_alert(anomaly)
        print(f"Alert ID: {alert_id}")

        # Fetch alerts with different filters
        print("All Active Alerts:", alert_manager.get_active_alerts())
        print("High Severity Alerts:", alert_manager.get_active_alerts(severity="high"))
        print("Alerts for API 'payment_service':", alert_manager.get_active_alerts(api_name="payment_service"))
        print("Production Alerts:", alert_manager.get_active_alerts(environment="production"))
        print("Paginated Alerts (limit=2, offset=1):", alert_manager.get_active_alerts(limit=2, offset=1))

    except Exception as e:
        logger.exception("Error in main execution", exc_info=True)
