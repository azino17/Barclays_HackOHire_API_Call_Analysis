# data_processor.py - Module for processing and normalizing log data
import logging
import datetime
import re
import json
from pymongo import MongoClient, ASCENDING, DESCENDING
import uuid

logger = logging.getLogger(__name__)

class LogProcessor:
    def __init__(self, db):
        """Initialize the LogProcessor with a MongoDB connection"""
        self.db = db
        self.logs_collection = db['api_logs']
        self.apis_collection = db['apis']
        
        # Create indexes for better query performance
        self.logs_collection.create_index([("timestamp", DESCENDING)])
        self.logs_collection.create_index([("api_name", ASCENDING)])
        self.logs_collection.create_index([("environment", ASCENDING)])
        self.logs_collection.create_index([("request_id", ASCENDING)])
        
    def process(self, log_data):
        """Process and normalize log data from various formats"""
        try:
            # Ensure we have a timestamp
            if 'timestamp' not in log_data:
                log_data['timestamp'] = datetime.datetime.now().isoformat()
            else:
                # Convert string timestamp to datetime if needed
                if isinstance(log_data['timestamp'], str):
                    log_data['timestamp'] = datetime.datetime.fromisoformat(log_data['timestamp'].replace('Z', '+00:00'))
            
            # Ensure required fields exist
            required_fields = ['api_name', 'environment', 'response_time', 'status_code']
            for field in required_fields:
                if field not in log_data:
                    if field == 'status_code':
                        log_data[field] = 500  # Default to error
                    elif field == 'response_time':
                        log_data[field] = 0  # Default response time
                    elif field == 'environment':
                        log_data[field] = 'unknown'  # Default environment
                    elif field == 'api_name':
                        log_data[field] = 'unknown_api'  # Default API name
            
            # Add error flag based on status code
            log_data['is_error'] = log_data['status_code'] >= 400
            
            # Generate or ensure request_id for journey tracking
            if 'request_id' not in log_data:
                log_data['request_id'] = str(uuid.uuid4())
            
            # Add processed timestamp
            log_data['processed_at'] = datetime.datetime.now()
            
            # Save to MongoDB
            self.logs_collection.insert_one(log_data)
            
            # Register API if it's new
            self._register_api(log_data['api_name'], log_data['environment'])
            
            return log_data
            
        except Exception as e:
            logger.error(f"Error processing log data: {str(e)}")
            raise
    
    def _register_api(self, api_name, environment):
        """Register an API in the system if it doesn't exist"""
        try:
            # Check if the API exists
            existing_api = self.apis_collection.find_one({
                'api_name': api_name,
                'environment': environment
            })
            
            if not existing_api:
                # Register new API
                api_data = {
                    'api_name': api_name,
                    'environment': environment,
                    'registered_at': datetime.datetime.now(),
                    'last_seen': datetime.datetime.now(),
                    'call_count': 1,
                    'error_count': 0,
                    'avg_response_time': 0
                }
                self.apis_collection.insert_one(api_data)
                logger.info(f"Registered new API: {api_name} in environment: {environment}")
            else:
                # Update last seen timestamp and call count
                self.apis_collection.update_one(
                    {'_id': existing_api['_id']},
                    {'$set': {'last_seen': datetime.datetime.now()},
                     '$inc': {'call_count': 1}}
                )
        
        except Exception as e:
            logger.error(f"Error registering API: {str(e)}")
    
    def get_metrics(self, api_name=None, environment=None, start_time=None, end_time=None):
        """Get API metrics based on query parameters"""
        try:
            # Build query
            query = {}
            if api_name:
                query['api_name'] = api_name
            if environment:
                query['environment'] = environment
            if start_time or end_time:
                query['timestamp'] = {}
                if start_time:
                    query['timestamp']['$gte'] = start_time
                if end_time:
                    query['timestamp']['$lte'] = end_time
            
            # Get logs that match the query
            logs = list(self.logs_collection.find(query).sort("timestamp", DESCENDING).limit(1000))
            
            if not logs:
                return {
                    "total_calls": 0,
                    "error_rate": 0,
                    "avg_response_time": 0,
                    "percentiles": {}
                }
            
            # Calculate metrics
            total_calls = len(logs)
            error_count = sum(1 for log in logs if log.get('is_error', False))
            response_times = [log.get('response_time', 0) for log in logs]
            
            # Sort response times for percentile calculation
            response_times.sort()
            
            metrics = {
                "total_calls": total_calls,
                "error_rate": (error_count / total_calls) * 100 if total_calls > 0 else 0,
                "avg_response_time": sum(response_times) / total_calls if total_calls > 0 else 0,
                "percentiles": {
                    "p50": response_times[int(total_calls * 0.5)] if total_calls > 0 else 0,
                    "p90": response_times[int(total_calls * 0.9)] if total_calls > 0 else 0,
                    "p95": response_times[int(total_calls * 0.95)] if total_calls > 0 else 0,
                    "p99": response_times[int(total_calls * 0.99)] if total_calls > 0 else 0
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}")
            raise
    
    def get_registered_apis(self):
        """Get list of all registered APIs"""
        try:
            apis = list(self.apis_collection.find())
            return apis
        except Exception as e:
            logger.error(f"Error getting registered APIs: {str(e)}")
            raise
    
    def get_environments(self):
        """Get list of all monitored environments"""
        try:
            environments = self.apis_collection.distinct("environment")
            return environments
        except Exception as e:
            logger.error(f"Error getting environments: {str(e)}")
            raise