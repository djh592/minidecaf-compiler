from backend.dataflow.basicblock import BasicBlock

"""
CFG: Control Flow Graph

nodes: sequence of basicblock
edges: sequence of edge(u,v), which represents after block u is executed, block v may be executed
links: links[u][0] represent the Prev of u, links[u][1] represent the Succ of u,
"""


class CFG:
    def __init__(self, nodes: list[BasicBlock], edges: list[(int, int)]) -> None:
        self.nodes = nodes
        self.edges = edges

        self.links = []

        for i in range(len(nodes)):
            self.links.append((set(), set()))

        for (u, v) in edges:
            self.links[u][1].add(v)
            self.links[v][0].add(u)

        """
        You can start from basic block 0 and do a DFS traversal of the CFG
        to find all the reachable basic blocks.
        """
        self.reachable = self.computeReachability()

    def computeReachability(self):
        reachable = [False] * len(self.nodes)

        def dfs(node_id):
            if reachable[node_id]:
                return
            reachable[node_id] = True
            for succ in self.getSucc(node_id):
                dfs(succ)

        dfs(0)
        return reachable

    def isReachable(self, id):
        return self.reachable[id]

    def getBlock(self, id):
        return self.nodes[id]

    def getPrev(self, id):
        return self.links[id][0]

    def getSucc(self, id):
        return self.links[id][1]

    def getInDegree(self, id):
        return len(self.links[id][0])

    def getOutDegree(self, id):
        return len(self.links[id][1])

    def iterator(self):
        return iter(self.nodes)
