"""GraphQL authentication testing."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.connection import Base, get_db
from app.models.user import User
from app.auth.password import password_manager


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_graphql_hello_query():
    """Test basic GraphQL hello query."""
    query = """
    query {
        hello
    }
    """
    
    response = client.post(
        "/graphql",
        json={"query": query}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["hello"] == "Hello from Origami Composer GraphQL API!"


def test_graphql_register_mutation():
    """Test GraphQL registration mutation."""
    mutation = """
    mutation Register($input: RegisterInput!) {
        register(input: $input) {
            ... on RegisterSuccess {
                message
                user {
                    id
                    email
                    username
                }
            }
            ... on AuthError {
                message
                code
                field
            }
        }
    }
    """
    
    variables = {
        "input": {
            "email": "test@example.com",
            "username": "testuser",
            "password": "Test1234!",
            "confirmPassword": "Test1234!"
        }
    }
    
    response = client.post(
        "/graphql",
        json={"query": mutation, "variables": variables}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check for successful registration
    register_result = data["data"]["register"]
    assert register_result["message"] == "User registered successfully"
    assert register_result["user"]["email"] == "test@example.com"
    assert register_result["user"]["username"] == "testuser"


def test_graphql_login_mutation():
    """Test GraphQL login mutation."""
    # First create a user
    db = TestingSessionLocal()
    user = User(
        email="login@example.com",
        username="loginuser",
        password_hash=password_manager.hash_password("Test1234!")
    )
    db.add(user)
    db.commit()
    db.close()
    
    mutation = """
    mutation Login($input: LoginInput!) {
        login(input: $input) {
            ... on LoginSuccess {
                message
                user {
                    id
                    email
                }
                tokens {
                    accessToken
                    refreshToken
                    tokenType
                }
            }
            ... on AuthError {
                message
                code
            }
        }
    }
    """
    
    variables = {
        "input": {
            "email": "login@example.com",
            "password": "Test1234!"
        }
    }
    
    response = client.post(
        "/graphql",
        json={"query": mutation, "variables": variables}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Check for successful login
    login_result = data["data"]["login"]
    assert login_result["message"] == "Login successful"
    assert login_result["user"]["email"] == "login@example.com"
    assert login_result["tokens"]["accessToken"] is not None
    assert login_result["tokens"]["refreshToken"] is not None
    assert login_result["tokens"]["tokenType"] == "bearer"


def test_graphql_me_query_unauthenticated():
    """Test GraphQL me query without authentication."""
    query = """
    query {
        me {
            id
            email
            username
        }
    }
    """
    
    response = client.post(
        "/graphql",
        json={"query": query}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["me"] is None


# Clean up test database after tests
def teardown_module(module):
    """Clean up test database."""
    import os
    try:
        os.remove("test.db")
    except:
        pass
