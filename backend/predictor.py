# predictor.py - Module for predicting API failures
import logging
import datetime
import numpy as np
from pymongo import MongoClient, ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

class Predictor:
    def __init__(self, db):
        """Initialize the Predictor with a MongoDB connection"""
        self.db = db
        self.logs_collection = db['api_logs']
        self.predictions_collection = db['predictions']
        
        # Create indexes
        self.predictions_collection.create_index([("api_name", ASCENDING)])
        self.predictions_collection.create_index([("environment", ASCENDING)])
        self.predictions_collection.create_index([("timestamp", DESCENDING)])
    
    def predict_failures(self, log_data):
        """Predict potential failures based on incoming log data"""
        try:
            api_name = log_data.get('api_name')
            environment = log_data.get('environment')
            request_id = log_data.get('request_id')
            
            # Get recent logs for this API
            recent_logs = list(self.logs_collection.find({
                'api_name': api_name,
                'environment': environment,
                'timestamp': {'$gte': datetime.datetime.now() - datetime.timedelta(hours=24)}
            }).sort("timestamp", DESCENDING))
            
            if len(recent_logs) < 10:
                # Not enough data to make predictions
                return None
            
            # Calculate trend metrics
            response_times = [log.get('response_time', 0) for log in recent_logs]
            error_count = sum(1 for log in recent_logs if log.get('is_error', False))
            error_rate = (error_count / len(recent_logs)) * 100
            
            # Simple prediction based on recent trend
            prediction = {
                'api_name': api_name,
                'environment': environment,
                'timestamp': datetime.datetime.now(),
                'request_id': request_id,
                'prediction_type': 'failure_risk',
                'details': {
                    'current_error_rate': error_rate,
                    'avg_response_time': np.mean(response_times) if response_times else 0,
                    'trend': 'increasing' if np.mean(response_times[-5:]) > np.mean(response_times[:5]) else 'stable',
                    'data_points': len(recent_logs)
                }
            }
            
            # Calculate failure risk score (simple algorithm)
            risk_score = 0
            
            # Factor 1: Increasing response times
            if len(response_times) > 10:
                first_half = response_times[:len(response_times)//2]
                second_half = response_times[len(response_times)//2:]
                if np.mean(second_half) > np.mean(first_half) * 1.2:
                    risk_score += 30
            
            # Factor 2: Error rate
            if error_rate > 5:
                risk_score += min(50, error_rate)
            
            # Factor 3: Response time volatility
            if len(response_times) > 5:
                volatility = np.std(response_times) / (np.mean(response_times) if np.mean(response_times) > 0 else 1)
                if volatility > 0.5:
                    risk_score += min(20, volatility * 20)
            
            # Set risk level based on score
            if risk_score > 70:
                prediction['risk_level'] = 'high'
                prediction['message'] = f"High failure risk detected for {api_name} in {environment}"
            elif risk_score > 40:
                prediction['risk_level'] = 'medium'
                prediction['message'] = f"Medium failure risk detected for {api_name} in {environment}"
            elif risk_score > 10:
                prediction['risk_level'] = 'low'
                prediction['message'] = f"Low failure risk detected for {api_name} in {environment}"
            else:
                prediction['risk_level'] = 'none'
                prediction['message'] = f"No significant failure risk for {api_name} in {environment}"
            
            prediction['risk_score'] = risk_score
            
            # Store prediction if risk is not none
            if prediction['risk_level'] != 'none':
                self.predictions_collection.insert_one(prediction)
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error predicting failures: {str(e)}")
            return None
    
    def get_predictions(self, api_name=None, environment=None):
        """Get recent predictions based on filters"""
        try:
            # Build query
            query = {}
            if api_name:
                query['api_name'] = api_name
            if environment:
                query['environment'] = environment
            
            # Get recent predictions
            predictions = list(self.predictions_collection.find(query)
                              .sort("timestamp", DESCENDING)
                              .limit(100))
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error getting predictions: {str(e)}")
            return []