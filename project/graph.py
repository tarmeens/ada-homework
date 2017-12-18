import numpy as np
import pandas as pd
import bisect

class ProductGraph:
    
    def __init__(self, records, add_edge_on, remove_edge_on=None):
        # Map keys ("asin") to numeric indices (for performance and practical reasons)
        self.records = records
        self.name_id_mapping = {}
        self.add_edge_on = add_edge_on
        self.remove_edge_on = remove_edge_on
        for i, record in enumerate(records):
            self.name_id_mapping[record['asin']] = i

        # Adjacency list, used for iterating the neighbors of a node
        self.adj_list = []
        
        # Adjacency set, used for efficient neighborhood queries
        self.adj_set = []
        
        for record in records:
            # Add edge on given key (e.g. buy after viewing)
            av = record[add_edge_on]
            av = list(filter(lambda x: x in self.name_id_mapping, av))
            self.adj_list.append(sorted(set([self.name_id_mapping[x] for x in av])))

            # Remove edge on given key (e.g. bought together), if added earlier
            if remove_edge_on is not None:
                bt = record[remove_edge_on]
                bt = list(filter(lambda x: x in self.name_id_mapping, bt))
                bt = [self.name_id_mapping[x] for x in bt]
                for o in bt:
                    if o in self.adj_list[-1]:
                        self.adj_list[-1].remove(o)
            
            self.adj_set.append(frozenset(self.adj_list[-1]))

        # Transposed graph (represents the incoming edges in every node)
        self.adj_list_incoming = []
        for adj in self.adj_list:
            self.adj_list_incoming.append([])

        for i, adj in enumerate(self.adj_list):
            for node in adj:
                self.adj_list_incoming[node].append(i)
        
        # Enrich records with new fields (fan-in, fan-out, connected components)
        for i, fan_in in enumerate(self.get_fan_in()):
            self.records[i]['fan_in'] = fan_in
            
        for i, fan_out in enumerate(self.get_fan_out()):
            self.records[i]['fan_out'] = fan_out
#        
#        for i, comp_id in enumerate(self.get_connected_components(directed=True)):
#            self.records[i]['comp_id_dir'] = comp_id
#            
#        for i, comp_id in enumerate(self.get_connected_components(directed=False)):
#            self.records[i]['comp_id_undir'] = comp_id
#            
#        conn_comps = self.extract_connected_components(directed=True)
#        for comp in conn_comps:
#            size = len(comp)
#            for i in comp:
#                self.records[i]['comp_size_dir'] = size
#                
#        conn_comps = self.extract_connected_components(directed=False)
#        for comp in conn_comps:
#            size = len(comp)
#            for i in comp:
#                self.records[i]['comp_size_undir'] = size
                
        # Build pandas dataframe out of this graph
        self.df = pd.DataFrame(self.records)
                
    def get_fan_in(self):
        """
        Returns a list of the count of incoming edges for each node.
        """
        return list(map(lambda x: len(x), self.adj_list_incoming))
    
    def get_fan_out(self):
        """
        Returns a list of the count of the outgoing edges for each node.
        """
        return list(map(lambda x: len(x), self.adj_list))
    
    def drop_singletons(self):
        """
        Returns a new graph with no singletons (isolated nodes without in/out edges).
        """
        mask = (np.array(self.get_fan_in()) > 0) | (np.array(self.get_fan_out()) > 0)
        valid_records = []
        for i in range(len(self.records)):
            if mask[i]:
                valid_records.append(self.records[i])
        return ProductGraph(valid_records, self.add_edge_on, self.remove_edge_on)
    
    def _extract_max_cliques(self, nodes):
        count = 0
        m = 0 if len(self.prev_list) == 0 else bisect.bisect_right(nodes, self.prev_list[-1])
        for a in nodes[m:]:
            connected = True
            for test in self.prev_list:
                if test not in self.adj_set[a] or a not in self.adj_set[test]:
                    connected = False
                    break

            if connected:
                self.prev_list.append(a)
                if self._extract_max_cliques(self.adj_list[a]) == 0:
                    self.cliques.append(self.prev_list.copy())
                    count += 1
                self.prev_list.pop()
        return count
    
    def extract_max_cliques(self):
        """
        Extracts all max-cliques from this graph, and returns them as a list of lists of indices.
        """
        self.cliques = []
        self.prev_list = []
        self._extract_max_cliques(range(len(self.adj_list)))
        return self.cliques
    
    def _visit(self, u, directed):
        if self.visited[u]:
            return
        self.visited[u] = True
        for v in self.adj_list[u]:
            self._visit(v, directed)
        if not directed:
            for v in self.adj_list_incoming[u]:
                self._visit(v, directed)
        self.L.append(u)

    def _assign(self, u, root, directed):
        if self.components[u] != -1:
            return
        self.components[u] = root
        for v in self.adj_list_incoming[u]:
            self._assign(v, root, directed)
        if not directed:
            for v in self.adj_list[u]:
                self._assign(v, root, directed)
            
    def _remap(self, labels):
        seen = {}
        i = 0
        for index, label in enumerate(labels):
            if label in seen:
                labels[index] = seen[label]
            else:
                seen[label] = i
                labels[index] = i
                i += 1
        return labels

    # Kosaraju's algorithm
    def get_connected_components(self, directed):
        """
        Computes the strongly connected components in this graph, and returns a list that
        represents the component label for each node.
        """
        # First DFS pass
        self.L = []
        self.visited = np.zeros(len(self.adj_list)).astype(bool)
        for node in range(len(self.adj_list)):
            self._visit(node, directed)

        # Second DFS pass
        self.components = np.ones(len(self.adj_list)).astype(int) * -1 # "-1" means unassigned
        for node in reversed(self.L):
            self._assign(node, node, directed)

        return self._remap(self.components)

    def extract_connected_components(self, directed):
        """
        Returns the strongly connected components in this graph as a list of lists of indices.
        """
        comps = self.get_connected_components(directed)
        comp_list = {}
        for i, comp in enumerate(comps):
            if comp not in comp_list:
                comp_list[comp] = []
            comp_list[comp].append(i)
        return list(comp_list.values())
    