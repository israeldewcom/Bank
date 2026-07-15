import networkx as nx
import matplotlib.pyplot as plt
from io import BytesIO
import base64

class CollateralGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_collateral_cycle(self, counterparty1, counterparty2, asset_type, amount):
        self.graph.add_edge(counterparty1, counterparty2, asset=asset_type, amount=amount)

    def find_cycles(self, max_depth=20):
        cycles = list(nx.simple_cycles(self.graph))
        filtered = [c for c in cycles if len(c) <= max_depth]
        return filtered

    def render_graph(self):
        plt.figure(figsize=(10,8))
        pos = nx.spring_layout(self.graph)
        nx.draw(self.graph, pos, with_labels=True, node_color='lightblue', edge_color='gray')
        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        return base64.b64encode(img.read()).decode()
