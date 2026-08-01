import boto3
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AWSConnector:
    """Connect to AWS and discover/monitor SageMaker models"""
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize AWS connector
        
        credentials should contain:
        - account_id: AWS account ID
        - iam_role_arn: IAM role ARN to assume (README-documented flow)
        - region: AWS region (default: us-east-1)
        
        Falls back to static access_key_id/secret_access_key only if no
        iam_role_arn is provided (local dev convenience).
        """
        self.account_id = credentials.get('account_id')
        self.iam_role_arn = credentials.get('iam_role_arn')
        self.region = credentials.get('region', 'us-east-1')
        self.access_key = credentials.get('access_key_id')
        self.secret_key = credentials.get('secret_access_key')
        
        session_kwargs = self._get_session_credentials()
        
        self.sagemaker = boto3.client('sagemaker', region_name=self.region, **session_kwargs)
        self.s3 = boto3.client('s3', region_name=self.region, **session_kwargs)
    
    def _get_session_credentials(self) -> Dict[str, str]:
        """
        Resolve credentials for this connection.
        
        Preferred path: STS AssumeRole using iam_role_arn — the cross-account,
        no-stored-keys model documented in the README. Falls back to static
        access keys only for local testing when no role ARN is given.
        """
        if self.iam_role_arn:
            sts = boto3.client('sts', region_name=self.region)
            assumed = sts.assume_role(
                RoleArn=self.iam_role_arn,
                RoleSessionName='citadel-governance-check'
            )
            creds = assumed['Credentials']
            return {
                'aws_access_key_id': creds['AccessKeyId'],
                'aws_secret_access_key': creds['SecretAccessKey'],
                'aws_session_token': creds['SessionToken'],
            }
        elif self.access_key and self.secret_key:
            return {
                'aws_access_key_id': self.access_key,
                'aws_secret_access_key': self.secret_key,
            }
        else:
            return {}
    
    async def discover_models(self) -> List[Dict[str, Any]]:
        """
        Discover all SageMaker endpoints in AWS account
        
        Returns:
            List of models with metadata
        """
        try:
            logger.info(f"Discovering SageMaker endpoints in {self.region}...")
            
            endpoints = []
            paginator = self.sagemaker.get_paginator('list_endpoints')
            
            for page in paginator.paginate():
                for endpoint in page.get('Endpoints', []):
                    models = []
                    
                    # Get endpoint details
                    endpoint_detail = self.sagemaker.describe_endpoint(
                        EndpointName=endpoint['EndpointName']
                    )
                    
                    # Extract model variants
                    for variant in endpoint_detail.get('ProductionVariants', []):
                        models.append({
                            'id': f"{endpoint['EndpointName']}/{variant['VariantName']}",
                            'name': endpoint['EndpointName'],
                            'variant': variant['VariantName'],
                            'model_name': variant.get('ModelName', 'unknown'),
                            'endpoint_url': f"https://runtime.sagemaker.{self.region}.amazonaws.com",
                            'created_date': endpoint.get('CreationTime'),
                            'last_modified': endpoint.get('LastModifiedTime'),
                            'status': endpoint.get('EndpointStatus'),
                            'cloud': 'aws'
                        })
                    
                    endpoints.extend(models)
            
            logger.info(f"✅ Found {len(endpoints)} SageMaker endpoints")
            return endpoints
        
        except Exception as e:
            logger.error(f"❌ AWS discovery failed: {e}")
            raise
    
    async def get_predictions(self, model_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Fetch recent predictions from SageMaker Data Capture logs in S3.
        
        Args:
            model_id: Model identifier (endpoint/variant)
            limit: Maximum predictions to fetch
        
        Returns:
            List of predictions with features and outputs
        
        NOTE: Real S3 Data Capture parsing (locating the data-capture bucket
        for the endpoint, listing/reading its JSONL objects, mapping captured
        request/response payloads to the {prediction, group, actual_label}
        shape the bias engine expects) is not implemented yet — this is
        real, separately-scoped work, not a one-line fix. Returns mock data
        for now so the rest of the pipeline is testable end to end.
        """
        try:
            endpoint_name = model_id.split('/')[0]
            logger.info(f"Fetching predictions for {endpoint_name}...")
            logger.warning("⚠️ Using mock predictions — S3 Data Capture parsing not yet implemented")
            
            predictions = self._generate_mock_predictions(limit)
            
            logger.info(f"✅ Retrieved {len(predictions)} predictions")
            return predictions
        
        except Exception as e:
            logger.error(f"❌ Failed to get predictions: {e}")
            raise
    
    def _generate_mock_predictions(self, limit: int) -> List[Dict[str, Any]]:
        """Generate mock predictions for testing"""
        predictions = []
        for i in range(limit):
            # Simulate hiring predictions with gender bias
            gender = 'M' if i % 2 == 0 else 'F'
            # Men: 80% approved, Women: 20% approved (simulates bias)
            prediction = 'approved' if (gender == 'M' and i % 5 < 4) or (gender == 'F' and i % 5 < 1) else 'rejected'
            
            predictions.append({
                'id': f"pred_{i}",
                'timestamp': (datetime.now() - timedelta(hours=1)).isoformat(),
                'input_features': {
                    'age': 25 + (i % 40),
                    'experience_years': i % 20,
                    'salary_expectation': 50000 + (i % 50) * 1000,
                    'education': 'bachelors',
                    'location': 'US'
                },
                'prediction': prediction,
                'confidence': 0.85 + (i % 15) / 100,
                'group': gender,  # Sensitive attribute
                'actual_label': prediction if i % 10 != 0 else ('approved' if prediction == 'rejected' else 'rejected')  # 90% correct
            })
        
        return predictions
    
    