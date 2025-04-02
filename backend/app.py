# app.py - Main application entry point
from flask import Flask, request, jsonify
from pymongo import MongoClient
import json
import logging
import datetime
import uuid
from bson import json_util

# Import custom modules
from data_processor import LogProcessor
from anomaly_detector import AnomalyDetector
from alert_manager import AlertManager
from predictor import Predictor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)

# MongoDB connection
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['api_monitoring']
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    exit(1)

# Initialize components
log_processor = LogProcessor(db)
anomaly_detector = AnomalyDetector(db)
alert_manager = AlertManager(db)
predictor = Predictor(db)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/ingest', methods=['POST'])
def ingest_logs():
    """Endpoint to ingest API logs"""
    try:
        log_data = request.json
        if not log_data:
            return jsonify({"error": "No data provided"}), 400
        
        # Process the log data
        processed_log = log_processor.process(log_data)
        
        # Check for anomalies
        anomalies = anomaly_detector.detect(processed_log)
        
        # Generate alerts if anomalies detected
        if anomalies:
            for anomaly in anomalies:
                alert_manager.create_alert(anomaly)
        
        # Run prediction for future failures
        predictor.predict_failures(processed_log)
        
        return jsonify({"status": "success", "message": "Log ingested successfully"}), 201
    
    except Exception as e:
        logger.error(f"Error ingesting logs: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/alerts', methods=['GET'])
def get_active_alerts():
    """Endpoint to retrieve alerts"""
    try:
        # Get query parameters
        status = request.args.get('status', None)
        severity = request.args.get('severity', None)
        api_name = request.args.get('api_name', None)
        environment = request.args.get('environment', None)
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Get alerts from the alert manager
        alerts = alert_manager.get_active_alerts(
            status=status, 
            severity=severity,
            api_name=api_name,
            environment=environment,
            limit=limit,
            offset=offset
        )
        
        # Convert MongoDB objects to JSON
        return json_util.dumps({"alerts": alerts, "total": len(alerts)}), 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        logger.error(f"Error retrieving alerts: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/alerts/<alert_id>', methods=['PUT'])
def update_alert(alert_id):
    """Endpoint to update an alert's status"""
    try:
        data = request.json
        if not data or 'status' not in data:
            return jsonify({"error": "Status not provided"}), 400
        
        result = alert_manager.update_alert(alert_id, data['status'])
        if result:
            return jsonify({"status": "success", "message": "Alert updated successfully"}), 200
        else:
            return jsonify({"error": "Alert not found"}), 404
    
    except Exception as e:
        logger.error(f"Error updating alert: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Endpoint to get system metrics"""
    try:
        api_name = request.args.get('api_name', None)
        environment = request.args.get('environment', None)
        start_time = request.args.get('start_time', None)
        end_time = request.args.get('end_time', None)
        
        # If start_time and end_time are strings, convert to datetime objects
        if start_time:
            start_time = datetime.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if end_time:
            end_time = datetime.datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        metrics = log_processor.get_metrics(
            api_name=api_name,
            environment=environment,
            start_time=start_time,
            end_time=end_time
        )
        
        return json_util.dumps(metrics), 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        logger.error(f"Error retrieving metrics: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/predictions', methods=['GET'])
def get_predictions():
    """Endpoint to get prediction data"""
    try:
        api_name = request.args.get('api_name', None)
        environment = request.args.get('environment', None)
        
        predictions = predictor.get_predictions(api_name, environment)
        
        return json_util.dumps({"predictions": predictions}), 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        logger.error(f"Error retrieving predictions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/apis', methods=['GET'])
def get_apis():
    """Endpoint to get list of monitored APIs"""
    try:
        apis = log_processor.get_registered_apis()
        return json_util.dumps({"apis": apis}), 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        logger.error(f"Error retrieving API list: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/environments', methods=['GET'])
def get_environments():
    """Endpoint to get list of monitored environments"""
    try:
        environments = log_processor.get_environments()
        return json_util.dumps({"environments": environments}), 200, {'Content-Type': 'application/json'}
    
    except Exception as e:
        logger.error(f"Error retrieving environments list: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)