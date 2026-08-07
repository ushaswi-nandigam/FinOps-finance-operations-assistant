"""Linkage analysis — a graph traversal, not an LLM (docs/architecture.md
§L5's Fraud Agent detail). Builds a customer<->device/IP graph from
transaction history and finds connected components, which is how the
synthetic fraud ring (scripts/seed.py's shared `fraud_ring_devices`) is
actually detectable: no single transaction reveals it, but the graph does.
"""

import networkx as nx
from sqlalchemy import text
from sqlalchemy.orm import Session


def _build_graph(db: Session, *, lookback_rows: int = 5000) -> nx.Graph:
    rows = db.execute(
        text("SELECT customer_ref, device_id, ip_address FROM transactions ORDER BY timestamp DESC LIMIT :limit"),
        {"limit": lookback_rows},
    ).mappings().all()

    graph = nx.Graph()
    for row in rows:
        cust_node = f"cust:{row['customer_ref']}"
        device_node = f"dev:{row['device_id']}"
        ip_node = f"ip:{row['ip_address']}"
        graph.add_edge(cust_node, device_node)
        graph.add_edge(cust_node, ip_node)
    return graph


def linked_customers(db: Session, customer_ref: str, *, lookback_rows: int = 5000) -> list[str]:
    """Every other customer connected to `customer_ref` via a shared device
    or IP, found via connected components — the whole point being that this
    catches rings a single-transaction view never would."""
    graph = _build_graph(db, lookback_rows=lookback_rows)
    target = f"cust:{customer_ref}"
    if target not in graph:
        return []

    component = nx.node_connected_component(graph, target)
    return sorted({node[len("cust:"):] for node in component if node.startswith("cust:") and node != target})
