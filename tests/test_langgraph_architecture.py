import unittest

from app.application.context_engine import ContextEngine
from app.application.langgraph_agent import LangGraphAgent


class LangGraphArchitectureTests(unittest.TestCase):
    def test_builds_graph_with_model_and_tools_nodes(self) -> None:
        agent = LangGraphAgent.__new__(LangGraphAgent)
        graph = agent.build_graph()

        self.assertIn("model", graph.nodes)
        self.assertIn("tools", graph.nodes)
        self.assertIn("__start__", graph.nodes)

    def test_context_engineering_builds_grounded_prompt(self) -> None:
        engine = ContextEngine()
        context = engine.build(
            user_message="Summarize the policy",
            system_prompt="You are a helpful assistant.",
            history_summary="User is asking about compliance.",
            tool_catalog="Available: none",
            retrieved_documents=[{"filename": "policy.txt", "text": "Use the approved process."}],
        )

        self.assertIn("User goal", context)
        self.assertIn("Grounding evidence", context)
        self.assertIn("policy.txt", context)


if __name__ == "__main__":
    unittest.main()
