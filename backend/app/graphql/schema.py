"""Main GraphQL schema assembly."""

import strawberry
from strawberry.fastapi import GraphQLRouter

from app.graphql.queries.user import UserQueries
from app.graphql.queries.symphony import SymphonyQueries
from app.graphql.queries.trading import TradingQueries
from app.graphql.mutations.auth import AuthMutations
from app.graphql.mutations.symphony import SymphonyMutations
from app.graphql.context import get_context


@strawberry.type
class Query(UserQueries, SymphonyQueries, TradingQueries):
    """Root Query type combining all queries."""
    
    @strawberry.field
    def hello(self) -> str:
        """Test query."""
        return "Hello from Origami Composer GraphQL API!"


@strawberry.type
class Mutation(AuthMutations, SymphonyMutations):
    """Root Mutation type combining all mutations."""
    pass


# Create the GraphQL schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation
)


def create_graphql_router() -> GraphQLRouter:
    """Create and configure the GraphQL router.
    
    Returns:
        Configured GraphQL router
    """
    return GraphQLRouter(
        schema,
        context_getter=get_context,
        graphiql=True  # Enable GraphiQL interface for development
    )
