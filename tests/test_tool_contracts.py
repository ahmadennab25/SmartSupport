import inspect
from unittest import mock

from django.test import SimpleTestCase

from apps.agent import tools


class ToolContractTests(SimpleTestCase):
    """The JSON schema the model sees must match the Python handler it will call."""

    def test_every_tool_schema_matches_its_handler_signature(self):
        registry = tools._REGISTRY
        self.assertTrue(registry)
        for tool in registry.values():
            with self.subTest(tool=tool.name):
                parameters = list(inspect.signature(tool.handler).parameters.values())
                self.assertEqual(parameters[0].name, "customer", "first handler argument must be the server-side customer")
                handler_args = {p.name: p for p in parameters[1:]}

                schema = tool.parameters
                self.assertEqual(schema["type"], "object")
                self.assertIs(schema["additionalProperties"], False)
                self.assertEqual(set(schema["properties"]), set(handler_args), "schema properties != handler arguments")

                must_have = {name for name, p in handler_args.items() if p.default is inspect.Parameter.empty}
                self.assertTrue(must_have <= set(schema["required"]), "a mandatory handler argument is not required in the schema")
                self.assertTrue(set(schema["required"]) <= set(handler_args), "schema requires an unknown argument")

                for name, prop in schema["properties"].items():
                    self.assertIn("type", prop, f"property {name} has no type")
                self.assertTrue(tool.description.strip())

    def test_models_cannot_supply_identity_arguments(self):
        for tool in tools._REGISTRY.values():
            with self.subTest(tool=tool.name):
                forbidden = {"customer", "customer_id", "phone", "phone_number"}
                self.assertFalse(forbidden & set(tool.parameters["properties"]))

    def test_bad_arguments_are_reported_as_argument_errors(self):
        customer = object()
        with self.assertLogs("apps.agent.tools", level="WARNING"):
            missing = tools.execute_tool("lookup_order", "{}", customer)
            unexpected = tools.execute_tool("lookup_order", '{"order_number": 1, "x": 2}', customer)
        self.assertIn("Invalid or missing", missing["error"])
        self.assertIn("Invalid or missing", unexpected["error"])

    def test_type_error_inside_a_handler_is_an_internal_error_not_an_argument_error(self):
        def broken(customer, order_number):
            raise TypeError("bug inside the handler")

        parameters = {
            "type": "object",
            "properties": {"order_number": {"type": "string"}},
            "required": ["order_number"],
            "additionalProperties": False,
        }
        fake = tools.Tool("broken_tool", "test tool", parameters, broken)
        with mock.patch.dict(tools._REGISTRY, {"broken_tool": fake}):
            with self.assertLogs("apps.agent.tools", level="ERROR"):
                result = tools.execute_tool("broken_tool", '{"order_number": "1"}', object())
        self.assertIn("Internal error", result["error"])
