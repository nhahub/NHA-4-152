from graph import graph, checkpointer


def test_graph_nodes_and_checkpointer():
    # "__end__" is not a real node in graph.nodes (END is a virtual target
    # reached via edges, not a registered node), so it's checked separately below.
    required = {"__start__", "data_agent", "insight_agent", "content_agent", "content_agent_single_post", "human_review"}
    node_names = set(graph.nodes.keys())

    assert required.issubset(node_names)

    # confirm END is actually reachable: human_review's conditional routing
    # must include a path to "end"
    branches = graph.builder.branches.get("human_review", {})
    reachable_targets = set()
    for branch in branches.values():
        if branch.ends:
            reachable_targets.update(branch.ends.values())
    assert "__end__" in reachable_targets

    assert checkpointer is not None
    