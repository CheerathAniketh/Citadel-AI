import boto3
import json
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

        Discovers the S3 destination dynamically from the endpoint's own
        config (describe_endpoint -> describe_endpoint_config ->
        DataCaptureConfig.DestinationS3Uri) — no hardcoded bucket, works
        for any user's endpoint under whatever AWS account/credentials
        this connector instance was built with.

        Args:
            model_id: Model identifier (endpoint_name/variant_name)
            limit: Maximum predictions to fetch

        Returns:
            List of predictions with features and outputs, parsed from
            real SageMaker Data Capture JSONL logs.
        """
        try:
            endpoint_name = model_id.split('/')[0]
            logger.info(f"Fetching predictions for {endpoint_name}...")

            endpoint_desc = self.sagemaker.describe_endpoint(EndpointName=endpoint_name)
            config_desc = self.sagemaker.describe_endpoint_config(
                EndpointConfigName=endpoint_desc['EndpointConfigName']
            )

            capture_config = config_desc.get('DataCaptureConfig')
            if not capture_config or not capture_config.get('EnableCapture'):
                logger.warning(f"Data Capture not enabled on {endpoint_name}")
                return []

            bucket, prefix = self._parse_s3_uri(capture_config['DestinationS3Uri'])
            full_prefix = f"{prefix}/{endpoint_name}/AllTraffic/"

            predictions = self._fetch_and_parse_capture_logs(bucket, full_prefix, limit)
            logger.info(f"✅ Retrieved {len(predictions)} predictions")
            return predictions

        except Exception as e:
            logger.error(f"❌ Failed to get predictions: {e}")
            raise

    def _parse_s3_uri(self, s3_uri: str):
        """Split an s3://bucket/prefix URI into (bucket, prefix)."""
        without_scheme = s3_uri.replace("s3://", "")
        bucket, _, prefix = without_scheme.partition("/")
        return bucket, prefix.rstrip("/")

    def _fetch_and_parse_capture_logs(self, bucket: str, prefix: str, limit: int) -> List[Dict[str, Any]]:
        """List and read .jsonl Data Capture objects directly from S3 (no local disk involved)."""
        keys = []
        paginator = self.s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                if obj['Key'].endswith('.jsonl'):
                    keys.append(obj['Key'])

        keys.sort(reverse=True)  # most recent first

        predictions = []
        for key in keys:
            if len(predictions) >= limit:
                break
            body = self.s3.get_object(Bucket=bucket, Key=key)['Body'].read().decode('utf-8')
            for line in body.splitlines():
                if not line.strip() or len(predictions) >= limit:
                    continue
                try:
                    record = self._parse_capture_line(line)
                    if record:
                        predictions.append(record)
                except Exception as e:
                    logger.warning(f"Skipping malformed capture line: {e}")

        return predictions

    def _parse_capture_line(self, line: str) -> Dict[str, Any]:
        """Unwrap SageMaker's double-JSON-encoded Data Capture envelope into a flat prediction record."""
        envelope = json.loads(line)
        cap = envelope['captureData']
        instance = json.loads(cap['endpointInput']['data'])['instances'][0]
        pred_obj = json.loads(cap['endpointOutput']['data'])['predictions'][0]
        gender_raw = instance.get('gender')
        gender_label = 'Male' if gender_raw == 1 else 'Female' if gender_raw == 0 else str(gender_raw)

        return {
            'id': envelope['eventMetadata']['eventId'],
            'timestamp': envelope['eventMetadata'].get('inferenceTime'),
            'input_features': instance,
            'prediction': pred_obj.get('hired'),
            'confidence': pred_obj.get('probability'),
            'group': gender_label,
        }
