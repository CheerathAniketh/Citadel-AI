from app.integrations.aws_connector import AWSConnector
import asyncio

conn = AWSConnector({
    "account_id": "447788060954",
    "iam_role_arn": "arn:aws:iam::447788060954:role/CitadelGovernanceRole",
    "region": "ap-south-1",
})

result = asyncio.run(conn.discover_models())
print(result)
