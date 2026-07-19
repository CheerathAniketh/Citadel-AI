import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AzureConnector:
    """Connect to Azure and discover/monitor ML models"""
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Azure connector
        
        credentials should contain:
        - subscription_id: Azure subscription ID
        - app_registration_id: Azure app registration ID
        - tenant_id: Azure tenant ID
        - client_id: Azure client ID
        - client_secret: Azure client secret
        """
        self.subscription_id = credentials.get('subscription_id')
        self.app_registration_id = credentials.get('app_registration_id')
        self.tenant_id = credentials.get('tenant_id')
        self.client_id = credentials.get('client_id')
        self.client_secret = credentials.get('client_secret')
        
        # In production, initialize Azure ML client
        # from azure.ai.ml import MLClient
        # from azure.identity import ClientSecretCredential
        
        logger.info(f"Initialized Azure connector for subscription {self.subscription_id}")
    
    async def discover_models(self) -> List[Dict[str, Any]]:
        """
        Discover all Azure ML models in workspace
        
        Returns:
            List of models with metadata
        """
        try:
            logger.info(f"Discovering Azure ML models in {self.subscription_id}...")
            
            # For local testing, return mock data
            models = self._generate_mock_models()
            
            logger.info(f"✅ Found {len(models)} Azure ML endpoints")
            return models
        
        except Exception as e:
            logger.error(f"❌ Azure discovery failed: {e}")
            raise
    
    async def get_predictions(self, model_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch recent predictions from Azure ML logs
        
        Args:
            model_id: Model identifier
            limit: Maximum predictions to fetch
        
        Returns:
            List of predictions with features and outputs
        """
        try:
            logger.info(f"Fetching predictions for {model_id}...")
            
            # For local testing, return mock data
            predictions = self._generate_mock_predictions_insurance(limit)
            
            logger.info(f"✅ Retrieved {len(predictions)} predictions")
            return predictions
        
        except Exception as e:
            logger.error(f"❌ Failed to get predictions: {e}")
            raise
    
    def _generate_mock_models(self) -> List[Dict[str, Any]]:
        """Generate mock Azure ML models for testing"""
        return [
            {
                'id': 'insurance-claim-model',
                'name': 'insurance-claim-model',
                'display_name': 'Insurance Claim Prediction',
                'created_time': datetime.now() - timedelta(days=45),
                'updated_time': datetime.now(),
                'endpoint_id': 'insurance-endpoint-prod',
                'status': 'Healthy',
                'cloud': 'azure',
                'workspace': 'production-ws'
            },
            {
                'id': 'fraud-detection-model',
                'name': 'fraud-detection-model',
                'display_name': 'Fraud Detection Model',
                'created_time': datetime.now() - timedelta(days=90),
                'updated_time': datetime.now(),
                'endpoint_id': 'fraud-endpoint-prod',
                'status': 'Healthy',
                'cloud': 'azure',
                'workspace': 'production-ws'
            }
        ]
    
    def _generate_mock_predictions_insurance(self, limit: int) -> List[Dict[str, Any]]:
        """Generate mock insurance predictions with income bias"""
        predictions = []
        for i in range(limit):
            # Simulate insurance approval with income bias
            annual_income = 30000 + (i % 150) * 1000  # 30k to 180k
            income_group = 'low' if annual_income < 60000 else 'medium' if annual_income < 120000 else 'high'
            
            # Low-income: 40% approval, others: 80% approval
            if income_group == 'low':
                approved = i % 10 < 4  # 40% approval
            else:
                approved = i % 10 < 8  # 80% approval
            
            prediction = 'approved' if approved else 'rejected'
            
            predictions.append({
                'id': f"pred_{i}",
                'timestamp': (datetime.now() - timedelta(hours=1)).isoformat(),
                'input_features': {
                    'annual_income': annual_income,
                    'age': 20 + (i % 60),
                    'years_customer': i % 30,
                    'claim_history_count': i % 10,
                    'insurance_type': 'auto' if i % 2 == 0 else 'home',
                    'location_risk': 'low' if i % 3 == 0 else 'medium' if i % 3 == 1 else 'high'
                },
                'prediction': prediction,
                'confidence': 0.82 + (i % 18) / 100,
                'group': income_group,  # Sensitive attribute
                'actual_label': prediction if i % 10 != 0 else ('approved' if prediction == 'rejected' else 'rejected')
            })
        
        return predictions