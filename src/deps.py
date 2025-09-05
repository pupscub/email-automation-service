from src.config import config, Config
from src.auth import GraphAuthenticator, authenticator
from src.graph_client import GraphClient, graph_client
from src.webhook_handler import WebhookHandler, webhook_handler


def get_config() -> Config:
    return config


def get_authenticator() -> GraphAuthenticator:
    return authenticator


def get_graph_client() -> GraphClient:
    return graph_client


def get_webhook_handler() -> WebhookHandler:
    return webhook_handler


