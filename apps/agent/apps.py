from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agent"

    def ready(self):
        # Registers the order, ticket and product tools. The policy tool is registered the same way
        # by KnowledgeConfig.ready() in apps.knowledge.
        from . import catalog_tools  # noqa: F401
