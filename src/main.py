import sys
import json
import networkx as nx
import numpy as np
from pathlib import Path


def read_matrix(path):
    text = path.read_text()
    numbers = list(map(int, text.split()))
    size = numbers[0]
    matrix = np.array(numbers[1:]).reshape(size, size)
    # matrix = matrix.astype(np.float64)
    # matrix[matrix < 0] = np.inf
    return matrix


def get_highest_demand_pair(demand_matrix):
    return np.unravel_index(np.argmax(demand_matrix), demand_matrix.shape)


def get_highest_demand_destination_from(source, demand_matrix):
    return np.argmax(demand_matrix[source])


def set_demand_satisfied_in_route(demand_matrix, route):
    demand_matrix = demand_matrix.copy()
    satisfied_demand = 0.
    for i in route:
        for j in route:
            satisfied_demand += demand_matrix[i][j]
            demand_matrix[i][j] = 0.
    return demand_matrix, satisfied_demand


def remove_nodes_in_route_from_graph(distance_matrix, route):
    distance_matrix = distance_matrix.copy()
    for i in route:
        distance_matrix[i] = np.inf
        distance_matrix[:, i] = np.inf
    return distance_matrix


def importance_of_node_in_between(source, dest, demand_matrix):
    demand_from_source = demand_matrix[source, :]
    demand_to_dest = demand_matrix[:, dest]
    return demand_from_source + demand_to_dest


def node_cost_from_importance(node_importance, weight):
    # return np.exp(- weight * node_importance)
    return weight / (1.0 + node_importance)


def get_best_route_between(source, dest, distance_matrix, demand_matrix, weight):
    node_importance = importance_of_node_in_between(source, dest, demand_matrix)
    node_cost = node_cost_from_importance(node_importance, weight)
    edge_cost = distance_matrix + np.add.outer(node_cost, node_cost)

    edge_cost[distance_matrix == np.inf] = 0.0
    # print('ratio: {}'.format(np.nanmax(edge_cost / np.add.outer(node_cost, node_cost))))

    graph = nx.convert_matrix.from_numpy_matrix(edge_cost)
    best_route = nx.algorithms.shortest_paths.weighted.dijkstra_path(graph, source, dest)

    return best_route


def get_route_satisfying_constraint(distance_matrix, demand_matrix, weight, min_hop_count, max_hop_count):
    distance_matrix = distance_matrix.copy()
    demand_matrix = demand_matrix.copy()
    source, dest = get_highest_demand_pair(demand_matrix)
    route = [source]
    while True:
        try:
            route_chunk = get_best_route_between(source, dest, distance_matrix, demand_matrix, weight)
        except nx.NetworkXNoPath as e:
            break
        route_chunk = route_chunk[1:]
        if len(route) + len(route_chunk) <= max_hop_count:
            route.extend(route_chunk)
        else:
            break
        distance_matrix = remove_nodes_in_route_from_graph(distance_matrix, route[:-1])
        demand_matrix, _ = set_demand_satisfied_in_route(demand_matrix, route)
        source, dest = dest, get_highest_demand_destination_from(dest, demand_matrix)
        if demand_matrix[source][dest] == 0.:
            break
    return route


def get_routes(graph, demand_matrix, weight, min_hop_count, max_hop_count):
    distance_matrix = nx.convert_matrix.to_numpy_matrix(graph)
    demand_matrix = demand_matrix.copy()
    while np.sum(demand_matrix) > 0.:
        route = get_route_satisfying_constraint(distance_matrix, demand_matrix, weight, min_hop_count, max_hop_count)
        demand_matrix, satisfied_demand = set_demand_satisfied_in_route(demand_matrix, route)
        print(route, satisfied_demand)
        yield route

def save_graph_as_json(distance_matrix, file_path):
    distance_matrix = distance_matrix.copy()
    distance_matrix[distance_matrix == -1] = 0
    graph = nx.convert_matrix.from_numpy_matrix(distance_matrix)
    dest_path = file_path.parent/(file_path.stem + '.json')
    data = nx.readwrite.json_graph.node_link_data(graph)
    with open(dest_path, 'w') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return graph


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python main.py distance_file demand_file max_hop_count weight")
        exit(0)

    dist_file = Path(sys.argv[1])
    if dist_file.suffix == '.json':
        with open(dist_file) as f:
            data = json.load(f)
        graph = nx.readwrite.json_graph.node_link_graph(data)
        distance_matrix = nx.convert_matrix.to_numpy_matrix(graph)
    else:
        distance_matrix = read_matrix(dist_file)
        graph = save_graph_as_json(distance_matrix, dist_file)

    mean = lambda l: sum(l) / len(l)
    print('Average distance: {}'.format(mean(list(map(lambda d:d[2], graph.edges.data(data='weight'))))))

    demand_file = Path(sys.argv[2])
    demand_matrix = read_matrix(demand_file)

    print('Average demand: {}'.format(demand_matrix[np.nonzero(demand_matrix)].mean()))
    print('Total demand: {}'.format(demand_matrix.sum()))

    weight = float(sys.argv[4])
    max_hop_count = int(sys.argv[3])
    min_hop_count = 0

    routes = list(get_routes(graph, demand_matrix, weight, min_hop_count, max_hop_count))

    print(len(routes))
    for route in routes:
        print(route)
        assert(len(route) == len(set(route)))
