"""Auth schemas for registration.

Owner: P6
Note: These schemas are kept here temporarily to respect file ownership boundaries.
P2 should eventually move them to app.schemas.
"""

from pydantic import BaseModel


class RegisterEnterpriseRequest(BaseModel):
    enterprise_name: str
    admin_email: str
    admin_password: str


class RegisterUserRequest(BaseModel):
    tenant_code: str
    email: str
    password: str
