from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.knowledge"

    def ready(self):
        # Registers the `search_policies` tool in the agent's tool registry.
        from . import agent_tools  # noqa: F401
