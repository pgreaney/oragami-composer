# Security Best Practices for Origami Composer

## OAuth Credentials Management

### Development Environment
- Store credentials in `.env` file (never commit to version control)
- Use `.gitignore` to exclude all `.env*` files
- Rotate credentials if accidentally exposed

### Production Deployment

#### 1. Environment Variable Obfuscation
Never store OAuth credentials as plain text in production. Use one of these approaches:

##### Option A: Cloud Provider Secret Management
```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
    --name origami-composer/alpaca-oauth \
    --secret-string '{
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET"
    }'

# Google Cloud Secret Manager
gcloud secrets create alpaca-oauth-client-id \
    --data-file=- <<< "YOUR_CLIENT_ID"
gcloud secrets create alpaca-oauth-client-secret \
    --data-file=- <<< "YOUR_CLIENT_SECRET"

# Azure Key Vault
az keyvault secret set \
    --vault-name origami-composer-vault \
    --name alpaca-client-id \
    --value "YOUR_CLIENT_ID"
az keyvault secret set \
    --vault-name origami-composer-vault \
    --name alpaca-client-secret \
    --value "YOUR_CLIENT_SECRET"
```

##### Option B: Kubernetes Secrets
```yaml
# k8s/alpaca-oauth-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: alpaca-oauth-credentials
type: Opaque
data:
  # Base64 encoded values
  client-id: <base64-encoded-client-id>
  client-secret: <base64-encoded-client-secret>
```

Apply with:
```bash
# Create secret from command line (recommended)
kubectl create secret generic alpaca-oauth-credentials \
    --from-literal=client-id=$ALPACA_CLIENT_ID \
    --from-literal=client-secret=$ALPACA_CLIENT_SECRET
```

##### Option C: HashiCorp Vault
```bash
# Store in Vault
vault kv put secret/origami-composer/alpaca \
    client_id="YOUR_CLIENT_ID" \
    client_secret="YOUR_CLIENT_SECRET"

# Application retrieves at runtime
vault kv get -field=client_id secret/origami-composer/alpaca
```

#### 2. Runtime Injection
Update your application to retrieve secrets at runtime:

```python
# backend/app/config.py - Production enhancement
import os
from typing import Optional

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Override with runtime secret retrieval
    @property
    def ALPACA_CLIENT_ID(self) -> Optional[str]:
        if self.ENVIRONMENT == "production":
            # AWS Secrets Manager example
            return get_secret_from_aws("alpaca-oauth", "client_id")
        return os.getenv("ALPACA_CLIENT_ID")
    
    @property
    def ALPACA_CLIENT_SECRET(self) -> Optional[str]:
        if self.ENVIRONMENT == "production":
            # AWS Secrets Manager example
            return get_secret_from_aws("alpaca-oauth", "client_secret")
        return os.getenv("ALPACA_CLIENT_SECRET")

def get_secret_from_aws(secret_name: str, key: str) -> str:
    """Retrieve secret from AWS Secrets Manager"""
    import boto3
    import json
    
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    secrets = json.loads(response['SecretString'])
    return secrets[key]
```

#### 3. Additional Security Measures

##### Access Control
- Use IAM roles for service authentication
- Implement least-privilege access policies
- Rotate credentials regularly (every 90 days)

##### Encryption
- Encrypt OAuth tokens at rest using AES-256
- Use TLS 1.3 for all API communications
- Implement field-level encryption for sensitive data

##### Monitoring
- Log all OAuth token usage (excluding the tokens themselves)
- Set up alerts for unusual access patterns
- Monitor for credential exposure in version control

##### Code Security
```python
# backend/app/services/alpaca_oauth_service.py
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class AlpacaOAuthService:
    def __init__(self, encryption_key: bytes):
        self.cipher = Fernet(encryption_key)
    
    def store_oauth_token(self, user_id: str, token: str):
        """Store encrypted OAuth token"""
        encrypted_token = self.cipher.encrypt(token.encode())
        # Store encrypted_token in database
        logger.info(f"OAuth token stored for user {user_id}")
        # Never log the actual token!
    
    def retrieve_oauth_token(self, user_id: str) -> str:
        """Retrieve and decrypt OAuth token"""
        # Get encrypted_token from database
        decrypted_token = self.cipher.decrypt(encrypted_token).decode()
        return decrypted_token
```

### Deployment Checklist

- [ ] Remove all credentials from code and config files
- [ ] Set up secret management solution
- [ ] Implement runtime secret injection
- [ ] Enable encryption for OAuth tokens
- [ ] Set up credential rotation schedule
- [ ] Configure monitoring and alerting
- [ ] Test secret retrieval in staging environment
- [ ] Document secret management procedures
- [ ] Train team on security best practices

### Emergency Response

If credentials are exposed:
1. Immediately rotate credentials in Alpaca dashboard
2. Check logs for unauthorized usage
3. Notify security team
4. Update all deployed instances with new credentials
5. Review and improve security procedures

### Resources
- [OWASP OAuth Security](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html)
- [AWS Secrets Manager Best Practices](https://docs.aws.amazon.com/secretsmanager/latest/userguide/best-practices.html)
- [Kubernetes Secrets Best Practices](https://kubernetes.io/docs/concepts/configuration/secret/#best-practices)
