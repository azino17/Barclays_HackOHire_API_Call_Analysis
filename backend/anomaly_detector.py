# anomaly_detector.py - Module for detecting API anomalies
import logging
import datetime
import numpy as np
import statistics
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId

logger = logging.getLogger(__name__)

class AnomalyDetector:
    def __init__(self, db):
        """Initialize the AnomalyDetector with a MongoDB connection"""
        self.db = db
        self.logs_collection = db['api_logs']
        self.apis_collection = db['apis']
        self.anomalies_collection = db['anomalies']
        self.baselines_collection = db['baselines']
        
        # Create indexes
        self.anomalies_collection.create_index([("timestamp", DESCENDING)])
        self.anomalies_collection.create_index([("api_name", ASCENDING)])
        self.anomalies_collection.create_index([("environment", ASCENDING)])
        self.anomalies_collection.create_index([("type", ASCENDING)])
        
        # Initialize baselines if needed
        self._initialize_baselines()
    
    def _initialize_baselines(self):
        """Initialize baseline metrics for all APIs if they don't exist"""
        try:
            apis = list(self.apis_collection.find())
            
            for api in apis:
                # Check if baseline exists
                existing_baseline = self.baselines_collection.find_one({
                    'api_name': api['api_name'],
                    'environment': api['environment']
                })
                
                if not existing_baseline:
                    # Create initial baseline
                    self._create_initial_baseline(api['api_name'], api['environment'])
        
        except Exception as e:
            logger.error(f"Error initializing baselines: {str(e)}")
    
    def _create_initial_baseline(self, api_name, environment):
        """Create initial baseline for an API"""
        try:
            # Get recent logs for the API
            logs = list(self.logs_collection.find({
                'api_name': api_name,
                'environment': environment
            }).sort("timestamp", DESCENDING).limit(1000))
            
            if not logs:
                # No logs yet, create empty baseline
                baseline = {
                    'api_name': api_name,
                    'environment': environment,
                    'created_at': datetime.datetime.now(),
                    'updated_at': datetime.datetime.now(),
                    'avg_response_time': 0,
                    'response_time_std': 0,
                    'error_rate': 0,
                    'call_volume': 0,
                    'percentiles': {
                        'p50': 0,
                        'p90': 0,
                        'p95': 0,
                        'p99': 0
                    }
                }
            else:
                # Calculate baseline metrics
                response_times = [log.get('response_time', 0) for log in logs]
                error_count = sum(1 for log in logs if log.get('is_error', False))
                
                # Sort for percentile calculation
                response_times.sort()
                total = len(logs)
                
                baseline = {
                    'api_name': api_name,
                    'environment': environment,
                    'created_at': datetime.datetime.now(),
                    'updated_at': datetime.datetime.now(),
                    'avg_response_time': sum(response_times) / total if total > 0 else 0,
                    'response_time_std': statistics.stdev(response_times) if total > 1 else 0,
                    'error_rate': (error_count / total) * 100 if total > 0 else 0,
                    'call_volume': total,
                    'percentiles': {
                        'p50': response_times[int(total * 0.5)] if total > 0 else 0,
                        'p90': response_times[int(total * 0.9)] if total > 0 else 0,
                        'p95': response_times[int(total * 0.95)] if total > 0 else 0,
                        'p99': response_times[int(total * 0.99)] if total > 0 else 0
                    }
                }
            
            # Save baseline
            self.baselines_collection.insert_one(baseline)
            logger.info(f"Created initial baseline for API: {api_name} in environment: {environment}")
            
            return baseline
        
        except Exception as e:
            logger.error(f"Error creating initial baseline: {str(e)}")
            raise
    
    def _update_baseline(self, api_name, environment):
        """Update baseline for an API with recent data"""
        try:
            # Get recent logs for the API (last 24 hours)
            twenty_four_hours_ago = datetime.datetime.now() - datetime.timedelta(hours=24)
            
            logs = list(self.logs_collection.find({
                'api_name': api_name,
                'environment': environment,
                'timestamp': {'$gte': twenty_four_hours_ago}
            }))
            
            if not logs:
                # No recent logs, skip update
                return
            
            # Calculate new baseline metrics
            response_times = [log.get('response_time', 0) for log in logs]
            error_count = sum(1 for log in logs if log.get('is_error', False))
            
            # Sort for percentile calculation
            response_times.sort()
            total = len(logs)
            
            # Calculate stats
            avg_response_time = sum(response_times) / total if total > 0 else 0
            response_time_std = statistics.stdev(response_times) if total > 1 else 0
            error_rate = (error_count / total) * 100 if total > 0 else 0
            
            # Update baseline
            self.baselines_collection.update_one(
                {
                    'api_name': api_name,
                    'environment': environment
                },
                {
                    '$set': {
                        'updated_at': datetime.datetime.now(),
                        'avg_response_time': avg_response_time,
                        'response_time_std': response_time_std,
                        'error_rate': error_rate,
                        'call_volume': total,
                        'percentiles': {
                            'p50': response_times[int(total * 0.5)] if total > 0 else 0,
                            'p90': response_times[int(total * 0.9)] if total > 0 else 0,
                            'p95': response_times[int(total * 0.95)] if total > 0 else 0,
                            'p99': response_times[int(total * 0.99)] if total > 0 else 0
                        }
                    }
                },
                upsert=True
            )
            
            logger.info(f"Updated baseline for API: {api_name} in environment: {environment}")
        
        except Exception as e:
            logger.error(f"Error updating baseline: {str(e)}")
    
    def detect(self, log_data):
        """Detect anomalies in the provided log data"""
        try:
            anomalies = []
            
            # Get API info
            api_name = log_data.get('api_name')
            environment = log_data.get('environment')
            
            if not api_name or not environment:
                return anomalies
            
            # Get baseline for the API
            baseline = self.baselines_collection.find_one({
                'api_name': api_name,
                'environment': environment
            })
            
            if not baseline:
                # No baseline yet, create one
                baseline = self._create_initial_baseline(api_name, environment)
            
            # Check for response time anomaly
            response_time = log_data.get('response_time', 0)
            if response_time > 0:
                response_time_anomaly = self._detect_response_time_anomaly(
                    log_data, baseline
                )
                if response_time_anomaly:
                    anomalies.append(response_time_anomaly)
            
            # Check for error anomaly
            is_error = log_data.get('is_error', False)
            if is_error:
                error_anomaly = self._detect_error_anomaly(
                    log_data, baseline
                )
                if error_anomaly:
                    anomalies.append(error_anomaly)
            
            # Save anomalies to database if found
            for anomaly in anomalies:
                self.anomalies_collection.insert_one(anomaly)
            
            # Periodically update baseline (every 100 logs)
            count = self.logs_collection.count_documents({
                'api_name': api_name,
                'environment': environment
            })
            
            if count % 100 == 0:
                self._update_baseline(api_name, environment)
            
            return anomalies
        
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")
            return []
    
    def _detect_response_time_anomaly(self, log_data, baseline):
        """Detect response time anomalies"""
        try:
            response_time = log_data.get('response_time', 0)
            avg_response_time = baseline.get('avg_response_time', 0)
            std_dev = baseline.get('response_time_std', 0)
            percentile_99 = baseline.get('percentiles', {}).get('p99', 0)
            
            # Skip if we don't have enough baseline data
            if avg_response_time == 0 or std_dev == 0:
                return None
            
            # Calculate z-score
            if std_dev > 0:
                z_score = (response_time - avg_response_time) / std_dev
            else:
                z_score = 0
            
            # Check if response time exceeds p99 or is significantly higher than average
            if response_time > percentile_99 or z_score > 3.0:
                # Create anomaly record
                anomaly = {
                    'api_name': log_data.get('api_name'),
                    'environment': log_data.get('environment'),
                    'timestamp': datetime.datetime.now(),
                    'log_id': log_data.get('_id'),
                    'request_id': log_data.get('request_id'),
                    'type': 'response_time',
                    'severity': self._calculate_severity(z_score),
                    'details': {
                        'response_time': response_time,
                        'avg_response_time': avg_response_time,
                        'percentile_99': percentile_99,
                        'z_score': z_score,
                        'threshold': 3.0  # Standard threshold for anomaly
                    },
                    'message': f"Response time anomaly detected for {log_data.get('api_name')} " \
                              f"in {log_data.get('environment')}: {response_time}ms " \
                              f"(Avg: {avg_response_time:.2f}ms, p99: {percentile_99}ms)"
                }
                return anomaly
            
            return None
        
        except Exception as e:
            logger.error(f"Error detecting response time anomaly: {str(e)}")
            return None
    
    def _detect_error_anomaly(self, log_data, baseline):
        """Detect error rate anomalies"""
        try:
            # Get recent error rate for this API (last hour)
            one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
            
            # Count total calls and errors in the last hour
            total_calls = self.logs_collection.count_documents({
                'api_name': log_data.get('api_name'),
                'environment': log_data.get('environment'),
                'timestamp': {'$gte': one_hour_ago}
            })
            
            if total_calls < 10:
                # Not enough data to detect anomaly
                return None
            
            error_calls = self.logs_collection.count_documents({
                'api_name': log_data.get('api_name'),
                'environment': log_data.get('environment'),
                'timestamp': {'$gte': one_hour_ago},
                'is_error': True
            })
            
            current_error_rate = (error_calls / total_calls) * 100
            baseline_error_rate = baseline.get('error_rate', 0)
            
            # If error rate is significantly higher than baseline
            if current_error_rate > max(baseline_error_rate * 2, 5.0):
                # Calculate severity based on difference
                error_diff = current_error_rate - baseline_error_rate
                
                if error_diff > 20:
                    severity = 'critical'
                elif error_diff > 10:
                    severity = 'high'
                elif error_diff > 5:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                # Create anomaly record
                anomaly = {
                    'api_name': log_data.get('api_name'),
                    'environment': log_data.get('environment'),
                    'timestamp': datetime.datetime.now(),
                    'log_id': log_data.get('_id'),
                    'request_id': log_data.get('request_id'),
                    'type': 'error_rate',
                    'severity': severity,
                    'details': {
                        'current_error_rate': current_error_rate,
                        'baseline_error_rate': baseline_error_rate,
                        'total_calls': total_calls,
                        'error_calls': error_calls,
                        'status_code': log_data.get('status_code')
                    },
                    'message': f"Error rate anomaly detected for {log_data.get('api_name')} " \
                              f"in {log_data.get('environment')}: {current_error_rate:.2f}% " \
                              f"(Baseline: {baseline_error_rate:.2f}%)"
                }
                return anomaly
            
            return None
        
        except Exception as e:
            logger.error(f"Error detecting error anomaly: {str(e)}")
            return None
    
    def _calculate_severity(self, z_score):
        """Calculate severity level based on z-score"""
        if z_score > 10:
            return 'critical'
        elif z_score > 5:
            return 'high'
        elif z_score > 3:
            return 'medium'
        else:
            return 'low'