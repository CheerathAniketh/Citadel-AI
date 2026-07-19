import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class GCPConnector:
    """Connect to GCP and discover/monitor Vertex AI models"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize GCP connector
        
        credentials should contain:
        - project_id: GCP project ID
        - service_account_json: Service account JSON
        """
        self.project_id = credentials.get('project_id')
        self.service_account_json = credentials.get('service_account_json')
        self.region = credentials.get('region', 'us-central1')
        
        # In production, initialize Vertex AI client
        # from google.cloud import aiplatform
        # aiplatform.init(project=self.project_id)
        
        logger.info(f"Initialized GCP connector for project {self.project_id}")
    
    async def discover_models(self) -> List[Dict[str, Any]]:
        """
        Discover all Vertex AI endpoints in GCP project
        
        Returns:
            List of models with metadata
        """
        try:
            logger.info(f"Discovering Vertex AI endpoints in {self.project_id}...")
            
            # For local testing, return mock data
            # In production, this would call Vertex AI API
            models = self._generate_mock_models()
            
            logger.info(f"✅ Found {len(models)} Vertex AI endpoints")
            return models
        
        except Exception as e:
            logger.error(f"❌ GCP discovery failed: {e}")
            raise
    
    async def get_predictions(self, model_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch recent predictions from Vertex AI logs
        
        Args:
            model_id: Model identifier
            limit: Maximum predictions to fetch
        
        Returns:
            List of predictions with features and outputs
        """
        try:
            logger.info(f"Fetching predictions for {model_id}...")
            
            # For local testing, return mock data
            predictions = self._generate_mock_predictions_loan(limit)
            
            logger.info(f"✅ Retrieved {len(predictions)} predictions")
            return predictions
        
        except Exception as e:
            logger.error(f"❌ Failed to get predictions: {e}")
            raise
    
    def _generate_mock_models(self) -> List[Dict[str, Any]]:
        """Generate mock Vertex AI models for testing"""
        return [
            {
                'id': 'loan-approval-model',
                'name': 'loan-approval-model',
                'display_name': 'Loan Approval Model',
                'created_time': datetime.now() - timedelta(days=30),
                'updated_time': datetime.now(),
                'endpoint_id': 'endpoints/1234567890',
                'status': 'DEPLOYED',
                'cloud': 'gcp',
                'region': 'us-central1'
            },
            {
                'id': 'credit-scoring-model',
                'name': 'credit-scoring-model',
                'display_name': 'Credit Scoring Model',
                'created_time': datetime.now() - timedelta(days=60),
                'updated_time': datetime.now(),
                'endpoint_id': 'endpoints/9876543210',
                'status': 'DEPLOYED',
                'cloud': 'gcp',
                'region': 'us-central1'
            }
        ]
    
    def _generate_mock_predictions_loan(self, limit: int) -> List[Dict[str, Any]]:
        """Generate mock loan approval predictions with age bias"""
        predictions = []
        for i in range(limit):
            # Simulate loan decisions with age bias
            age = 25 + (i % 60)  # Ages 25-85
            age_group = 'young' if age < 45 else 'middle' if age < 65 else 'senior'
            
            # Seniors rejected at 70%, others at 15%
            if age_group == 'senior':
                approved = i % 10 < 3  # 30% approval for seniors
            else:
                approved = i % 10 < 8  # 80% approval for others
            
            prediction = 'approved' if approved else 'rejected'
            
            predictions.append({
                'id': f"pred_{i}",
                'timestamp': (datetime.now() - timedelta(hours=1)).isoformat(),
                'input_features': {
                    'age': age,
                    'annual_income': 30000 + (i % 80) * 1000,
                    'credit_score': 600 + (i % 400),
                    'years_employed': i % 40,
                    'debt_to_income_ratio': 0.1 + (i % 50) / 100,
                    'homeowner': 'yes' if i % 2 == 0 else 'no'
                },
                'prediction': prediction,
                'confidence': 0.80 + (i % 20) / 100,
                'group': age_group,  # Sensitive attribute
                'actual_label': prediction if i % 10 != 0 else ('approved' if prediction == 'rejected' else 'rejected')
            })
        
        return predictions