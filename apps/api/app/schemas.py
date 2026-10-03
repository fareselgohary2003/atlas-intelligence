from typing import Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["owner", "admin", "researcher", "viewer"]
Depth = Literal["quick", "standard", "deep"]


class RolePatch(BaseModel):
    role: Role


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    workspace_name: str = Field(min_length=1, max_length=120)
    issue_token: bool = False  # API clients may ask for a bearer token in the body; browsers use the httpOnly cookie


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    issue_token: bool = False


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MemberIn(BaseModel):
    email: EmailStr
    role: Role = "researcher"


class ResearchIn(BaseModel):
    workspace_id: str
    title: str | None = Field(default=None, max_length=200)
    objective: str = Field(min_length=10, max_length=8000)
    industry: str | None = Field(default=None, max_length=120)
    geography: str | None = Field(default=None, max_length=120)
    target_customer: str | None = Field(default=None, max_length=200)
    time_range: str | None = Field(default=None, max_length=60)
    competitors: list[str] = Field(default_factory=list, max_length=20)
    depth: Depth = "deep"


class ResearchPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    objective: str | None = Field(default=None, min_length=10, max_length=8000)
    industry: str | None = None
    geography: str | None = None
    target_customer: str | None = None
    time_range: str | None = None
    competitors: list[str] | None = None
    depth: Depth | None = None
